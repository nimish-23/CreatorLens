"""
db — Database package for CreatorLens.

Re-exports key symbols for clean imports:
    from db import get_db, init_db, Campaign, InfluencerResult
"""

from db.database import get_db, init_db, engine, SessionLocal
from db.database import (
    create_campaign,
    update_campaign_status,
    update_campaign_artifacts,
    save_pipeline_run,
    save_results,
    get_campaign,
    list_campaigns,
)
from db.models import (
    Base,
    Campaign,
    PipelineRun,
    InfluencerResult,
    Audit,
    Pricing,
    BrandSafety,
)
