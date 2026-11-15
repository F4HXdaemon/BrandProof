import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.services.rule_engine.base import BaseRuleChecker, FindingCandidate
from app.services.scoping_service import matches_scope, UNIVERSAL_PRODUCT_SCOPES, UNIVERSAL_REGION_SCOPES, UNIVERSAL_CHANNEL_SCOPES


def _find_offsets_and_pages(text: str, match_str: str, chunks: List[Any], case_sensitive: bool = False):
    """Helper to locate start/end offsets and approximate page numbers."""
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(match_str), flags)
    matches = []
    for m in pattern.finditer(text):
        start, end = m.span()
        matched_text = m.group()
        # Find page number from chunks if available
        page_num = 1
        for chunk in chunks:
            chunk_text = getattr(chunk, "text", "") or ""
            if matched_text in chunk_text:
                page_num = getattr(chunk, "page_number", 1) or 1
                break
        matches.append((start, end, matched_text, page_num))
    return matches


class TerminologyChecker(BaseRuleChecker):
    @property
    def name(self) -> str:
        return "TerminologyChecker"

    def check(
        self,
        text: str,
        chunks: List[Any],
        context: Dict[str, Any],
        knowledge: Dict[str, Any],
    ) -> List[FindingCandidate]:
        candidates: List[FindingCandidate] = []
        terms = knowledge.get("terms", [])

        for term in terms:
            disallowed = term.disallowed_variants or []
            if isinstance(disallowed, str):
                disallowed = [v.strip() for v in disallowed.split(",") if v.strip()]

            # 1. Check disallowed variants
            for variant in disallowed:
                if not variant or not variant.strip():
                    continue
                variant_clean = variant.strip()
                # Word boundary search
                flags = 0 if term.case_sensitive else re.IGNORECASE
                pattern = re.compile(rf"\b{re.escape(variant_clean)}\b", flags)

                for m in pattern.finditer(text):
                    start, end = m.span()
                    matched_text = m.group()

                    # Determine page number
                    page_num = 1
                    for chunk in chunks:
                        if matched_text in (getattr(chunk, "text", "") or ""):
                            page_num = getattr(chunk, "page_number", 1) or 1
                            break

                    candidates.append(
                        FindingCandidate(
                            finding_type="terminology",
                            severity="Warning",
                            title=f"Disallowed Terminology: '{matched_text}'",
                            message=f"Use approved term '{term.term}' instead of disallowed variant '{matched_text}'.",
                            quoted_text=matched_text,
                            start_offset=start,
                            end_offset=end,
                            page_number=page_num,
                            source_type="term",
                            source_id=term.id,
                            source_reference=term.source_reference or f"Brand Terminology Guide § Term: {term.term}",
                            suggested_replacement=term.term,
                            checker=self.name,
                            confidence=1.0,
                            metadata={"canonical_term": term.term, "disallowed_variant": variant_clean}
                        )
                    )

            # 2. If case sensitive, check if canonical term itself was typed with wrong casing
            if term.case_sensitive:
                canonical = term.term.strip()
                pattern = re.compile(rf"\b{re.escape(canonical)}\b", re.IGNORECASE)
                for m in pattern.finditer(text):
                    matched_text = m.group()
                    if matched_text != canonical:
                        start, end = m.span()
                        candidates.append(
                            FindingCandidate(
                                finding_type="terminology",
                                severity="Warning",
                                title=f"Incorrect Casing: '{matched_text}'",
                                message=f"Approved brand term requires strict casing: '{canonical}'.",
                                quoted_text=matched_text,
                                start_offset=start,
                                end_offset=end,
                                page_number=1,
                                source_type="term",
                                source_id=term.id,
                                source_reference=term.source_reference or f"Brand Terminology Guide § Term: {canonical}",
                                suggested_replacement=canonical,
                                checker=self.name,
                                confidence=1.0,
                                metadata={"canonical_term": canonical}
                            )
                        )

        return candidates


