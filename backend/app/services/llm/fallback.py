import re
from typing import List, Dict, Any, Optional
from app.services.llm.base import (
    LLMProvider,
    ExtractedClaimProposal,
    ClaimAnalysisResult,
    ToneReviewResult,
    FixProposal,
)
from app.models.review import ClaimStatus
from app.services.scoping_service import matches_scope, UNIVERSAL_PRODUCT_SCOPES, UNIVERSAL_REGION_SCOPES, UNIVERSAL_CHANNEL_SCOPES


class DeterministicFallbackLLMProvider(LLMProvider):
    """
    Zero-key, offline, deterministic fallback LLM provider.
    Ensures 100% reliable execution during hackathons and test runs without external API keys.
    """

    def extract_claims(self, text: str) -> List[ExtractedClaimProposal]:
        if not text:
            return []

        proposals: List[ExtractedClaimProposal] = []
        # Split text into paragraphs and sentences
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        claim_patterns = [
            ("Numeric", re.compile(r"(\b\d+(?:\.\d+)?%|\$\d+(?:\.\d+)?[MBKmbk]?|\b\d+\s*(?:ms|days|hours|years|GB|TB|PB|users|customers)\b)", re.IGNORECASE)),
            ("Superlative", re.compile(r"\b(best-in-class|unmatched|fastest|highest|industry-leading|flawless|unbreakable|zero downtime|infinitely scalable)\b", re.IGNORECASE)),
            ("Guarantee", re.compile(r"\b(guaranteed|guarantees|100% secure|absolute guarantee|warranted)\b", re.IGNORECASE)),
            ("Comparative", re.compile(r"\b(faster than|superior to|better than|twice as|outperforms|cheaper than)\b", re.IGNORECASE)),
            ("Certification", re.compile(r"\b(SOC 2|ISO 27001|HIPAA|GDPR|PCI-DSS|FedRAMP|certified|accredited)\b", re.IGNORECASE)),
            ("Product capability", re.compile(r"\b(supports|provides|features|encrypts|integrates with|automates)\b", re.IGNORECASE)),
        ]

        for p_idx, para in enumerate(paragraphs, start=1):
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for s_idx, sentence in enumerate(sentences):
                sentence_clean = sentence.strip()
                if len(sentence_clean) < 10:
                    continue

                matched_type = "General factual"
                for c_type, pattern in claim_patterns:
                    if pattern.search(sentence_clean):
                        matched_type = c_type
                        break

                # If sentence contains a claim keyword or is declarative with metrics/facts
                if matched_type != "General factual" or any(w in sentence_clean.lower() for w in ["we offer", "our platform", "system delivers"]):
                    proposals.append(
                        ExtractedClaimProposal(
                            claim_text=sentence_clean,
                            claim_type=matched_type,
                            page_number=1,
                            paragraph_number=p_idx,
                            confidence=0.95 if matched_type != "General factual" else 0.8,
                            location_metadata={"paragraph": p_idx, "sentence": s_idx + 1}
                        )
                    )

        return proposals

    def analyze_claim_against_facts(
        self,
        claim: str,
        facts: List[Any],
        context: Dict[str, Any],
    ) -> ClaimAnalysisResult:
        claim_lower = claim.lower()
        product = context.get("product")
        region = context.get("region")
        channel = context.get("channel")

        # 1. Search for a matching fact by keywords and numbers
        best_fact = None
        best_score = 0.0

        claim_tokens = set(re.findall(r"\w+", claim_lower))

        for fact in facts:
            fact_tokens = set(re.findall(r"\w+", fact.title.lower() + " " + fact.canonical_value.lower()))
            overlap = len(claim_tokens.intersection(fact_tokens))
            if overlap > best_score:
                best_score = overlap
                best_fact = fact

        if not best_fact or best_score < 2:
            return ClaimAnalysisResult(
                claim_text=claim,
                status=ClaimStatus.UNSUPPORTED.value,
                matched_fact_id=None,
                reasoning="No approved source in the knowledge base substantiates this claim. (Rule: NO VALID SOURCE = NO FINDING)",
                confidence=0.85
            )

        # 2. Check Expiration
        if getattr(best_fact, "is_expired", False):
            exp_date = best_fact.expires_at.strftime("%Y-%m-%d") if getattr(best_fact, "expires_at", None) else "past date"
            return ClaimAnalysisResult(
                claim_text=claim,
                status=ClaimStatus.EXPIRED.value,
                matched_fact_id=best_fact.id,
                reasoning=f"Matched approved fact '{best_fact.title}', but the fact expired on {exp_date}.",
                confidence=0.98
            )

        # 3. Check Scoping
        prod_in_scope = matches_scope(best_fact.product_scope, product, UNIVERSAL_PRODUCT_SCOPES)
        reg_in_scope = matches_scope(best_fact.region_scope, region, UNIVERSAL_REGION_SCOPES)
        chan_in_scope = matches_scope(best_fact.channel_scope, channel, UNIVERSAL_CHANNEL_SCOPES)

        if not (prod_in_scope and reg_in_scope and chan_in_scope):
            return ClaimAnalysisResult(
                claim_text=claim,
                status=ClaimStatus.OUT_OF_SCOPE.value,
                matched_fact_id=best_fact.id,
                reasoning=f"Fact '{best_fact.title}' is valid only for Product '{best_fact.product_scope}', Region '{best_fact.region_scope}', Channel '{best_fact.channel_scope}', which does not apply to this review context.",
                confidence=0.95
            )

        # 4. Check for Numeric / Value Conflict
        pct_regex = re.compile(r"(\b\d{1,3}(?:\.\d+)?\s*%)")
        canon_pcts = pct_regex.findall(best_fact.canonical_value)
        claim_pcts = pct_regex.findall(claim)

        if canon_pcts and claim_pcts:
            canon_val = canon_pcts[0].replace(" ", "")
            claim_val = claim_pcts[0].replace(" ", "")
            if canon_val != claim_val:
                return ClaimAnalysisResult(
                    claim_text=claim,
                    status=ClaimStatus.CONFLICTS.value,
                    matched_fact_id=best_fact.id,
                    reasoning=f"Claimed metric '{claim_val}' contradicts approved canonical value '{canon_val}' for '{best_fact.title}'.",
                    confidence=1.0
                )

        # 5. Otherwise Supported
        return ClaimAnalysisResult(
            claim_text=claim,
            status=ClaimStatus.SUPPORTED.value,
            matched_fact_id=best_fact.id,
            reasoning=f"Verified and supported by approved fact '{best_fact.title}' [Ref: {best_fact.source_reference}].",
            confidence=0.95
        )

    def review_tone(
        self,
        text: str,
        guidelines: List[Any],
    ) -> List[ToneReviewResult]:
        results: List[ToneReviewResult] = []
        text_lower = text.lower()

        for g in guidelines:
            donts = getattr(g, "dont_examples", []) or []
            if isinstance(donts, str):
                donts = [donts]

            # Check explicit DON'T examples
            for example in donts:
                if not example or not example.strip():
                    continue
                ex_clean = example.strip().lower()
                if ex_clean in text_lower:
                    idx = text_lower.find(ex_clean)
                    actual_snippet = text[idx:idx + len(ex_clean)]
                    suggested = None
                    dos = getattr(g, "do_examples", []) or []
                    if dos and len(dos) > 0:
                        suggested = dos[0]

                    results.append(
                        ToneReviewResult(
                            guideline_id=g.id,
                            principle=getattr(g, "principle", "") or g.name,
                            violation_snippet=actual_snippet,
                            reasoning=f"Document contains phrasing '{actual_snippet}' explicitly listed as a DON'T in guideline '{g.name}'.",
                            suggested_fix=suggested,
                            severity="Warning"
                        )
                    )

            # Check generic hyperbolic tone terms if guideline is tone/voice
            if any(k in g.name.lower() for k in ["tone", "voice", "style"]):
                hyperbolic_words = ["miraculous", "cheap as dirt", "insanely fast", "world's best"]
                for hw in hyperbolic_words:
                    if hw in text_lower:
                        idx = text_lower.find(hw)
                        actual_snippet = text[idx:idx + len(hw)]
                        results.append(
                            ToneReviewResult(
                                guideline_id=g.id,
                                principle=getattr(g, "principle", "") or g.name,
                                violation_snippet=actual_snippet,
                                reasoning=f"Phrasing '{actual_snippet}' violates professional brand tone principle: '{g.name}'.",
                                suggested_fix="Use objective, professional tone without sensationalism",
                                severity="Warning"
                            )
                        )

        return results

    def generate_intent_preserving_fix(
        self,
        original_text: str,
        finding_message: str,
        approved_truth: str,
    ) -> FixProposal:
        if not original_text:
            return FixProposal(original_text="", replacement_text="", explanation="Empty input")

        # Minimal intent-preserving substitution
        replacement = original_text
        if approved_truth and approved_truth.strip():
            # If approved truth is a canonical term or metric
            clean_truth = approved_truth.strip()
            # If original contains forbidden phrase or disallowed term
            # Replace target token
            replacement = re.sub(
                r"(\b\d+(?:\.\d+)?%|guaranteed|guarantees|100%|best-in-class)",
                clean_truth,
                original_text,
                flags=re.IGNORECASE,
                count=1
            )
            if replacement == original_text:
                # Append or prepend approved truth
                replacement = f"{original_text} ({clean_truth})"

        return FixProposal(
            original_text=original_text,
            replacement_text=replacement,
            explanation=f"Surgically aligned with approved source of truth: '{approved_truth}' while preserving original marketing intent."
        )
