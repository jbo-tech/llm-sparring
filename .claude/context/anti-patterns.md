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

### Reasoning model renvoie `content: null` avec 200 OK
**Problem**: Un provider (Zhipu GLM, DeepSeek R1, Qwen thinking, etc.) répond HTTP 200 avec usage facturé, mais `choices[0].message.content` est `null`. Le MCP remonte un `response: None` silencieux et l'orchestrateur le traite comme "réponse vide".
**Cause**: Les reasoning models mettent leur production dans un champ séparé — `reasoning_content` (Zhipu direct, DeepSeek) ou `reasoning` (OpenRouter, variantes). Si `max_tokens` est trop bas, tout le budget part en reasoning invisible et `finish_reason=length` arrive avant que `content` soit produit. Un parser qui lit seulement `message.content` jette la moitié des cas.
**Solution**: Dans le parser OpenAI-compat, lire `content`, `reasoning_content` ET `reasoning`. Surface `finish_reason` systématiquement. Distinguer 4 modes d'échec : `truncated before content` (length sans reasoning), `truncated during reasoning` (length + reasoning présent), `content_filter`, `empty response`. Diagnostiquer d'abord avec un script de probe qui dumpe le raw response (voir `scripts/probe_providers.py`).
**Date**: 2026-04-23

### Thinking tokens invisibles épuisent `max_tokens`
**Problem**: Un modèle retourne du contenu tronqué (`finish_reason: length`) bien avant d'atteindre la limite apparente — 50 chars de réponse pour `max_tokens=200`.
**Cause**: Les reasoning models modernes (Gemini 2.5/3, GPT-5, o-series, GLM-4.6, Qwen thinking) consomment 100-600 tokens en thinking invisible **avant** de produire du texte. Gemini 3 Flash : ~190 tokens silencieux sur un prompt trivial. Qwen : 600+. Un défaut statique de 1000-1500 tokens est fatal sur des tâches non triviales.
**Solution**: Cascade `max_tokens` par modèle : arg utilisateur > `model.default_max_tokens` (config) > `settings.default_max_tokens` > hard default (2000 min). Pour reasoning models, 4000-8000. Surface `reasoning_len` / `inline_thinking_len` dans la réponse MCP pour que l'orchestrateur détecte les modèles à relever.
**Date**: 2026-04-23

### GPT-5 / o-series rejettent `max_tokens`
**Problem**: Tous les appels à `gpt-5*`, `o1*`, `o3*` échouent en HTTP 400 avec `Unsupported parameter: 'max_tokens' is not supported with this model`. Le circuit breaker ouvre en cascade.
**Cause**: OpenAI a silencieusement migré les modèles reasoning vers `max_completion_tokens`. Les SDK clients génériques (httpx + dict) continuent d'envoyer l'ancien nom.
**Solution**: Détection par préfixe (`gpt-5`, `o1`, `o3`, `o4`) sur provider `openai` uniquement — OpenRouter normalise. Helper `_max_tokens_param(model_id, provider)` renvoie le bon nom. À chaque nouvelle famille de reasoning models chez un provider, vérifier si leur endpoint OpenAI-compat a aussi migré.
**Date**: 2026-04-23

### Reasoning model local expose `<think>` inline dans `content`
**Problem**: phi-4, QwQ, DeepSeek-R1 local (via Ollama) remontent leur raisonnement **dans `content`** sous forme de balises `<think>...</think>`. L'orchestrateur reçoit la réflexion brute et pas la réponse finale. Si `num_predict` est petit, le `</think>` n'arrive jamais.
**Cause**: Pas de champ `reasoning_content` côté Ollama — le contrat "content = réponse utilisateur" ne tient plus pour ces modèles. Un parser qui ne strip rien laisse passer la pensée.
**Solution**: `_strip_inline_thinking(content)` retire `^\s*<think>(.*?)</think>\s*` en tête. Si `<think>` sans fermeture → erreur `truncated during inline thinking`. Si `<think></think>` seul → erreur `empty final answer`. Expose `inline_thinking_len` pour signaler qu'il faut monter `max_tokens`.
**Date**: 2026-04-23

### Compta qui dépend d'un champ optionnel du handler
**Problem**: Les totaux `session_cost` / `daily_cost` d'`ask_all` sous-estiment la facture réelle. Les appels cloud semblent gratuits alors que les providers ont facturé.
**Cause**: Bug latent — `ask_all` additionnait `result["cost"]` mais seul le handler Ollama renvoyait ce champ (toujours 0). Les handlers cloud ne l'émettaient pas, leur coût n'était ni agrégé ni persisté.
**Solution**: Ne jamais dépendre d'un champ optionnel du handler pour la compta. Calculer le coût au niveau handler-consumer via `budget_manager.estimate_request_cost(...)` dans la boucle, toujours, même si le handler le fournit.
**Date**: 2026-04-23
