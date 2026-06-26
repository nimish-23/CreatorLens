"""
YouTube API smoke test using the current youtube.py client.
Run from backend/: python tests/test_youtube.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chains"))

from dotenv import load_dotenv

load_dotenv()

from chains.chain_2_discovery import extract_channel_id
from services.platforms.youtube import youtube_search, youtube_channel_stats_batch


async def run_tests():
    if not os.getenv("YOUTUBE_API_KEY"):
        print("YOUTUBE_API_KEY not set — skipping YouTube test.")
        return

    print("Testing YouTube API via services/platforms/youtube.py...\n")

    queries = ["fitness review", "male fitness influencer"]

    for q in queries:
        print("=" * 50)
        print(f"QUERY: '{q}'")
        print("=" * 50)

        items = await youtube_search(q, max_results=2)
        if not items:
            print("No results returned.\n")
            continue

        channel_ids = []
        for item in items:
            cid = extract_channel_id(item)
            if cid:
                channel_ids.append(cid)

        if channel_ids:
            stats = await youtube_channel_stats_batch(channel_ids)
            for item, stat in zip(items, stats):
                item["channel_stats"] = stat

        print(json.dumps(items, indent=2, default=str))
        print()


if __name__ == "__main__":
    asyncio.run(run_tests())
