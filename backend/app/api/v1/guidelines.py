from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.knowledge import Guideline, SeverityLevel
from app.schemas.knowledge import GuidelineCreate, GuidelineUpdate, GuidelineOut
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/guidelines", tags=["Guidelines"])


@router.get("", response_model=List[GuidelineOut])
def list_guidelines(
    category: Optional[str] = Query(None, description="Category filter"),
    severity: Optional[str] = Query(None, description="Severity filter: Blocker, High, Warning, Info"),
    product_scope: Optional[str] = Query(None),
    region_scope: Optional[str] = Query(None),
    channel_scope: Optional[str] = Query(None),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Guideline).filter(Guideline.organization_id == current_user.organization_id)
    if active_only:
        query = query.filter(Guideline.active == True)
    if category and category.lower() != "all":
        query = query.filter(Guideline.category.ilike(f"%{category}%"))
    if severity and severity.lower() != "all":
        query = query.filter(Guideline.severity.ilike(f"%{severity}%"))
    if product_scope and product_scope.lower() != "all":
        query = query.filter(Guideline.product_scope.ilike(f"%{product_scope}%"))
    if region_scope and region_scope.lower() not in ["all", "global"]:
        query = query.filter(Guideline.region_scope.ilike(f"%{region_scope}%"))
    if channel_scope and channel_scope.lower() != "all":
        query = query.filter(Guideline.channel_scope.ilike(f"%{channel_scope}%"))

    return query.order_by(Guideline.title.asc()).all()


@router.post("", response_model=GuidelineOut)
def create_guideline(
    item_in: GuidelineCreate,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    new_g = Guideline(
        organization_id=current_user.organization_id,
        title=item_in.title,
        description=item_in.description,
        category=item_in.category,
        severity=item_in.severity.value if isinstance(item_in.severity, SeverityLevel) else str(item_in.severity),
        product_scope=item_in.product_scope or "All",
        region_scope=item_in.region_scope or "Global",
        channel_scope=item_in.channel_scope or "All",
        source_reference=item_in.source_reference,
        status=item_in.status or "Approved",
        active=item_in.active,
    )
    db.add(new_g)
    db.commit()
    db.refresh(new_g)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="GUIDELINE_CREATED",
        entity_type="Guideline",
        entity_id=new_g.id,
        metadata={
            "title": new_g.title,
            "category": new_g.category,
            "severity": new_g.severity,
            "product_scope": new_g.product_scope,
        }
    )

    return new_g


@router.get("/{guideline_id}", response_model=GuidelineOut)
def get_guideline(
    guideline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    g = db.query(Guideline).filter(
        Guideline.id == guideline_id,
        Guideline.organization_id == current_user.organization_id
    ).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guideline not found")
    return g


@router.put("/{guideline_id}", response_model=GuidelineOut)
def update_guideline(
    guideline_id: str,
    item_in: GuidelineUpdate,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    g = db.query(Guideline).filter(
        Guideline.id == guideline_id,
        Guideline.organization_id == current_user.organization_id
    ).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guideline not found")

    old_vals = {"title": g.title, "category": g.category, "severity": g.severity}
    new_vals = {}

    for field, val in item_in.model_dump(exclude_unset=True).items():
        if val is not None:
            if field == "severity" and isinstance(val, SeverityLevel):
                setattr(g, field, val.value)
                new_vals[field] = val.value
            else:
                setattr(g, field, val)
                new_vals[field] = val

    db.commit()
    db.refresh(g)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="GUIDELINE_UPDATED",
        entity_type="Guideline",
        entity_id=g.id,
        metadata={
            "title": g.title,
            "old_values": old_vals,
            "new_values": new_vals,
        }
    )

    return g


@router.put("/{guideline_id}/archive", response_model=GuidelineOut)
def archive_guideline(
    guideline_id: str,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    g = db.query(Guideline).filter(
        Guideline.id == guideline_id,
        Guideline.organization_id == current_user.organization_id
    ).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guideline not found")

    g.active = False
    g.status = "Archived"
    db.commit()
    db.refresh(g)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="GUIDELINE_ARCHIVED",
        entity_type="Guideline",
        entity_id=g.id,
        metadata={"title": g.title}
    )

    return g


@router.delete("/{guideline_id}")
def delete_guideline(
    guideline_id: str,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    g = db.query(Guideline).filter(
        Guideline.id == guideline_id,
        Guideline.organization_id == current_user.organization_id
    ).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guideline not found")

    title = g.title
    db.delete(g)
    db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="GUIDELINE_DELETED",
        entity_type="Guideline",
        entity_id=guideline_id,
        metadata={"title": title}
    )

    return {"message": f"Guideline '{title}' deleted successfully"}
