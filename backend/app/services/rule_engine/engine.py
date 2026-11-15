from typing import List, Dict, Any, Optional
from app.services.rule_engine.base import BaseRuleChecker, FindingCandidate
from app.services.rule_engine.checkers import (
    TerminologyChecker,
    RequiredDisclaimerChecker,
    ForbiddenPhraseChecker,
    NumericClaimChecker,
    ExpiryChecker,
    RegexChecker,
    AccessibilityAndImageChecker,
)


class DeterministicRuleEngine:
    def __init__(self, checkers: Optional[List[BaseRuleChecker]] = None):
        if checkers is not None:
            self.checkers = checkers
        else:
            self.checkers = [
                TerminologyChecker(),
                RequiredDisclaimerChecker(),
                ForbiddenPhraseChecker(),
                NumericClaimChecker(),
                ExpiryChecker(),
                RegexChecker(),
                AccessibilityAndImageChecker(),
            ]

    def run_all(
        self,
        text: str,
        chunks: List[Any],
        context: Dict[str, Any],
        knowledge: Dict[str, Any],
    ) -> List[FindingCandidate]:
        """
        Executes all registered checkers deterministically against the document text, chunks,
        review context (product, region, channel), and scoped knowledge.
        Returns a aggregated list of FindingCandidate objects.
        """
        findings: List[FindingCandidate] = []
        if not text:
            return findings

        for checker in self.checkers:
            try:
                checker_candidates = checker.check(
                    text=text,
                    chunks=chunks,
                    context=context,
                    knowledge=knowledge,
                )
                findings.extend(checker_candidates)
            except Exception as e:
                # Log or handle checker exceptions gracefully so others continue
                print(f"Error running checker {checker.name}: {e}")

        return findings
