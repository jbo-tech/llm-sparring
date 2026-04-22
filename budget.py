"""
Budget management for Sparring.

Tracks usage and enforces limits:
- Per-request confirmation threshold
- Session limit
- Daily limit

Pricing source: pricing.json (vendored depuis LiteLLM, cf. scripts/refresh_pricing.py).
Cascade de résolution dans get_model_pricing:
  1. Override config.yaml (custom_pricing, per-1M-tokens)
  2. pricing.json — lookup exact par model_id
  3. pricing.json — lookup {provider}/{model_id}
  4. Règle locale : provider=="ollama" ou base_url local → 0
  5. Fallback avec warning : pricing conservateur
"""

import json
import logging
import os
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("sparring.budget")

# Chemin du JSON pricing vendored (à la racine du projet)
PRICING_FILE = Path(__file__).resolve().parent / "pricing.json"

# Hosts considérés comme locaux (cost = 0 sans warning)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}

# Fallback si modèle inconnu (hors providers locaux)
FALLBACK_PRICING = {"input": 1.00, "output": 3.00}


def _load_pricing_db() -> dict:
    """Charge pricing.json et convertit per-token → per-1M-tokens.

    Retourne un dict {model_key: {"input": float, "output": float}}.
    Les entrées sans prix sont ignorées (ex: sample_spec).
    """
    if not PRICING_FILE.exists():
        logger.warning(f"pricing.json introuvable à {PRICING_FILE}, lookup externe désactivé")
        return {}

    try:
        with open(PRICING_FILE) as f:
            raw = json.load(f)
    except Exception as e:
        logger.warning(f"Impossible de charger {PRICING_FILE}: {e}")
        return {}

    db = {}
    for key, entry in raw.items():
        if key == "sample_spec" or not isinstance(entry, dict):
            continue
        inp = entry.get("input_cost_per_token")
        out = entry.get("output_cost_per_token")
        if inp is None or out is None:
            continue
        db[key] = {
            "input": float(inp) * 1_000_000,
            "output": float(out) * 1_000_000,
        }
    return db


# Chargement au module-load (partagé entre instances)
_PRICING_DB = _load_pricing_db()


