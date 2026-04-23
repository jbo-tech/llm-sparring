"""
LLM Provider implementations.

Tous les providers cloud passent par un handler OpenAI-compatible unique
(Anthropic et Google exposent désormais des endpoints officiels compatibles).
Seul Ollama conserve un handler spécifique (format de réponse différent).

Supported providers:
- openai, openrouter, mistral, deepseek, groq, together, xai,
  anthropic, google → OpenAI-compatible
- ollama → Specific handler (local, no auth, different response format)
- custom → OpenAI-compatible with custom base_url
"""

import asyncio
import logging
import os
import re
import time
from typing import Any

import httpx

logger = logging.getLogger("sparring.providers")

DEFAULT_TIMEOUT = 30

# Défauts du circuit breaker (surchargés via settings.circuit_breaker)
DEFAULT_BREAKER_THRESHOLD = 3
DEFAULT_BREAKER_COOLDOWN = 300  # secondes

# Familles OpenAI reasoning qui rejettent `max_tokens` et exigent
# `max_completion_tokens` (observé sur gpt-5*, o1*, o3*, o4*).
_OPENAI_REASONING_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def _max_tokens_param(model_id: str, provider: str) -> str:
    """Retourne le nom du param budget tokens à envoyer pour ce modèle."""
    if provider == "openai" and any(model_id.startswith(p) for p in _OPENAI_REASONING_PREFIXES):
        return "max_completion_tokens"
    return "max_tokens"


def _parse_openai_compat_response(data: dict) -> dict:
    """Parse une réponse OpenAI-compat et distingue les modes d'échec.

    Gère plusieurs cas observés sur des modèles reasoning :
    - `content` vide mais `reasoning_content` (Zhipu, DeepSeek) ou `reasoning`
      (OpenRouter) rempli → le modèle a réfléchi sans jamais répondre.
    - `finish_reason=length` → budget tokens épuisé (thinking tokens inclus
      chez Gemini 2.5/3, o-series, etc.).
    - `finish_reason=content_filter` → bloqué par la modération.
    """
    usage = data.get("usage") or {}
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")

    choices = data.get("choices") or []
    if not choices:
        return {
            "error": "no choices in response",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    choice = choices[0]
    message = choice.get("message") or {}
    finish_reason = choice.get("finish_reason")
    content = message.get("content")
    # Nom du champ reasoning varie : `reasoning_content` (Zhipu direct,
    # DeepSeek) vs `reasoning` (OpenRouter, parfois xAI).
    reasoning = message.get("reasoning_content") or message.get("reasoning")

    base = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "finish_reason": finish_reason,
    }
    if reasoning:
        base["reasoning_len"] = len(reasoning)

    if content and content.strip():
        base["content"] = content
        return base

    # Content vide : distinguer les causes pour un diagnostic précis.
    if finish_reason == "length":
        if reasoning:
            base["error"] = (
                f"truncated during reasoning (finish=length, reasoning_len={len(reasoning)}) "
                "— raise max_tokens or disable thinking"
            )
        else:
            base["error"] = "truncated before content (finish=length) — raise max_tokens"
    elif finish_reason == "content_filter":
        base["error"] = "blocked by content filter (finish=content_filter)"
    elif reasoning:
        base["error"] = (
            f"empty content, reasoning-only response (finish={finish_reason}, "
            f"reasoning_len={len(reasoning)}) — reasoning model did not emit final answer"
        )
    else:
        base["error"] = f"empty response (finish={finish_reason}, message_keys={sorted(message.keys())})"

    return base


# Certains modèles (phi-4, QwQ, DeepSeek-R1 local…) exposent leur raisonnement
# en clair dans le content sous forme de balises <think>...</think> au lieu
# d'un champ reasoning_content séparé. On retire ce bloc pour ne garder que
# la réponse finale — et on détecte la troncature « in the middle of thinking »
# (pas de balise fermante) comme une erreur dédiée.
_THINK_BLOCK_RE = re.compile(r"^\s*<think>(.*?)</think>\s*", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"^\s*<think>", re.IGNORECASE)


