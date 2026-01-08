"""
Caching layer for API responses.

Supports:
- Exact match caching (default)
- Semantic caching with embeddings + vector search (optional)
"""

import json
import time
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from collections import OrderedDict
import threading
import numpy as np


@dataclass
class CacheEntry:
    """A cached response with metadata."""
    response: Dict[str, Any]
    created_at: float
    prompt_text: str = ""
    hits: int = 0


@dataclass 
class CacheStats:
    """Statistics about cache performance."""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    semantic_hits: int = 0
    exact_hits: int = 0
    total_tokens_saved: int = 0
    total_cost_saved_usd: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "semantic_hits": self.semantic_hits,
            "exact_hits": self.exact_hits,
            "hit_rate": self.hit_rate,
            "total_tokens_saved": self.total_tokens_saved,
            "total_cost_saved_usd": round(self.total_cost_saved_usd, 4),
        }
    
    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests


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


def extract_prompt_text(request_body: Dict[str, Any]) -> str:
    """Extract searchable text from request for semantic matching."""
    parts = []
    
    # System prompt
    if "system" in request_body:
        parts.append(str(request_body["system"]))
    
    # Messages
    messages = request_body.get("messages", [])
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
    
    return "\n".join(parts)


class SemanticIndex:
    """Vector index for semantic similarity search using FAISS."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", similarity_threshold: float = 0.85):
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self._model = None
        self._index = None
        self._cache_keys: List[str] = []  # Maps index position to cache key
        self._dimension = None
        self._lock = threading.Lock()
        self._initialized = False
        
    def _init_model(self):
        """Lazy load the embedding model."""
        if self._model is not None:
            return
            
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            self._initialized = True
            print(f"✅ Semantic caching enabled (model: {self.model_name}, dim: {self._dimension})")
        except ImportError:
            raise ImportError(
                "Semantic caching requires: pip install sentence-transformers faiss-cpu"
            )
    
    def _init_index(self):
        """Initialize FAISS index."""
        if self._index is not None:
            return
            
        try:
            import faiss
            self._index = faiss.IndexFlatIP(self._dimension)  # Inner product (cosine after normalization)
        except ImportError:
            raise ImportError(
                "Semantic caching requires: pip install sentence-transformers faiss-cpu"
            )
    
    def _embed(self, text: str) -> np.ndarray:
        """Generate normalized embedding for text."""
        self._init_model()
        embedding = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return embedding.astype(np.float32)
    
    def add(self, cache_key: str, text: str):
        """Add text to the semantic index."""
        with self._lock:
            self._init_model()
            self._init_index()
            
            embedding = self._embed(text)
            self._index.add(embedding.reshape(1, -1))
            self._cache_keys.append(cache_key)
    
    def search(self, text: str) -> Optional[Tuple[str, float]]:
        """Search for similar text. Returns (cache_key, similarity) or None."""
        with self._lock:
            if not self._initialized or self._index is None or self._index.ntotal == 0:
                return None
            
            embedding = self._embed(text)
            
            # Search for top 1 match
            scores, indices = self._index.search(embedding.reshape(1, -1), k=1)
            
            score = scores[0][0]
            idx = indices[0][0]
            
            if score >= self.similarity_threshold and idx < len(self._cache_keys):
                return (self._cache_keys[idx], float(score))
            
            return None
    
    def clear(self):
        """Clear the index."""
        with self._lock:
            if self._index is not None:
                self._index.reset()
            self._cache_keys = []
    
    @property
    def size(self) -> int:
        if self._index is None:
            return 0
        return self._index.ntotal


class ResponseCache:
    """Main cache interface with exact + semantic matching."""
    
    def __init__(
        self, 
        max_size: int = 1000,
        ttl: int = 3600,
        semantic: bool = True,
        similarity_threshold: float = 0.85,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self.max_size = max_size
        self.ttl = ttl
        self.semantic_enabled = semantic
        
        # Exact match cache
        self._exact_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # Semantic index (lazy loaded)
        self._semantic_index: Optional[SemanticIndex] = None
        if semantic:
            try:
                self._semantic_index = SemanticIndex(
                    model_name=model_name,
                    similarity_threshold=similarity_threshold,
                )
            except Exception as e:
                print(f"⚠️  Semantic caching disabled: {e}")
                self.semantic_enabled = False
        
        self.stats = CacheStats()
        self._lock = threading.Lock()
    
    def _generate_exact_key(self, request_body: Dict[str, Any]) -> str:
        """Generate exact match cache key."""
        cache_fields = {
            "model": request_body.get("model"),
            "messages": request_body.get("messages"),
            "system": request_body.get("system"),
            "temperature": request_body.get("temperature", 1.0),
            "max_tokens": request_body.get("max_tokens"),
        }
        cache_fields = {k: v for k, v in cache_fields.items() if v is not None}
        cache_str = json.dumps(cache_fields, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()[:32]
    
    def get(self, request_body: Dict[str, Any], model: str = "default") -> Optional[Dict[str, Any]]:
        """Try to get cached response. Tries exact match first, then semantic."""
        with self._lock:
            self.stats.total_requests += 1
        
        exact_key = self._generate_exact_key(request_body)
        
        # 1. Try exact match first
        with self._lock:
            if exact_key in self._exact_cache:
                entry = self._exact_cache[exact_key]
                if time.time() - entry.created_at <= self.ttl:
                    self._exact_cache.move_to_end(exact_key)
                    entry.hits += 1
                    self._record_hit(entry.response, model, is_semantic=False)
                    return entry.response
                else:
                    del self._exact_cache[exact_key]
        
        # 2. Try semantic match
        if self.semantic_enabled and self._semantic_index is not None:
            prompt_text = extract_prompt_text(request_body)
            result = self._semantic_index.search(prompt_text)
            
            if result is not None:
                semantic_key, similarity = result
                with self._lock:
                    if semantic_key in self._exact_cache:
                        entry = self._exact_cache[semantic_key]
                        if time.time() - entry.created_at <= self.ttl:
                            entry.hits += 1
                            self._record_hit(entry.response, model, is_semantic=True)
                            print(f"🎯 Semantic match (similarity: {similarity:.3f})")
                            return entry.response
        
        # Cache miss
        with self._lock:
            self.stats.cache_misses += 1
        return None
    
    def set(self, request_body: Dict[str, Any], response: Dict[str, Any]):
        """Store response in cache."""
        exact_key = self._generate_exact_key(request_body)
        prompt_text = extract_prompt_text(request_body)
        
        with self._lock:
            # Evict if at capacity
            while len(self._exact_cache) >= self.max_size:
                self._exact_cache.popitem(last=False)
            
            self._exact_cache[exact_key] = CacheEntry(
                response=response,
                created_at=time.time(),
                prompt_text=prompt_text,
            )
        
        # Add to semantic index
        if self.semantic_enabled and self._semantic_index is not None:
            try:
                self._semantic_index.add(exact_key, prompt_text)
            except Exception as e:
                print(f"⚠️  Failed to add to semantic index: {e}")
    
    def _record_hit(self, response: Dict[str, Any], model: str, is_semantic: bool):
        """Record cache hit statistics."""
        usage = response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = input_tokens + output_tokens
        cost_saved = estimate_cost(model, input_tokens, output_tokens)
        
        self.stats.cache_hits += 1
        if is_semantic:
            self.stats.semantic_hits += 1
        else:
            self.stats.exact_hits += 1
        self.stats.total_tokens_saved += total_tokens
        self.stats.total_cost_saved_usd += cost_saved
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                **self.stats.to_dict(),
                "cache_size": len(self._exact_cache),
                "semantic_index_size": self._semantic_index.size if self._semantic_index else 0,
                "semantic_enabled": self.semantic_enabled,
            }
    
    def clear(self):
        with self._lock:
            self._exact_cache.clear()
            if self._semantic_index:
                self._semantic_index.clear()
            self.stats = CacheStats()


# Global cache instance
_cache: Optional[ResponseCache] = None


def get_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache


def init_cache(
    semantic: bool = True,
    similarity_threshold: float = 0.85,
    **kwargs
) -> ResponseCache:
    global _cache
    _cache = ResponseCache(
        semantic=semantic,
        similarity_threshold=similarity_threshold,
        **kwargs
    )
    return _cache