class RequiredDisclaimerChecker(BaseRuleChecker):
    @property
    def name(self) -> str:
        return "RequiredDisclaimerChecker"

    def check(
        self,
        text: str,
        chunks: List[Any],
        context: Dict[str, Any],
        knowledge: Dict[str, Any],
    ) -> List[FindingCandidate]:
        candidates: List[FindingCandidate] = []
        rules = knowledge.get("rules", [])
        text_lower = text.lower()

        for rule in rules:
            r_type = (rule.rule_type or "").upper()
            config = rule.config or {}

            if r_type != "REQUIRED_DISCLAIMER" and config.get("type") != "required_disclaimer":
                continue

            disclaimer_text = config.get("disclaimer_text") or config.get("required_text") or rule.description
            if not disclaimer_text:
                continue

            # Check if disclaimer text or required key phrases are present
            disclaimer_lower = disclaimer_text.lower()
            key_phrases = config.get("key_phrases") or [disclaimer_lower]
            if isinstance(key_phrases, str):
                key_phrases = [key_phrases]

            # If any required key phrase is present, we consider it satisfied
            is_present = any(phrase.lower() in text_lower for phrase in key_phrases if phrase)

            if not is_present:
                candidates.append(
                    FindingCandidate(
                        finding_type="disclaimer",
                        severity=str(rule.severity.value if hasattr(rule.severity, "value") else (rule.severity or "Blocker")),
                        title=f"Missing Required Disclaimer: {rule.name}",
                        message=f"Mandatory disclaimer is missing: '{disclaimer_text}'. Required for channel '{context.get('channel', 'All')}' and region '{context.get('region', 'Global')}'.",
                        quoted_text=None,
                        start_offset=0,
                        end_offset=min(len(text), 100),
                        page_number=1,
                        source_type="rule",
                        source_id=rule.id,
                        source_reference=rule.source_reference or f"Brand Governance Rule: {rule.name}",
                        suggested_replacement=disclaimer_text,
                        checker=self.name,
                        confidence=1.0,
                        metadata={"rule_name": rule.name, "disclaimer_text": disclaimer_text}
                    )
                )

        return candidates


class ForbiddenPhraseChecker(BaseRuleChecker):
    @property
    def name(self) -> str:
        return "ForbiddenPhraseChecker"

    def check(
        self,
        text: str,
        chunks: List[Any],
        context: Dict[str, Any],
        knowledge: Dict[str, Any],
    ) -> List[FindingCandidate]:
        candidates: List[FindingCandidate] = []
        rules = knowledge.get("rules", [])

        for rule in rules:
            r_type = (rule.rule_type or "").upper()
            config = rule.config or {}

            if r_type != "FORBIDDEN_PHRASE" and config.get("type") != "forbidden_phrase":
                continue

            phrases = config.get("phrases") or []
            if isinstance(phrases, str):
                phrases = [p.strip() for p in phrases.split(",") if p.strip()]
            if not phrases and config.get("phrase"):
                phrases = [config.get("phrase")]
            if not phrases and rule.name:
                phrases = [rule.name]

            replacement = config.get("suggested_replacement") or "Delete or qualify statement"

            for phrase in phrases:
                if not phrase or not phrase.strip():
                    continue
                clean_phrase = phrase.strip()
                pattern = re.compile(rf"\b{re.escape(clean_phrase)}\b", re.IGNORECASE)

                for m in pattern.finditer(text):
                    start, end = m.span()
                    matched_text = m.group()

                    page_num = 1
                    for chunk in chunks:
                        if matched_text in (getattr(chunk, "text", "") or ""):
                            page_num = getattr(chunk, "page_number", 1) or 1
                            break

                    candidates.append(
                        FindingCandidate(
                            finding_type="forbidden_phrase",
                            severity=str(rule.severity.value if hasattr(rule.severity, "value") else (rule.severity or "Blocker")),
                            title=f"Forbidden Phrase: '{matched_text}'",
                            message=rule.description or f"Forbidden phrase '{matched_text}' is prohibited by brand compliance policy.",
                            quoted_text=matched_text,
                            start_offset=start,
                            end_offset=end,
                            page_number=page_num,
                            source_type="rule",
                            source_id=rule.id,
                            source_reference=rule.source_reference or f"Brand Governance Rule: {rule.name}",
                            suggested_replacement=replacement,
                            checker=self.name,
                            confidence=1.0,
                            metadata={"forbidden_phrase": clean_phrase}
                        )
                    )

        return candidates