def _strip_inline_thinking(content: str) -> tuple[str, int | None, bool]:
    """Retire un bloc <think>...</think> en tête de content.

    Retourne (cleaned, thinking_len, truncated_in_thinking) :
    - pas de balise <think> → (content, None, False)
    - balise ouverte + fermée → (reste après </think>, len du bloc stripé, False)
    - balise ouverte SANS fermeture → ("", len(content), True)
      (le modèle a épuisé max_tokens avant de sortir du think)
    """
    if not content:
        return content, None, False

    match = _THINK_BLOCK_RE.match(content)
    if match:
        stripped = content[match.end():]
        return stripped, match.end(), False

    if _THINK_OPEN_RE.match(content):
        return "", len(content), True

    return content, None, False


def _postprocess_result(result: dict) -> dict:
    """Post-traitement commun aux handlers après succès.

    Pour l'instant : strip des balises <think>...</think> inline. Convertit
    en erreur si la réponse était tronquée dans le bloc thinking.
    """
    if "error" in result:
        return result
    content = result.get("content")
    if not content:
        return result

    cleaned, thinking_len, truncated = _strip_inline_thinking(content)

    if truncated:
        new = {k: v for k, v in result.items() if k != "content"}
        new["error"] = (
            f"truncated during inline thinking (<think> without </think>, "
            f"thinking_len={thinking_len}) — raise max_tokens"
        )
        new["inline_thinking_len"] = thinking_len
        return new

    if thinking_len is not None:
        result["content"] = cleaned
        result["inline_thinking_len"] = thinking_len
        if not cleaned.strip():
            new = {k: v for k, v in result.items() if k != "content"}
            new["error"] = (
                f"inline thinking block present but empty final answer "
                f"(thinking_len={thinking_len})"
            )
            return new

    return result


class CircuitBreaker:
    """Désactive temporairement un modèle après N erreurs consécutives.

    État en mémoire uniquement — un redémarrage du serveur remet tout à zéro.
    """

    def __init__(self, threshold: int = DEFAULT_BREAKER_THRESHOLD, cooldown: int = DEFAULT_BREAKER_COOLDOWN):
        self.threshold = threshold
        self.cooldown = cooldown
        self.state: dict[str, dict] = {}

    def _entry(self, model_name: str) -> dict:
        return self.state.setdefault(
            model_name,
            {"errors": 0, "disabled_until": None, "last_error": None, "last_error_ts": None},
        )

    def is_disabled(self, model_name: str) -> tuple[bool, float | None]:
        entry = self.state.get(model_name)
        if not entry:
            return False, None
        disabled_until = entry.get("disabled_until")
        if disabled_until and time.time() < disabled_until:
            return True, disabled_until
        return False, None

    def record_success(self, model_name: str):
        if model_name in self.state:
            self.state[model_name] = {
                "errors": 0,
                "disabled_until": None,
                "last_error": None,
                "last_error_ts": None,
            }

    def record_error(self, model_name: str, reason: str):
        entry = self._entry(model_name)
        entry["errors"] += 1
        entry["last_error"] = reason
        entry["last_error_ts"] = time.time()
        if entry["errors"] >= self.threshold:
            entry["disabled_until"] = time.time() + self.cooldown
            logger.warning(
                f"Circuit breaker OPEN pour {model_name} ({entry['errors']} erreurs) — "
                f"désactivé pendant {self.cooldown}s. Dernière erreur: {reason}"
            )

    def status(self, model_name: str) -> dict:
        entry = self.state.get(model_name)
        if not entry:
            return {"errors": 0, "disabled": False}
        now = time.time()
        disabled_until = entry.get("disabled_until")
        disabled = bool(disabled_until and now < disabled_until)
        return {
            "errors": entry["errors"],
            "disabled": disabled,
            "disabled_until": disabled_until,
            "last_error": entry.get("last_error"),
        }

# =============================================================================
# Provider Registry
# =============================================================================
# Maps provider name to their configuration
# All OpenAI-compatible providers just need base_url and api_key_env

