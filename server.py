#!/usr/bin/env python3
"""
Sparring MCP Server

Make your LLMs disagree.

An MCP server that orchestrates sparring sessions between LLMs:
- ask_model: Query a specific model
- ask_all: Query all enabled models in parallel  
- challenge: Have one model critique another's response (the heart of sparring)
- get_models: List available models with status
- get_lenses: List available challenge lenses
- get_usage: Get current budget usage
"""

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from providers import ProviderManager
from budget import BudgetManager, estimate_cost
from lenses import (
    LENSES,
    DEFAULT_LENS,
    get_challenge_prompt,
    get_lens_list,
    validate_lens,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sparring")

# Initialize server
server = Server("sparring")

# Global managers (initialized on startup)
provider_manager: ProviderManager | None = None
budget_manager: BudgetManager | None = None

# Limits
MAX_PROMPT_CHARS = 50000
RATE_LIMIT_REQUESTS = 30  # Max requêtes par fenêtre
RATE_LIMIT_WINDOW = 60  # Fenêtre en secondes


class RateLimiter:
    """Rate limiter simple avec fenêtre glissante."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: list[float] = []

    def check(self) -> tuple[bool, str | None]:
        """Vérifie si la requête est autorisée. Retourne (allowed, reason)."""
        import time
        now = time.time()
        # Nettoyer les requêtes hors fenêtre
        self.requests = [t for t in self.requests if now - t < self.window]
        if len(self.requests) >= self.max_requests:
            return False, f"Rate limit: {self.max_requests} requêtes/{self.window}s"
        return True, None

    def record(self):
        """Enregistre une requête."""
        import time
        self.requests.append(time.time())


# Rate limiter global
rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _ensure_initialized():
    """Raise if managers not initialized."""
    if provider_manager is None or budget_manager is None:
        raise RuntimeError("Server not initialized")


def get_config_path() -> Path:
    """Get config file path."""
    config_dir = Path(os.environ.get("SPARRING_CONFIG_DIR", "~/.config/mcp/llm-sparring")).expanduser()
    return config_dir / "config.yaml"


def load_config() -> dict:
    """Load configuration from YAML file."""
    import yaml
    
    config_path = get_config_path()
    
    if not config_path.exists():
        logger.warning(f"Config file not found at {config_path}, using defaults")
        return get_default_config()
    
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_default_config() -> dict:
    """Return default configuration."""
    return {
        "models": [
            {
                "name": "gpt-4o",
                "provider": "openai",
                "model_id": "gpt-4o",
                "enabled": True,
            },
            {
                "name": "gemini-flash",
                "provider": "google",
                "model_id": "gemini-2.0-flash",
                "enabled": True,
            },
            {
                "name": "llama-local",
                "provider": "ollama",
                "model_id": "llama3.2",
                "base_url": "http://localhost:11434",
                "enabled": True,
            },
        ],
        "settings": {
            "default_timeout": 30,
            "max_parallel": 3,
        },
        "budget": {
            "confirm_threshold": 0.10,
            "session_limit": 1.00,
            "daily_limit": 5.00,
            "tracking_file": "~/.config/mcp/llm-sparring/usage.json",
        },
    }


# =============================================================================
# MCP Tools
# =============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    
    # Build lens enum for schema
    lens_enum = list(LENSES.keys())
    
    return [
        Tool(
            name="ask_model",
            description="Query a specific LLM model. Returns the model's response.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Name of the model to query (e.g., 'gpt-4o', 'gemini-flash', 'llama-local')",
                    },
                    "question": {
                        "type": "string",
                        "description": "The question or prompt to send to the model",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional context to provide to the model",
                        "default": "",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens in response",
                        "default": 1000,
                    },
                },
                "required": ["model", "question"],
            },
        ),
        Tool(
            name="ask_all",
            description="Query all enabled LLM models in parallel. Returns a dict of model_name -> response.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question or prompt to send to all models",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional context to provide to all models",
                        "default": "",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens in each response",
                        "default": 1000,
                    },
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="challenge",
            description="""Have one model critique a response through an optional lens.
            
Without lens: Natural critique from the challenger's perspective.
With lens: Critique through a specific angle (devil_advocate, cynical_dev, security, cost, user, etc.)

The target can be a model response OR file content — just pass the content and indicate the source.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "challenger_model": {
                        "type": "string",
                        "description": "Name of the model that will critique",
                    },
                    "original_question": {
                        "type": "string",
                        "description": "The original question or context",
                    },
                    "target_response": {
                        "type": "string",
                        "description": "The response or content to critique (model response, file content, code, etc.)",
                    },
                    "target_source": {
                        "type": "string",
                        "description": "Source of the response: model name (e.g., 'gpt-4o') or file name (e.g., 'server.py')",
                        "default": "unknown source",
                    },
                    "lens": {
                        "type": ["string", "null"],
                        "enum": lens_enum + [None],
                        "description": f"Challenge lens. Available: {', '.join(lens_enum)}. Use null for natural critique without persona.",
                        "default": None,
                    },
                    "language": {
                        "type": "string",
                        "enum": ["fr", "en"],
                        "description": "Response language",
                        "default": "fr",
                    },
                },
                "required": ["challenger_model", "original_question", "target_response"],
            },
        ),
        Tool(
            name="get_models",
            description="List all configured models with their availability status and pricing.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_lenses",
            description="List available challenge lenses with descriptions.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_usage",
            description="Get current budget usage (session, daily, monthly).",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="estimate_cost",
            description="Estimate the cost of a query before executing it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "models": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of model names to estimate for",
                    },
                    "input_tokens": {
                        "type": "integer",
                        "description": "Estimated input tokens",
                        "default": 500,
                    },
                    "output_tokens": {
                        "type": "integer",
                        "description": "Estimated output tokens",
                        "default": 1000,
                    },
                },
                "required": ["models"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    # Rate limiting pour les outils qui font des requêtes externes
    tools_with_requests = {"ask_model", "ask_all", "challenge"}
    if name in tools_with_requests:
        allowed, reason = rate_limiter.check()
        if not allowed:
            return [TextContent(type="text", text=json.dumps({"error": reason}))]
        rate_limiter.record()

    try:
        if name == "ask_model":
            result = await handle_ask_model(arguments)
        elif name == "ask_all":
            result = await handle_ask_all(arguments)
        elif name == "challenge":
            result = await handle_challenge(arguments)
        elif name == "get_models":
            result = await handle_get_models()
        elif name == "get_lenses":
            result = await handle_get_lenses()
        elif name == "get_usage":
            result = await handle_get_usage()
        elif name == "estimate_cost":
            result = await handle_estimate_cost(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
    
    except Exception as e:
        logger.exception(f"Error in tool {name}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


# =============================================================================
# Tool Handlers
# =============================================================================

async def handle_ask_model(args: dict) -> dict:
    """Handle ask_model tool."""
    _ensure_initialized()
    model_name = args["model"]
    question = args["question"]
    context = args.get("context", "")
    max_tokens = args.get("max_tokens", 1000)

    # Contexte pricing (model_id/provider/base_url) pour la cascade de lookup
    model_cfg = provider_manager.models.get(model_name, {})
    pricing_ctx = {
        "model_id": model_cfg.get("model_id"),
        "provider": model_cfg.get("provider"),
        "base_url": model_cfg.get("base_url"),
    }

    # Build prompt
    prompt = question
    if context:
        prompt = f"Context:\n{context}\n\nQuestion:\n{question}"

    if len(prompt) > MAX_PROMPT_CHARS:
        return {"error": "Prompt too large", "chars": len(prompt), "limit": MAX_PROMPT_CHARS}

    # Check budget
    estimated_input = _estimate_tokens(prompt)
    cost_estimate = budget_manager.estimate_request_cost(model_name, estimated_input, max_tokens, **pricing_ctx)
    budget_check = budget_manager.check_budget(cost_estimate)

    if not budget_check["allowed"]:
        return {
            "error": "Budget exceeded",
            "reason": budget_check["reason"],
            "estimated_cost": cost_estimate,
            "usage": budget_manager.get_usage(),
        }

    # Query model
    response = await provider_manager.query(model_name, prompt, max_tokens)

    # Track usage
    actual_cost = 0
    if "error" not in response:
        actual_cost = budget_manager.estimate_request_cost(
            model_name,
            response.get("input_tokens", 500),
            response.get("output_tokens", max_tokens),
            **pricing_ctx,
        )
        budget_manager.record_usage(actual_cost)

    return {
        "summary": f"[{model_name} | ${actual_cost:.4f}]",
        "model": model_name,
        "response": response.get("content", response.get("error", "No response")),
        "tokens": {
            "input": response.get("input_tokens"),
            "output": response.get("output_tokens"),
        },
        "cost": actual_cost,
    }


async def handle_ask_all(args: dict) -> dict:
    """Handle ask_all tool."""
    _ensure_initialized()
    question = args["question"]
    context = args.get("context", "")
    max_tokens = args.get("max_tokens", 1000)

    # Build prompt
    prompt = question
    if context:
        prompt = f"Context:\n{context}\n\nQuestion:\n{question}"

    if len(prompt) > MAX_PROMPT_CHARS:
        return {"error": "Prompt too large", "chars": len(prompt), "limit": MAX_PROMPT_CHARS}

    # Get available models
    available_models = [m["name"] for m in provider_manager.get_available_models()]

    if not available_models:
        return {"error": "No models available"}

    # Estimate total cost
    estimated_input = _estimate_tokens(prompt)
    total_estimate = 0.0
    for m in available_models:
        cfg = provider_manager.models.get(m, {})
        total_estimate += budget_manager.estimate_request_cost(
            m, estimated_input, max_tokens,
            model_id=cfg.get("model_id"),
            provider=cfg.get("provider"),
            base_url=cfg.get("base_url"),
        )

    budget_check = budget_manager.check_budget(total_estimate)
    if not budget_check["allowed"]:
        return {
            "error": "Budget exceeded",
            "reason": budget_check["reason"],
            "estimated_cost": total_estimate,
            "models_requested": available_models,
        }

    # Query all models in parallel (with concurrency limit)
    max_parallel = provider_manager.settings.get("max_parallel", 3)
    sem = asyncio.Semaphore(max_parallel)

    async def bounded_query(model):
        async with sem:
            return await provider_manager.query(model, prompt, max_tokens)

    tasks = [bounded_query(model) for model in available_models]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    responses = {}
    total_cost = 0
    
    for model, result in zip(available_models, results):
        if isinstance(result, Exception):
            responses[model] = {"error": str(result)}
        else:
            responses[model] = {
                "response": result.get("content", result.get("error", "No response")),
                "tokens": {
                    "input": result.get("input_tokens"),
                    "output": result.get("output_tokens"),
                },
            }
            if "cost" in result:
                total_cost += result["cost"]
    
    # Track usage
    if total_cost > 0:
        budget_manager.record_usage(total_cost)
    
    return {
        "summary": f"[{len(available_models)} models | ${total_cost:.4f}]",
        "responses": responses,
        "total_cost": total_cost,
        "models_queried": len(available_models),
    }


async def handle_challenge(args: dict) -> dict:
    """Handle challenge tool with optional lens."""
    _ensure_initialized()
    challenger = args["challenger_model"]
    original_question = args["original_question"]
    target_response = args["target_response"]
    target_source = args.get("target_source", "unknown source")
    lens = args.get("lens", None)
    language = args.get("language", "fr")
    lens_warning = None

    # Validate lens if provided
    if lens is not None:
        lens, lens_warning = validate_lens(lens)

    # Build prompt based on lens
    if lens is not None:
        prompt = get_challenge_prompt(
            lens=lens,
            original_question=original_question,
            original_response=target_response,
            language=language,
        )
        prompt = prompt.replace(
            "## Response to challenge",
            f"## Response to challenge (source: {target_source})"
        )
    else:
        # Natural critique without lens
        lang_instruction = "Réponds en français." if language == "fr" else "Respond in English."
        prompt = f"""Analyse critique de la réponse suivante.

{lang_instruction}

## Question / Contexte original
{original_question}

## Réponse à analyser (source: {target_source})
{target_response}

## Ta tâche
Donne ton analyse critique de cette réponse :
1. Points forts
2. Points faibles, lacunes, ou erreurs
3. Hypothèses à questionner
4. Ce qui manque ou pourrait être amélioré

Sois constructif mais rigoureux. Si tu es en désaccord, explique pourquoi."""

    if len(prompt) > MAX_PROMPT_CHARS:
        return {"error": "Prompt too large", "chars": len(prompt), "limit": MAX_PROMPT_CHARS}

    # Contexte pricing
    challenger_cfg = provider_manager.models.get(challenger, {})
    pricing_ctx = {
        "model_id": challenger_cfg.get("model_id"),
        "provider": challenger_cfg.get("provider"),
        "base_url": challenger_cfg.get("base_url"),
    }

    # Check budget
    estimated_input = _estimate_tokens(prompt)
    cost_estimate = budget_manager.estimate_request_cost(challenger, estimated_input, 1500, **pricing_ctx)
    budget_check = budget_manager.check_budget(cost_estimate)

    if not budget_check["allowed"]:
        return {
            "error": "Budget exceeded",
            "reason": budget_check["reason"],
            "estimated_cost": cost_estimate,
        }

    # Query challenger
    response = await provider_manager.query(challenger, prompt, 1500)

    # Track usage
    actual_cost = 0
    if "error" not in response:
        actual_cost = budget_manager.estimate_request_cost(
            challenger,
            response.get("input_tokens", 800),
            response.get("output_tokens", 1500),
            **pricing_ctx,
        )
        budget_manager.record_usage(actual_cost)

    lens_label = lens or "natural"
    result = {
        "summary": f"[{challenger} | {lens_label} | ${actual_cost:.4f}]",
        "challenger": challenger,
        "target_source": target_source,
        "lens": lens,
        "lens_description": LENSES[lens]["description"] if lens else "Natural critique (no lens)",
        "critique": response.get("content", response.get("error", "No response")),
        "cost": actual_cost,
    }

    if lens_warning:
        result["warning"] = lens_warning

    return result


async def handle_get_models() -> dict:
    """Handle get_models tool."""
    _ensure_initialized()
    all_models = provider_manager.get_all_models()
    available = provider_manager.get_available_models()
    available_names = {m["name"] for m in available}
    
    models = []
    for model in all_models:
        status = "available" if model["name"] in available_names else "unavailable"
        pricing = budget_manager.get_model_pricing(
            model["name"],
            model_id=model.get("model_id"),
            provider=model.get("provider"),
            base_url=model.get("base_url"),
        )

        models.append({
            "name": model["name"],
            "provider": model["provider"],
            "model_id": model["model_id"],
            "status": status,
            "enabled": model.get("enabled", True),
            "pricing": pricing,
        })
    
    return {"models": models}


async def handle_get_lenses() -> dict:
    """Handle get_lenses tool."""
    return {
        "lenses": get_lens_list(),
        "default": DEFAULT_LENS,
        "note": "Use lens=null for natural critique without persona",
    }


async def handle_get_usage() -> dict:
    """Handle get_usage tool."""
    _ensure_initialized()
    return budget_manager.get_usage()


async def handle_estimate_cost(args: dict) -> dict:
    """Handle estimate_cost tool."""
    _ensure_initialized()
    models = args["models"]
    input_tokens = args.get("input_tokens", 500)
    output_tokens = args.get("output_tokens", 1000)
    
    estimates = {}
    total = 0

    for model in models:
        cfg = provider_manager.models.get(model, {})
        cost = budget_manager.estimate_request_cost(
            model, input_tokens, output_tokens,
            model_id=cfg.get("model_id"),
            provider=cfg.get("provider"),
            base_url=cfg.get("base_url"),
        )
        estimates[model] = cost
        total += cost
    
    budget_check = budget_manager.check_budget(total)
    
    return {
        "estimates": estimates,
        "total": total,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "budget_status": budget_check,
    }


# =============================================================================
# Main
# =============================================================================

async def main():
    """Run the MCP server."""
    global provider_manager, budget_manager
    
    # Load config
    config = load_config()
    
    # Initialize managers
    provider_manager = ProviderManager(config.get("models", []), config.get("settings", {}))
    budget_manager = BudgetManager(config.get("budget", {}))
    
    logger.info("Sparring MCP Server starting...")
    logger.info(f"Config: {get_config_path()}")
    logger.info(f"Available sparring partners: {[m['name'] for m in provider_manager.get_available_models()]}")
    logger.info(f"Available lenses: {list(LENSES.keys())}")

    # Graceful shutdown
    def handle_shutdown(signum, frame):
        logger.info(f"Received signal {signum}, saving tracking...")
        if budget_manager:
            budget_manager._save_tracking()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Run server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
