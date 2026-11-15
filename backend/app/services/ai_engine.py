from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class ExtractedClaimProposal(BaseModel):
    text: str
    location_metadata: Dict[str, Any]
    confidence: float = 0.95


class ProposedFinding(BaseModel):
    claim_text: Optional[str] = None
    rule_id: Optional[str] = None
    guideline_id: Optional[str] = None
    fact_id: Optional[str] = None
    severity: str
    message: str
    suggestion: Optional[str] = None
    source_reference: str  # Critical invariant: "NO VALID SOURCE = NO FINDING"


class AnalysisEngineInterface(ABC):
    """
    BrandProof AI Analysis Engine Interface.

    Principles:
    1. AI proposes.
    2. Evidence decides.
    3. People approve.
    4. NO VALID SOURCE = NO FINDING.
    5. AI must never be the final approver.
    """

    @abstractmethod
    def extract_claims(self, document_text: str) -> List[ExtractedClaimProposal]:
        """Extract factual, statistical, performance, or capability claims from document text."""
        pass

    @abstractmethod
    def evaluate_claims(
        self,
        claims: List[ExtractedClaimProposal],
        approved_facts: List[Any],
        guidelines: List[Any],
        terms: List[Any],
        rules: List[Any]
    ) -> List[ProposedFinding]:
        """
        Evaluate extracted claims against the approved Source of Truth.
        Every finding must link strictly to an approved source reference.
        """
        pass


class PlaceholderAnalysisEngine(AnalysisEngineInterface):
    """
    Foundation implementation and clean placeholder for subsequent AI engine prompt phases.
    Allows testing full end-to-end review lifecycle with deterministic governance checks.
    """

    def extract_claims(self, document_text: str) -> List[ExtractedClaimProposal]:
        # Extension point: plug in LLM extraction prompt or NLP claim boundary detection
        claims: List[ExtractedClaimProposal] = []
        lines = [line.strip() for line in document_text.split("\n") if line.strip()]
        for idx, line in enumerate(lines[:10]):
            # If line mentions statistics, SLAs, or product capabilities
            if any(term in line.lower() for term in ["%", "sla", "guarantee", "fastest", "unlimited", "soc", "uptime"]):
                claims.append(ExtractedClaimProposal(
                    text=line,
                    location_metadata={"line_number": idx + 1, "source_type": "paragraph"},
                    confidence=0.92
                ))
        return claims

    def evaluate_claims(
        self,
        claims: List[ExtractedClaimProposal],
        approved_facts: List[Any],
        guidelines: List[Any],
        terms: List[Any],
        rules: List[Any]
    ) -> List[ProposedFinding]:
        # Extension point: plug in semantic vector retrieval & multi-stage guideline verifier
        findings: List[ProposedFinding] = []
        return findings


def get_analysis_engine() -> AnalysisEngineInterface:
    return PlaceholderAnalysisEngine()
