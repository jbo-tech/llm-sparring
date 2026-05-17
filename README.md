# Sparring

**Make your LLMs disagree.**

An MCP server that orchestrates sparring sessions between LLMs. Query multiple models, have them challenge each other, sharpen your ideas through friction.

## Features

- **Multi-provider**: OpenAI, Anthropic, Google, OpenRouter, Moonshot (Kimi), z.ai (GLM), Ollama, custom endpoints
- **Reasoning-model aware**: Parser unifié qui gère `reasoning_content`, `reasoning` (OpenRouter), `<think>` inline (phi-4, QwQ), `max_completion_tokens` (GPT-5 / o-series), `finish_reason` exposé au caller
- **Budget control**: Session, daily, per-request limits + journal append-only avec `session_id` pour consolider a posteriori (par modèle, par sparring)
- **Circuit breaker**: Désactive automatiquement un provider après N erreurs consécutives (content null, HTTP 5xx, timeout)
- **Simple primitives**: `ask_model`, `ask_all`, `challenge`, `get_models`, `get_lenses`, `get_usage`, `estimate_cost`
- **Challenge lenses**: 10 perspectives (devil_advocate, cynical_dev, security, cost, user, scale, simplicity, naive, pragmatist, steelman)
- **Diagnostic tooling**: `scripts/probe_providers.py` (raw response dump), `scripts/consolidate_usage.py` (agrégation JSONL)
- **Local-first**: Works with Ollama for free local inference

## Installation

### 1. Clone/Copy

```bash
mkdir -p ~/.claude/mcp/llm-sparring
cp -r . ~/.claude/mcp/llm-sparring/

# Or clone from git
# git clone https://github.com/you/llm-sparring ~/.claude/mcp/llm-sparring
```

### 2. Dependencies

```bash
cd ~/.claude/mcp/llm-sparring
uv sync
```

`uv` gère l'installation de Python 3.11 si besoin, crée `.venv/` et installe les deps depuis `uv.lock`. [Installer uv](https://docs.astral.sh/uv/getting-started/installation/) si absent.

### 3. Configure models

```bash
mkdir -p ~/.config/mcp/llm-sparring
cp config.yaml ~/.config/mcp/llm-sparring/config.yaml
nano ~/.config/mcp/llm-sparring/config.yaml
```

### 4. Set API keys

Trois options, par ordre de préférence :

**A. Fichier `.env` dans le dossier du serveur (recommandé)**

Le serveur charge automatiquement `~/.claude/mcp/llm-sparring/.env` au démarrage.
Les clés restent scopées au MCP, ne polluent pas l'environnement global, et ne
dépendent pas du shell qui lance Claude Code.

```bash
cat > ~/.claude/mcp/llm-sparring/.env <<'EOF'
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
OPENROUTER_API_KEY=sk-or-...
# MISTRAL_API_KEY=...
# DEEPSEEK_API_KEY=...
# GROQ_API_KEY=...
# XAI_API_KEY=...
# MOONSHOT_API_KEY=...
# ZAI_API_KEY=...
# ANTHROPIC_API_KEY=...   # rarement utile (on EST Claude)
EOF
chmod 600 ~/.claude/mcp/llm-sparring/.env
```

`.env` est déjà listé dans `.gitignore`.

**B. Bloc `env` de la config MCP** — voir l'étape 5 ci-dessous. Clés en clair dans `~/.claude.json`.

**C. Variables d'environnement globales** (via `~/.zshenv` de préférence, pas `~/.zshrc` qui n'est pas lu par les shells non-interactifs).

```bash
# ~/.zshenv
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="..."
export OPENROUTER_API_KEY="sk-or-..."
```

> ⚠️ Un simple `export` dans un terminal ouvert ne suffit pas : Claude Code
> doit être relancé depuis un shell qui a ces variables dans son environnement.

### 5. Add to Claude Code

