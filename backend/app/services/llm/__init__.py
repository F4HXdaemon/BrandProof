import os
from typing import Optional
from app.services.llm.base import (
    LLMProvider,
    ExtractedClaimProposal,
    ClaimAnalysisResult,
    ToneReviewResult,
    FixProposal,
)
from app.services.llm.fallback import DeterministicFallbackLLMProvider
from app.services.llm.diff_engine import compute_word_diff, compute_diff_stats
from app.services.llm.retrieval_service import retrieve_relevant_facts


_PROVIDER_INSTANCE: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """
    Returns the active LLMProvider instance.
    Defaults to DeterministicFallbackLLMProvider ensuring zero-key reliability.
    """
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is None:
        _PROVIDER_INSTANCE = DeterministicFallbackLLMProvider()
    return _PROVIDER_INSTANCE


__all__ = [
    "LLMProvider",
    "ExtractedClaimProposal",
    "ClaimAnalysisResult",
    "ToneReviewResult",
    "FixProposal",
    "DeterministicFallbackLLMProvider",
    "compute_word_diff",
    "compute_diff_stats",
    "retrieve_relevant_facts",
    "get_llm_provider",
]
