from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditEvent


def record_audit_event(
    db: Session,
    organization_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AuditEvent:
    """Record an immutable audit event for compliance tracking."""
    event = AuditEvent(
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        event_metadata=metadata or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
