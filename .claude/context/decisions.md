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
**Statut**: superseded le 2026-04-16 — voir « Migration vers uv + pyproject.toml »

### Lens definitions in English
**Decision**: Write all lens system prompts and focus instructions in English, even though response language is configurable (fr/en)
**Context**: Lens config is code-level instructions to LLMs. English is more universal and avoids mixing config language with output language. The `language` parameter controls the response language independently.
**Alternatives considered**: Keep in French (original), make configurable per-lens
**Date**: 2026-02-10

### Summary field in tool responses
**Decision**: Add a compact `summary` field as first key in all tool response dicts
**Context**: Gives at-a-glance metadata (model, lens, cost) without parsing the full JSON. Format: `[model | $cost]` for ask, `[model | lens | $cost]` for challenge. Being first in dict means it's immediately visible in output.
**Alternatives considered**: Prepend to response text (pollutes content), separate metadata endpoint (extra call)
**Date**: 2026-02-10

### OpenAI-compat endpoints unifiés pour Anthropic et Google
**Decision**: Supprimer les handlers custom `_query_anthropic` et `_query_google` et router les deux providers via `_query_openai_compatible` sur leurs endpoints officiels.
**Context**: Anthropic (`https://api.anthropic.com/v1/`) et Google (`https://generativelanguage.googleapis.com/v1beta/openai/`) exposent désormais des endpoints OpenAI-compatibles. Supprime ~90 lignes de handlers spécifiques et unifie le chemin d'exécution sur un seul generic handler. Réaffirme la décision "Multi-provider architecture" de 2025-01-29 en la simplifiant : 11 providers, 1 handler cloud + 1 handler ollama.
**Tradeoff**: Le prompt caching Anthropic **n'est pas supporté** sur l'endpoint OpenAI-compat (limitation officielle documentée). Pour un usage sparring one-shot l'impact est mineur. Si le caching devient nécessaire un jour, réintroduire un handler natif pour Anthropic uniquement.
**Alternatives considered**: Conserver les handlers custom (dette maintenance, 90 lignes de duplication), migrer sur LiteLLM complet (overhead 200 MB + startup +3s + API qui bouge tous les X jours, rejeté — cf. analyse pré-plan).
**Date**: 2026-04-15

