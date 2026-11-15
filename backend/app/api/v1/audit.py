from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.audit import AuditEvent
from app.schemas.document_and_review import AuditEventOut

router = APIRouter(prefix="/audit", tags=["Audit Log"])


@router.get("", response_model=List[AuditEventOut])
def list_audit_events(
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(AuditEvent).filter(AuditEvent.organization_id == current_user.organization_id)
    if action:
        query = query.filter(AuditEvent.action.ilike(f"%{action}%"))
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)

    events = query.order_by(AuditEvent.timestamp.desc()).offset(offset).limit(limit).all()

    results = []
    for e in events:
        out = AuditEventOut(
            id=e.id,
            organization_id=e.organization_id,
            actor_id=e.actor_id,
            actor_name=e.actor.full_name if e.actor else "System Governance",
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            metadata=e.event_metadata or {},
            timestamp=e.timestamp,
        )
        results.append(out)
    return results
