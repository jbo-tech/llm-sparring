"""
Budget management for Sparring.

Tracks usage and enforces limits:
- Per-request confirmation threshold
- Session limit
- Daily limit
"""

import json
import logging
import os
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Any

logger = logging.getLogger("sparring.budget")

# Pricing per 1M tokens (as of Jan 2025)
# Format: {model_pattern: {"input": price, "output": price}}
DEFAULT_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    
    # Anthropic
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    
    # Google Gemini
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    
    # Mistral
    "mistral-large": {"input": 2.00, "output": 6.00},
    "mistral-small": {"input": 0.20, "output": 0.60},
    "mixtral": {"input": 0.24, "output": 0.24},
    
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    
    # Groq (pricing varies, these are estimates)
    "groq": {"input": 0.05, "output": 0.08},
    "llama-3.3-70b": {"input": 0.59, "output": 0.79},
    
    # xAI Grok
    "grok": {"input": 2.00, "output": 10.00},
    
    # OpenRouter (examples, actual prices vary by model)
    "mistralai/mixtral-8x7b": {"input": 0.24, "output": 0.24},
    "meta-llama/llama-3": {"input": 0.10, "output": 0.10},
    "qwen": {"input": 0.15, "output": 0.15},
    
    # Local (free)
    "ollama": {"input": 0, "output": 0},
    "local": {"input": 0, "output": 0},
    "phi": {"input": 0, "output": 0},
}


class BudgetManager:
    """Manages budget tracking and enforcement."""
    
    def __init__(self, config: dict):
        self.confirm_threshold = config.get("confirm_threshold", 0.10)
        self.session_limit = config.get("session_limit", 1.00)
        self.daily_limit = config.get("daily_limit", 5.00)
        
        # Tracking file
        tracking_path = config.get("tracking_file", "~/.config/sparring/usage.json")
        self.tracking_file = Path(tracking_path).expanduser()
        
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
    
    def get_model_pricing(self, model_name: str) -> dict:
        """Get pricing for a model."""
        # Check custom pricing first
        if model_name in self.custom_pricing:
            return self.custom_pricing[model_name]
        
        # Check default pricing (partial match)
        model_lower = model_name.lower()
        for pattern, pricing in DEFAULT_PRICING.items():
            if pattern in model_lower:
                return pricing
        
        # Check if it's a local model
        if "local" in model_lower or "ollama" in model_lower or "llama-local" in model_lower:
            return {"input": 0, "output": 0}
        
        # Default: assume moderate pricing
        logger.warning(f"No pricing found for {model_name}, using default")
        return {"input": 1.00, "output": 3.00}
    
    def estimate_request_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request."""
        pricing = self.get_model_pricing(model_name)
        
        # Convert from per-1M-tokens to actual cost
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


def estimate_cost(models: list[str], input_tokens: int, output_tokens: int, pricing: dict = None) -> dict:
    """Standalone cost estimation function."""
    if pricing is None:
        pricing = DEFAULT_PRICING
    
    estimates = {}
    total = 0
    
    for model in models:
        model_lower = model.lower()
        model_pricing = None
        
        # Find matching pricing
        for pattern, price in pricing.items():
            if pattern in model_lower:
                model_pricing = price
                break
        
        if model_pricing is None:
            model_pricing = {"input": 1.00, "output": 3.00}  # Default
        
        cost = (input_tokens / 1_000_000) * model_pricing["input"] + \
               (output_tokens / 1_000_000) * model_pricing["output"]
        
        estimates[model] = round(cost, 6)
        total += cost
    
    return {
        "estimates": estimates,
        "total": round(total, 6),
    }