**For Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "sparring": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/YOU/.claude/mcp/llm-sparring",
        "run",
        "server.py"
      ],
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "GOOGLE_API_KEY": "...",
        "OPENROUTER_API_KEY": "sk-or-..."
      }
    }
  }
}
```

**For Claude Code CLI**:

```bash
claude mcp add sparring -- uv --directory ~/.claude/mcp/llm-sparring run server.py
```

## Tools

### `ask_model`

Query a specific model.

```
ask_model(
  model: "gpt-4o",
  question: "What are the pros/cons of microservices?",
  context: "Building a SaaS product",  # optional
  max_tokens: 1000,                    # optional — voir cascade ci-dessous
  session_id: "20260423-143012"        # optional — pour regrouper la facturation
)
```

`max_tokens` (cascade, du plus fort au plus faible) : arg explicite > `model.default_max_tokens` (config) > `settings.default_max_tokens` > 2000. Raise pour reasoning models (Gemini 3, Qwen, GLM, o-series, phi-4 local).

### `ask_all`

Query all enabled models in parallel. Chaque modèle applique sa propre cascade `max_tokens`.

```
ask_all(
  question: "What database should I use for time-series data?",
  context: "IoT project with 10M events/day",  # optional
  max_tokens: 1000,                            # optional — override uniforme
  session_id: "20260423-143012"                # optional
)
```

Retourne un `meta` par modèle avec `finish_reason`, `reasoning_len`, `inline_thinking_len` quand pertinent + un `models_with_errors` au niveau top pour l'orchestrateur.

### `challenge`

Have one model critique a response (from another model, a file, a snippet — any text).
This is the heart of sparring.

```
challenge(
  challenger_model: "gemini-flash",
  original_question: "Best database for time-series?",
  target_response: "PostgreSQL with TimescaleDB because...",
  target_source: "gpt-4o",         # optional: model name, file name, etc.
  lens: "devil_advocate",          # optional: see get_lenses. null = natural critique
  language: "fr",                  # optional: "fr" (default) or "en"
  max_tokens: 2000,                # optional — même cascade que ask_model
  session_id: "20260423-143012"    # optional
)
```

### `get_models`

List all configured models with their status and pricing.

```
get_models()
```

```json
{
  "models": [
    {
      "name": "gpt-4o",
      "provider": "openai",
      "model_id": "gpt-4o",
      "status": "available",
      "enabled": true,
      "pricing": {"input": 2.50, "output": 10.00},
      "breaker": {"errors": 0, "disabled": false}
    },
    {
      "name": "or-zai-glm",
      "provider": "openrouter",
      "model_id": "z-ai/glm-4.6",
      "status": "available",
      "enabled": true,
      "pricing": {"input": 0.5, "output": 2.0},
      "breaker": {
        "errors": 3,
        "disabled": true,
        "disabled_until": 1745421012.5,
        "last_error": "truncated during reasoning (finish=length, reasoning_len=693)"
      }
    }
  ]
}
```

Le champ `breaker` reflète l'état du circuit breaker : `disabled: true` signifie que le modèle a échoué ≥ `threshold` fois consécutivement et est mis au frigo jusqu'à `disabled_until`.

### `get_lenses`

List available challenge lenses with descriptions.

```
get_lenses()
```

Returns the 10 built-in lenses (`devil_advocate`, `steelman`, `pragmatist`, `cynical_dev`, `security`, `cost`, `user`, `scale`, `simplicity`, `naive`) plus the default and a note on passing `lens: null` for a natural critique without persona.

### `get_usage`

Get current budget usage. Sans arg : totaux session (in-memory) / daily / monthly. Avec `session_id` : breakdown par modèle agrégé depuis le journal JSONL.

```
get_usage()
get_usage(session_id: "20260423-143012")
```

```json
{
  "session": {"cost": 0.05, "requests": 3, "limit": 1.00, "remaining": 0.95},
  "daily": {"cost": 0.25, "requests": 12, "limit": 5.00, "remaining": 4.75},
  "monthly": {"cost": 3.50, "requests": 156},
  "sparring_session": {
    "session_id": "20260423-143012",
    "total_cost": 0.0172,
    "requests": 3,
    "errors": 1,
    "by_model": {
      "gpt-4o":   {"cost": 0.017,  "requests": 2, "errors": 0, "input_tokens": 400, "output_tokens": 600},
      "or-zai-glm": {"cost": 0.0002, "requests": 1, "errors": 1, "input_tokens": 100, "output_tokens": 0}
    }
  }
}
```

### `estimate_cost`

Estimate cost before making requests.

```
estimate_cost(
  models: ["gpt-4o", "gemini-flash", "llama-local"],
  input_tokens: 500,
  output_tokens: 1000
)
```

## Configuration

### Models

```yaml
models:
  - name: "gpt-4o"
    provider: "openai"
    model_id: "gpt-4o"
    enabled: true

  - name: "or-zai-glm"
    provider: "openrouter"
    model_id: "z-ai/glm-4.6"
    default_max_tokens: 4000   # reasoning model — besoin de marge pour thinking
    enabled: true

  - name: "llama-local"
    provider: "ollama"
    model_id: "llama3.2"
    base_url: "http://localhost:11434"
    enabled: true
