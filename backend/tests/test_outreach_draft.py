"""
Smoke test for outreach message drafting.
Run from backend/: python tests/test_outreach_draft.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from services.outreach import draft_outreach


MOCK_INFLUENCER = {
    "handle": "tech_guru_99",
    "platform": "youtube",
    "followers": 150000,
    "engagement_rate": 5.2,
    "ai_summary": "Tech reviewer focused on mechanical keyboards and productivity setups.",
}

MOCK_BRIEF = {
    "niche": "Technology and Peripherals",
    "target_audience": "Software engineers and desk setup enthusiasts",
    "budget_inr": 500000,
}


async def main():
    if not os.getenv("GROQ_API_KEY"):
        print("GROQ_API_KEY not set — skipping live outreach test.")
        return

    print(f"Drafting outreach for @{MOCK_INFLUENCER['handle']}...")
    try:
        draft = await draft_outreach(MOCK_INFLUENCER, MOCK_BRIEF)
        print("\n--- GENERATED DRAFT ---")
        print(draft)
        print("-----------------------")
    except Exception as e:
        print(f"Error generating draft: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
