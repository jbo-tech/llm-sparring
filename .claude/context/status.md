# Status

## Objective
Build an MCP server that orchestrates sparring sessions between LLMs — query multiple models, have them challenge each other, sharpen ideas through productive friction.

## Current focus
Ajout de nouveaux providers (Moonshot/Kimi, z.ai/GLM).

## Log

### 2026-05-17
- Done: Ajout providers `moonshot` (Kimi, `https://api.moonshot.ai/v1`, `MOONSHOT_API_KEY`) et `zai` (z.ai/GLM, `https://api.z.ai/api/coding/paas/v4`, `ZAI_API_KEY`) dans `PROVIDER_REGISTRY` + `ALLOWED_HOSTS` (`providers.py`).
- Done: Entrées modèles dans `config.yaml` — `kimi` (`moonshot-v1-auto`) et `zai-glm` (`glm-4-plus`), disabled par défaut.
- Note: z.ai utilise des modèles GLM (pas DeepSeek). Erreur corrigée en cours de session.
- Pending: Changements non commités (providers.py, config.yaml, fichiers contexte).
- Next: Commit, tester avec clés API réelles (`--sweep` sur kimi et zai-glm). Vérifier si z.ai accepte le format OpenAI-compat standard ou nécessite des ajustements (headers, format body).

