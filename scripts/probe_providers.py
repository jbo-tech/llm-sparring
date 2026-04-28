#!/usr/bin/env python3
"""Diagnostic brut : envoie un prompt trivial à chaque modèle et dumpe la
réponse HTTP telle que le provider la renvoie.

But : identifier rapidement où disparaît le contenu (champ `reasoning_content`
au lieu de `content`, `finish_reason: length`, filtre de modération, etc.).

Usage:
  python scripts/probe_providers.py                  # tous les modèles enabled
  python scripts/probe_providers.py --model zai-glm  # un seul
  python scripts/probe_providers.py --prompt "..."   # prompt custom
  python scripts/probe_providers.py --max-tokens 50  # forcer la troncature
  python scripts/probe_providers.py --json           # sortie JSON brute
  python scripts/probe_providers.py --model deepseek --sweep 500,1000,2000,4000,8000
                                                     # boucle pour trouver le seuil utile

Ne passe PAS par ProviderManager.query() (qui cache le raw). Duplique le
minimum nécessaire pour matcher le comportement de providers.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# On importe après load_dotenv pour que les providers voient les clés
sys.path.insert(0, str(PROJECT_ROOT))
from providers import PROVIDER_REGISTRY, _max_tokens_param  # noqa: E402

CONFIG_PATH = Path(
    os.environ.get("SPARRING_CONFIG_DIR", "~/.config/mcp/llm-sparring")
).expanduser() / "config.yaml"

DEFAULT_PROMPT = "Dis bonjour en une phrase."
DEFAULT_MAX_TOKENS = 200
DEFAULT_TIMEOUT = 30


def load_models() -> list[dict]:
    import yaml
    if not CONFIG_PATH.exists():
        print(f"Config introuvable: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    return [m for m in cfg.get("models", []) if m.get("enabled", True)]


async def probe_openai_compat(model: dict, prompt: str, max_tokens: int) -> dict:
    provider = model["provider"]
    reg = PROVIDER_REGISTRY.get(provider) or {}
    base_url = model.get("base_url") or reg.get("base_url")
    api_key = None
    env_var = reg.get("api_key_env")
    if env_var:
        api_key = os.environ.get(env_var)
    if model.get("api_key"):
        api_key = model["api_key"]

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if reg.get("extra_headers"):
        headers.update(reg["extra_headers"])

    token_param = _max_tokens_param(model["model_id"], provider)
    body = {
        "model": model["model_id"],
        "messages": [{"role": "user", "content": prompt}],
        token_param: max_tokens,
    }

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        r = await client.post(f"{base_url}/chat/completions", headers=headers, json=body)
    return {
        "http_status": r.status_code,
        "raw": (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text),
    }


async def probe_ollama(model: dict, prompt: str, max_tokens: int) -> dict:
    reg = PROVIDER_REGISTRY.get("ollama") or {}
    base_url = model.get("base_url") or reg.get("base_url")
    body = {
        "model": model["model_id"],
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT * 2) as client:
        r = await client.post(f"{base_url}/api/chat", json=body)
    return {
        "http_status": r.status_code,
        "raw": (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text),
    }


async def probe(model: dict, prompt: str, max_tokens: int) -> dict:
    provider = model["provider"]
    reg = PROVIDER_REGISTRY.get(provider) or {"type": "openai_compatible"}
    try:
        if reg.get("type") == "ollama":
            result = await probe_ollama(model, prompt, max_tokens)
        else:
            result = await probe_openai_compat(model, prompt, max_tokens)
        result["error"] = None
    except Exception as e:
        result = {"http_status": None, "raw": None, "error": f"{type(e).__name__}: {e}"}
    result["model_name"] = model["name"]
    result["provider"] = provider
    result["model_id"] = model.get("model_id")
    return result


def summarize(result: dict) -> dict:
    """Extrait les champs-clés du raw pour affichage humain."""
    raw = result.get("raw")
    summary = {
        "model": result["model_name"],
        "provider": result["provider"],
        "http": result.get("http_status"),
        "error": result.get("error"),
        "finish_reason": None,
        "content_len": None,
        "content_preview": None,
        "reasoning_len": None,
        "message_keys": None,
        "usage": None,
    }
    if not isinstance(raw, dict):
        return summary

    # Ollama
    if "message" in raw and "choices" not in raw:
        msg = raw.get("message") or {}
        content = msg.get("content")
        summary["message_keys"] = sorted(msg.keys())
        summary["content_len"] = len(content) if content else 0
        summary["content_preview"] = (content or "")[:80]
        summary["finish_reason"] = raw.get("done_reason")
        summary["usage"] = {
            "input": raw.get("prompt_eval_count"),
            "output": raw.get("eval_count"),
        }
        return summary

    # OpenAI-compatible
    choices = raw.get("choices") or []
    if choices:
        choice = choices[0]
        msg = choice.get("message") or {}
        content = msg.get("content")
        reasoning = msg.get("reasoning_content") or msg.get("reasoning")
        summary["message_keys"] = sorted(msg.keys())
        summary["content_len"] = len(content) if content else 0
        summary["content_preview"] = (content or "")[:80]
        summary["reasoning_len"] = len(reasoning) if reasoning else None
        summary["finish_reason"] = choice.get("finish_reason")
    summary["usage"] = raw.get("usage")
    # Certains providers renvoient une erreur dans le body malgré un 200
    if "error" in raw:
        summary["error"] = summary["error"] or raw["error"]
    return summary


def classify(s: dict) -> str:
    """Diagnostic court en une ligne."""
    if s["error"]:
        return f"ERREUR: {s['error']}"
    if s["http"] and s["http"] >= 400:
        return f"HTTP {s['http']}"
    if s["content_len"] is None:
        return "Format inconnu — voir --json"
    if s["content_len"] == 0:
        if s["reasoning_len"]:
            return f"⚠️  content vide MAIS reasoning_content présent ({s['reasoning_len']} chars) — thinking model"
        if s["finish_reason"] == "length":
            return "⚠️  tronqué avant tout content (finish=length) — augmenter max_tokens"
        if s["finish_reason"] == "content_filter":
            return "⚠️  bloqué par le filtre de modération (finish=content_filter)"
        return f"⚠️  content vide (finish={s['finish_reason']}, keys={s['message_keys']})"
    if s["finish_reason"] == "length":
        return f"⚠️  tronqué à {s['content_len']} chars (finish=length)"
    return f"OK — {s['content_len']} chars (finish={s['finish_reason']})"


def print_human(summaries: list[dict]):
    print(f"\n{'Modèle':<22} {'Provider':<12} {'Diagnostic'}")
    print("-" * 100)
    for s in summaries:
        print(f"{s['model']:<22} {s['provider']:<12} {classify(s)}")

    print("\n== Détails ==")
    for s in summaries:
        print(f"\n--- {s['model']} ({s['provider']}) ---")
        print(f"  http={s['http']}  finish_reason={s['finish_reason']}")
        print(f"  message_keys={s['message_keys']}")
        print(f"  content_len={s['content_len']}  reasoning_len={s['reasoning_len']}")
        if s["content_preview"]:
            print(f"  preview: {s['content_preview']!r}")
        print(f"  usage={s['usage']}")
        if s["error"]:
            print(f"  error={s['error']}")


def parse_sweep(raw: str) -> list[int]:
    """Parse '500,1000,2000' en liste d'entiers triés."""
    try:
        values = sorted({int(x.strip()) for x in raw.split(",") if x.strip()})
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--sweep doit être une liste d'entiers séparés par virgule: {e}")
    if not values:
        raise argparse.ArgumentTypeError("--sweep est vide")
    return values


