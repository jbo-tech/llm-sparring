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
