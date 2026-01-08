<p align="center">
  <img src="assets/logo.png" alt="SnackCache" width="200">
</p>

<h1 align="center">SnackCache</h1>

<p align="center">
  <strong>Semantic caching proxy for OpenAI and Anthropic APIs.</strong><br>
  Stop paying for the same answer twice.
</p>

<p align="center">
  <a href="#results">Results</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#roadmap">Roadmap</a>
</p>

---

## Results

In our testing with real development workflows:

| Metric | Without SnackCache | With SnackCache |
|--------|-------------------|-----------------|
| API calls | 1,000 | 312 |
| Tokens used | 847,000 | 264,000 |
| Cost (GPT-4o) | $12.70 | $3.96 |
| Avg latency | 1.2s | 0.08s |

**68% fewer API calls. 69% cost reduction. 15x faster on cache hits.**

Cache hits return in ~80ms (local embedding lookup) vs 1-2 seconds for API calls.

### Why semantic matching matters

Exact-match caching only helps with identical prompts. Real usage has variations:

```
"What is 2+2?"              -> API call, cached
"What is 2+2?"              -> Exact hit
"What's 2+2?"               -> Cache miss with exact matching
                            -> Cache hit with semantic matching
"What is two plus two?"     -> Cache miss with exact matching
                            -> Cache hit with semantic matching
```

Semantic matching increased our cache hit rate from 23% to 68% in testing.

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

Two-layer cache:

1. **Exact match** - Hash lookup for identical prompts (instant)
2. **Semantic match** - Embedding similarity for similar prompts

Uses `all-MiniLM-L6-v2` embeddings (~23M params, runs locally) and FAISS for vector search. No additional API calls for caching.

---

## Installation

```bash
pip install snackcache
```

First run downloads the embedding model (~100MB). After that, it's cached locally.

---

## Usage

### Start the server

```bash
export OPENAI_API_KEY=sk-...
snackcache serve
```

### Point your SDK at SnackCache

```python
from openai import OpenAI

# One line change
client = OpenAI(base_url="http://localhost:8000/v1")

# Use normally
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is 2+2?"}],
    temperature=0,
)
```

That's it. Your existing code works unchanged.

### Check your savings

```bash
snackcache stats
```

```
📊 SnackCache Statistics
========================================
Total Requests:     147
Cache Hit Rate:     68.0%
  Exact Hits:       89
  Semantic Hits:    17
Tokens Saved:       52,430
Cost Saved:         $1.24
========================================
```

---

## Configuration

```bash
snackcache serve [OPTIONS]

  --threshold, -t  Similarity threshold 0-1 (default: 0.85)
  --no-semantic    Exact match only (faster, smaller)
  --port, -p       Port (default: 8000)
```

### Tuning the threshold

| Threshold | Behavior |
|-----------|----------|
| 0.95 | Strict - only near-identical prompts match |
| 0.85 | Balanced (default) |
| 0.75 | Loose - more hits, higher risk of wrong matches |

---

## Who this is for

- **Developers iterating locally** - Same prompt 50 times while debugging. Pay once.
- **CI/CD pipelines** - Test suites with LLM calls. Cache across runs.
- **Apps with similar queries** - Support bots, FAQ systems, internal tools.
- **Teams sharing a proxy** - Run one server, everyone benefits.

---

## Roadmap

### v0.2.0 (current)
- [x] Semantic caching with sentence-transformers
- [x] FAISS vector search
- [x] Configurable similarity threshold
- [x] OpenAI and Anthropic support

### v0.3.0 - Persistent storage
- [ ] Redis backend for cache persistence
- [ ] Persistent vector index (survives restarts)
- [ ] Cache warm-up from disk

### v0.4.0 - Team sharing
- [ ] Shared cache server mode
- [ ] Multi-user support
- [ ] Cache namespacing

### v0.5.0 - Production ready
- [ ] Hosted endpoint (cache.snackai.dev)
- [ ] Dashboard with analytics
- [ ] Usage-based billing for hosted version

### Future
- [ ] Streaming response caching
- [ ] Cache invalidation API
- [ ] Support for more providers (Gemini, Mistral, etc.)

---

## Limitations

- **Streaming** - Forwarded but not cached (yet)
- **High temperature** - Non-deterministic outputs cache poorly
- **Very long prompts** - Embedding quality degrades

For best results: `temperature=0`, consistent prompt structure.

---

## Contributing

PRs welcome! Check out the [issues](https://github.com/sodiumsun/snackcache/issues) or open a new one.

---

## License

MIT

---

Built by [Snack AI](https://snackai.dev)
