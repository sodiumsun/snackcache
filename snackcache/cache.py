"""
Caching layer for API responses.

Supports both in-memory caching (for development/single instance)
and Redis caching (for production/multi-instance).
"""

import json
import time
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from collections import OrderedDict
import threading


@dataclass
class CacheEntry:
    """A cached response with metadata."""
    response: Dict[str, Any]
    created_at: float
    hits: int = 0


@dataclass 
class CacheStats:
    """Statistics about cache performance."""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_tokens_saved: int = 0
    total_cost_saved_usd: float = 0.0
    total_time_saved_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.hit_rate,
            "total_tokens_saved": self.total_tokens_saved,
            "total_cost_saved_usd": round(self.total_cost_saved_usd, 4),
            "total_time_saved_ms": round(self.total_time_saved_ms, 2),
        }
    
    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def set(self, key: str, response: Dict[str, Any], ttl: Optional[int] = None) -> None:
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    def clear(self) -> None:
        pass
    
    @abstractmethod
    def size(self) -> int:
        pass


class InMemoryCache(CacheBackend):
    """Simple in-memory LRU cache."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            if time.time() - entry.created_at > self.default_ttl:
                del self._cache[key]
                return None
            
            self._cache.move_to_end(key)
            entry.hits += 1
            
            return entry.response
    
    def set(self, key: str, response: Dict[str, Any], ttl: Optional[int] = None) -> None:
        with self._lock:
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = CacheEntry(
                response=response,
                created_at=time.time(),
            )
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
    
    def size(self) -> int:
        return len(self._cache)


class RedisCache(CacheBackend):
    """Redis-backed cache for production deployments."""
    
    def __init__(
        self, 
        host: str = "localhost", 
        port: int = 6379, 
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = "snackcache:",
        default_ttl: int = 3600
    ):
        try:
            import redis
        except ImportError:
            raise ImportError("Redis support requires 'redis' package: pip install redis")
        
        self.client = redis.Redis(
            host=host, port=port, db=db, password=password, decode_responses=True
        )
        self.prefix = prefix
        self.default_ttl = default_ttl
    
    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        data = self.client.get(self._key(key))
        if data is None:
            return None
        return json.loads(data)
    
    def set(self, key: str, response: Dict[str, Any], ttl: Optional[int] = None) -> None:
        ttl = ttl or self.default_ttl
        self.client.setex(self._key(key), ttl, json.dumps(response))
    
    def delete(self, key: str) -> bool:
        return self.client.delete(self._key(key)) > 0
    
    def clear(self) -> None:
        keys = self.client.keys(f"{self.prefix}*")
        if keys:
            self.client.delete(*keys)
    
    def size(self) -> int:
        return len(self.client.keys(f"{self.prefix}*"))


# Pricing per 1M tokens
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "default": {"input": 2.00, "output": 8.00},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get("default")
    for model_prefix, model_pricing in MODEL_PRICING.items():
        if model_prefix in model.lower():
            pricing = model_pricing
            break
    
    return (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]


class ResponseCache:
    """Main cache interface combining backend + stats tracking."""
    
    def __init__(self, backend: Optional[CacheBackend] = None):
        self.backend = backend or InMemoryCache()
        self.stats = CacheStats()
        self._lock = threading.Lock()
    
    def get(self, cache_key: str, model: str = "default") -> Optional[Dict[str, Any]]:
        with self._lock:
            self.stats.total_requests += 1
        
        response = self.backend.get(cache_key)
        
        if response is None:
            with self._lock:
                self.stats.cache_misses += 1
            return None
        
        usage = response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = input_tokens + output_tokens
        cost_saved = estimate_cost(model, input_tokens, output_tokens)
        time_saved_ms = (total_tokens / 50) * 1000
        
        with self._lock:
            self.stats.cache_hits += 1
            self.stats.total_tokens_saved += total_tokens
            self.stats.total_cost_saved_usd += cost_saved
            self.stats.total_time_saved_ms += time_saved_ms
        
        return response
    
    def set(self, cache_key: str, response: Dict[str, Any], ttl: Optional[int] = None) -> None:
        self.backend.set(cache_key, response, ttl)
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {**self.stats.to_dict(), "cache_size": self.backend.size()}
    
    def clear(self) -> None:
        self.backend.clear()
        with self._lock:
            self.stats = CacheStats()


_cache: Optional[ResponseCache] = None


def get_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache


def init_cache(backend: CacheBackend) -> ResponseCache:
    global _cache
    _cache = ResponseCache(backend)
    return _cache
