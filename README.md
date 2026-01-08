<p align="center">
  <img src="assets/logo.png" alt="SnackCache" width="200">
</p>

<h1 align="center">SnackCache</h1>

<p align="center">
  <strong>Semantic caching proxy for OpenAI and Anthropic APIs.</strong><br>
  Stop paying for the same answer twice.
</p>

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#configuration">Configuration</a>
</p>

---

## Overview

SnackCache **reduces your LLM API costs** by caching responses and returning them for similar queries. Unlike simple string matching, SnackCache uses **semantic similarity** - so "What is 2+2?" and "What's two plus two?" can hit the same cache.

```python
# One line change
client = OpenAI(base_url="http://localhost:8000/v1")
```

Works with existing SDKs. No code changes beyond the base URL.

### What matches

```
"What is 2+2?"              -> cached
"What's 2+2?"               -> cache hit (semantic match)
"What is two plus two?"     -> cache hit (semantic match)
"What is 2*2?"              -> cache miss (different meaning)
```

### Who this is for

- **Developers iterating locally** - Run similar prompts while debugging. Pay once.
- **Apps with varied user queries** - FAQ bots, support systems, internal tools.
- **CI/CD pipelines** - Test prompts with slight variations still hit cache.

---

## How It Works

```
Your App -> SnackCache -> OpenAI/Anthropic
               |
         [Embed prompt]
               |
         [Search for similar]
               |
         +-----+-----+
         |           |
    SIMILAR       NOT FOUND
   (return       (forward to API,
    cached)       cache response)
```

SnackCache uses a two-layer approach:

1. **Exact match** - Hash-based lookup for identical prompts (instant)
2. **Semantic match** - Embedding similarity search for similar prompts

The semantic layer uses `all-MiniLM-L6-v2` embeddings and FAISS for fast vector search. Default similarity threshold is 0.85 (configurable).

---

## Installation

```bash
pip install snackcache
```

This installs semantic caching dependencies (~100MB for the embedding model on first run).

For exact-match only (smaller install):

```bash
pip install snackcache
snackcache serve --no-semantic
```

---

## Usage

### Start the server

```bash
snackcache serve
```

```
🍿 SnackCache is running!

Semantic caching: enabled (threshold: 0.85)

OpenAI-compatible endpoint:
  POST http://localhost:8000/v1/chat/completions

Anthropic-compatible endpoint:
  POST http://localhost:8000/v1/messages
```

### Point your SDK at SnackCache

**OpenAI:**

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is 2+2?"}],
    temperature=0,
)

# Later, a similar query hits the cache:
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What's two plus two?"}],
    temperature=0,
)
# -> Returns cached response (semantic match)
```

**Anthropic:**

```python
import anthropic

client = anthropic.Anthropic(base_url="http://localhost:8000/v1")

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain quantum computing"}],
)
```

### Check your savings

```bash
snackcache stats
```

```
📊 SnackCache Statistics
========================================
Total Requests:     147
Cache Hit Rate:     72.0%
  Exact Hits:       89
  Semantic Hits:    17
Tokens Saved:       52,430
Cost Saved:         $1.24
----------------------------------------
Semantic Enabled:   True
Cache Size:         41
Index Size:         41
========================================
```

---

## Configuration

### CLI Options

```bash
snackcache serve [OPTIONS]

  --host, -H       Host to bind (default: 0.0.0.0)
  --port, -p       Port (default: 8000)
  --threshold, -t  Similarity threshold 0-1 (default: 0.85)
  --no-semantic    Disable semantic caching (exact match only)
  --redis, -r      Redis URL for persistent caching
  --verbose, -v    Verbose logging
```

### Tuning the threshold

- **0.95** - Very strict, only near-identical prompts match
- **0.85** - Default, good balance of hits vs accuracy
- **0.75** - Loose, more hits but risk of wrong matches

```bash
# Stricter matching
snackcache serve --threshold 0.95

# Looser matching
snackcache serve --threshold 0.75
```

### Environment Variables

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Limitations

- **Streaming responses** - forwarded but not cached
- **High temperature** - outputs won't cache well (non-deterministic)
- **Very long prompts** - embedding quality degrades for very long text

For best results, use `temperature=0` and keep prompts reasonably sized.

---

## How semantic matching works

1. When a new prompt comes in, we generate an embedding using `all-MiniLM-L6-v2`
2. We search the FAISS index for similar embeddings
3. If similarity >= threshold, we return the cached response
4. Otherwise, we forward to the API and cache the new response + embedding

The embedding model runs locally - no additional API calls.

---

## Contributing

PRs welcome! Feel free to open issues for bugs, feature requests, or questions.

---

## License

MIT

---

Built by [Snack AI](https://snackai.dev)
