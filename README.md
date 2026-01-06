<p align="center">
  <img src="assets/logo.png" alt="SnackCache" width="200">
</p>

<h1 align="center">SnackCache</h1>

<p align="center">
  <strong>Drop-in caching proxy for OpenAI and Anthropic APIs.</strong><br>
  Stop paying for the same answer twice.
</p>

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#roadmap">Roadmap</a>
</p>

---

## Overview

SnackCache **reduces your LLM API costs** by caching responses locally. Repeated prompts return instantly - no API call, no charge.

It also **saves ~11% on tokens** by normalizing prompts before sending them upstream (collapsing whitespace, standardizing formatting).

```python
# One line change
client = OpenAI(base_url="http://localhost:8000/v1")
```

Works with existing SDKs. No code changes beyond the base URL.

### Who this is for

- **Developers iterating locally** - Run the same prompt 50 times while debugging. Pay once.
- **Apps with repeated queries** - Customer support bots, FAQ systems, internal tools.
- **CI/CD pipelines** - Same test prompts every build. Cache them.
- **Teams sharing a proxy** - Everyone benefits from the same cache.

---

## How It Works

```
Your App -> SnackCache -> OpenAI/Anthropic
               |
         [Normalize prompt]
               |
         [Check cache]
               |
         +-----+-----+
         |           |
       HIT         MISS
    (instant,     (forward to API,
     free)        cache response)
```

### Prompt Normalization

SnackCache normalizes prompts before caching, which means **different formatting still hits the same cache**:

```
"What is 2+2?"       -> cache key: 8c21c2ea...
"What is 2+2? "      -> cache key: 8c21c2ea...  same (trailing space)
"What is  2+2?"      -> cache key: 8c21c2ea...  same (double space)
"What is 2+2?\n"     -> cache key: 8c21c2ea...  same (newline)
```

This also reduces token counts on every request - fewer tokens sent upstream, lower costs even on cache misses.

---

## Installation

```bash
pip install snackcache
```

For Redis support (persistent caching across restarts):

```bash
pip install snackcache[redis]
```

---

## Usage

### Start the server

```bash
snackcache serve
```

```
🍿 SnackCache is running!

OpenAI-compatible endpoint:
  POST http://localhost:8000/v1/chat/completions

Anthropic-compatible endpoint:
  POST http://localhost:8000/v1/messages

Stats:
  GET  http://localhost:8000/stats
```

### Point your SDK at SnackCache

**OpenAI:**

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
    temperature=0,  # Deterministic responses cache better
)
```

**Anthropic:**

```python
import anthropic

client = anthropic.Anthropic(base_url="http://localhost:8000/v1")

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}],
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
Cache Hit Rate:     68.0%
Tokens Saved:       45,230
Cost Saved:         $0.89
========================================
```

---

## Configuration

### Environment Variables

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### CLI Options

```bash
snackcache serve [OPTIONS]

  --host, -H     Host to bind (default: 0.0.0.0)
  --port, -p     Port (default: 8000)
  --redis, -r    Redis URL for persistent caching
  --reload       Auto-reload for development
  --verbose, -v  Verbose logging
```

### Persistent Caching with Redis

```bash
snackcache serve --redis redis://localhost:6379
```

---

## Limitations

- **Streaming responses** - forwarded but not cached
- **High temperature** - outputs won't cache well (non-deterministic)
- **Unique long conversations** - won't benefit from caching

For best results, use `temperature=0` and structure prompts consistently.

---

## Roadmap

- [ ] Streaming response caching
- [ ] Request deduplication
- [ ] Semantic caching (similar prompts, not just identical)

---

## Contributing

PRs welcome! Feel free to open issues for bugs, feature requests, or questions.

---

## License

MIT

---

Built by [Snack AI](https://snackai.dev)

Feedback? hello@snackai.dev
