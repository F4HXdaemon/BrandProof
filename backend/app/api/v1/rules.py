from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.knowledge import Rule, SeverityLevel, RuleType
from app.schemas.knowledge import RuleCreate, RuleUpdate, RuleOut
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/rules", tags=["Rules"])


@router.get("", response_model=List[RuleOut])
def list_rules(
    rule_type: Optional[str] = Query(None, description="Filter by rule type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    product_scope: Optional[str] = Query(None),
    region_scope: Optional[str] = Query(None),
    channel_scope: Optional[str] = Query(None),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Rule).filter(Rule.organization_id == current_user.organization_id)
    if active_only:
        query = query.filter(Rule.active == True)
    if rule_type and rule_type.lower() != "all":
        query = query.filter(Rule.rule_type == rule_type.upper())
    if severity and severity.lower() != "all":
        query = query.filter(Rule.severity.ilike(f"%{severity}%"))
    if product_scope and product_scope.lower() != "all":
        query = query.filter(Rule.product_scope.ilike(f"%{product_scope}%"))
    if region_scope and region_scope.lower() not in ["all", "global"]:
        query = query.filter(Rule.region_scope.ilike(f"%{region_scope}%"))
    if channel_scope and channel_scope.lower() != "all":
        query = query.filter(Rule.channel_scope.ilike(f"%{channel_scope}%"))

    return query.order_by(Rule.name.asc()).all()


@router.post("", response_model=RuleOut)
def create_rule(
    rule_in: RuleCreate,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    new_rule = Rule(
        organization_id=current_user.organization_id,
        name=rule_in.name,
        description=rule_in.description,
        rule_type=rule_in.rule_type.value if isinstance(rule_in.rule_type, RuleType) else str(rule_in.rule_type),
        severity=rule_in.severity.value if isinstance(rule_in.severity, SeverityLevel) else str(rule_in.severity),
        configuration=rule_in.configuration,
        source_reference=rule_in.source_reference,
        product_scope=rule_in.product_scope or "All",
        region_scope=rule_in.region_scope or "Global",
        channel_scope=rule_in.channel_scope or "All",
        status=rule_in.status or "Approved",
        active=rule_in.active,
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="RULE_CREATED",
        entity_type="Rule",
        entity_id=new_rule.id,
        metadata={
            "name": new_rule.name,
            "rule_type": new_rule.rule_type,
            "severity": new_rule.severity,
            "product_scope": new_rule.product_scope,
        }
    )

    return new_rule


@router.get("/{rule_id}", response_model=RuleOut)
def get_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule = db.query(Rule).filter(
        Rule.id == rule_id,
        Rule.organization_id == current_user.organization_id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: str,
    rule_in: RuleUpdate,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    rule = db.query(Rule).filter(
        Rule.id == rule_id,
        Rule.organization_id == current_user.organization_id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    old_vals = {"name": rule.name, "rule_type": rule.rule_type, "severity": rule.severity}
    new_vals = {}

    for field, val in rule_in.model_dump(exclude_unset=True).items():
        if val is not None:
            if field == "severity" and isinstance(val, SeverityLevel):
                setattr(rule, field, val.value)
                new_vals[field] = val.value
            elif field == "rule_type" and isinstance(val, RuleType):
                setattr(rule, field, val.value)
                new_vals[field] = val.value
            else:
                setattr(rule, field, val)
                new_vals[field] = val

    db.commit()
    db.refresh(rule)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="RULE_UPDATED",
        entity_type="Rule",
        entity_id=rule.id,
        metadata={"name": rule.name, "old_values": old_vals, "new_values": new_vals}
    )

    return rule


@router.put("/{rule_id}/archive", response_model=RuleOut)
def archive_rule(
    rule_id: str,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    rule = db.query(Rule).filter(
        Rule.id == rule_id,
        Rule.organization_id == current_user.organization_id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.active = False
    rule.status = "Archived"
    db.commit()
    db.refresh(rule)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="RULE_ARCHIVED",
        entity_type="Rule",
        entity_id=rule.id,
        metadata={"name": rule.name}
    )

    return rule


@router.delete("/{rule_id}")
def delete_rule(
    rule_id: str,
    current_user: User = Depends(require_roles([UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    rule = db.query(Rule).filter(
        Rule.id == rule_id,
        Rule.organization_id == current_user.organization_id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    name = rule.name
    db.delete(rule)
    db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="RULE_DELETED",
        entity_type="Rule",
        entity_id=rule_id,
        metadata={"name": name}
    )

    return {"message": f"Rule '{name}' deleted successfully"}
