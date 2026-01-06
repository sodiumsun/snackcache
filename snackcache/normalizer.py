"""
Prompt normalization and compression.

Normalizes prompts before caching to improve cache hit rates,
and compresses prompts to reduce token counts on cache misses.
"""

import re
import hashlib
import json
from typing import List, Dict, Any


class PromptNormalizer:
    """Normalizes and compresses prompts for caching and cost savings."""
    
    def __init__(self, aggressive: bool = False):
        self.aggressive = aggressive
        self.stats = {
            "total_original_chars": 0,
            "total_normalized_chars": 0,
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize a text string."""
        if not text:
            return text
        
        original_len = len(text)
        
        # Standardize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove trailing whitespace from each line
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
        
        # Collapse multiple blank lines to single blank line
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Collapse multiple spaces to single space
        text = re.sub(r'  +', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        # Track stats
        self.stats["total_original_chars"] += original_len
        self.stats["total_normalized_chars"] += len(text)
        
        return text
    
    def normalize_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single message object."""
        normalized = message.copy()
        
        if "content" in normalized:
            content = normalized["content"]
            
            if isinstance(content, str):
                normalized["content"] = self.normalize_text(content)
            elif isinstance(content, list):
                normalized_content = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        normalized_content.append({
                            **item,
                            "text": self.normalize_text(item.get("text", ""))
                        })
                    else:
                        normalized_content.append(item)
                normalized["content"] = normalized_content
        
        return normalized
    
    def normalize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize a list of messages."""
        return [self.normalize_message(msg) for msg in messages]
    
    def normalize_request(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an entire API request body."""
        normalized = request_body.copy()
        
        if "messages" in normalized:
            normalized["messages"] = self.normalize_messages(normalized["messages"])
        
        if "system" in normalized and isinstance(normalized["system"], str):
            normalized["system"] = self.normalize_text(normalized["system"])
        
        return normalized
    
    def generate_cache_key(self, request_body: Dict[str, Any]) -> str:
        """Generate a cache key from a normalized request."""
        normalized = self.normalize_request(request_body)
        
        cache_fields = {
            "model": normalized.get("model"),
            "messages": normalized.get("messages"),
            "system": normalized.get("system"),
            "temperature": normalized.get("temperature", 1.0),
            "max_tokens": normalized.get("max_tokens"),
            "top_p": normalized.get("top_p"),
            "stop": normalized.get("stop"),
        }
        
        cache_fields = {k: v for k, v in cache_fields.items() if v is not None}
        cache_str = json.dumps(cache_fields, sort_keys=True, ensure_ascii=True)
        
        return hashlib.sha256(cache_str.encode()).hexdigest()[:32]
    
    def get_compression_ratio(self) -> float:
        if self.stats["total_original_chars"] == 0:
            return 1.0
        return self.stats["total_normalized_chars"] / self.stats["total_original_chars"]
    
    def get_savings_percent(self) -> float:
        return (1 - self.get_compression_ratio()) * 100


_default_normalizer = PromptNormalizer()


def normalize_request(request_body: Dict[str, Any]) -> Dict[str, Any]:
    return _default_normalizer.normalize_request(request_body)


def generate_cache_key(request_body: Dict[str, Any]) -> str:
    return _default_normalizer.generate_cache_key(request_body)


def get_normalizer_stats() -> Dict[str, Any]:
    return {
        **_default_normalizer.stats,
        "compression_ratio": _default_normalizer.get_compression_ratio(),
        "savings_percent": _default_normalizer.get_savings_percent(),
    }