PROVIDER_REGISTRY = {
    # OpenAI-compatible providers
    "openai": {
        "type": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
    "openrouter": {
        "type": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "extra_headers": {
            "HTTP-Referer": "https://github.com/sparring-mcp",
            "X-Title": "Sparring MCP",
        },
    },
    "mistral": {
        "type": "openai_compatible",
        "base_url": "https://api.mistral.ai/v1",
        "api_key_env": "MISTRAL_API_KEY",
    },
    "deepseek": {
        "type": "openai_compatible",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "groq": {
        "type": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
    },
    "together": {
        "type": "openai_compatible",
        "base_url": "https://api.together.xyz/v1",
        "api_key_env": "TOGETHER_API_KEY",
    },
    "xai": {
        "type": "openai_compatible",
        "base_url": "https://api.x.ai/v1",
        "api_key_env": "XAI_API_KEY",
    },
    "ollama": {
        "type": "ollama",  # Slightly different (no auth, different endpoint)
        "base_url": "http://localhost:11434",
        "api_key_env": None,
    },
    # Endpoints OpenAI-compatibles officiels (beta vendor)
    # Limitation connue Anthropic : prompt caching non disponible sur cet endpoint
    "anthropic": {
        "type": "openai_compatible",
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "google": {
        "type": "openai_compatible",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GOOGLE_API_KEY",
    },
}

# Hosts autorisés pour les requêtes (sécurité SSRF)
ALLOWED_HOSTS = {
    # Providers officiels
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.mistral.ai",
    "api.deepseek.com",
    "api.groq.com",
    "api.together.xyz",
    "api.x.ai",
    "openrouter.ai",
    # Local
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
}


def _validate_url(url: str) -> bool:
    """Valide qu'une URL pointe vers un host autorisé."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if host is None:
            return False
        # Autoriser localhost avec n'importe quel port
        if host in ("localhost", "127.0.0.1", "0.0.0.0"):
            return True
        return host in ALLOWED_HOSTS
    except Exception:
        return False


class ProviderManager:
    """Manages multiple LLM providers."""
    
    def __init__(self, models_config: list[dict], settings: dict):
        self.models = {m["name"]: m for m in models_config}
        self.settings = settings
        self.timeout = settings.get("default_timeout", DEFAULT_TIMEOUT)

        # Circuit breaker (in-memory, per-model)
        breaker_cfg = settings.get("circuit_breaker", {}) or {}
        self.breaker = CircuitBreaker(
            threshold=breaker_cfg.get("threshold", DEFAULT_BREAKER_THRESHOLD),
            cooldown=breaker_cfg.get("cooldown_seconds", DEFAULT_BREAKER_COOLDOWN),
        )

        # Load API keys from environment
        self._load_api_keys()
    
    def _load_api_keys(self):
        """Load API keys from environment variables."""
        self.api_keys = {}
        
        for provider, config in PROVIDER_REGISTRY.items():
            env_var = config.get("api_key_env")
            if env_var:
                key = os.environ.get(env_var)
                if key:
                    self.api_keys[provider] = key
                    logger.debug(f"Provider {provider} configured")
                # Ne pas logger l'absence de clé (évite l'énumération)
    
    def get_all_models(self) -> list[dict]:
        """Get all configured models."""
        return list(self.models.values())
    
    def get_available_models(self) -> list[dict]:
        """Get models that are enabled and have required credentials."""
        available = []
        
        for model in self.models.values():
            if not model.get("enabled", True):
                continue
            
            provider = model["provider"]
            provider_config = PROVIDER_REGISTRY.get(provider, {})
            
            # Check if provider needs API key
            if provider_config.get("api_key_env") is None:
                # No API key needed (e.g., Ollama)
                available.append(model)
            elif provider in self.api_keys:
                # API key available
                available.append(model)
            elif provider == "custom":
                # Custom provider - check model-specific config
                if model.get("api_key") or not model.get("requires_auth", True):
                    available.append(model)
        
        return available
    
    async def query(self, model_name: str, prompt: str, max_tokens: int = 1000) -> dict:
        """Query a specific model."""
        if model_name not in self.models:
            return {"error": f"Unknown model: {model_name}"}

        # Court-circuit si le breaker est ouvert pour ce modèle
        disabled, until_ts = self.breaker.is_disabled(model_name)
        if disabled:
            return {
                "error": "circuit breaker open",
                "disabled_until": until_ts,
                "reason": self.breaker.state[model_name].get("last_error"),
            }

        model = self.models[model_name]
        provider = model["provider"]

        # Get provider config (or use custom)
        if provider == "custom":
            provider_config = {
                "type": "openai_compatible",
                "base_url": model.get("base_url"),
                "api_key_env": model.get("api_key_env"),
            }
        else:
            provider_config = PROVIDER_REGISTRY.get(provider)
            if not provider_config:
                return {"error": f"Unknown provider: {provider}"}

        try:
            provider_type = provider_config["type"]

            if provider_type == "openai_compatible":
                result = await self._query_openai_compatible(model, provider_config, prompt, max_tokens)
            elif provider_type == "ollama":
                result = await self._query_ollama(model, provider_config, prompt, max_tokens)
            else:
                return {"error": f"Unknown provider type: {provider_type}"}

        except asyncio.TimeoutError:
            self.breaker.record_error(model_name, "timeout")
            return {"error": f"Timeout querying {model_name}"}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error querying {model_name}: {e.response.status_code}")
            self.breaker.record_error(model_name, f"HTTP {e.response.status_code}")
            # Ne pas exposer le corps de réponse (peut contenir des infos sensibles)
            return {"error": f"HTTP {e.response.status_code} from provider"}
        except Exception as e:
            logger.exception(f"Error querying {model_name}")
            self.breaker.record_error(model_name, str(e)[:200])
            return {"error": str(e)}

        # Post-traitement commun (strip <think> inline, etc.). Peut convertir
        # un succès apparent en erreur (cas : tronqué dans le think).
        result = _postprocess_result(result)

        # Le parser + postprocess renvoient déjà `error` pour les réponses
        # vides/tronquées/filtrées. On se contente d'alimenter le breaker.
        if "error" in result:
            self.breaker.record_error(model_name, result["error"])
            return result

        content = result.get("content")
        if not content or not str(content).strip():
            # Filet de sécurité — ne devrait plus arriver après le parser.
            self.breaker.record_error(model_name, "empty response (safety net)")
            return {
                "error": "empty response",
                "input_tokens": result.get("input_tokens"),
                "output_tokens": result.get("output_tokens"),
            }

        self.breaker.record_success(model_name)
        return result
    
    # =========================================================================
    # Generic OpenAI-Compatible Handler
    # =========================================================================
    
    async def _query_openai_compatible(
        self, 
        model: dict, 
        provider_config: dict, 
        prompt: str, 
        max_tokens: int
    ) -> dict:
        """
        Generic handler for all OpenAI-compatible APIs.
        Works with: OpenAI, OpenRouter, Mistral, DeepSeek, Groq, Together, xAI, etc.
        """
        provider = model["provider"]

        # Get base URL (model can override provider default)
        base_url = model.get("base_url") or provider_config["base_url"]

        # Validation SSRF
        if not _validate_url(base_url):
            return {"error": f"URL non autorisée: {base_url}. Ajoutez le host à ALLOWED_HOSTS."}

        # Get API key
        api_key = None
        if provider_config.get("api_key_env"):
            api_key = self.api_keys.get(provider) or os.environ.get(provider_config["api_key_env"])
        # Model-level API key override
        if model.get("api_key"):
            api_key = model["api_key"]
        
        if not api_key and provider_config.get("api_key_env"):
            return {"error": f"{provider} API key not found"}
        
        # Build headers
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Add provider-specific extra headers
        if provider_config.get("extra_headers"):
            headers.update(provider_config["extra_headers"])
        
        # Build request — certains modèles (gpt-5*, o-series) n'acceptent que max_completion_tokens
        token_param = _max_tokens_param(model["model_id"], provider)
        request_body = {
            "model": model["model_id"],
            "messages": [{"role": "user", "content": prompt}],
            token_param: max_tokens,
        }

        # Make request
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()

        return _parse_openai_compat_response(data)
    
    # =========================================================================
    # Ollama Handler (slightly different from OpenAI)
    # =========================================================================
    
    async def _query_ollama(
        self,
        model: dict,
        provider_config: dict,
        prompt: str,
        max_tokens: int
    ) -> dict:
        """Handler for local Ollama instance."""
        base_url = model.get("base_url") or provider_config["base_url"]

        # Validation SSRF
        if not _validate_url(base_url):
            return {"error": f"URL non autorisée: {base_url}. Ajoutez le host à ALLOWED_HOSTS."}

        async with httpx.AsyncClient(timeout=self.timeout * 2) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model["model_id"],
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
        
        # done_reason Ollama : "stop" | "length" (num_predict épuisé) | "load" | ...
        # On l'aligne sur `finish_reason` OpenAI-compat pour un diagnostic unifié.
        message = data.get("message") or {}
        content = message.get("content")
        finish_reason = data.get("done_reason")
        result = {
            "content": content,
            "input_tokens": data.get("prompt_eval_count"),
            "output_tokens": data.get("eval_count"),
            "finish_reason": finish_reason,
            "cost": 0,  # Local models are free
        }
        if not content or not content.strip():
            result.pop("content", None)
            result["error"] = f"empty response from ollama (done_reason={finish_reason})"
        return result