class BudgetManager:
    """Manages budget tracking and enforcement."""
    
    def __init__(self, config: dict):
        self.confirm_threshold = config.get("confirm_threshold", 0.10)
        self.session_limit = config.get("session_limit", 1.00)
        self.daily_limit = config.get("daily_limit", 5.00)
        
        # Tracking file
        tracking_path = config.get("tracking_file", "~/.config/mcp/llm-sparring/usage.json")
        self.tracking_file = Path(tracking_path).expanduser()

        # Journal append-only (une ligne JSON par requête)
        journal_path = config.get(
            "journal_file",
            str(self.tracking_file.parent / "usage.jsonl"),
        )
        self.journal_file = Path(journal_path).expanduser()

        # Custom pricing overrides
        self.custom_pricing = config.get("pricing", {})
        
        # Session tracking (in-memory)
        self.session_cost = 0.0
        self.session_requests = 0
        
        # Load persistent tracking
        self._load_tracking()
    
    def _load_tracking(self):
        """Load usage tracking from file."""
        self.tracking = {
            "daily": {},
            "monthly": {},
        }
        
        if self.tracking_file.exists():
            try:
                with open(self.tracking_file) as f:
                    self.tracking = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load tracking file: {e}")
    
    def _save_tracking(self):
        """Save usage tracking to file (atomic write)."""
        try:
            self.tracking_file.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=self.tracking_file.parent)
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self.tracking, f, indent=2)
                os.replace(tmp_path, self.tracking_file)
            except:
                os.unlink(tmp_path)
                raise
        except Exception as e:
            logger.warning(f"Could not save tracking file: {e}")
    
    def get_model_pricing(
        self,
        model_name: str,
        model_id: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
    ) -> dict:
        """Résout le pricing d'un modèle selon la cascade documentée.

        Args:
            model_name: Nom logique (clé du config.yaml, utilisé pour custom_pricing)
            model_id: ID exact chez le provider (ex: "gpt-4o-mini", "mistral-large-latest")
            provider: Nom du provider (ex: "openai", "ollama", "openrouter")
            base_url: URL éventuelle (pour détecter les endpoints locaux non-ollama)
        """
        # 1. Override config.yaml (priorité max)
        if model_name in self.custom_pricing:
            return self.custom_pricing[model_name]

        # 2 & 3. Lookup pricing.json : exact puis {provider}/{model_id}
        lookup_id = model_id or model_name
        if lookup_id in _PRICING_DB:
            return _PRICING_DB[lookup_id]
        if provider:
            prefixed = f"{provider}/{lookup_id}"
            if prefixed in _PRICING_DB:
                return _PRICING_DB[prefixed]

        # 4. Règle locale : ollama ou base_url pointant sur localhost
        if provider == "ollama":
            return {"input": 0, "output": 0}
        if base_url:
            host = urlparse(base_url).hostname
            if host in LOCAL_HOSTS:
                return {"input": 0, "output": 0}

        # 5. Fallback conservateur avec warning
        logger.warning(f"Pricing introuvable pour {model_name} (id={model_id}, provider={provider}), fallback par défaut")
        return dict(FALLBACK_PRICING)

    def estimate_request_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        model_id: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
    ) -> float:
        """Estime le coût d'une requête (per-1M-tokens)."""
        pricing = self.get_model_pricing(model_name, model_id=model_id, provider=provider, base_url=base_url)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost
    
    def check_budget(self, estimated_cost: float) -> dict:
        """Check if a request is within budget."""
        today = date.today().isoformat()
        
        # Get current daily total
        daily_total = self.tracking.get("daily", {}).get(today, {}).get("cost", 0)
        
        result = {
            "allowed": True,
            "reason": None,
            "estimated_cost": estimated_cost,
            "session_total": self.session_cost,
            "daily_total": daily_total,
        }
        
        # Check session limit
        if self.session_cost + estimated_cost > self.session_limit:
            result["allowed"] = False
            result["reason"] = f"Session limit exceeded (${self.session_limit:.2f})"
            return result
        
        # Check daily limit
        if daily_total + estimated_cost > self.daily_limit:
            result["allowed"] = False
            result["reason"] = f"Daily limit exceeded (${self.daily_limit:.2f})"
            return result
        
        # Check confirmation threshold
        if estimated_cost > self.confirm_threshold:
            result["needs_confirmation"] = True
            result["confirmation_reason"] = f"Cost ${estimated_cost:.4f} exceeds threshold ${self.confirm_threshold:.2f}"
        
        return result
    
    def record_usage(self, cost: float):
        """Record actual usage after a request."""
        # Update session
        self.session_cost += cost
        self.session_requests += 1
        
        # Update daily tracking
        today = date.today().isoformat()
        if "daily" not in self.tracking:
            self.tracking["daily"] = {}
        if today not in self.tracking["daily"]:
            self.tracking["daily"][today] = {"cost": 0, "requests": 0}
        
        self.tracking["daily"][today]["cost"] += cost
        self.tracking["daily"][today]["requests"] += 1
        
        # Update monthly tracking
        month = date.today().strftime("%Y-%m")
        if "monthly" not in self.tracking:
            self.tracking["monthly"] = {}
        if month not in self.tracking["monthly"]:
            self.tracking["monthly"][month] = {"cost": 0, "requests": 0}
        
        self.tracking["monthly"][month]["cost"] += cost
        self.tracking["monthly"][month]["requests"] += 1
        
        # Save to file
        self._save_tracking()
        
        logger.debug(f"Recorded usage: ${cost:.4f} (session: ${self.session_cost:.4f})")
    
    def get_usage(self) -> dict:
        """Get current usage summary."""
        today = date.today().isoformat()
        month = date.today().strftime("%Y-%m")
        
        daily = self.tracking.get("daily", {}).get(today, {"cost": 0, "requests": 0})
        monthly = self.tracking.get("monthly", {}).get(month, {"cost": 0, "requests": 0})
        
        return {
            "session": {
                "cost": round(self.session_cost, 4),
                "requests": self.session_requests,
                "limit": self.session_limit,
                "remaining": round(self.session_limit - self.session_cost, 4),
            },
            "daily": {
                "cost": round(daily["cost"], 4),
                "requests": daily["requests"],
                "limit": self.daily_limit,
                "remaining": round(self.daily_limit - daily["cost"], 4),
                "date": today,
            },
            "monthly": {
                "cost": round(monthly["cost"], 4),
                "requests": monthly["requests"],
                "month": month,
            },
        }
    
    def reset_session(self):
        """Reset session tracking (e.g., when starting a new sparring session)."""
        self.session_cost = 0.0
        self.session_requests = 0

    def record_event(self, event: dict):
        """Append un évènement au journal JSONL (append-only, best-effort).

        Un évènement = une requête (succès ou échec). Format attendu :
          {ts, session_id, tool, model, provider, input_tokens, output_tokens,
           cost, error, duration_ms}
        """
        try:
            self.journal_file.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(event, ensure_ascii=False)
            with open(self.journal_file, "a") as f:
                f.write(line + "\n")
        except Exception as e:
            logger.warning(f"Could not append journal event: {e}")

    def aggregate_session(self, session_id: str) -> dict:
        """Agrège le journal pour une session donnée (lecture à la demande).

        Retourne un breakdown par modèle + totaux. Si le journal est absent
        ou la session introuvable, retourne des compteurs à zéro.
        """
        by_model: dict[str, dict] = {}
        total_cost = 0.0
        requests = 0
        errors = 0
        first_ts: str | None = None
        last_ts: str | None = None

        if self.journal_file.exists():
            with open(self.journal_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("session_id") != session_id:
                        continue

                    model = ev.get("model", "unknown")
                    bucket = by_model.setdefault(
                        model,
                        {"cost": 0.0, "requests": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0},
                    )
                    cost = ev.get("cost") or 0
                    bucket["cost"] += cost
                    bucket["requests"] += 1
                    bucket["input_tokens"] += ev.get("input_tokens") or 0
                    bucket["output_tokens"] += ev.get("output_tokens") or 0
                    if ev.get("error"):
                        bucket["errors"] += 1
                        errors += 1
                    total_cost += cost
                    requests += 1

                    ts = ev.get("ts")
                    if ts:
                        if first_ts is None or ts < first_ts:
                            first_ts = ts
                        if last_ts is None or ts > last_ts:
                            last_ts = ts

        return {
            "session_id": session_id,
            "total_cost": round(total_cost, 6),
            "requests": requests,
            "errors": errors,
            "first_event": first_ts,
            "last_event": last_ts,
            "by_model": {
                m: {**v, "cost": round(v["cost"], 6)} for m, v in by_model.items()
            },
        }


def estimate_cost(models: list[str], input_tokens: int, output_tokens: int, pricing: dict = None) -> dict:
    """Estimation standalone (sans instance BudgetManager).

    Lookup simple par model_id dans la DB pricing.json ; fallback sur FALLBACK_PRICING.
    """
    db = pricing if pricing is not None else _PRICING_DB

    estimates = {}
    total = 0

    for model in models:
        model_pricing = db.get(model) or FALLBACK_PRICING

        cost = (input_tokens / 1_000_000) * model_pricing["input"] + \
               (output_tokens / 1_000_000) * model_pricing["output"]

        estimates[model] = round(cost, 6)
        total += cost

    return {
        "estimates": estimates,
        "total": round(total, 6),
    }
