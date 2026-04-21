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

### Clés API absentes sans feedback (`status: "unavailable"` silencieux)
**Problem**: `get_models()` renvoie `status: "unavailable"` sans message d'erreur. L'utilisateur a « fait `export OPENAI_API_KEY=...` » mais les providers restent down.
**Cause**: Trois pièges cumulés. (1) Le MCP tourne dans un sous-processus lancé par Claude Code — il n'hérite pas des `export` faits dans un terminal après le démarrage de Claude Code. (2) Le bloc `env: {}` vide dans `~/.claude.json` ne force rien côté MCP. (3) `providers.py:145` fait `os.environ.get(env_var)` et en cas d'absence désactive le provider silencieusement (pas de log). (4) `python-dotenv` était présent en transitif mais jamais appelé : pas de `.env` local lu.
**Solution**: Charger les clés via `load_dotenv(Path(__file__).parent / ".env")` en haut de `server.py`, avant l'import de `providers`. Ancrer le chemin via `__file__` pour ne pas dépendre du `cwd`. Documenter le `.env` comme option principale dans le README, avertir que `export` dans un shell ne suffit pas. En debug : toujours vérifier le vrai `env` vu par le sous-processus, pas `echo $VAR` dans le shell de l'utilisateur.
**Date**: 2026-04-21

### Dev repo et runtime repo confondus
**Problem**: Patcher un fichier dans le repo de dev n'a aucun effet sur le comportement observé — le MCP continue à se comporter comme avant.
**Cause**: Deux clones git distincts (`/home/jbo/Wip/coding/mcp/llm-sparring/` dev, `/home/jbo/.claude/mcp/llm-sparring/` runtime enregistré dans `~/.claude.json`). Pas de symlink, pas de sync automatique. Facilement invisible si on ne vérifie pas le chemin du `command` MCP.
**Solution**: Avant toute modif, vérifier le chemin exact dans `~/.claude.json` → `mcpServers.<name>.args`. Traiter le dev comme source de vérité, pousser via `git pull` côté runtime. En début de diagnostic, toujours comparer le chemin du runtime avec le `cwd` actuel.
**Date**: 2026-04-21
