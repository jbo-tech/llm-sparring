# Sparring

**Make your LLMs disagree.**

An MCP server that orchestrates sparring sessions between LLMs. Query multiple models, have them challenge each other, sharpen your ideas through friction.

## Features

- **Multi-provider**: OpenAI, Anthropic, Google, OpenRouter, Ollama, custom endpoints
- **Budget control**: Session, daily, and per-request limits with tracking
- **Simple primitives**: `ask_model`, `ask_all`, `challenge`, `get_models`, `get_usage`
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
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure models

```bash
mkdir -p ~/.config/mcp/llm-sparring
cp config.yaml ~/.config/mcp/llm-sparring/config.yaml
nano ~/.config/mcp/llm-sparring/config.yaml
```

### 4. Set API keys

```bash
# Add to ~/.zshrc or ~/.bashrc

# Core providers
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="..."

# Recommended: OpenRouter gives access to 400+ models
export OPENROUTER_API_KEY="sk-or-..."

# Additional providers (optional)
export MISTRAL_API_KEY="..."
export DEEPSEEK_API_KEY="..."
export GROQ_API_KEY="..."
export XAI_API_KEY="..."

# Usually not needed (we ARE Claude)
# export ANTHROPIC_API_KEY="..."
```

### 5. Add to Claude Code

**For Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "sparring": {
      "command": "/Users/YOU/.claude/mcp/llm-sparring/.venv/bin/python",
      "args": ["/Users/YOU/.claude/mcp/llm-sparring/server.py"],
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
claude mcp add sparring ~/.claude/mcp/llm-sparring/.venv/bin/python ~/.claude/mcp/llm-sparring/server.py
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

Have one model critique another's response. This is the heart of sparring.

```
challenge(
  challenger_model: "gemini-flash",
  original_question: "Best database for time-series?",
  target_response: "PostgreSQL with TimescaleDB because...",
  target_model: "gpt-4o"  # optional, for context
)
```

### `get_models`

List all configured models with their status.

```
get_models()
```

```json
{
  "models": [
    {"name": "gpt-4o", "status": "available", "pricing": {"input": 2.50, "output": 10.00}},
    {"name": "llama-local", "status": "available", "pricing": {"input": 0, "output": 0}},
    {"name": "claude-haiku", "status": "unavailable", "enabled": false}
  ]
}
```

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
| `openrouter` | `OPENROUTER_API_KEY` | OpenAI-compat | **Recommended**: 400+ models |
| `mistral` | `MISTRAL_API_KEY` | OpenAI-compat | Mistral Large, Small |
| `deepseek` | `DEEPSEEK_API_KEY` | OpenAI-compat | DeepSeek Chat, Reasoner |
| `groq` | `GROQ_API_KEY` | OpenAI-compat | Very fast inference |
| `together` | `TOGETHER_API_KEY` | OpenAI-compat | Open source models |
| `xai` | `XAI_API_KEY` | OpenAI-compat | Grok |
| `ollama` | — | Ollama | Local models, free |
| `anthropic` | `ANTHROPIC_API_KEY` | Custom | Claude |
| `google` | `GOOGLE_API_KEY` | Custom | Gemini |
| `custom` | Custom | OpenAI-compat | Any compatible endpoint |

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
source .venv/bin/activate
python server.py
# Ctrl+C to stop
```

In debug mode for more details:

```bash
LOG_LEVEL=DEBUG python server.py
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
  target_model: "gpt-4o"
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

### "No models available"

- Check API keys: `echo $OPENAI_API_KEY`
- Check config: `cat ~/.config/mcp/llm-sparring/config.yaml`
- At least one model must be `enabled: true`

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
python server.py
LOG_LEVEL=DEBUG python server.py
```

## License

MIT
