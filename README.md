# Sparring

**Make your LLMs disagree.**

An MCP server that orchestrates sparring sessions between LLMs. Query multiple models, have them challenge each other, sharpen your ideas through friction.

## Features

- **Multi-provider**: OpenAI, Anthropic, Google, OpenRouter, Ollama, custom endpoints
- **Budget control**: Session, daily, and per-request limits with tracking
- **Simple primitives**: `ask_model`, `ask_all`, `challenge`, `get_models`, `get_lenses`, `get_usage`, `estimate_cost`
- **Challenge lenses**: 10 perspectives (devil_advocate, cynical_dev, security, cost, user, scale, simplicity, naive, pragmatist, steelman)
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
  max_tokens: 1000  # optional
)
```

### `ask_all`

Query all enabled models in parallel.

```
ask_all(
  question: "What database should I use for time-series data?",
  context: "IoT project with 10M events/day",  # optional
  max_tokens: 1000  # optional
)
```

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
  language: "fr"                   # optional: "fr" (default) or "en"
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
      "pricing": {"input": 2.50, "output": 10.00}
    },
    {
      "name": "llama-local",
      "provider": "ollama",
      "model_id": "llama3.2",
      "status": "available",
      "enabled": true,
      "pricing": {"input": 0, "output": 0}
    }
  ]
}
```

### `get_lenses`

List available challenge lenses with descriptions.

```
get_lenses()
```

Returns the 10 built-in lenses (`devil_advocate`, `steelman`, `pragmatist`, `cynical_dev`, `security`, `cost`, `user`, `scale`, `simplicity`, `naive`) plus the default and a note on passing `lens: null` for a natural critique without persona.

### `get_usage`

Get current budget usage.

```
get_usage()
```

```json
{
  "session": {"cost": 0.05, "requests": 3, "limit": 1.00, "remaining": 0.95},
  "daily": {"cost": 0.25, "requests": 12, "limit": 5.00, "remaining": 4.75},
  "monthly": {"cost": 3.50, "requests": 156}
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

  - name: "llama-local"
    provider: "ollama"
    model_id: "llama3.2"
    base_url: "http://localhost:11434"
    enabled: true
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
```

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

## Development

```bash
uv run server.py
LOG_LEVEL=DEBUG uv run server.py
```

## License

MIT