### Migration vers uv + pyproject.toml
**Decision**: Remplacer `pip + venv + requirements.txt` par `uv + pyproject.toml + uv.lock`. MCP invoqué via `uv --directory <path> run server.py` au lieu de `.venv/bin/python server.py`. `requirements.txt` supprimé, `uv.lock` committé. Pas de `.python-version` committé — `requires-python = ">=3.11"` dans `pyproject.toml` suffit à uv, et un `.python-version` partagé entre outils entre en conflit avec `pyenv` (qui exige une version exactement installée).
**Context**: Supersede la décision du 2026-02-08. `uv run` rend l'installation auto-bootstrap (clone → run sans étape manuelle). Lockfile déterministe remplace les contraintes `>=` floues. Un seul outil gère Python (installe 3.11 si absent) + venv + deps. Corrige aussi l'incohérence entre la doc (3.11+) et le venv réel (3.10).
**Tradeoff**: `uv` devient un prérequis pour exécuter le MCP. Pour un projet perso maintenu solo, gain > coût.
**Alternatives considered**: Garder `requirements.txt` généré en parallèle (double source de vérité, rejeté), aligner la doc sur Python 3.10 (garde le setup intact mais n'adresse pas les motivations principales), committer `.python-version` (rejeté après test — conflit avec `pyenv` installé en parallèle qui lit le même fichier).
**Date**: 2026-04-16

### Template sparring exposé via MCP Prompt
**Decision**: Exposer le template d'orchestration sparring comme MCP Prompt (`list_prompts` + `get_prompt` dans `server.py`), en lisant `.claude/commands/sparring.md` à la volée. Claude Code le surface automatiquement comme `/mcp__sparring__sparring [topic]` dès que le serveur est connecté.
**Context**: Le fichier `.claude/commands/sparring.md` n'est scanné par Claude Code que si on lance depuis le dossier du repo. Quand l'utilisateur installe le MCP ailleurs (`~/.claude/mcp/llm-sparring/...` suivant le README), le slash command n'est jamais vu. MCP Prompts est la primitive native pour distribuer un template invocable par l'utilisateur — pas besoin de symlink ou de copie.
**Tradeoff**: Nom de commande verbose côté Claude Code (`/mcp__sparring__sparring`). Acceptable car toutes les commandes MCP suivent ce format — c'est cohérent.
**Alternatives considered**: Symlink `~/.claude/commands/sparring.md` (hors-MCP, setup manuel, à documenter), dupliquer le fichier (deux sources de vérité), mover le template en `prompts/sparring.md` (casserait `/sparring` pour les contributeurs qui bossent dans le repo).
**Date**: 2026-04-18

### Clés API chargées via `.env` local (option par défaut documentée)
**Decision**: `server.py` appelle `load_dotenv(Path(__file__).parent / ".env")` au démarrage, avant l'import `providers`. `python-dotenv` promu en dep explicite. README réordonné pour présenter `.env` comme option A (recommandée), `~/.claude.json` → `env` comme option B, `~/.zshenv` comme option C.
**Context**: Les trois options qui fonctionnaient en théorie avaient chacune un piège : (A) `.env` invisible car `load_dotenv()` jamais appelé malgré `python-dotenv` installé en transitif ; (B) bloc `env: {}` vide par défaut dans Claude Code ; (C) `~/.zshrc` documenté comme cible mais pas lu par les shells non-interactifs (et un simple `export` volatil ne suffit pas). L'option `.env` garde les secrets scopés au MCP, ne pollue pas l'environnement global, survit à un redémarrage de shell, et ne dépend pas du shell qui a lancé Claude Code. Chemin ancré via `Path(__file__).parent` pour être indépendant du `cwd`.
**Tradeoff**: Un secret-store chiffré serait plus robuste (agenix, pass, sops), mais coût d'install trop élevé pour un outil perso mono-utilisateur. `.env` + `chmod 600` + `.gitignore` couvre le modèle de menace réel (éviter leak git, limiter exposition locale).
**Alternatives considered**: `~/.zshenv` en défaut (rejeté : expose les clés à tout process lancé depuis zsh, mal scopé) ; bloc `env` dans `~/.claude.json` (rejeté par défaut : clés en clair dans un JSON manipulé par d'autres outils, pas au `chmod 600`) ; secret-store chiffré (rejeté : overkill).
**Date**: 2026-04-21

### Pricing vendored depuis LiteLLM
**Decision**: Remplacer `DEFAULT_PRICING` hardcodé (~45 entrées figées « as of Jan 2025 ») par un `pricing.json` vendored depuis `BerriAI/litellm`. Refresh manuel trimestriel via `scripts/refresh_pricing.py`.
**Context**: La table hardcodée s'était dégradée : Claude 4.x, GPT-5, Gemini 2.5 absents. Le JSON LiteLLM donne ~2600 modèles à jour. Vendor plutôt que dépendance runtime évite 200 MB d'overhead et un chemin réseau caché au démarrage. Cascade de lookup : override config.yaml → exact model_id → `{provider}/{model_id}` → règle locale (ollama/localhost → 0) → fallback conservateur avec warning.
**Tradeoff**: Refresh manuel requis (~1×/trimestre). Les modèles dépréciés non listés par LiteLLM tombent en fallback warning-loggé — l'utilisateur doit soit passer à un modèle récent, soit ajouter un override dans la section `pricing` de `config.yaml`.
**Alternatives considered**: Dépendance runtime `litellm` (rejeté : overhead mémoire/startup, API unstable, incompatible KISS), maintenir manuellement (status quo, non viable long terme), loader le JSON runtime depuis GitHub (ajoute un appel réseau au boot + point de panne).
**Date**: 2026-04-15
