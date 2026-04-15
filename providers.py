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
from typing import Any

import httpx

logger = logging.getLogger("sparring.providers")

DEFAULT_TIMEOUT = 30

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
                return await self._query_openai_compatible(model, provider_config, prompt, max_tokens)
            elif provider_type == "ollama":
                return await self._query_ollama(model, provider_config, prompt, max_tokens)
            else:
                return {"error": f"Unknown provider type: {provider_type}"}
        
        except asyncio.TimeoutError:
            return {"error": f"Timeout querying {model_name}"}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error querying {model_name}: {e.response.status_code}")
            # Ne pas exposer le corps de réponse (peut contenir des infos sensibles)
            return {"error": f"HTTP {e.response.status_code} from provider"}
        except Exception as e:
            logger.exception(f"Error querying {model_name}")
            return {"error": str(e)}
    
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
        
        # Build request
        request_body = {
            "model": model["model_id"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
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
        
        # Parse response (standard OpenAI format)
        return {
            "content": data["choices"][0]["message"]["content"],
            "input_tokens": data.get("usage", {}).get("prompt_tokens"),
            "output_tokens": data.get("usage", {}).get("completion_tokens"),
        }
    
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
        
        return {
            "content": data["message"]["content"],
            "input_tokens": data.get("prompt_eval_count"),
            "output_tokens": data.get("eval_count"),
            "cost": 0,  # Local models are free
        }
