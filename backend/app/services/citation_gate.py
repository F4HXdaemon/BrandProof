"""
Central Citation Gate for BrandProof.

Core Rule: "NO VALID SOURCE = NO FINDING"
Every finding candidate emitted by any deterministic checker or AI model must pass
through CitationGate before being presented to a reviewer or persisted to the database.

Any candidate lacking an active, valid, scoped source record in the organization's
database is quarantined and discarded.
"""
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.models.knowledge import Fact, Rule, Term, Guideline, ApprovedAsset, FactStatus
from app.models.evidence import Evidence, EvidenceStatus
from app.services.rule_engine.base import FindingCandidate
from app.services.scoping_service import matches_scope, UNIVERSAL_PRODUCT_SCOPES, UNIVERSAL_REGION_SCOPES, UNIVERSAL_CHANNEL_SCOPES


VALID_SOURCE_TYPES = {"fact", "rule", "term", "guideline", "asset", "evidence"}


class CitationGate:
    def __init__(self, db: Session, organization_id: str):
        self.db = db
        self.organization_id = organization_id

    def validate_candidate(
        self,
        candidate: FindingCandidate,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates a candidate finding against the organization's knowledge base.
        Returns (is_valid, rejection_reason).
        """
        context = context or {}
        product = context.get("product")
        region = context.get("region")
        channel = context.get("channel")

        # 1. Non-blank source reference check
        if not candidate.source_reference or not candidate.source_reference.strip():
            return False, "Violation of cardinal principle: 'NO VALID SOURCE = NO FINDING'. Source reference is empty."

        # 2. Source type check
        source_type = (candidate.source_type or "").lower().strip()
        if source_type not in VALID_SOURCE_TYPES:
            # Allow fallback for standard WCAG accessibility rule
            if candidate.finding_type == "accessibility" and "wcag" in candidate.source_reference.lower():
                return True, None
            return False, f"Invalid source_type '{candidate.source_type}'. Must be one of: {VALID_SOURCE_TYPES}."

        # 3. Source ID presence check
        if not candidate.source_id or not str(candidate.source_id).strip():
            # Allow accessibility WCAG guideline if rule exists or fallback
            if candidate.finding_type == "accessibility" and "wcag" in candidate.source_reference.lower():
                return True, None
            return False, "Candidate missing source_id linking to approved knowledge base."

        # 4. Database existence and cross-org isolation check
        source_id = str(candidate.source_id).strip()
        source_obj = None

        if source_type == "fact":
            source_obj = self.db.query(Fact).filter(
                Fact.id == source_id,
                Fact.organization_id == self.organization_id
            ).first()
            if not source_obj:
                return False, f"Fact with id '{source_id}' does not exist in organization."
            # Status check
            if source_obj.status == FactStatus.ARCHIVED.value:
                return False, f"Fact '{source_obj.title}' is archived."
            if source_obj.status == FactStatus.DRAFT.value:
                return False, f"Fact '{source_obj.title}' is still in Draft state."
            if source_obj.is_expired and candidate.finding_type != "expired_fact":
                return False, f"Fact '{source_obj.title}' is expired; cannot cite as current truth."

        elif source_type == "rule":
            source_obj = self.db.query(Rule).filter(
                Rule.id == source_id,
                Rule.organization_id == self.organization_id
            ).first()
            if not source_obj:
                if candidate.finding_type == "accessibility" and "wcag" in source_id.lower():
                    return True, None
                return False, f"Rule with id '{source_id}' does not exist in organization."
            if not source_obj.active:
                return False, f"Rule '{source_obj.name}' is inactive."

        elif source_type == "term":
            source_obj = self.db.query(Term).filter(
                Term.id == source_id,
                Term.organization_id == self.organization_id
            ).first()
            if not source_obj:
                return False, f"Term with id '{source_id}' does not exist in organization."
            if not source_obj.active:
                return False, f"Term '{source_obj.term}' is inactive."

        elif source_type == "guideline":
            source_obj = self.db.query(Guideline).filter(
                Guideline.id == source_id,
                Guideline.organization_id == self.organization_id
            ).first()
            if not source_obj:
                return False, f"Guideline with id '{source_id}' does not exist in organization."
            if not source_obj.active:
                return False, f"Guideline '{source_obj.name}' is inactive."

        elif source_type == "asset":
            source_obj = self.db.query(ApprovedAsset).filter(
                ApprovedAsset.id == source_id,
                ApprovedAsset.organization_id == self.organization_id
            ).first()
            if not source_obj:
                return False, f"Approved asset with id '{source_id}' does not exist in organization."
            if not source_obj.active:
                return False, f"Approved asset '{source_obj.name}' is inactive."

        elif source_type == "evidence":
            source_obj = self.db.query(Evidence).filter(
                Evidence.id == source_id,
                Evidence.organization_id == self.organization_id
            ).first()
            if not source_obj:
                return False, f"Evidence with id '{source_id}' does not exist in organization."
            eff_status = source_obj.effective_status
            if eff_status == EvidenceStatus.INVALID.value:
                return False, f"Evidence '{source_obj.title}' is marked Invalid (validation error: {source_obj.validation_errors or 'content corrupted'})."
            if eff_status == EvidenceStatus.REJECTED.value:
                return False, f"Evidence '{source_obj.title}' is Rejected."
            if eff_status == EvidenceStatus.UNAVAILABLE.value:
                return False, f"Evidence '{source_obj.title}' is Unavailable in storage."
            if eff_status == EvidenceStatus.EXPIRED.value:
                return False, f"Evidence '{source_obj.title}' has expired; cannot cite as current valid support."

        # 5. Scoping check: does the source apply to the document's product, region, channel?
        if source_obj:
            prod_scope = getattr(source_obj, "product_scope", "All")
            reg_scope = getattr(source_obj, "region_scope", "Global")
            chan_scope = getattr(source_obj, "channel_scope", "All")

            if not matches_scope(prod_scope, product, UNIVERSAL_PRODUCT_SCOPES):
                return False, f"Source '{source_id}' is scoped to product '{prod_scope}', which does not match '{product}'."
            if not matches_scope(reg_scope, region, UNIVERSAL_REGION_SCOPES):
                return False, f"Source '{source_id}' is scoped to region '{reg_scope}', which does not match '{region}'."
            if not matches_scope(chan_scope, channel, UNIVERSAL_CHANNEL_SCOPES):
                return False, f"Source '{source_id}' is scoped to channel '{chan_scope}', which does not match '{channel}'."

        return True, None

    def validate_and_filter(
        self,
        candidates: List[FindingCandidate],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[FindingCandidate], List[Dict[str, Any]]]:
        """
        Filters a list of candidate findings through the CitationGate.
        Returns:
            (valid_candidates, quarantined_candidates)
        """
        valid: List[FindingCandidate] = []
        quarantined: List[Dict[str, Any]] = []

        for candidate in candidates:
            is_valid, reason = self.validate_candidate(candidate, context)
            if is_valid:
                valid.append(candidate)
            else:
                quarantined.append({
                    "candidate_title": candidate.title,
                    "finding_type": candidate.finding_type,
                    "source_reference": candidate.source_reference,
                    "source_id": candidate.source_id,
                    "rejection_reason": reason,
                })

        return valid, quarantined
