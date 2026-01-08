"""
Command-line interface for SnackCache.
"""

import argparse
import sys
import os


def print_banner():
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║   🍿 SnackCache                                           ║
    ║   Stop paying for the same answer twice                   ║
    ╚═══════════════════════════════════════════════════════════╝
    """)


def cmd_serve(args):
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn required. Install with: pip install uvicorn")
        sys.exit(1)
    
    # Initialize cache with settings before starting server
    from snackcache.cache import init_cache
    
    print_banner()
    
    # Cache settings
    semantic = not args.no_semantic
    if semantic:
        try:
            import sentence_transformers
            import faiss
            print(f"Semantic caching: enabled (threshold: {args.threshold})")
        except ImportError:
            print("⚠️  Semantic caching disabled (install: pip install sentence-transformers faiss-cpu)")
            semantic = False
    else:
        print("Semantic caching: disabled")
    
    init_cache(
        semantic=semantic,
        similarity_threshold=args.threshold,
    )
    
    if args.redis:
        os.environ["SNACKCACHE_REDIS_URL"] = args.redis
        print(f"Redis: {args.redis}")
    else:
        print("Storage: in-memory")
    
    # Set env vars for startup message
    display_host = "localhost" if args.host == "0.0.0.0" else args.host
    os.environ["SNACKCACHE_HOST"] = display_host
    os.environ["SNACKCACHE_PORT"] = str(args.port)
    
    print()
    
    uvicorn.run(
        "snackcache.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info" if args.verbose else "warning",
    )


def cmd_stats(args):
    import httpx
    
    url = f"http://{args.host}:{args.port}/stats"
    
    try:
        response = httpx.get(url)
        response.raise_for_status()
        stats = response.json()
    except Exception as e:
        print(f"Error: {e}")
        print("Is the server running?")
        sys.exit(1)
    
    summary = stats.get("summary", {})
    cache = stats.get("cache", {})
    
    print("\n📊 SnackCache Statistics")
    print("=" * 40)
    print(f"Total Requests:     {summary.get('total_requests', 0)}")
    print(f"Cache Hit Rate:     {summary.get('cache_hit_rate', '0%')}")
    print(f"  Exact Hits:       {summary.get('exact_hits', 0)}")
    print(f"  Semantic Hits:    {summary.get('semantic_hits', 0)}")
    print(f"Tokens Saved:       {summary.get('tokens_saved', 0):,}")
    print(f"Cost Saved:         {summary.get('cost_saved', '$0')}")
    print("-" * 40)
    print(f"Semantic Enabled:   {cache.get('semantic_enabled', False)}")
    print(f"Cache Size:         {cache.get('cache_size', 0)}")
    print(f"Index Size:         {cache.get('semantic_index_size', 0)}")
    print("=" * 40 + "\n")


def cmd_clear(args):
    import httpx
    
    url = f"http://{args.host}:{args.port}/stats/reset"
    
    try:
        response = httpx.post(url)
        response.raise_for_status()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print("✅ Cache cleared")


def main():
    parser = argparse.ArgumentParser(
        description="SnackCache - Semantic caching proxy for LLM APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  snackcache serve
  snackcache serve --port 3000
  snackcache serve --threshold 0.9
  snackcache serve --no-semantic
  snackcache stats

Usage with OpenAI SDK:
  from openai import OpenAI
  client = OpenAI(base_url="http://localhost:8000/v1")
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    serve_parser = subparsers.add_parser("serve", help="Start the server")
    serve_parser.add_argument("--host", "-H", default="0.0.0.0")
    serve_parser.add_argument("--port", "-p", type=int, default=8000)
    serve_parser.add_argument("--redis", "-r", help="Redis URL")
    serve_parser.add_argument("--threshold", "-t", type=float, default=0.85,
                              help="Semantic similarity threshold (0-1, default: 0.85)")
    serve_parser.add_argument("--no-semantic", action="store_true",
                              help="Disable semantic caching (exact match only)")
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.add_argument("--verbose", "-v", action="store_true")
    serve_parser.set_defaults(func=cmd_serve)
    
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.add_argument("--host", default="localhost")
    stats_parser.add_argument("--port", "-p", type=int, default=8000)
    stats_parser.set_defaults(func=cmd_stats)
    
    clear_parser = subparsers.add_parser("clear", help="Clear cache")
    clear_parser.add_argument("--host", default="localhost")
    clear_parser.add_argument("--port", "-p", type=int, default=8000)
    clear_parser.set_defaults(func=cmd_clear)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(0)
    
    args.func(args)


if __name__ == "__main__":
    main()
