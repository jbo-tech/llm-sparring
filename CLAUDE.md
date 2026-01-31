# Sparring

MCP server for multi-LLM sparring sessions. Make your LLMs disagree.

## Commands

```bash
python server.py                    # Run server
LOG_LEVEL=DEBUG python server.py    # Debug mode
pip install -r requirements.txt     # Install deps
```

## Stack

- Python 3.11+
- MCP SDK (mcp)
- httpx for async HTTP
- pydantic for config validation
- YAML config (~/.config/sparring/config.yaml)

## Conventions

- OpenAI-compatible providers use generic handler
- Custom handlers only for non-compatible APIs (Anthropic, Google)
- All tools return structured JSON
- Budget tracking per session/day

## Core primitives

- `ask_model` — query single model
- `ask_all` — query all enabled models in parallel
- `challenge` — have one model critique another's response
- `get_models` — list configured models
- `get_usage` — budget consumption
- `estimate_cost` — cost estimation before requests

## Context

When relevant, read:
- Current work: `.claude/context/status.md`
- Past mistakes: `.claude/context/anti-patterns.md`
- Technical decisions: `.claude/context/decisions.md`

## End of session

Run `/retro` before stopping to update context files.
