"""
models/schemas.py — Pydantic request/response models for API routes.

The BrandBrief here mirrors chain_0_ICP.BrandBrief exactly so the
frontend → route → chain pipeline has zero translation friction.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ─────────────────────────────────────────────
# ENUMS  (match chain_0_ICP.py exactly)
# ─────────────────────────────────────────────

class Platform(str, Enum):
    youtube   = "youtube"
    instagram = "instagram"
    twitter   = "twitter"


class CampaignGoal(str, Enum):
    awareness      = "awareness"
    conversion     = "conversion"
    engagement     = "engagement"
    lead_generation = "lead_generation"


class FollowerTier(str, Enum):
    nano  = "nano"
    micro = "micro"
    mid   = "mid"
    macro = "macro"
    mega  = "mega"


class RiskFlag(str, Enum):
    green = "green"
    amber = "amber"
    red   = "red"


# ─────────────────────────────────────────────
# REQUEST — matches chain_0_ICP.BrandBrief
# ─────────────────────────────────────────────

class BrandBrief(BaseModel):
    """Campaign brief submitted from BriefForm.jsx → POST /api/run-campaign."""

    # Brand identity
    brand_name:          str = Field(..., description="Name of the brand")
    product_description: str = Field(..., description="What the product is and what it does")
    campaign_goal:       CampaignGoal = Field(..., description="Primary campaign objective")

    # Creator targeting
    niche:               str              = Field(..., description="Primary niche e.g. 'skincare'")
    platforms:           List[Platform]   = Field(..., min_length=1)
    follower_tier:       FollowerTier     = Field(..., description="Target creator size tier")

    # Audience targeting
    target_audience:     str = Field(..., description="Who the brand wants to reach")
    audience_location:   str = Field(..., description="Country or region")
    audience_age_range:  str = Field(..., description="e.g. '18-24', '25-35'")
    language:            str = Field(default="English")

    # Optional enrichment
    competitor_brands:   List[str]       = Field(default_factory=list)
    budget_inr:          Optional[int]   = Field(default=None, description="Total campaign budget in INR")
    excluded_niches:     List[str]       = Field(default_factory=list)
    additional_context:  Optional[str]   = Field(default=None)


# ─────────────────────────────────────────────
# RESPONSE — Influencer dossier from Chain 4
# ─────────────────────────────────────────────

class InfluencerDossier(BaseModel):
    handle:           str
    platform:         Platform
    followers:        Optional[int] = 0
    engagement_rate:  Optional[float] = None
    risk_flag:        Optional[RiskFlag] = RiskFlag.green
    risk_evidence:    Optional[str] = None
    risk_sources:     Optional[List] = []
    price_low:        Optional[int] = 0
    price_high:       Optional[int] = 0
    composite_score:  Optional[float] = 0.0
    ai_summary:       Optional[str] = ""
    competitor_flag:  Optional[bool] = False
    competitor_evidence: Optional[str] = None


# ─────────────────────────────────────────────
# JOB STATUS + CAMPAIGN RESPONSE
# ─────────────────────────────────────────────

class JobStatus(str, Enum):
    pending  = "pending"
    running  = "running"
    complete = "complete"
    failed   = "failed"


class CampaignResponse(BaseModel):
    job_id:  str
    status:  JobStatus
    results: Optional[List[InfluencerDossier]] = None
    error:   Optional[str] = None