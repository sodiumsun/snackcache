"""
SnackCache - Caching proxy for LLM APIs.
"""

from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from .cache import get_cache
from .normalizer import normalize_request, generate_cache_key, get_normalizer_stats
from .proxy import get_proxy


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "=" * 50)
    print("🍿 SnackCache is running!")
    print("=" * 50)
    print(f"\nOpenAI-compatible endpoint:")
    print(f"  POST http://localhost:8000/v1/chat/completions")
    print(f"\nAnthropic-compatible endpoint:")
    print(f"  POST http://localhost:8000/v1/messages")
    print(f"\nStats:")
    print(f"  GET  http://localhost:8000/stats")
    print(f"\n" + "=" * 50 + "\n")
    yield
    proxy = get_proxy()
    await proxy.close()


app = FastAPI(
    title="SnackCache",
    description="Caching proxy for LLM APIs",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def format_cost(usd: float) -> str:
    if usd < 0.01:
        return f"${usd:.4f}"
    return f"${usd:.2f}"


def log_request(cache_hit: bool, cache_key: str, model: str, stats: Dict[str, Any]):
    status = "✅ CACHE HIT" if cache_hit else "🔄 CACHE MISS"
    hit_rate = stats.get("hit_rate", 0) * 100
    saved = format_cost(stats.get("total_cost_saved_usd", 0))
    print(f"{status} | {model} | key={cache_key[:8]}... | hit_rate={hit_rate:.1f}% | saved={saved}")


@app.get("/")
async def root():
    return {
        "service": "snackcache",
        "status": "running",
        "version": "0.1.0",
        "endpoints": {
            "openai": "/v1/chat/completions",
            "anthropic": "/v1/messages",
            "stats": "/stats",
        }
    }


@app.get("/stats")
async def get_stats():
    cache = get_cache()
    cache_stats = cache.get_stats()
    normalizer_stats = get_normalizer_stats()
    
    return {
        "cache": cache_stats,
        "normalization": normalizer_stats,
        "summary": {
            "total_requests": cache_stats["total_requests"],
            "cache_hit_rate": f"{cache_stats['hit_rate'] * 100:.1f}%",
            "tokens_saved": cache_stats["total_tokens_saved"],
            "cost_saved": format_cost(cache_stats["total_cost_saved_usd"]),
        }
    }


@app.post("/stats/reset")
async def reset_stats():
    cache = get_cache()
    cache.clear()
    return {"status": "reset"}


@app.post("/v1/chat/completions")
async def openai_chat_completions(
    request: Request,
    authorization: Optional[str] = Header(None),
):
    cache = get_cache()
    proxy = get_proxy()
    
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    
    api_key = None
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization[7:]
    
    is_streaming = body.get("stream", False)
    normalized_body = normalize_request(body)
    cache_key = generate_cache_key(body)
    model = body.get("model", "unknown")
    
    if is_streaming:
        try:
            return StreamingResponse(
                proxy.forward_openai_stream("/chat/completions", normalized_body, api_key),
                media_type="text/event-stream",
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")
    
    cached_response = cache.get(cache_key, model)
    
    if cached_response is not None:
        log_request(True, cache_key, model, cache.get_stats())
        cached_response["_snackcache"] = {"cache_hit": True, "cache_key": cache_key}
        return JSONResponse(content=cached_response)
    
    try:
        response = await proxy.forward_openai("/chat/completions", normalized_body, api_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")
    
    cache.set(cache_key, response)
    log_request(False, cache_key, model, cache.get_stats())
    response["_snackcache"] = {"cache_hit": False, "cache_key": cache_key}
    
    return JSONResponse(content=response)


@app.post("/v1/messages")
async def anthropic_messages(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    cache = get_cache()
    proxy = get_proxy()
    
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    
    is_streaming = body.get("stream", False)
    normalized_body = normalize_request(body)
    cache_key = generate_cache_key(body)
    model = body.get("model", "unknown")
    
    if is_streaming:
        try:
            return StreamingResponse(
                proxy.forward_anthropic_stream("/messages", normalized_body, x_api_key),
                media_type="text/event-stream",
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")
    
    cached_response = cache.get(cache_key, model)
    
    if cached_response is not None:
        log_request(True, cache_key, model, cache.get_stats())
        return JSONResponse(content=cached_response)
    
    try:
        response = await proxy.forward_anthropic("/messages", normalized_body, x_api_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")
    
    cache.set(cache_key, response)
    log_request(False, cache_key, model, cache.get_stats())
    
    return JSONResponse(content=response)


@app.post("/chat/completions")
async def openai_chat_completions_alt(request: Request, authorization: Optional[str] = Header(None)):
    return await openai_chat_completions(request, authorization)


@app.post("/messages")
async def anthropic_messages_alt(request: Request, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    return await anthropic_messages(request, x_api_key)
