from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles, read_upload_file_bounded
from app.models.user import User, UserRole
from app.models.knowledge import Term
from app.schemas.knowledge import TermCreate, TermUpdate, TermOut, CsvImportResponse
from app.services.audit_service import record_audit_event
from app.services.csv_service import import_terms_from_csv

router = APIRouter(prefix="/terms", tags=["Terminology"])


@router.get("", response_model=List[TermOut])
def list_terms(
    q: Optional[str] = Query(None, description="Search term or variant"),
    product_scope: Optional[str] = Query(None),
    region_scope: Optional[str] = Query(None),
    channel_scope: Optional[str] = Query(None),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Term).filter(Term.organization_id == current_user.organization_id)
    if active_only:
        query = query.filter(Term.active == True)

    if q:
        search_fmt = f"%{q}%"
        query = query.filter(
            or_(
                Term.approved_term.ilike(search_fmt),
                Term.replacement.ilike(search_fmt),
                Term.notes.ilike(search_fmt),
            )
        )

    if product_scope and product_scope.lower() != "all":
        query = query.filter(Term.product_scope.ilike(f"%{product_scope}%"))

    if region_scope and region_scope.lower() not in ["all", "global"]:
        query = query.filter(Term.region_scope.ilike(f"%{region_scope}%"))

    if channel_scope and channel_scope.lower() != "all":
        query = query.filter(Term.channel_scope.ilike(f"%{channel_scope}%"))

    return query.order_by(Term.approved_term.asc()).all()


@router.post("", response_model=TermOut)
def create_term(
    term_in: TermCreate,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    new_term = Term(
        organization_id=current_user.organization_id,
        approved_term=term_in.approved_term,
        disallowed_variants=term_in.disallowed_variants,
        replacement=term_in.replacement or term_in.approved_term,
        notes=term_in.notes,
        product_scope=term_in.product_scope or "All",
        region_scope=term_in.region_scope or "Global",
        channel_scope=term_in.channel_scope or "All",
        status=term_in.status or "Approved",
        active=term_in.active,
    )
    db.add(new_term)
    db.commit()
    db.refresh(new_term)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="TERM_CREATED",
        entity_type="Term",
        entity_id=new_term.id,
        metadata={
            "term": new_term.approved_term,
            "disallowed_variants": new_term.disallowed_variants,
            "replacement": new_term.replacement,
        }
    )

    return new_term


@router.post("/import-csv", response_model=CsvImportResponse)
async def import_terms_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Batch import brand terminology via CSV."""
    file_bytes = await read_upload_file_bounded(file, max_bytes=5 * 1024 * 1024)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")

    try:
        csv_text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_text = file_bytes.decode("latin-1")

    result = import_terms_from_csv(
        csv_content=csv_text,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        db=db,
    )
    return CsvImportResponse(**result)


@router.get("/{term_id}", response_model=TermOut)
def get_term(
    term_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    term = db.query(Term).filter(
        Term.id == term_id,
        Term.organization_id == current_user.organization_id
    ).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    return term


@router.put("/{term_id}", response_model=TermOut)
def update_term(
    term_id: str,
    term_in: TermUpdate,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    term = db.query(Term).filter(
        Term.id == term_id,
        Term.organization_id == current_user.organization_id
    ).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    old_vals = {
        "approved_term": term.approved_term,
        "disallowed_variants": term.disallowed_variants,
        "replacement": term.replacement,
    }

    new_vals = {}
    for field, val in term_in.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(term, field, val)
            new_vals[field] = val

    db.commit()
    db.refresh(term)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="TERM_UPDATED",
        entity_type="Term",
        entity_id=term.id,
        metadata={
            "term": term.approved_term,
            "old_values": old_vals,
            "new_values": new_vals,
        }
    )

    return term


@router.put("/{term_id}/archive", response_model=TermOut)
def archive_term(
    term_id: str,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    term = db.query(Term).filter(
        Term.id == term_id,
        Term.organization_id == current_user.organization_id
    ).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    term.active = False
    term.status = "Archived"
    db.commit()
    db.refresh(term)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="TERM_ARCHIVED",
        entity_type="Term",
        entity_id=term.id,
        metadata={"term": term.approved_term}
    )

    return term


@router.delete("/{term_id}")
def delete_term(
    term_id: str,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    term = db.query(Term).filter(
        Term.id == term_id,
        Term.organization_id == current_user.organization_id
    ).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    approved = term.approved_term
    db.delete(term)
    db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="TERM_DELETED",
        entity_type="Term",
        entity_id=term_id,
        metadata={"term": approved}
    )

    return {"message": f"Term '{approved}' deleted successfully"}
