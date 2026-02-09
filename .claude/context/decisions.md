# Decisions

Technical decisions and their context. Added via `/retro`.

### Project naming: Sparring
**Decision**: Name the project "Sparring" (repo: llm-sparring)
**Context**: Needed a name that captures productive friction between LLMs, not passive consensus. "Council" was rejected as too static/hierarchical.
**Alternatives considered**: Council, Quorum, Agora, Chorus, Dialectic, Caucus, Clash, Peers
**Date**: 2025-01-29

### Multi-provider architecture
**Decision**: Support multiple LLM providers via OpenAI-compatible API + custom handlers for Anthropic/Google
**Context**: OpenRouter recommended for access to 400+ models with single key. Ollama for local-first free inference.
**Alternatives considered**: Single provider, abstraction layer
**Date**: 2025-01-29

### Budget tracking built-in
**Decision**: Integrate budget control (session/daily limits) from the start
**Context**: Querying multiple LLMs costs money. Budget awareness forces asking the right questions.
**Alternatives considered**: External budget tracking, no tracking
**Date**: 2025-01-29

### Lens validation: warn, don't refuse
**Decision**: Invalid lens triggers warning but still executes (natural critique)
**Context**: The goal is to challenge ideas. Even with wrong lens, the critique has value.
**Alternatives considered**: Reject request, silent fallback to default lens
**Date**: 2026-01-31

### URL allowlist for SSRF protection
**Decision**: Validate all `base_url` against ALLOWED_HOSTS before making requests
**Context**: Custom URLs in config could enable SSRF attacks (internal network scanning, credential exfiltration to rogue servers). Even for local-only usage, defense in depth matters.
**Alternatives considered**: No validation (trust config), regex patterns, blocklist approach
**Date**: 2026-02-05

### Rate limiting at tool level
**Decision**: Add sliding window rate limiter (30 req/60s) for tools making external requests
**Context**: Prevents runaway loops or abuse. Budget limits cost but not request volume. Rate limiting is orthogonal protection.
**Alternatives considered**: No rate limiting, per-provider limits, token bucket algorithm
**Date**: 2026-02-05

### Config path: ~/.config/mcp/llm-sparring
**Decision**: Move config from `~/.config/sparring` to `~/.config/mcp/llm-sparring`
**Context**: Groups all MCP server configs under `~/.config/mcp/`, making it scalable if more MCP servers are added. Follows XDG convention more consistently.
**Alternatives considered**: Keep `~/.config/sparring` (simpler but isolated), `~/.config/llm-sparring` (no MCP grouping)
**Date**: 2026-02-08

### Dedicated venv for MCP server
**Decision**: Use a `.venv` inside the MCP server directory, referenced directly in Claude Desktop/CLI config
**Context**: Isolates MCP dependencies from global Python. The `.gitignore` already had `.venv/` listed. Claude Desktop `command` and CLI `mcp add` point to `.venv/bin/python` to avoid activation issues.
**Alternatives considered**: Global pip install, uv, system package manager
**Date**: 2026-02-08
