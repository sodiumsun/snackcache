"""
Demo: See SnackCache in action.

1. Start server: snackcache serve
2. Run this: python examples/demo.py
"""

import time
import httpx

URL = "http://localhost:8000"


def chat(message: str) -> dict:
    return httpx.post(
        f"{URL}/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": message}],
            "temperature": 0,
        },
        headers={"Authorization": "Bearer demo"},
        timeout=60,
    ).json()


def main():
    print("\n🍿 SnackCache Demo\n" + "=" * 40)
    
    try:
        httpx.get(URL)
    except httpx.ConnectError:
        print("Server not running. Start with: snackcache serve")
        return
    
    prompt = "What is 2 + 2?"
    
    print(f"\nPrompt: \"{prompt}\"")
    print("-" * 40)
    
    # First request
    print("\nRequest 1...")
    start = time.time()
    r1 = chat(prompt)
    t1 = time.time() - start
    hit1 = r1.get("_snackcache", {}).get("cache_hit", False)
    print(f"  {'HIT' if hit1 else 'MISS'} | {t1:.2f}s")
    
    # Second request (should hit cache)
    print("\nRequest 2...")
    start = time.time()
    r2 = chat(prompt)
    t2 = time.time() - start
    hit2 = r2.get("_snackcache", {}).get("cache_hit", False)
    print(f"  {'HIT' if hit2 else 'MISS'} | {t2:.2f}s")
    
    # Stats
    stats = httpx.get(f"{URL}/stats").json().get("summary", {})
    print(f"\n" + "=" * 40)
    print(f"Hit Rate: {stats.get('cache_hit_rate', '0%')}")
    print(f"Saved: {stats.get('cost_saved', '$0')}")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    main()