```

**`default_max_tokens`** (optionnel) — budget tokens par défaut pour ce modèle. À relever pour les reasoning models qui consomment 100-600 tokens invisibles en thinking avant de produire du texte :

| Modèle | Suggéré | Pourquoi |
|--------|---------|----------|
| Gemini 2.5/3 Flash/Pro | 6000 | ~190 tokens thinking invisible même sur prompt trivial |
| GPT-5 / o-series | 4000 | reasoning_tokens comptés dans completion_tokens |
| GLM-4.6 / Qwen thinking | 4000 | 200-600 reasoning tokens avant réponse |
| phi-4 / QwQ / DeepSeek-R1 local | 8000 | `<think>` inline exposé dans content |
| Modèles standards (gpt-4o, mistral, claude) | — (fallback settings) | pas de thinking invisible |

### Settings

```yaml
settings:
  default_timeout: 30          # secondes
  max_parallel: 3              # concurrence ask_all
  default_max_tokens: 2000     # fallback global — voir cascade plus haut

  circuit_breaker:             # optionnel, défauts indiqués
    threshold: 3               # erreurs consécutives avant désactivation
    cooldown_seconds: 300      # durée de mise au frigo
```

### Providers

| Provider | Env Var | Type | Notes |
|----------|---------|------|-------|
| `openai` | `OPENAI_API_KEY` | OpenAI-compat | GPT-4, GPT-4o |
| `anthropic` | `ANTHROPIC_API_KEY` | OpenAI-compat | Claude (endpoint beta, **no prompt caching**) |
| `google` | `GOOGLE_API_KEY` | OpenAI-compat | Gemini (endpoint beta) |
| `openrouter` | `OPENROUTER_API_KEY` | OpenAI-compat | **Recommended**: 400+ models |
| `mistral` | `MISTRAL_API_KEY` | OpenAI-compat | Mistral Large, Small |
| `deepseek` | `DEEPSEEK_API_KEY` | OpenAI-compat | DeepSeek Chat, Reasoner |
| `groq` | `GROQ_API_KEY` | OpenAI-compat | Very fast inference |
| `together` | `TOGETHER_API_KEY` | OpenAI-compat | Open source models |
| `xai` | `XAI_API_KEY` | OpenAI-compat | Grok |
| `moonshot` | `MOONSHOT_API_KEY` | OpenAI-compat | Kimi |
| `zai` | `ZAI_API_KEY` | OpenAI-compat | GLM (z.ai) |
| `custom` | Custom | OpenAI-compat | Any compatible endpoint |
| `ollama` | — | Ollama | Local models, free (dedicated handler) |

Adding an OpenAI-compatible provider in `providers.py`:

```python
"newprovider": {
    "type": "openai_compatible",
    "base_url": "https://api.newprovider.com/v1",
    "api_key_env": "NEWPROVIDER_API_KEY",
},
```

### Budget

```yaml
budget:
  confirm_threshold: 0.10  # Confirm if request > $0.10
  session_limit: 1.00      # Max per session
  daily_limit: 5.00        # Max per day
  tracking_file: "~/.config/mcp/llm-sparring/usage.json"
  journal_file: "~/.config/mcp/llm-sparring/usage.jsonl"  # optionnel, défaut à côté de tracking_file
```

Deux fichiers sont maintenus en parallèle :

- **`usage.json`** — totaux agrégés par session (in-memory), jour, mois. Source pour les checks de budget en temps réel.
- **`usage.jsonl`** — journal append-only, une ligne par requête : `ts`, `session_id`, `tool`, `model`, `provider`, `input_tokens`, `output_tokens`, `cost`, `error`, `finish_reason`, `reasoning_len`, `inline_thinking_len`, `duration_ms`. Source de vérité pour l'audit rétro et la consolidation par session.

### Pricing

Pricing data comes from `pricing.json` (~2600 modèles, vendored depuis [LiteLLM](https://github.com/BerriAI/litellm)).
Résolution en cascade : override `config.yaml` → lookup exact → `{provider}/{model_id}` → règle locale (ollama/localhost → 0) → fallback conservateur avec warning.

Refresh trimestriel recommandé :

```bash
uv run scripts/refresh_pricing.py
```

Override pour un modèle absent du JSON ou pour forcer un tarif, dans `config.yaml` :

```yaml
pricing:
  my-custom-model:
    input: 0.50    # per 1M tokens
    output: 1.50
