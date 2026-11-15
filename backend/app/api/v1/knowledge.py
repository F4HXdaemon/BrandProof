from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.knowledge import (
    ApplicableKnowledgeResponse,
    FactOut,
    GuidelineOut,
    TermOut,
    RuleOut,
)
from app.services.scoping_service import get_applicable_knowledge

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


def _format_fact_out(f) -> FactOut:
    now = datetime.now(timezone.utc)
    is_exp = f.is_expired
    eff_status = f.effective_status
    days_left = None
    if f.expires_at:
        exp = f.expires_at if f.expires_at.tzinfo else f.expires_at.replace(tzinfo=timezone.utc)
        diff = (exp - now).total_seconds()
        days_left = int(diff // 86400)

    out = FactOut.model_validate(f)
    out.is_expired = is_exp
    out.effective_status = eff_status
    out.days_until_expiry = days_left
    if f.owner:
        out.owner_name = f.owner.full_name
    return out


@router.get("/applicable", response_model=ApplicableKnowledgeResponse)
def get_scoped_applicable_knowledge(
    product: Optional[str] = Query(None, description="Target product (e.g. Starter, Pro, Enterprise, Sovereign Cloud)"),
    region: Optional[str] = Query(None, description="Target region (e.g. Global, India, US, EU)"),
    channel: Optional[str] = Query(None, description="Target publication channel (e.g. Website, Social, Email, Advertisement, Sales Deck)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve all approved facts, guidelines, terminology, and rules applicable to the given
    Product, Region, and Channel combination. Automatically filters out expired or archived information.
    """
    result = get_applicable_knowledge(
        db=db,
        organization_id=current_user.organization_id,
        product=product,
        region=region,
        channel=channel,
    )

    return ApplicableKnowledgeResponse(
        scopes=result["scopes"],
        counts=result["counts"],
        facts=[_format_fact_out(f) for f in result["facts"]],
        guidelines=[GuidelineOut.model_validate(g) for g in result["guidelines"]],
        terms=[TermOut.model_validate(t) for t in result["terms"]],
        rules=[RuleOut.model_validate(r) for r in result["rules"]],
        expired_facts_excluded=[_format_fact_out(f) for f in result["expired_facts_excluded"]],
    )