class NumericClaimChecker(BaseRuleChecker):
    @property
    def name(self) -> str:
        return "NumericClaimChecker"

    def check(
        self,
        text: str,
        chunks: List[Any],
        context: Dict[str, Any],
        knowledge: Dict[str, Any],
    ) -> List[FindingCandidate]:
        candidates: List[FindingCandidate] = []
        facts = knowledge.get("facts", [])

        # Common metric patterns: percentages, latency, currency, counts
        pct_regex = re.compile(r"(\b\d{1,3}(?:\.\d+)?\s*%)", re.IGNORECASE)

        for fact in facts:
            canonical = fact.canonical_value.strip()
            # If canonical value is or contains a percentage (e.g. "99.95%")
            pct_canonical_match = pct_regex.search(canonical)
            if pct_canonical_match:
                canonical_pct = pct_canonical_match.group(1).replace(" ", "")
                # Find all percentages in text within relevant context
                for m in pct_regex.finditer(text):
                    found_pct = m.group(1).replace(" ", "")
                    # Look at surrounding 100 characters to determine if context matches fact topic
                    start_ctx = max(0, m.start() - 60)
                    end_ctx = min(len(text), m.end() + 60)
                    window = text[start_ctx:end_ctx].lower()

                    # Check if window relates to the fact title or keywords
                    title_words = [w.lower() for w in re.split(r"\W+", fact.title) if len(w) > 3]
                    matches_topic = any(w in window for w in title_words) or ("uptime" in window and "uptime" in fact.title.lower()) or ("sla" in window and "sla" in fact.title.lower()) or ("accuracy" in window and "accuracy" in fact.title.lower())

                    if matches_topic and found_pct != canonical_pct:
                        # Direct numerical conflict!
                        start, end = m.span()
                        matched_text = text[max(0, m.start() - 20):min(len(text), m.end() + 20)].strip()
                        candidates.append(
                            FindingCandidate(
                                finding_type="numeric_conflict",
                                severity="Blocker",
                                title=f"Factual Numeric Conflict: '{fact.title}'",
                                message=f"Claimed metric '{found_pct}' contradicts approved canonical value '{canonical}' for '{fact.title}'.",
                                quoted_text=m.group(1),
                                start_offset=start,
                                end_offset=end,
                                page_number=1,
                                source_type="fact",
                                source_id=fact.id,
                                source_reference=fact.source_reference,
                                suggested_replacement=canonical,
                                checker=self.name,
                                confidence=1.0,
                                metadata={"canonical": canonical, "claimed": found_pct}
                            )
                        )

            # Check exact string conflicts for short canonical values (e.g. "$1.2B" vs "$1.5B" or "500ms")
            num_unit_regex = re.compile(r"(\$?\d+(?:\.\d+)?\s*(?:ms|s|GB|TB|users|million|billion)?)", re.IGNORECASE)
            canon_match = num_unit_regex.search(canonical)
            if canon_match and len(canon_match.group(1).strip()) > 2 and canon_match.group(1).strip() != canonical_pct if pct_canonical_match else True:
                canon_val = canon_match.group(1).strip().lower()
                # If fact topic is present in text but with a different number
                title_words = [w.lower() for w in re.split(r"\W+", fact.title) if len(w) > 3]
                for tw in title_words:
                    if tw in text.lower():
                        # Search near this word
                        idx = text.lower().find(tw)
                        window = text[max(0, idx - 80):min(len(text), idx + 120)]
                        for num_m in num_unit_regex.finditer(window):
                            claimed_val = num_m.group(1).strip().lower()
                            if claimed_val and claimed_val != canon_val and len(claimed_val) > 2:
                                # Candidate conflict
                                pass

        return candidates