```

## Monitoring & billing

### Agrégation par session

L'orchestrateur (`/sparring`) génère un `session_id` unique par sparring et le propage à chaque appel d'outil. Deux moyens de consolider :

**Depuis Claude Code (in-line)** :
```
get_usage(session_id: "20260423-143012")
```
→ retourne `sparring_session.by_model` avec coût, erreurs, tokens par modèle.

**Hors-ligne (script)** :
```bash
# Détail d'une session
uv run scripts/consolidate_usage.py --session 20260423-143012

# Top sessions de la journée par coût
uv run scripts/consolidate_usage.py --day 2026-04-23 --by-session

# Breakdown par outil (ask_model / ask_all / challenge)
uv run scripts/consolidate_usage.py --by-tool

# Dump JSON pour traitement externe
uv run scripts/consolidate_usage.py --json | jq '.by_model'
```

Par défaut, lit `~/.config/mcp/llm-sparring/usage.jsonl` ; `--file <path>` pour un autre chemin.

## Scripts

Trois utilitaires CLI dans `scripts/`, tous lancés via `uv run` :

| Script | Rôle | Quand l'utiliser |
|--------|------|------------------|
| `probe_providers.py` | Envoie un prompt trivial à un ou tous les modèles, dumpe le raw HTTP | Modèle qui renvoie vide, tronqué, erreur, ou `circuit breaker open` |
| `consolidate_usage.py` | Agrège `usage.jsonl` par session / jour / modèle / outil | Audit rétro d'un sparring, top sessions par coût |
| `refresh_pricing.py` | Re-télécharge `pricing.json` depuis LiteLLM | Trimestriel, ou modèle absent du JSON |

## Diagnosing providers

Un modèle qui renvoie systématiquement vide, tronqué ou "circuit breaker open" ? `scripts/probe_providers.py` envoie un prompt trivial et dumpe la réponse HTTP brute du provider — sans passer par le parser interne, donc sans masquer où disparaît le contenu.

### Flags

| Flag | Défaut | Effet |
|------|--------|-------|
| `--model <name>` | tous les `enabled` | Ne tester qu'un seul modèle (nom logique de `config.yaml`) |
| `--prompt "..."` | `"Dis bonjour en une phrase."` | Prompt custom (utile pour tester un cas qui a échoué en prod) |
| `--max-tokens <N>` | `200` | Budget tokens pour la requête |
| `--sweep "500,1000,2000,4000"` | — | Boucle sur plusieurs `max_tokens` pour identifier le seuil utile. Requiert `--model`. |
| `--json` | tableau humain | Dump JSON brut (raw par modèle) pour analyse externe |

### Workflows

**1. Triage global** — tous les modèles enabled, format humain :

```bash
uv run scripts/probe_providers.py
```

**2. Tester un modèle spécifique** — ex. après une erreur deepseek :

```bash
uv run scripts/probe_providers.py --model deepseek-v4-flash
uv run scripts/probe_providers.py --model deepseek-v4-flash --max-tokens 4000
uv run scripts/probe_providers.py --model deepseek-v4-flash --prompt "<le prompt qui a foiré>"
```

Lire la ligne `Diagnostic` puis le bloc `Détails` : `content_len`, `reasoning_len`, `finish_reason`, `message_keys` indiquent où est passé le texte. Un `HTTP 401` sur toutes les valeurs signifie que la clé API du provider n'est pas chargée — vérifier `.env`.

**3. Trouver le `max_tokens` minimum utile** — ex. pour kimi qui retourne `null` :

```bash
uv run scripts/probe_providers.py --model or-kimi-k2 --sweep 500,1000,2000,4000,8000
```

Sortie type :

```
max_tokens  content  reasoning  finish          diagnostic
   500          0        487    length          ⚠️  content vide MAIS reasoning_content présent (487 chars) — thinking model
  1000          0        923    length          ⚠️  tronqué avant tout content (finish=length) — augmenter max_tokens
  2000         42       1450    stop            OK — 42 chars (finish=stop)
  4000        180       1502    stop            OK — 180 chars (finish=stop)
  8000        180       1502    stop            OK — 180 chars (finish=stop)

→ Seuil utile détecté : 2000 (premier max_tokens avec content non-vide et non tronqué)
```

Ensuite, propager le seuil dans `~/.config/mcp/llm-sparring/config.yaml` :

```yaml
- name: "or-kimi-k2"
  provider: "openrouter"
  model_id: "moonshotai/kimi-k2"
  default_max_tokens: 2000   # ou 4000 pour marge de sécurité
  enabled: true
