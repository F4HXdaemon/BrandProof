from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod


@dataclass
class FindingCandidate:
    finding_type: str  # terminology, disclaimer, forbidden_phrase, numeric_conflict, expired_fact, regex, tone, accessibility, asset
    severity: str  # Blocker, High, Warning, Info
    title: str
    message: str
    quoted_text: Optional[str] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    page_number: Optional[int] = None
    source_type: str = "rule"  # fact, rule, term, guideline, asset
    source_id: str = ""
    source_reference: str = ""
    suggested_replacement: Optional[str] = None
    checker: str = "RuleEngine"
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseRuleChecker(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def check(
        self,
        text: str,
        chunks: List[Any],
        context: Dict[str, Any],
        knowledge: Dict[str, Any],
    ) -> List[FindingCandidate]:
        """
        Executes checker against document text, chunks, context (product, region, channel)
        and applicable scoped knowledge base.
        """
        pass
