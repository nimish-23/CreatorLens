"""
db/models.py — SQLAlchemy ORM models for CreatorLens (Supabase PostgreSQL).

Normalized schema:
  campaigns          → campaign brief + ICP + keywords (JSONB)
  pipeline_runs      → timing & stats per campaign run
  influencer_results → core influencer data
  audits             → LLM audit dimension scores (1:1)
  pricing            → pricing estimates (1:1)
  brand_safety       → risk assessment (1:1)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# CAMPAIGNS  (replaces old 'jobs' table)
# ─────────────────────────────────────────────

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String(20), nullable=False, default="pending")
    brief = Column(JSONB)                # full BrandBrief dict
    icp_profile = Column(JSONB)          # Chain 0 output — enables replay
    keywords = Column(JSONB)             # Chain 1 output
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    influencer_results = relationship(
        "InfluencerResult", back_populates="campaign",
        cascade="all, delete-orphan", lazy="selectin",
        order_by="InfluencerResult.composite_score.desc()",
    )
    pipeline_run = relationship(
        "PipelineRun", back_populates="campaign",
        uselist=False, cascade="all, delete-orphan", lazy="selectin",
    )

    def to_list_dict(self) -> dict:
        """Format for GET /api/campaigns (backward compat with frontend)."""
        import json
        return {
            "job_id": str(self.id),
            "status": self.status,
            "brief_json": json.dumps(self.brief) if self.brief else "{}",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ─────────────────────────────────────────────
# PIPELINE RUNS  (new — performance monitoring)
# ─────────────────────────────────────────────

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    timings = Column(JSONB)
    discovered_count = Column(Integer, default=0)
    filtered_count = Column(Integer, default=0)
    audited_count = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))

    campaign = relationship("Campaign", back_populates="pipeline_run")


# ─────────────────────────────────────────────
# INFLUENCER RESULTS
# ─────────────────────────────────────────────

class InfluencerResult(Base):
    __tablename__ = "influencer_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    handle = Column(String(255), nullable=False)
    platform = Column(String(20), nullable=False, default="youtube")
    followers = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    composite_score = Column(Float, default=0.0)
    ai_summary = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    campaign = relationship("Campaign", back_populates="influencer_results")
    audit = relationship(
        "Audit", back_populates="influencer_result",
        uselist=False, cascade="all, delete-orphan", lazy="selectin",
    )
    pricing = relationship(
        "Pricing", back_populates="influencer_result",
        uselist=False, cascade="all, delete-orphan", lazy="selectin",
    )
    brand_safety = relationship(
        "BrandSafety", back_populates="influencer_result",
        uselist=False, cascade="all, delete-orphan", lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", "handle", name="uq_campaign_handle"),
        Index("ix_influencer_campaign_id", "campaign_id"),
        Index("ix_influencer_composite_score", "composite_score"),
    )

    def to_api_dict(self) -> dict:
        """Flatten normalized data back to the format the frontend expects."""
        d = {
            "handle": self.handle,
            "platform": self.platform,
            "followers": self.followers,
            "engagement_rate": self.engagement_rate,
            "composite_score": self.composite_score,
            "ai_summary": self.ai_summary,
        }

        if self.brand_safety:
            d["risk_flag"] = self.brand_safety.risk_flag
            d["risk_evidence"] = self.brand_safety.risk_evidence
            d["risk_sources"] = self.brand_safety.risk_sources or []
        else:
            d["risk_flag"] = "green"
            d["risk_evidence"] = None
            d["risk_sources"] = []

        if self.pricing:
            d["price_low"] = self.pricing.price_low_inr
            d["price_high"] = self.pricing.price_high_inr
        else:
            d["price_low"] = 0
            d["price_high"] = 0

        if self.audit:
            d["score_breakdown"] = {
                "engagement": round((self.audit.engagement_consistency or 0) * 100),
                "authenticity": round((self.audit.authenticity_score or 0) * 100),
                "relevance": round((self.audit.niche_authority or 0) * 100),
                "safety": 100 if d["risk_flag"] == "green" else (
                    50 if d["risk_flag"] == "amber" else 0
                ),
            }

        return d


# ─────────────────────────────────────────────
# AUDITS  (1:1 with influencer_results)
# ─────────────────────────────────────────────

class Audit(Base):
    __tablename__ = "audits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    influencer_result_id = Column(
        Integer, ForeignKey("influencer_results.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    audience_fit = Column(Float)
    authenticity_score = Column(Float)
    sentiment_score = Column(Float)
    engagement_consistency = Column(Float)
    engagement_vs_tier = Column(String(20))
    top_content_type = Column(String(100))
    credibility_score = Column(Float)
    niche_authority = Column(Float)
    disclosure_compliance = Column(Float)
    professionalism = Column(Float)
    audit_rationale = Column(Text)

    influencer_result = relationship("InfluencerResult", back_populates="audit")


# ─────────────────────────────────────────────
# PRICING  (1:1 with influencer_results)
# ─────────────────────────────────────────────

class Pricing(Base):
    __tablename__ = "pricing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    influencer_result_id = Column(
        Integer, ForeignKey("influencer_results.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    price_low_inr = Column(Integer, default=0)
    price_high_inr = Column(Integer, default=0)
    cpm_usd = Column(Float, default=0.0)
    pricing_tier = Column(String(20))
    niche_multiplier = Column(Float, default=1.0)
    platform_multiplier = Column(Float, default=1.0)

    influencer_result = relationship("InfluencerResult", back_populates="pricing")


# ─────────────────────────────────────────────
# BRAND SAFETY  (1:1 with influencer_results)
# ─────────────────────────────────────────────

class BrandSafety(Base):
    __tablename__ = "brand_safety"

    id = Column(Integer, primary_key=True, autoincrement=True)
    influencer_result_id = Column(
        Integer, ForeignKey("influencer_results.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    risk_flag = Column(String(10), nullable=False, default="green")
    risk_level = Column(String(20))
    tier1_triggered = Column(Boolean, default=False)
    tier2_triggered = Column(Boolean, default=False)
    tier3_triggered = Column(Boolean, default=False)
    risk_evidence = Column(Text)
    risk_sources = Column(JSONB, default=list)
    partnership_conflicts = Column(JSONB, default=list)
    rationale = Column(Text)

    influencer_result = relationship("InfluencerResult", back_populates="brand_safety")
