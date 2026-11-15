from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod


@dataclass
class ExtractedClaimProposal:
    claim_text: str
    claim_type: str  # Numeric, Certification, Product capability, Comparative, Superlative, Guarantee, General factual
    page_number: int = 1
    paragraph_number: int = 1
    confidence: float = 1.0
    location_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaimAnalysisResult:
    claim_text: str
    status: str  # SUPPORTED, CONFLICTS, EXPIRED, OUT_OF_SCOPE, UNSUPPORTED
    matched_fact_id: Optional[str] = None
    reasoning: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ToneReviewResult:
    guideline_id: str
    principle: str
    violation_snippet: str
    reasoning: str
    suggested_fix: Optional[str] = None
    severity: str = "Warning"


@dataclass
class FixProposal:
    original_text: str
    replacement_text: str
    explanation: str


class LLMProvider(ABC):
    @abstractmethod
    def extract_claims(self, text: str) -> List[ExtractedClaimProposal]:
        """Extracts factual and compliance claims from document text."""
        pass

    @abstractmethod
    def analyze_claim_against_facts(
        self,
        claim: str,
        facts: List[Any],
        context: Dict[str, Any],
    ) -> ClaimAnalysisResult:
        """Evaluates a claim against approved facts and outputs status with source citation."""
        pass

    @abstractmethod
    def review_tone(
        self,
        text: str,
        guidelines: List[Any],
    ) -> List[ToneReviewResult]:
        """Evaluates text tone against brand guidelines and DO/DON'T examples."""
        pass

    @abstractmethod
    def generate_intent_preserving_fix(
        self,
        original_text: str,
        finding_message: str,
        approved_truth: str,
    ) -> FixProposal:
        """Generates a minimal, intent-preserving surgical fix for a finding."""
        pass