async def run_sweep(model: dict, prompt: str, values: list[int]) -> int:
    """Boucle sur plusieurs max_tokens pour identifier le seuil utile."""
    print(f"Sweep sur '{model['name']}' ({model['provider']}/{model['model_id']})", file=sys.stderr)
    print(f"Prompt: {prompt!r} | valeurs: {values}\n", file=sys.stderr)

    results = await asyncio.gather(*(probe(model, prompt, n) for n in values))
    summaries = [summarize(r) for r in results]

    print(f"{'max_tokens':>10}  {'content':>7}  {'reasoning':>9}  {'finish':<14}  diagnostic")
    print("-" * 100)
    for n, s in zip(values, summaries):
        c = s["content_len"] if s["content_len"] is not None else "—"
        r = s["reasoning_len"] if s["reasoning_len"] is not None else "—"
        finish = s["finish_reason"] or "—"
        print(f"{n:>10}  {str(c):>7}  {str(r):>9}  {finish:<14}  {classify(s)}")

    # Indice de seuil : premier max_tokens où content_len > 0 et finish != length
    ok = [n for n, s in zip(values, summaries)
          if s["content_len"] and s["finish_reason"] != "length"]
    if ok:
        print(f"\n→ Seuil utile détecté : {ok[0]} (premier max_tokens avec content non-vide et non tronqué)")
    else:
        print("\n→ Aucune valeur testée n'a produit de réponse complète. Augmenter la plage ou vérifier le prompt.")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Probe LLM providers for raw response format")
    parser.add_argument("--model", help="Ne tester qu'un seul modèle (nom logique)")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--json", action="store_true", help="Dump JSON brut (raw par modèle)")
    parser.add_argument(
        "--sweep",
        type=parse_sweep,
        help="Liste de max_tokens à tester en boucle (ex: 500,1000,2000,4000). Requiert --model.",
    )
    args = parser.parse_args()

    models = load_models()
    if args.model:
        models = [m for m in models if m["name"] == args.model]
        if not models:
            print(f"Modèle '{args.model}' introuvable ou non enabled.", file=sys.stderr)
            return 1

    if args.sweep:
        if len(models) != 1:
            print("--sweep nécessite --model (un seul modèle à la fois).", file=sys.stderr)
            return 1
        return await run_sweep(models[0], args.prompt, args.sweep)

    print(f"Prompt: {args.prompt!r} | max_tokens={args.max_tokens} | {len(models)} modèles", file=sys.stderr)

    results = await asyncio.gather(*(probe(m, args.prompt, args.max_tokens) for m in models))

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
        return 0

    summaries = [summarize(r) for r in results]
    print_human(summaries)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
