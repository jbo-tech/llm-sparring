# Status

## Objective
Build an MCP server that orchestrates sparring sessions between LLMs — query multiple models, have them challenge each other, sharpen ideas through productive friction.

## Current focus
Template sparring exposé nativement via MCP Prompts. Prêt pour tests d'usage cross-projets.

## Log

### 2026-04-18
- Done: Ajout `list_prompts` / `get_prompt` dans `server.py` — le template `.claude/commands/sparring.md` est désormais exposé comme MCP Prompt (`/mcp__sparring__sparring [topic]`). Frontmatter YAML strippé à la lecture, argument `topic` optionnel suffixé en bas du prompt.
- Done: Frontmatter ajouté à `.claude/commands/sparring.md` (commit `26eea49`).
- Done: Smoke test handlers OK (list + get avec topic).
- Décision actée: MCP Prompt choisi plutôt que symlink `~/.claude/commands/` — distribution native, zéro setup utilisateur, fonctionne partout où le MCP est connecté.
- Anti-pattern identifié: j'avais diagnostiqué un problème de frontmatter sans demander où le repo était installé (`~/.claude/mcp/...` = hors scope du scan Claude Code).
- Next: Commit du changement MCP Prompt. Retro + mise à jour README pour documenter `/mcp__sparring__sparring`.

### 2026-04-16
- Done: Migration `pip + venv + requirements.txt` → `uv + pyproject.toml + uv.lock`. `.python-version` pinné à `3.11`. `requirements.txt` supprimé. Venv recréé sur Python 3.11.14 (corrige l'incohérence 3.10 vs doc 3.11+).
- Done: Refresh README (install, Claude Desktop JSON, CLI `mcp add`, refresh pricing, testing, development) et CLAUDE.md pour pointer sur `uv run server.py` / `uv sync`.
- Done: `decisions.md` — ancienne entrée venv marquée superseded, nouvelle entrée migration uv.
- Tradeoff acté: `uv` devient un prérequis côté opérateur.
- Next: Re-enregistrer le MCP avec la nouvelle commande `uv --directory <path> run server.py`, tester `get_models` en live.

### 2026-04-15
- Done: Refactor `providers.py` — Anthropic et Google migrés sur endpoint OpenAI-compat (`api.anthropic.com/v1` et `generativelanguage.googleapis.com/v1beta/openai`). Handlers `_query_anthropic` et `_query_google` supprimés (~90 lignes). Seul Ollama conserve un handler dédié.
- Done: Externalisation du pricing — `DEFAULT_PRICING` hardcodé remplacé par `pricing.json` vendored depuis LiteLLM (2659 entrées). Cascade de lookup : override → exact → `{provider}/{id}` → local → fallback.
- Done: Script `scripts/refresh_pricing.py` pour refresh trimestriel manuel.
- Done: `get_model_pricing` et `estimate_request_cost` reçoivent désormais `model_id`/`provider`/`base_url` pour la résolution fine.
- Done: 2 entrées dans `decisions.md` (OpenAI-compat unifié avec tradeoff caching, pricing vendored).
- Tradeoff acté: prompt caching Anthropic indisponible via endpoint OpenAI-compat.
- Done: Refresh README — providers table (anthropic/google en OpenAI-compat), signature `challenge` (target_source/lens/language), ajout section `get_lenses`, section Pricing avec `pricing.json` et `refresh_pricing.py`, exemple `get_models` complet. Écarts doc pré-existants résorbés.
- Next: Tester end-to-end avec clés API réelles (ask_model sur claude-haiku, gemini-flash, régression gpt-4o-mini). Commit.

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
