from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles, read_upload_file_bounded
from app.models.user import User, UserRole
from app.models.knowledge import Fact, FactStatus
from app.schemas.knowledge import FactCreate, FactUpdate, FactOut, CsvImportResponse
from app.services.audit_service import record_audit_event
from app.services.csv_service import import_facts_from_csv

router = APIRouter(prefix="/facts", tags=["Facts"])


def _format_fact(f: Fact) -> FactOut:
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


@router.get("", response_model=List[FactOut])
def list_facts(
    q: Optional[str] = Query(None, description="Search keyword in title, canonical_value, or source"),
    status: Optional[str] = Query(None, description="Filter by status: Approved, Draft, Expired, Archived"),
    owner_id: Optional[str] = Query(None, description="Filter by owner user ID"),
    product_scope: Optional[str] = Query(None, description="Filter by product scope"),
    region_scope: Optional[str] = Query(None, description="Filter by region scope"),
    channel_scope: Optional[str] = Query(None, description="Filter by channel scope"),
    expiring_soon: Optional[bool] = Query(False, description="Filter facts expiring within 30 days"),
    expired_only: Optional[bool] = Query(False, description="Filter facts that are already expired"),
    include_archived: bool = Query(False, description="Include archived facts"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List facts with comprehensive multi-attribute filtering, dynamic expiration detection,
    and owner mapping.
    """
    now = datetime.now(timezone.utc)
    query = db.query(Fact).filter(Fact.organization_id == current_user.organization_id)

    if not include_archived and status != FactStatus.ARCHIVED.value:
        query = query.filter(Fact.status != FactStatus.ARCHIVED.value)

    if q:
        search_fmt = f"%{q}%"
        query = query.filter(
            or_(
                Fact.title.ilike(search_fmt),
                Fact.canonical_value.ilike(search_fmt),
                Fact.source_reference.ilike(search_fmt),
                Fact.description.ilike(search_fmt),
            )
        )

    if owner_id:
        query = query.filter(Fact.owner_id == owner_id)

    if product_scope and product_scope.lower() != "all":
        query = query.filter(Fact.product_scope.ilike(f"%{product_scope}%"))

    if region_scope and region_scope.lower() not in ["all", "global"]:
        query = query.filter(Fact.region_scope.ilike(f"%{region_scope}%"))

    if channel_scope and channel_scope.lower() != "all":
        query = query.filter(Fact.channel_scope.ilike(f"%{channel_scope}%"))

    if status:
        if status.lower() == "expired":
            query = query.filter(Fact.expires_at.isnot(None), Fact.expires_at < now)
        elif status.lower() in ["approved", "active"]:
            query = query.filter(
                Fact.status.in_([FactStatus.APPROVED.value, "Active"]),
                or_(Fact.expires_at.is_(None), Fact.expires_at >= now)
            )
        else:
            query = query.filter(Fact.status == status)

    if expiring_soon:
        soon = now + timedelta(days=30)
        query = query.filter(Fact.expires_at.isnot(None), Fact.expires_at <= soon, Fact.expires_at >= now)

    if expired_only:
        query = query.filter(Fact.expires_at.isnot(None), Fact.expires_at < now)

    facts = query.order_by(Fact.updated_at.desc()).all()
    return [_format_fact(f) for f in facts]


@router.post("", response_model=FactOut)
def create_fact(
    fact_in: FactCreate,
    current_user: User = Depends(require_roles([UserRole.FACT_OWNER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Register an approved fact into the source of truth."""
    new_fact = Fact(
        organization_id=current_user.organization_id,
        owner_id=fact_in.owner_id or current_user.id,
        title=fact_in.title,
        canonical_value=fact_in.canonical_value,
        description=fact_in.description,
        source_reference=fact_in.source_reference,
        product_scope=fact_in.product_scope or "All",
        region_scope=fact_in.region_scope or "Global",
        channel_scope=fact_in.channel_scope or "All",
        valid_from=fact_in.valid_from,
        expires_at=fact_in.expires_at,
        status=fact_in.status.value if isinstance(fact_in.status, FactStatus) else str(fact_in.status),
    )
    db.add(new_fact)
    db.commit()
    db.refresh(new_fact)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="FACT_CREATED",
        entity_type="Fact",
        entity_id=new_fact.id,
        metadata={
            "title": new_fact.title,
            "canonical_value": new_fact.canonical_value,
            "source": new_fact.source_reference,
            "product_scope": new_fact.product_scope,
            "region_scope": new_fact.region_scope,
            "expires_at": str(new_fact.expires_at) if new_fact.expires_at else None,
        }
    )

    return _format_fact(new_fact)


@router.post("/import-csv", response_model=CsvImportResponse)
async def import_facts_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles([UserRole.FACT_OWNER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Batch import approved facts via CSV with validation and audit logging."""
    file_bytes = await read_upload_file_bounded(file, max_bytes=5 * 1024 * 1024)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")

    try:
        csv_text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_text = file_bytes.decode("latin-1")

    result = import_facts_from_csv(
        csv_content=csv_text,
        organization_id=current_user.organization_id,
        owner_id=current_user.id,
        db=db,
    )
    return CsvImportResponse(**result)


@router.get("/{fact_id}", response_model=FactOut)
def get_fact(
    fact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed information for a single fact."""
    fact = db.query(Fact).filter(
        Fact.id == fact_id,
        Fact.organization_id == current_user.organization_id
    ).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    return _format_fact(fact)


@router.put("/{fact_id}", response_model=FactOut)
def update_fact(
    fact_id: str,
    fact_in: FactUpdate,
    current_user: User = Depends(require_roles([UserRole.FACT_OWNER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Update an existing fact with change auditing."""
    fact = db.query(Fact).filter(
        Fact.id == fact_id,
        Fact.organization_id == current_user.organization_id
    ).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    old_values = {
        "title": fact.title,
        "canonical_value": fact.canonical_value,
        "source_reference": fact.source_reference,
        "status": fact.status,
        "product_scope": fact.product_scope,
        "expires_at": str(fact.expires_at) if fact.expires_at else None,
    }

    new_values = {}
    for field, val in fact_in.model_dump(exclude_unset=True).items():
        if val is not None:
            if field == "status" and isinstance(val, FactStatus):
                setattr(fact, field, val.value)
                new_values[field] = val.value
            else:
                setattr(fact, field, val)
                new_values[field] = str(val) if isinstance(val, datetime) else val

    db.commit()
    db.refresh(fact)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="FACT_UPDATED",
        entity_type="Fact",
        entity_id=fact.id,
        metadata={
            "fact_title": fact.title,
            "old_values": old_values,
            "new_values": new_values,
        }
    )

    return _format_fact(fact)


@router.put("/{fact_id}/archive", response_model=FactOut)
def archive_fact(
    fact_id: str,
    current_user: User = Depends(require_roles([UserRole.FACT_OWNER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Archive a fact so it is no longer used for verification."""
    fact = db.query(Fact).filter(
        Fact.id == fact_id,
        Fact.organization_id == current_user.organization_id
    ).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    fact.status = FactStatus.ARCHIVED.value
    db.commit()
    db.refresh(fact)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="FACT_ARCHIVED",
        entity_type="Fact",
        entity_id=fact.id,
        metadata={"title": fact.title}
    )

    return _format_fact(fact)


@router.delete("/{fact_id}")
def delete_fact(
    fact_id: str,
    current_user: User = Depends(require_roles([UserRole.FACT_OWNER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Permanently delete a fact from the database."""
    fact = db.query(Fact).filter(
        Fact.id == fact_id,
        Fact.organization_id == current_user.organization_id
    ).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    title = fact.title
    db.delete(fact)
    db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="FACT_DELETED",
        entity_type="Fact",
        entity_id=fact_id,
        metadata={"title": title}
    )

    return {"message": f"Fact '{title}' deleted successfully"}
