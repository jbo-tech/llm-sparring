# Anti-patterns

Errors encountered and how to avoid them. Added via `/retro`.

<!-- Format:
### [Short title]
**Problem**: What went wrong
**Cause**: Why it happened
**Solution**: How to fix/avoid
**Date**: YYYY-MM-DD
-->

### Hardcoded token estimates
**Problem**: Budget checks used hardcoded 500 input tokens, underestimating actual cost
**Cause**: Prompt is built after budget check, so real length unknown at check time
**Solution**: Build prompt first, then estimate with `len(prompt) // 4`
**Date**: 2026-01-31

### Non-atomic file writes
**Problem**: Tracking file can be corrupted if process killed mid-write
**Cause**: Direct `open(file, "w")` truncates before write completes
**Solution**: Write to tempfile, then `os.replace()` (atomic on POSIX)
**Date**: 2026-01-31

### API key in query params
**Problem**: Google API key passed via `params={"key": api_key}` appears in URL
**Cause**: Query params are logged by proxies, CDNs, and server access logs
**Solution**: Use header authentication (`x-goog-api-key` for Google, `Authorization: Bearer` for OpenAI-compatible)
**Date**: 2026-02-05

### HTTP error body exposure
**Problem**: `return {"error": f"HTTP {status}: {response.text[:200]}"}` leaks server internals
**Cause**: Error responses may contain sensitive info (internal paths, tokens, stack traces)
**Solution**: Return only status code, log details server-side at DEBUG level
**Date**: 2026-02-05

### Unvalidated external URLs (SSRF)
**Problem**: Custom `base_url` in config can point to arbitrary hosts
**Cause**: No validation before making HTTP requests
**Solution**: Maintain ALLOWED_HOSTS allowlist, validate before every request
**Date**: 2026-02-05

### Slash command Claude Code confondu avec MCP Prompt
**Problem**: Un fichier `.claude/commands/sparring.md` placé dans le repo MCP n'apparaît pas comme `/sparring` quand le repo est installé hors du cwd (ex. `~/.claude/mcp/<repo>/`).
**Cause**: Claude Code scanne seulement `./.claude/commands/` (cwd) et `~/.claude/commands/` (global). Les `.claude/` de repos tiers sont invisibles. Un slash command projet n'est **pas** un canal de distribution — c'est un outil de dev interne au repo.
**Solution**: Pour distribuer un template invocable par l'utilisateur via un MCP, exposer un **MCP Prompt** (`@server.list_prompts()` + `@server.get_prompt()`). Claude Code le surface comme `/mcp__<serveur>__<nom>` dès que le MCP est connecté, sans setup côté utilisateur. Avant de diagnostiquer un "slash command qui ne marche pas", demander **où le repo est installé**.
**Date**: 2026-04-18
