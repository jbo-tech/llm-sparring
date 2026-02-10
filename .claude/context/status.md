# Status

## Objective
Build an MCP server that orchestrates sparring sessions between LLMs — query multiple models, have them challenge each other, sharpen ideas through productive friction.

## Current focus
Lenses and response UX improvements done. Ready for testing.

## Log

### 2026-02-10
- Done: Added `naive` lens — questions fundamentals, jargon, implicit assumptions
- Done: Converted all lens definitions (system/focus) from French to English
- Done: Converted prompt builder template (headers, instructions) to English
- Done: Added `summary` field to all tool responses (`ask_model`, `ask_all`, `challenge`)
  - Format: `[model | $cost]`, `[N models | $cost]`, `[model | lens | $cost]`
- Done: Fixed `prompt.replace` in `handle_challenge` to match new English header
- Done: Updated `.claude/context/lenses.md` with naive lens, kickoff sequence, example
- Next: Test with real providers, commit changes

### 2026-02-08
- Done: Migrated config path from `~/.config/sparring` to `~/.config/mcp/llm-sparring`
- Done: Added virtual environment setup (`.venv`) in installation steps
- Done: Added step-by-step Testing section to README (7 steps)
- Done: Updated all references across server.py, budget.py, config.yaml, CLAUDE.md, README.md
- Commit: `7043bbf`
- Next: Follow Testing section — create venv, install deps, configure models, run server

### 2026-02-05
- Done: Security audit based on WorkOS MCP best practices article
- Done: Fixed 4 critical security issues:
  - SSRF protection via ALLOWED_HOSTS + URL validation
  - Credential leak prevention (no API key logging, no HTTP body in errors)
  - Google API key moved from query param to header (`x-goog-api-key`)
  - Rate limiting (30 req/60s sliding window)
- Pending commit: security fixes in `providers.py` + `server.py`
- Next: Commit, test server with real providers

### 2025-01-31
- Done: Code review (internal + @infra-expert)
- Done: Hardening pass — 7 fixes for budget/security/usage:
  - Atomic write for tracking file
  - Signal handlers (SIGTERM/SIGINT)
  - Guard globals before use
  - Semaphore for max_parallel
  - Prompt size limit (50k chars)
  - Dynamic token estimation
  - Lens validation with warning
- Commits: `b6d1f9c` (initial), `db181c4` (hardening)

### 2025-01-29
- Init: Project context initialized
- Done: Project naming (Sparring), intent document, README
- State: Design complete, no code yet