```

**4. Raw JSON pour analyse fine** — utile quand le format est inconnu :

```bash
uv run scripts/probe_providers.py --model <name> --json | jq '.[0].raw.choices[0].message | keys'
```

### Cartographie des signaux

| Symptôme | Colonne à vérifier | Action |
|----------|-------------------|--------|
| `content_len=0` + `reasoning_len>0` | reasoning-only response | Monter `default_max_tokens` pour ce modèle (sweep recommandé) |
| `finish_reason=length` + `content_len<50` | thinking tokens épuisent le budget | Idem — sweep `2000,4000,8000` |
| `finish_reason=content_filter` | modération provider | Reformuler le prompt |
| `HTTP 400 max_tokens unsupported` | GPT-5 / o-series | Déjà géré automatiquement (helper `_max_tokens_param`) |
| `<think>` dans `content_preview` | reasoning model local | Strip automatique, vérifier qu'il y a un `</think>` |
| `HTTP 401/403` | clé API absente ou invalide | Vérifier `.env` ou bloc `env` MCP |
| `ERREUR: TimeoutException` | endpoint lent / surchargé | Augmenter `settings.default_timeout` |

## Usage with /sparring

This MCP is designed to work with a `/sparring` command in Claude Code:

```
/sparring Should I use microservices or monolith for my startup?

→ Claude orchestrates:
  1. Framing with you
  2. ask_all() to gather perspectives
  3. challenge() to have models critique each other
  4. Synthesis and recommendation
```

## Testing

### 1. Verify the server starts

```bash
cd ~/.claude/mcp/llm-sparring
uv run server.py
# Ctrl+C to stop
```

In debug mode for more details:

```bash
LOG_LEVEL=DEBUG uv run server.py
```

### 2. Check model configuration

In Claude Code, run:

```
get_models()
```

Verify that your enabled models appear with `status: "available"`.

### 3. Test a single model

```
ask_model(model: "gpt-4o", question: "Say hello in one word")
```

Start with a cheap/fast model (e.g. `gpt-4o-mini`, `gemini-flash`, or a local Ollama model).

### 4. Test parallel queries

```
ask_all(question: "What is 2+2?")
```

All enabled models should respond.

### 5. Test challenge

```
challenge(
  challenger_model: "gemini-flash",
  original_question: "What is the best programming language?",
  target_response: "Python because it's simple",
  target_source: "gpt-4o",
  lens: "devil_advocate"
)
```

### 6. Check budget tracking

```
get_usage()
```

Verify that session and daily costs reflect your test queries.

### 7. Test with /sparring

```
/sparring Should I use SQLite or PostgreSQL for a side project?
```

This runs the full orchestration flow (framing, ask_all, challenge, synthesis).

## Troubleshooting

### "No models available" / `status: "unavailable"`

- Vérifier que le serveur voit bien les clés : `cat ~/.claude/mcp/llm-sparring/.env`
  (option A) ou le bloc `env` dans `~/.claude.json` (option B).
- `echo $OPENAI_API_KEY` dans un terminal ne prouve rien : le MCP tourne dans un
  sous-processus lancé par Claude Code, pas dans ton shell.
- Check config: `cat ~/.config/mcp/llm-sparring/config.yaml`
- At least one model must be `enabled: true`
- Après modif du `.env` ou de `~/.claude.json`, redémarrer Claude Code.

### "Timeout querying model"

- Increase `default_timeout` in config
- For Ollama: `ollama serve`
- Local models need time to load on first query

### "Budget exceeded"

- Check with `get_usage`
- Adjust limits in config
- Wait for daily reset (midnight)

### Réponse vide, tronquée, ou `circuit breaker open`

Trois causes fréquentes sur les reasoning models (Gemini 3, GPT-5, o-series, GLM, Qwen thinking, phi-4 local) :

1. **`max_tokens` trop bas** — les thinking tokens invisibles consomment le budget avant que le modèle ne produise du texte. Pour trouver le seuil utile : `uv run scripts/probe_providers.py --model <name> --sweep 500,1000,2000,4000,8000` (voir section "Diagnosing providers"). Puis relever `default_max_tokens` pour ce modèle dans `config.yaml`.
2. **Champ reasoning mal routé** — Zhipu met la réponse dans `reasoning_content`, OpenRouter dans `reasoning`, phi-4 local dans `<think>` inline. Le parser gère les trois automatiquement ; si ça casse, lancer `scripts/probe_providers.py --model <name> --json` pour confirmer le format.
3. **Circuit breaker ouvert** — après 3 erreurs consécutives le modèle est mis au frigo 5 min. Vérifier `get_models()` → champ `breaker`. Le compteur se remet à zéro au premier succès ou au redémarrage du serveur.

## Development

```bash
uv run server.py
LOG_LEVEL=DEBUG uv run server.py
```

## License

MIT
