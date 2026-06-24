"""
db/database.py — Supabase PostgreSQL connection + CRUD operations.

Uses sync SQLAlchemy with psycopg2 driver via Supabase's
transaction pooler (port 6543). NullPool is used because
pgBouncer handles connection pooling server-side.
"""

import os
import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from db.models import (
    Base, Campaign, PipelineRun, InfluencerResult,
    Audit, Pricing, BrandSafety,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# ENGINE + SESSION FACTORY
# ─────────────────────────────────────────────

def _build_database_url() -> str:
    """Build PostgreSQL URL from individual env vars (Supabase style)."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    user = os.getenv("user", "")
    password = quote_plus(os.getenv("password", ""))
    host = os.getenv("host", "localhost")
    port = os.getenv("port", "5432")
    dbname = os.getenv("dbname", "postgres")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}?sslmode=require"


DATABASE_URL = _build_database_url()

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,       # Supabase pgBouncer handles pooling
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    """FastAPI dependency — yields a session, auto-closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist (runs on startup)."""
    logger.info("Initializing database tables on Supabase...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")


# ─────────────────────────────────────────────
# CAMPAIGN CRUD
# ─────────────────────────────────────────────

def create_campaign(db: Session, campaign_id: str, brief_dict: dict) -> Campaign:
    """Create a new campaign row."""
    campaign = Campaign(
        id=campaign_id,
        status="pending",
        brief=brief_dict,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def update_campaign_status(db: Session, campaign_id: str, status: str):
    """Update campaign status. Sets completed_at when status is 'complete'."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        logger.warning("Campaign %s not found for status update", campaign_id)
        return
    campaign.status = status
    if status == "complete":
        campaign.completed_at = datetime.now(timezone.utc)
    db.commit()


def update_campaign_artifacts(
    db: Session, campaign_id: str,
    icp_profile: dict | None = None,
    keywords: dict | None = None,
):
    """Save ICP profile and/or keywords to the campaign (after Chain 0/1)."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        return
    if icp_profile is not None:
        campaign.icp_profile = icp_profile
    if keywords is not None:
        campaign.keywords = keywords
    db.commit()


# ─────────────────────────────────────────────
# PIPELINE RUN CRUD
# ─────────────────────────────────────────────

def save_pipeline_run(
    db: Session, campaign_id: str,
    timings: dict, discovered: int, filtered: int, audited: int,
    error_message: str | None = None,
):
    """Save pipeline execution stats."""
    run = PipelineRun(
        campaign_id=campaign_id,
        timings=timings,
        discovered_count=discovered,
        filtered_count=filtered,
        audited_count=audited,
        error_message=error_message,
        finished_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()


# ─────────────────────────────────────────────
# RESULTS CRUD  (saves to 4 normalized tables)
# ─────────────────────────────────────────────

def save_results(db: Session, campaign_id: str, dossiers: list[dict]):
    """
    Save flattened dossier dicts into normalized tables.

    Each dossier dict is expected to have:
      - handle, platform, followers, engagement_rate, composite_score, ai_summary
      - risk_flag, risk_evidence, risk_sources, risk_level
      - price_low, price_high, cpm_usd, pricing_tier, niche_multiplier, platform_multiplier
      - audit_* fields (audience_fit, authenticity_score, etc.)
    """
    for d in dossiers:
        # 1) InfluencerResult
        influencer = InfluencerResult(
            campaign_id=campaign_id,
            handle=d.get("handle", ""),
            platform=(d.get("platform") or "youtube").lower(),
            followers=d.get("followers", 0),
            engagement_rate=d.get("engagement_rate", 0.0),
            composite_score=d.get("composite_score", 0.0),
            ai_summary=d.get("ai_summary", ""),
        )
        db.add(influencer)
        db.flush()  # get influencer.id

        # 2) BrandSafety
        risk_flag = d.get("risk_flag", "green")
        if risk_flag not in ("green", "amber", "red"):
            risk_flag = "green"

        safety = BrandSafety(
            influencer_result_id=influencer.id,
            risk_flag=risk_flag,
            risk_level=d.get("risk_level"),
            tier1_triggered=d.get("tier1_triggered", False),
            tier2_triggered=d.get("tier2_triggered", False),
            tier3_triggered=d.get("tier3_triggered", False),
            risk_evidence=d.get("risk_evidence"),
            risk_sources=d.get("risk_sources", []),
            partnership_conflicts=d.get("partnership_conflicts", []),
            rationale=d.get("risk_evidence"),
        )
        db.add(safety)

        # 3) Pricing
        pricing = Pricing(
            influencer_result_id=influencer.id,
            price_low_inr=d.get("price_low", 0),
            price_high_inr=d.get("price_high", 0),
            cpm_usd=d.get("cpm_usd", 0.0),
            pricing_tier=d.get("pricing_tier"),
            niche_multiplier=d.get("niche_multiplier", 1.0),
            platform_multiplier=d.get("platform_multiplier", 1.0),
        )
        db.add(pricing)

        # 4) Audit (if audit data is present)
        audit_data = d.get("audit")
        if audit_data and isinstance(audit_data, dict):
            aq = audit_data.get("audience_quality", {})
            em = audit_data.get("engagement_metrics", {})
            cr = audit_data.get("credibility", {})
            co = audit_data.get("compliance", {})

            audit = Audit(
                influencer_result_id=influencer.id,
                audience_fit=aq.get("audience_fit"),
                authenticity_score=aq.get("authenticity_score"),
                sentiment_score=aq.get("sentiment_score"),
                engagement_consistency=em.get("engagement_consistency"),
                engagement_vs_tier=em.get("engagement_vs_tier"),
                top_content_type=em.get("top_content_type"),
                credibility_score=cr.get("credibility_score"),
                niche_authority=cr.get("niche_authority"),
                disclosure_compliance=co.get("disclosure_compliance"),
                professionalism=co.get("professionalism"),
                audit_rationale=audit_data.get("audit_rationale"),
            )
            db.add(audit)

    db.commit()
    logger.info("Saved %d influencer results for campaign %s", len(dossiers), campaign_id)


# ─────────────────────────────────────────────
# QUERY FUNCTIONS
# ─────────────────────────────────────────────

def get_campaign(db: Session, campaign_id: str):
    """
    Get a campaign with all related data (eager loaded).

    Returns (campaign_dict, results_list) for backward compatibility
    with existing route handlers.
    """
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        return None, []

    campaign_dict = {
        "job_id": str(campaign.id),
        "status": campaign.status,
        "brief_json": json.dumps(campaign.brief) if campaign.brief else "{}",
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None,
    }

    results = [ir.to_api_dict() for ir in campaign.influencer_results]

    return campaign_dict, results


def list_campaigns(db: Session, limit: int = 20) -> list[dict]:
    """List recent campaigns (for campaign history page)."""
    stmt = (
        select(Campaign)
        .order_by(Campaign.created_at.desc())
        .limit(limit)
    )
    campaigns = db.scalars(stmt).all()
    return [c.to_list_dict() for c in campaigns]