"""
Pipeline — YouTube Creator Discovery Orchestrator
===================================================
Executes all chains in sequence:

  Chain 0: ICP Builder      → BrandBrief → ICPProfile
  Chain 1: Keyword Expansion → ICPProfile → ExpandedKeywordSet
  Chain 2: Discovery         → YouTube search → list[RawCreatorProfile]
  Chain 3: Filtering         → Hard-drop rules → filtered list
  Chain 4: Audit             → LLM scoring + brand safety → enriched dossiers

Usage:
    from chains.pipline import run_pipeline

    results = await run_pipeline(brief, groq_api_key)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))  # chains/ dir for bare imports


from chain_0_ICP import BrandBrief, ICPProfile, run_icp_chain
from chain_1_keywordExpansion import ExpandedKeywordSet, run_keyword_expansion
from chain_2_discovery import RawCreatorProfile, run_discovery
from chain_3_filtering import run_filtering
from chain_4_audit import run_audit

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# PIPELINE RESULT
# ─────────────────────────────────────────────

class PipelineResult:
    """Container for the full pipeline output."""

    def __init__(
        self,
        icp: ICPProfile,
        keywords: ExpandedKeywordSet,
        discovered: list[RawCreatorProfile],
        filtered: list[RawCreatorProfile],
        audited: list[dict[str, Any]],
        timings: dict[str, float],
    ):
        self.icp = icp
        self.keywords = keywords
        self.discovered = discovered
        self.filtered = filtered
        self.audited = audited
        self.timings = timings

    @property
    def summary(self) -> dict[str, Any]:
        """Quick stats for logging / API response."""
        return {
            "discovered_count": len(self.discovered),
            "filtered_count": len(self.filtered),
            "audited_count": len(self.audited),
            "successful_audits": sum(
                1 for r in self.audited if r.get("audit") is not None
            ),
            "primary_niches": self.icp.primary_niches,
            "timings": self.timings,
        }


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

async def run_pipeline(
    brief: BrandBrief,
    groq_api_key: str,
    *,
    max_discovery_queries: int | None = None,
    max_audit_candidates: int | None = None,
    follower_tolerance: float = 0.5,
) -> PipelineResult:
    """
    Execute the full CreatorLens pipeline end-to-end.

    Args:
        brief:                 The brand's campaign brief
        groq_api_key:          Groq API key for LLM chains (Chain 0 + Chain 4)
        max_discovery_queries: Cap YouTube queries (saves API quota in dev/test)
        max_audit_candidates:  Cap how many candidates get audited (saves Groq tokens)
        follower_tolerance:    How far outside the tier range is acceptable (0.5 = ±50%)

    Returns:
        PipelineResult with all chain outputs and timing data.
    """
    timings: dict[str, float] = {}
    pipeline_start = time.time()

    # ── Chain 0: ICP ──
    logger.info("━━━ Chain 0: Building ICP for '%s' ━━━", brief.brand_name)
    t0 = time.time()
    icp = await run_icp_chain(brief, groq_api_key)
    timings["chain_0_icp"] = round(time.time() - t0, 2)
    logger.info(
        "Chain 0 done (%.1fs). Niches: %s | Tier: %s",
        timings["chain_0_icp"],
        icp.primary_niches,
        icp.benchmarks.follower_tier,
    )

    # ── Chain 1: Keyword Expansion ──
    logger.info("━━━ Chain 1: Expanding keywords ━━━")
    t0 = time.time()
    keywords = run_keyword_expansion(icp)
    timings["chain_1_keywords"] = round(time.time() - t0, 2)
    logger.info(
        "Chain 1 done (%.1fs). %d YT queries | Est. quota: %d",
        timings["chain_1_keywords"],
        len(keywords.youtube_queries),
        keywords.estimated_quota_cost,
    )

    # Optional: cap queries for dev/test
    if max_discovery_queries and len(keywords.youtube_queries) > max_discovery_queries:
        logger.info(
            "Capping YouTube queries: %d → %d",
            len(keywords.youtube_queries),
            max_discovery_queries,
        )
        keywords.youtube_queries = keywords.youtube_queries[:max_discovery_queries]

    # ── Chain 2: Discovery ──
    logger.info("━━━ Chain 2: YouTube Discovery ━━━")
    t0 = time.time()
    discovered = await run_discovery(icp, keywords)
    timings["chain_2_discovery"] = round(time.time() - t0, 2)
    logger.info(
        "Chain 2 done (%.1fs). Discovered %d unique candidates",
        timings["chain_2_discovery"],
        len(discovered),
    )

    if not discovered:
        logger.warning("No candidates discovered — pipeline stopping early")
        timings["total"] = round(time.time() - pipeline_start, 2)
        return PipelineResult(
            icp=icp,
            keywords=keywords,
            discovered=[],
            filtered=[],
            audited=[],
            timings=timings,
        )

    # ── Chain 3: Filtering ──
    logger.info("━━━ Chain 3: Filtering %d candidates ━━━", len(discovered))
    t0 = time.time()
    filtered = run_filtering(icp, discovered, follower_tolerance=follower_tolerance)
    timings["chain_3_filtering"] = round(time.time() - t0, 2)
    logger.info(
        "Chain 3 done (%.1fs). %d → %d passed filters",
        timings["chain_3_filtering"],
        len(discovered),
        len(filtered),
    )

    if not filtered:
        logger.warning("All candidates filtered out — pipeline stopping early")
        timings["total"] = round(time.time() - pipeline_start, 2)
        return PipelineResult(
            icp=icp,
            keywords=keywords,
            discovered=discovered,
            filtered=[],
            audited=[],
            timings=timings,
        )

    # Optional: cap candidates for audit
    audit_candidates = filtered
    if max_audit_candidates and len(filtered) > max_audit_candidates:
        logger.info(
            "Capping audit candidates: %d → %d",
            len(filtered),
            max_audit_candidates,
        )
        audit_candidates = filtered[:max_audit_candidates]

    # ── Chain 4: Audit ──
    logger.info("━━━ Chain 4: Auditing %d candidates ━━━", len(audit_candidates))
    t0 = time.time()
    audited = await run_audit(icp, audit_candidates, groq_api_key=groq_api_key)
    timings["chain_4_audit"] = round(time.time() - t0, 2)

    successful = sum(1 for r in audited if r.get("audit") is not None)
    logger.info(
        "Chain 4 done (%.1fs). %d/%d audited successfully",
        timings["chain_4_audit"],
        successful,
        len(audit_candidates),
    )

    timings["total"] = round(time.time() - pipeline_start, 2)

    logger.info(
        "━━━ Pipeline complete (%.1fs total) ━━━\n"
        "  Discovered: %d | Filtered: %d | Audited: %d/%d",
        timings["total"],
        len(discovered),
        len(filtered),
        successful,
        len(audit_candidates),
    )

    return PipelineResult(
        icp=icp,
        keywords=keywords,
        discovered=discovered,
        filtered=filtered,
        audited=audited,
        timings=timings,
    )

# ─────────────────────────────────────────────
# RESULT FLATTENING  (Chain 4 → DB/Frontend)
# ─────────────────────────────────────────────

def flatten_audit_to_dossier(audited: dict[str, Any]) -> dict[str, Any]:
    """
    Flatten Chain 4's rich audit output into the flat dict format
    expected by database.save_results() and the frontend Dashboard.
    """
    audit = audited.get("audit") or {}
    pricing = audited.get("pricing") or {}
    brand_safety = audit.get("brand_safety") or {}
    engagement = audit.get("engagement_metrics") or {}
    credibility = audit.get("credibility") or {}
    audience = audit.get("audience_quality") or {}

    # Map risk_level → risk_flag (green/amber/red)
    risk_level = brand_safety.get("risk_level", "safe")
    risk_flag_map = {"safe": "green", "review": "amber", "risk": "amber", "high_risk": "red"}
    risk_flag = risk_flag_map.get(risk_level, "green")

    risk_evidence = brand_safety.get("rationale")
    risk_sources = brand_safety.get("partnership_conflicts", [])

    # Composite score: weighted average of audit dimensions
    try:
        eng_score = (engagement.get("engagement_rate") or 0)
        auth_score = (audience.get("authenticity_score") or 0) * 100
        niche_score = (credibility.get("niche_authority") or 0) * 100
        safety_score = 100 if risk_flag == "green" else (50 if risk_flag == "amber" else 0)
        composite = round(
            eng_score * 0.4 + auth_score * 0.3 + niche_score * 0.2 + safety_score * 0.1, 1
        )
    except (TypeError, ValueError):
        composite = 0.0

    ai_summary = audit.get("audit_rationale", "")
    price_low = int(pricing.get("estimated_rate_inr", 0))
    price_high = int(price_low * 1.5) if price_low else 0

    return {
        "handle": audited.get("handle", ""),
        "platform": audited.get("platform", "youtube"),
        "followers": audited.get("followers", 0),
        "engagement_rate": audited.get("engagement_rate") or audited.get("median_er") or 0,
        "risk_flag": risk_flag,
        "risk_evidence": risk_evidence,
        "risk_sources": risk_sources,
        "price_low": price_low,
        "price_high": price_high,
        "composite_score": composite,
        "ai_summary": ai_summary,
    }


# ─────────────────────────────────────────────
# BACKGROUND TASK ENTRY POINT  (called by route)
# ─────────────────────────────────────────────

async def execute_pipeline(job_id: str, route_brief) -> None:
    """
    Background task called by campaign.py:
        background_tasks.add_task(execute_pipeline, job_id, brief)

    Converts the route-level BrandBrief → chain BrandBrief,
    runs the full pipeline, flattens results, and saves to DB.

    Creates its own DB session since background tasks run
    outside the request lifecycle.
    """
    import traceback
    from db.database import (
        SessionLocal, update_campaign_status, update_campaign_artifacts,
        save_results, save_pipeline_run,
    )

    db = SessionLocal()
    logger.info("[Pipeline] Starting job %s", job_id)
    update_campaign_status(db, job_id, "running")

    try:
        # Convert route brief → chain brief
        chain_brief = BrandBrief(**route_brief.model_dump())

        groq_api_key = os.environ.get("GROQ_API_KEY", "")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY not set in environment")

        result = await run_pipeline(
            brief=chain_brief,
            groq_api_key=groq_api_key,
            max_discovery_queries=5,
            max_audit_candidates=5,
            follower_tolerance=0.5,
        )

        # Save ICP profile and keywords to campaign
        update_campaign_artifacts(
            db, job_id,
            icp_profile=result.icp.model_dump() if result.icp else None,
            keywords=result.keywords.model_dump() if result.keywords else None,
        )

        # Build enriched dossiers with full audit data for normalized tables
        enriched = []
        for a in result.audited:
            flat = flatten_audit_to_dossier(a)
            # Attach full audit dict so save_results can populate the audits table
            flat["audit"] = a.get("audit")
            # Attach pricing details
            pricing = a.get("pricing", {})
            flat["cpm_usd"] = pricing.get("cpm_usd", 0.0)
            flat["pricing_tier"] = pricing.get("pricing_tier")
            flat["niche_multiplier"] = pricing.get("niche_multiplier", 1.0)
            flat["platform_multiplier"] = pricing.get("platform_multiplier", 1.0)
            enriched.append(flat)

        enriched.sort(key=lambda d: d.get("composite_score", 0), reverse=True)

        if enriched:
            save_results(db, job_id, enriched)

        # Save pipeline run stats
        save_pipeline_run(
            db, job_id,
            timings=result.timings,
            discovered=len(result.discovered),
            filtered=len(result.filtered),
            audited=len(result.audited),
        )

        update_campaign_status(db, job_id, "complete")
        logger.info(
            "[Pipeline] Job %s complete — %d dossiers (%.1fs)",
            job_id, len(enriched), result.timings.get("total", 0),
        )

    except Exception as e:
        logger.error("[Pipeline] Job %s failed: %s\n%s", job_id, e, traceback.format_exc())
        update_campaign_status(db, job_id, "failed")

    finally:
        db.close()




# ─────────────────────────────────────────────
# QUICK LOCAL TEST
# ─────────────────────────────────────────────


if __name__ == "__main__":
    import json
    from chain_0_ICP import CampaignGoal, Platform, FollowerTier

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    sample_brief = BrandBrief(
        brand_name         = "Notion",
        product_description= "All-in-one workspace for notes, project management, and task tracking",
        campaign_goal      = CampaignGoal.AWARENESS,
        niche              = "productivity",
        platforms          = [Platform.YOUTUBE],
        follower_tier      = FollowerTier.MACRO,
        target_audience    = "Students, professionals, and tech enthusiasts",
        audience_location  = "United States",
        audience_age_range = "18-35",
        language           = "English",
        competitor_brands  = ["Evernote", "Roam Research", "Obsidian"],
        excluded_niches    = ["adult content", "gambling"],
    )

    async def main():
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            print("ERROR: GROQ_API_KEY not set in .env")
            return

        # We don't want to drop everyone during the local test
        # So we override the benchmarks to be extremely loose
        from chain_0_ICP import run_icp_chain
        icp = await run_icp_chain(sample_brief, api_key)
        icp.benchmarks.min_engagement_rate = 0.0
        icp.benchmarks.min_view_to_sub_ratio = 0.0

        # Now pass it directly to the rest of the chains
        from chain_1_keywordExpansion import run_keyword_expansion
        from chain_2_discovery import run_discovery
        from chain_3_filtering import run_filtering
        from chain_4_audit import run_audit
        
        keywords = run_keyword_expansion(icp)
        keywords.youtube_queries = keywords.youtube_queries[:3]
        
        discovered = await run_discovery(icp, keywords)
        filtered = run_filtering(icp, discovered, follower_tolerance=0.9)
        
        audited = await run_audit(icp, filtered[:3], groq_api_key=api_key)
        
        # Build fake pipeline result to reuse the print code
        result = PipelineResult(
            icp=icp,
            keywords=keywords,
            discovered=discovered,
            filtered=filtered,
            audited=audited,
            timings={"total": 0.0}
        )

        print(f"\n{'='*60}")
        print(f"PIPELINE SUMMARY")
        print(f"{'='*60}")
        print(json.dumps(result.summary, indent=2, default=str))

        print(f"\n{'='*60}")
        print(f"AUDITED CREATORS ({len(result.audited)})")
        print(f"{'='*60}")
        for c in result.audited:
            handle = c.get("handle", "?")
            followers = c.get("followers")
            followers_str = f"{followers:,}" if followers else "unknown"

            print(f"\n@{handle} — {followers_str} subscribers")

            if c.get("audit"):
                a = c["audit"]
                safety = a.get("brand_safety", {})
                eng = a.get("engagement_metrics", {})
                cred = a.get("credibility", {})
                print(f"  Brand safety:  {safety.get('risk_level', '?')}")
                print(f"  ER vs tier:    {eng.get('engagement_vs_tier', '?')}")
                print(f"  Niche auth:    {cred.get('niche_authority', '?')}")
                print(f"  Rationale:     {(a.get('audit_rationale') or '')[:120]}")

            if c.get("pricing"):
                p = c["pricing"]
                print(f"  Pricing:       INR {p['estimated_rate_inr']:,.0f} "
                      f"| CPM: ${p['cpm_usd']:.2f} | {p['pricing_tier']}")

            if c.get("audit_error"):
                print(f"  ⚠ ERROR: {c['audit_error']}")

    asyncio.run(main())
