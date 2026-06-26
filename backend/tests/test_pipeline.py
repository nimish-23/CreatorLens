"""
Connectivity diagnostic for the current CreatorLens stack.
Run from backend/: python tests/test_pipeline.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def check_env() -> dict[str, bool]:
    keys = {
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
        "YOUTUBE_API_KEY": os.getenv("YOUTUBE_API_KEY"),
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY"),
    }
    return {name: bool(value and value.strip()) for name, value in keys.items()}


async def test_groq() -> bool:
    print("\n[TEST] Groq LLM connectivity...")
    from services.llm_client import llm_chat

    try:
        result = await llm_chat("You are helpful.", "Reply with exactly: ok")
        print(f"  [OK] Groq responded: {result[:80]}")
        return True
    except Exception as e:
        print(f"  [FAIL] Groq FAILED: {e}")
        return False


async def test_youtube() -> bool:
    print("\n[TEST] YouTube API connectivity...")
    from services.platforms.youtube import youtube_search

    try:
        items = await youtube_search("fitness review", max_results=1)
        if not items:
            print("  [FAIL] YouTube returned no results (check YOUTUBE_API_KEY / quota)")
            return False
        print(f"  [OK] YouTube search returned {len(items)} item(s)")
        return True
    except Exception as e:
        print(f"  [FAIL] YouTube FAILED: {e}")
        return False


async def test_tavily() -> bool:
    print("\n[TEST] Tavily API connectivity...")
    from services.platforms.instagram import tavily_search

    try:
        results = await tavily_search("test query", max_results=1)
        print(f"  [OK] Tavily returned {len(results)} result(s)")
        return True
    except Exception as e:
        print(f"  [FAIL] Tavily FAILED: {e}")
        return False


async def main():
    print("=" * 60)
    print("CreatorLens Pipeline Diagnostic (current stack)")
    print("=" * 60)

    env = check_env()
    print("\n[TEST] Environment variables...")
    for name, ok in env.items():
        print(f"  {name}: {'[OK] set' if ok else '[FAIL] NOT SET'}")

    groq_ok = await test_groq() if env["GROQ_API_KEY"] else False
    yt_ok = await test_youtube() if env["YOUTUBE_API_KEY"] else False
    tavily_ok = await test_tavily() if env["TAVILY_API_KEY"] else False

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Groq:    {'[OK] PASS' if groq_ok else '[FAIL] FAIL'}")
    print(f"  YouTube: {'[OK] PASS' if yt_ok else '[FAIL] FAIL'}")
    print(f"  Tavily:  {'[OK] PASS' if tavily_ok else '[FAIL] FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
