"""
SnackCache - Semantic caching proxy for LLM APIs.
Stop paying for the same answer twice.
"""

__version__ = "0.2.0"

from .cache import get_cache, init_cache, ResponseCache, SemanticIndex
from .normalizer import normalize_request, PromptNormalizer
from .proxy import get_proxy, UpstreamProxy, ProxyConfig

__all__ = [
    "get_cache", "init_cache", "ResponseCache", "SemanticIndex",
    "normalize_request", "PromptNormalizer",
    "get_proxy", "UpstreamProxy", "ProxyConfig",
]
