"""
Proxy module for forwarding requests to upstream APIs.
"""

import os
from typing import Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass
import httpx


@dataclass
class ProxyConfig:
    """Configuration for upstream API proxying."""
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    timeout: float = 120.0
    
    @classmethod
    def from_env(cls) -> "ProxyConfig":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
            timeout=float(os.getenv("PROXY_TIMEOUT", "120")),
        )


class UpstreamProxy:
    """Handles proxying requests to upstream LLM APIs."""
    
    def __init__(self, config: Optional[ProxyConfig] = None):
        self.config = config or ProxyConfig.from_env()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._client
    
    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def forward_openai(
        self, endpoint: str, request_body: Dict[str, Any], api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        client = await self.get_client()
        key = api_key or self.config.openai_api_key
        if not key:
            raise ValueError("OpenAI API key not configured")
        
        url = f"{self.config.openai_base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        
        response = await client.post(url, json=request_body, headers=headers)
        response.raise_for_status()
        return response.json()
    
    async def forward_openai_stream(
        self, endpoint: str, request_body: Dict[str, Any], api_key: Optional[str] = None,
    ) -> AsyncIterator[str]:
        client = await self.get_client()
        key = api_key or self.config.openai_api_key
        if not key:
            raise ValueError("OpenAI API key not configured")
        
        url = f"{self.config.openai_base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        
        async with client.stream("POST", url, json=request_body, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line + "\n\n"
    
    async def forward_anthropic(
        self, endpoint: str, request_body: Dict[str, Any], api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        client = await self.get_client()
        key = api_key or self.config.anthropic_api_key
        if not key:
            raise ValueError("Anthropic API key not configured")
        
        url = f"{self.config.anthropic_base_url}{endpoint}"
        headers = {
            "x-api-key": key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        
        response = await client.post(url, json=request_body, headers=headers)
        response.raise_for_status()
        return response.json()
    
    async def forward_anthropic_stream(
        self, endpoint: str, request_body: Dict[str, Any], api_key: Optional[str] = None,
    ) -> AsyncIterator[str]:
        client = await self.get_client()
        key = api_key or self.config.anthropic_api_key
        if not key:
            raise ValueError("Anthropic API key not configured")
        
        url = f"{self.config.anthropic_base_url}{endpoint}"
        headers = {
            "x-api-key": key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        
        async with client.stream("POST", url, json=request_body, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: ") or line.startswith("event: "):
                    yield line + "\n"
                elif line == "":
                    yield "\n"


_proxy: Optional[UpstreamProxy] = None


def get_proxy() -> UpstreamProxy:
    global _proxy
    if _proxy is None:
        _proxy = UpstreamProxy()
    return _proxy
