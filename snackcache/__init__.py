"""
SnackCache - Stop paying for the same answer twice.
"""

__version__ = "0.1.0"

from .cache import get_cache, ResponseCache, InMemoryCache, RedisCache
from .normalizer import normalize_request, generate_cache_key, PromptNormalizer
from .proxy import get_proxy, UpstreamProxy, ProxyConfig

__all__ = [
    "get_cache", "ResponseCache", "InMemoryCache", "RedisCache",
    "normalize_request", "generate_cache_key", "PromptNormalizer",
    "get_proxy", "UpstreamProxy", "ProxyConfig",
]