### 2026-04-28
- Done: `scripts/probe_providers.py` reçoit un flag `--sweep "v1,v2,v3"` qui boucle sur plusieurs `max_tokens` pour un seul modèle, affiche un tableau `max_tokens / content / reasoning / finish / diagnostic`, et détecte automatiquement le premier seuil utile (content non-vide + `finish ≠ length`).
- Done: README — section "Diagnosing providers" étoffée. Nouvelle table récap des 3 scripts (`probe_providers`, `consolidate_usage`, `refresh_pricing`). Table exhaustive des flags de probe (incluant `--prompt` et `--json` qui n'étaient pas documentés). Quatre workflows concrets : triage global, test ciblé deepseek, sweep kimi avec sortie type, raw JSON + jq. Cartographie des signaux étendue (HTTP 401/403, timeout). Lien depuis Troubleshooting "Réponse vide/tronquée" vers la commande sweep.
- Observé : test `--sweep` sur `deepseek-v4-flash` → HTTP 401 sur toutes les valeurs. Donc l'erreur deepseek que l'utilisateur avait rencontrée venait probablement d'une `DEEPSEEK_API_KEY` absente du `.env`, pas d'un souci de parser ou de `max_tokens`. Cas déjà couvert par l'anti-pattern « Clés API absentes sans feedback » (2026-04-21).
- Done: Refresh incident `pricing.json` (2688 entrées) en testant `refresh_pricing.py --help` — le script s'exécute directement sans flag, donc l'invoquer pour voir l'aide déclenche le download.
- Commits: `8c1463b` (feat probe + docs), `7496f6c` (chore pricing). Push master OK.
- Next: Quand l'utilisateur retombe sur l'erreur deepseek, lancer `--sweep` sur le vrai modèle pour confirmer que le seuil est bien un problème de clé API et non de budget tokens. Envisager `--help` propre pour `refresh_pricing.py` (early-exit avant le téléchargement).

### 2026-04-23
- Done: Parser OpenAI-compat refait (`providers._parse_openai_compat_response`) — distingue 4 modes d'échec : `truncated before content`, `truncated during reasoning`, `content_filter`, `empty response`. Lit `reasoning_content` (Zhipu/DeepSeek) ET `reasoning` (OpenRouter). Surface `finish_reason`.
- Done: Fix GPT-5 / o-series — helper `_max_tokens_param` détecte `gpt-5*`/`o1*`/`o3*`/`o4*` sur provider `openai` et envoie `max_completion_tokens` au lieu de `max_tokens` (HTTP 400 avant le fix).
- Done: Strip inline `<think>...</think>` via `_strip_inline_thinking` + `_postprocess_result` — phi-4 / QwQ / DeepSeek-R1 local remontent content propre. Troncature dans le bloc think détectée comme erreur dédiée.
- Done: Ollama remonte `done_reason` sous le nom `finish_reason` pour diagnostic unifié.
- Done: Cascade `max_tokens` : arg utilisateur > `model.default_max_tokens` > `settings.default_max_tokens` > 2000. Hardcodes 1000/1500 retirés. `challenge` expose maintenant un arg `max_tokens` optionnel.
- Done: MCP responses enrichies d'un champ `meta` (finish_reason, reasoning_len, inline_thinking_len) + flags dans le `summary` (`⚠ length`, `⚠ filter`, `• thinking=N`). `ask_all` ajoute `models_with_errors`.
- Done: `scripts/probe_providers.py` — envoie un prompt trivial à chaque modèle enabled, dumpe `message_keys`, `finish_reason`, longueurs content vs reasoning, usage. Outil principal de triage.
- Done: Circuit breaker en mémoire (`providers.CircuitBreaker`, défauts threshold=3 / cooldown=300s) intégré dans `query()`. Détecte content null/vide + erreurs HTTP. Statut exposé via `get_models`.
- Done: Journal append-only `~/.config/mcp/llm-sparring/usage.jsonl` — une ligne par requête (ts, session_id, tool, model, provider, tokens, cost, error, finish_reason, reasoning_len, inline_thinking_len, duration_ms).
- Done: `session_id` optionnel sur `ask_model`/`ask_all`/`challenge`. `get_usage(session_id=…)` agrège depuis le journal. Script `scripts/consolidate_usage.py` (modes `--session`, `--day`, `--by-session`, `--by-tool`, `--json`).
- Done: Fix latent — `ask_all` ne comptait le coût que des modèles Ollama (handlers cloud ne renvoyaient pas `cost`). Désormais cost recalculé par modèle via `estimate_request_cost`.
- Done: Template `/sparring` mis à jour — étape 0 génère `session_id` (`date +%Y%m%d-%H%M%S`), propagé à chaque appel, reporté dans le debrief.
- Done: `config.yaml` template documente `default_max_tokens` (par modèle + settings) et `circuit_breaker`.
- Observé au probe : zai-glm → 462 reasoning_tokens avant réponse visible. Qwen → 598. phi-4 local → `<think>` inline qui déborde à num_predict=200. Gemini 3 → ~190 tokens de thinking invisible.
- Commits: `5c4c160` (breaker + journal), `c92784a` (parser + probe + cascade). Push master OK.
- Next: Documenter les nouveaux outils dans README (monitoring/billing, probe, consolidate), suggérer des `default_max_tokens` réalistes par modèle dans la config utilisateur, envisager contrepoids pour les coûts des réponses en erreur (provider facture mais notre budget session ne l'enregistre pas — seul le JSONL l'a).

### 2026-04-21
- Done: Ajout `load_dotenv(Path(__file__).parent / ".env")` dans `server.py` avant l'import `providers` — le MCP lit désormais un `.env` à côté du binaire au lieu de dépendre de l'environnement hérité du process parent.
- Done: `python-dotenv>=1.0` promu en dep explicite dans `pyproject.toml`, `uv.lock` régénéré.
- Done: README §4 réécrit en trois options (A=`.env` recommandé, B=bloc `env` dans `~/.claude.json`, C=`~/.zshenv`). Warning explicite que `export` dans un terminal ne suffit pas. Troubleshooting « No models available » clarifié (vérifier `.env`, pas `echo $OPENAI_API_KEY` depuis un shell).
- Diagnostic posé: `status: "unavailable"` silencieux venait du fait que le MCP tournait avec `env: {}` dans `~/.claude.json` + clés jamais persistées (ni `.zshrc` ni `.env`). `providers.py:145` renvoie `None` sans feedback.
- Noté: repo **dev** (`/home/jbo/Wip/coding/mcp/llm-sparring/`) et repo **runtime** (`/home/jbo/.claude/mcp/llm-sparring/`) sont deux clones git distincts, pas des symlinks. Source de vérité = dev, `git pull` côté runtime pour propager.
- Next: commit, `git pull` + `uv sync` côté runtime, créer `.env` runtime (`chmod 600`), redémarrer Claude Code, valider `get_models()`.

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
