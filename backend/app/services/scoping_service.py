from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.knowledge import Fact, Guideline, Term, Rule, FactStatus


UNIVERSAL_PRODUCT_SCOPES = {"all", "all products", "global"}
UNIVERSAL_REGION_SCOPES = {"all", "global", "all regions"}
UNIVERSAL_CHANNEL_SCOPES = {"all", "all channels", "global"}


def matches_scope(item_scope: Optional[str], target_scope: Optional[str], universal_set: set) -> bool:
    """
    Determines if an item's scope matches the target scope.
    An item applies if its scope is universal or if it matches the target.
    """
    if not item_scope:
        return True

    clean_item = item_scope.strip().lower()
    if clean_item in universal_set:
        return True

    if not target_scope or target_scope.strip().lower() in universal_set:
        # If target didn't specify or specified universal, universal items apply
        return True

    clean_target = target_scope.strip().lower()

    # Support comma-separated scopes e.g. "Pro, Enterprise"
    item_parts = [p.strip() for p in clean_item.split(",")]
    if clean_target in item_parts:
        return True

    # Partial word matching e.g. "Northstar Pro" matches "Pro"
    for part in item_parts:
        if clean_target in part or part in clean_target:
            return True

    return False


def get_applicable_knowledge(
    db: Session,
    organization_id: str,
    product: Optional[str] = None,
    region: Optional[str] = None,
    channel: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Filters and returns approved, active, and non-expired knowledge applicable
    to the given Product, Region, and Channel.
    """
    now = datetime.now(timezone.utc)

    # 1. Query Facts
    raw_facts = db.query(Fact).filter(
        Fact.organization_id == organization_id,
        Fact.status.in_([FactStatus.APPROVED.value, "Approved", "Active"])
    ).all()

    applicable_facts = []
    expired_facts = []

    for f in raw_facts:
        # Dynamic expiration check
        if f.is_expired:
            expired_facts.append(f)
            continue

        if not matches_scope(f.product_scope, product, UNIVERSAL_PRODUCT_SCOPES):
            continue
        if not matches_scope(f.region_scope, region, UNIVERSAL_REGION_SCOPES):
            continue
        if not matches_scope(f.channel_scope, channel, UNIVERSAL_CHANNEL_SCOPES):
            continue

        applicable_facts.append(f)

    # 2. Query Guidelines
    raw_guidelines = db.query(Guideline).filter(
        Guideline.organization_id == organization_id,
        Guideline.active == True
    ).all()

    applicable_guidelines = [
        g for g in raw_guidelines
        if matches_scope(g.product_scope, product, UNIVERSAL_PRODUCT_SCOPES)
        and matches_scope(g.region_scope, region, UNIVERSAL_REGION_SCOPES)
        and matches_scope(g.channel_scope, channel, UNIVERSAL_CHANNEL_SCOPES)
    ]

    # 3. Query Terminology
    raw_terms = db.query(Term).filter(
        Term.organization_id == organization_id,
        Term.active == True
    ).all()

    applicable_terms = [
        t for t in raw_terms
        if matches_scope(t.product_scope, product, UNIVERSAL_PRODUCT_SCOPES)
        and matches_scope(t.region_scope, region, UNIVERSAL_REGION_SCOPES)
        and matches_scope(t.channel_scope, channel, UNIVERSAL_CHANNEL_SCOPES)
    ]

    # 4. Query Rules
    raw_rules = db.query(Rule).filter(
        Rule.organization_id == organization_id,
        Rule.active == True
    ).all()

    applicable_rules = [
        r for r in raw_rules
        if matches_scope(r.product_scope, product, UNIVERSAL_PRODUCT_SCOPES)
        and matches_scope(r.region_scope, region, UNIVERSAL_REGION_SCOPES)
        and matches_scope(r.channel_scope, channel, UNIVERSAL_CHANNEL_SCOPES)
    ]

    return {
        "scopes": {
            "product": product or "All",
            "region": region or "Global",
            "channel": channel or "All",
        },
        "counts": {
            "facts": len(applicable_facts),
            "guidelines": len(applicable_guidelines),
            "terms": len(applicable_terms),
            "rules": len(applicable_rules),
            "expired_facts_excluded": len(expired_facts),
        },
        "facts": applicable_facts,
        "guidelines": applicable_guidelines,
        "terms": applicable_terms,
        "rules": applicable_rules,
        "expired_facts_excluded": expired_facts,
    }
