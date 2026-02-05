# Status

## Objective
Build an MCP server that orchestrates sparring sessions between LLMs — query multiple models, have them challenge each other, sharpen ideas through productive friction.

## Current focus
Security audit complete. Fixes applied. Ready for commit and testing.

## Log

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