class ExpiryChecker(BaseRuleChecker):
    @property
    def name(self) -> str:
        return "ExpiryChecker"

    def check(
        self,
        text: str,
        chunks: List[Any],
        context: Dict[str, Any],
        knowledge: Dict[str, Any],
    ) -> List[FindingCandidate]:
        candidates: List[FindingCandidate] = []
        expired_facts = knowledge.get("expired_facts_excluded", [])

        for fact in expired_facts:
            # Check if canonical value or distinctive title phrase is cited in text
            canonical = fact.canonical_value.strip()
            if canonical and canonical.lower() in text.lower():
                idx = text.lower().find(canonical.lower())
                start = idx
                end = idx + len(canonical)
                matched_text = text[start:end]

                exp_str = fact.expires_at.strftime("%Y-%m-%d") if getattr(fact, "expires_at", None) else "past date"
                candidates.append(
                    FindingCandidate(
                        finding_type="expired_fact",
                        severity="High",
                        title=f"Expired Fact Cited: '{fact.title}'",
                        message=f"Fact '{fact.title}' expired on {exp_str}. Citing expired claims is prohibited by governance policy.",
                        quoted_text=matched_text,
                        start_offset=start,
                        end_offset=end,
                        page_number=1,
                        source_type="fact",
                        source_id=fact.id,
                        source_reference=fact.source_reference,
                        suggested_replacement="Update or verify claim against current knowledge base",
                        checker=self.name,
                        confidence=1.0,
                        metadata={"fact_id": fact.id, "expired_at": exp_str}
                    )
                )

        return candidates


class RegexChecker(BaseRuleChecker):
    @property
    def name(self) -> str:
        return "RegexChecker"

    def check(
        self,
        text: str,
        chunks: List[Any],
        context: Dict[str, Any],
        knowledge: Dict[str, Any],
    ) -> List[FindingCandidate]:
        candidates: List[FindingCandidate] = []
        rules = knowledge.get("rules", [])

        for rule in rules:
            r_type = (rule.rule_type or "").upper()
            config = rule.config or {}

            if r_type != "REGEX" and config.get("type") != "regex":
                continue

            pattern_str = config.get("pattern")
            if not pattern_str:
                continue

            try:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                for m in pattern.finditer(text[:50000]):  # bounded length for safety
                    start, end = m.span()
                    matched_text = m.group()

                    candidates.append(
                        FindingCandidate(
                            finding_type="regex",
                            severity=str(rule.severity.value if hasattr(rule.severity, "value") else (rule.severity or "Warning")),
                            title=f"Regex Rule Violation: {rule.name}",
                            message=rule.description or f"Text matches prohibited regex pattern '{pattern_str}'.",
                            quoted_text=matched_text,
                            start_offset=start,
                            end_offset=end,
                            page_number=1,
                            source_type="rule",
                            source_id=rule.id,
                            source_reference=rule.source_reference or f"Brand Governance Rule: {rule.name}",
                            suggested_replacement=config.get("suggested_replacement"),
                            checker=self.name,
                            confidence=1.0,
                            metadata={"pattern": pattern_str}
                        )
                    )
            except Exception:
                continue

        return candidates


class AccessibilityAndImageChecker(BaseRuleChecker):
    @property
    def name(self) -> str:
        return "AccessibilityAndImageChecker"

    def check(
        self,
        text: str,
        chunks: List[Any],
        context: Dict[str, Any],
        knowledge: Dict[str, Any],
    ) -> List[FindingCandidate]:
        candidates: List[FindingCandidate] = []
        rules = knowledge.get("rules", [])
        accessibility_rule = next((r for r in rules if (r.rule_type or "").upper() == "ACCESSIBILITY"), None)

        # Markdown image detection: ![alt](url)
        img_pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")
        for m in img_pattern.finditer(text):
            alt_text = m.group(1).strip()
            img_url = m.group(2).strip()
            start, end = m.span()

            # WCAG 1.1.1 Non-text Content: Check for missing or placeholder alt text
            if not alt_text or alt_text.lower() in {"image", "img", "photo", "screenshot", "picture"}:
                source_ref = accessibility_rule.source_reference if accessibility_rule else "WCAG 2.1 §1.1.1 Non-text Content (Level A)"
                source_id = accessibility_rule.id if accessibility_rule else "wcag-1.1.1"
                candidates.append(
                    FindingCandidate(
                        finding_type="accessibility",
                        severity="Warning",
                        title="Missing Alt Text for Image",
                        message=f"Image '{img_url}' is missing meaningful alternative text. Non-text content must provide text alternatives for WCAG compliance.",
                        quoted_text=m.group(0),
                        start_offset=start,
                        end_offset=end,
                        page_number=1,
                        source_type="rule" if accessibility_rule else "guideline",
                        source_id=source_id,
                        source_reference=source_ref,
                        suggested_replacement=f"![Descriptive explanation of image content]({img_url})",
                        checker=self.name,
                        confidence=1.0,
                        metadata={"image_url": img_url, "alt_text": alt_text}
                    )
                )

        return candidates
