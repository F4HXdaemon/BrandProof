import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def parse_knowledge_proposals(
    text: str,
    filename: str,
    evidence_id: Optional[str] = None,
    target_category: Optional[str] = "all",
) -> Dict[str, Any]:
    """
    Parses extracted text from uploaded documents or images into structured candidate
    knowledge proposals for human review and approval.
    Categories supported:
      - facts (Approved Facts)
      - guidelines (Brand Guidelines & Voice)
      - terms (Terminology & Glossaries)
      - rules (Deterministic Governance Rules)
    """
    clean_text = (text or "").strip()
    source_ref = f"Evidence [{filename}]" if filename else "Uploaded Document Evidence"
    if evidence_id:
        source_ref = f"{source_ref} (ID: {evidence_id[:8]})"

    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    if not paragraphs and clean_text:
        paragraphs = [clean_text]

    # Split into candidate sentences
    sentences: List[str] = []
    for p in paragraphs:
        for s in re.split(r"(?<=[.!?])\s+", p):
            s_clean = s.strip()
            if len(s_clean) > 8:
                sentences.append(s_clean)

    # 1. Facts Extraction
    suggested_facts: List[Dict[str, Any]] = []
    # Patterns for metric statements, numbers, percentages, certifications, guarantees
    metric_pattern = re.compile(
        r"(\b\d+(?:\.\d+)?%|\$\d+(?:\.\d+)?[MBKmbk]?|\b\d+\s*(?:ms|days|hours|minutes|seconds|years|GB|TB|users|customers)\b|99\.\d+%)",
        re.IGNORECASE
    )
    cert_pattern = re.compile(r"\b(ISO\s*27001|SOC\s*2|HIPAA|GDPR|PCI-DSS|FedRAMP|certified|accredited)\b", re.IGNORECASE)
    sla_pattern = re.compile(r"\b(uptime|SLA|latency|speed|performance|throughput|accuracy)\b", re.IGNORECASE)

    for idx, sent in enumerate(sentences):
        has_metric = metric_pattern.search(sent)
        has_cert = cert_pattern.search(sent)
        has_sla = sla_pattern.search(sent)

        if has_metric or has_cert or has_sla:
            # Generate concise title
            first_words = sent.split()[:5]
            title_candidate = " ".join(first_words)
            if len(title_candidate) > 40:
                title_candidate = title_candidate[:37] + "..."

            # Deduce product if mentioned
            product = "All"
            for prod in ["Northstar Pro", "Apex Cloud", "Sovereign Cloud", "Enterprise", "Starter"]:
                if prod.lower() in sent.lower():
                    product = prod
                    break

            # Deduce region
            region = "Global"
            for reg in ["India", "US", "EU", "APAC", "EMEA", "UK"]:
                if reg.lower() in sent.lower():
                    region = reg
                    break

            suggested_facts.append({
                "title": f"Fact: {title_candidate}",
                "canonical_value": sent,
                "description": f"Extracted from {filename}. Verified source of truth for claims verification.",
                "source_reference": f"{source_ref} § Item {idx + 1}",
                "product_scope": product,
                "region_scope": region,
                "channel_scope": "All",
                "expires_at": None,
                "confidence": 0.95 if has_metric else 0.85,
            })

    # If no metrics detected, provide a generic fact proposal based on first sentence/paragraph
    if not suggested_facts and paragraphs:
        first_p = paragraphs[0]
        suggested_facts.append({
            "title": f"Summary Truth: {filename}",
            "canonical_value": first_p[:200] if len(first_p) > 200 else first_p,
            "description": f"Extracted statement from {filename}.",
            "source_reference": source_ref,
            "product_scope": "All",
            "region_scope": "Global",
            "channel_scope": "All",
            "expires_at": None,
            "confidence": 0.8,
        })

    # 2. Guidelines Extraction
    suggested_guidelines: List[Dict[str, Any]] = []
    # Directives like "Always", "Never", "Do not", "Ensure", "Tone", "Voice"
    guideline_pattern = re.compile(r"\b(always|never|do not|don't|ensure|must|should|avoid|tone|voice)\b", re.IGNORECASE)

    for idx, sent in enumerate(sentences):
        if guideline_pattern.search(sent):
            category = "Brand Voice"
            severity = "High"
            if any(k in sent.lower() for k in ["legal", "disclaimer", "compliance", "copyright"]):
                category = "Legal & Regulatory"
                severity = "Blocker"
            elif any(k in sent.lower() for k in ["claim", "guarantee", "metric"]):
                category = "Marketing Claims"
                severity = "Blocker"
            elif any(k in sent.lower() for k in ["color", "font", "logo", "visual"]):
                category = "Visual & Design"
                severity = "Warning"

            # Parse simple Do/Don't if present
            do_ex: List[str] = []
            dont_ex: List[str] = []
            if "do not" in sent.lower() or "never" in sent.lower() or "avoid" in sent.lower():
                dont_ex.append(sent)
            else:
                do_ex.append(sent)

            suggested_guidelines.append({
                "title": f"Guideline: {sent[:35]}...",
                "principle": sent[:60] if len(sent) > 60 else sent,
                "category": category,
                "severity": severity,
                "description": f"Extracted from {filename}. Brand governance directive.",
                "do_examples": do_ex,
                "dont_examples": dont_ex,
                "source_reference": f"{source_ref} § Guideline {idx + 1}",
                "product_scope": "All",
                "region_scope": "Global",
                "channel_scope": "All",
            })

    # Default guideline if none detected
    if not suggested_guidelines and paragraphs:
        suggested_guidelines.append({
            "title": f"Brand Voice Guideline from {filename}",
            "principle": "Maintain objective, verified, enterprise-grade brand communication.",
            "category": "Brand Voice",
            "severity": "High",
            "description": f"Derived from brand documentation in {filename}.",
            "do_examples": ["Use clear, substantiated claims with documented references."],
            "dont_examples": ["Do not make unsubstantiated superlative claims."],
            "source_reference": source_ref,
            "product_scope": "All",
            "region_scope": "Global",
            "channel_scope": "All",
        })

    # 3. Terminology Extraction
    suggested_terms: List[Dict[str, Any]] = []
    # Identify quoted terms or capitalized nouns
    term_matches = re.findall(r"['\"]([A-Za-z0-9\s\-]+)['\"]", clean_text)
    # Deduplicate terms
    seen_terms = set()
    for tm in term_matches:
        tm_clean = tm.strip()
        if 2 <= len(tm_clean) <= 40 and tm_clean.lower() not in seen_terms:
            seen_terms.add(tm_clean.lower())
            suggested_terms.append({
                "approved_term": tm_clean,
                "disallowed_variants": [tm_clean.lower(), tm_clean.upper(), tm_clean.replace(" ", "")],
                "replacement": tm_clean,
                "notes": f"Extracted brand term from {filename}.",
                "source_reference": source_ref,
                "product_scope": "All",
                "region_scope": "Global",
                "channel_scope": "All",
            })

    if not suggested_terms and paragraphs:
        # Suggest term from title or first words
        words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", clean_text[:500])
        for w in words[:3]:
            if w.lower() not in seen_terms and len(w) > 3:
                seen_terms.add(w.lower())
                suggested_terms.append({
                    "approved_term": w,
                    "disallowed_variants": [w.lower()],
                    "replacement": w,
                    "notes": f"Extracted prospective brand term from {filename}.",
                    "source_reference": source_ref,
                    "product_scope": "All",
                    "region_scope": "Global",
                    "channel_scope": "All",
                })

    # 4. Rules Engine Extraction
    suggested_rules: List[Dict[str, Any]] = []
    # Forbidden phrases detection
    forbidden_words = ["guaranteed", "100% bug-free", "zero risk", "infinitely scalable", "cheap as dirt", "miraculous"]
    for fw in forbidden_words:
        if fw in clean_text.lower():
            suggested_rules.append({
                "name": f"Prohibit '{fw.title()}' Unsubstantiated Claim",
                "rule_type": "FORBIDDEN_PHRASE",
                "severity": "Blocker",
                "description": f"Enforces brand policy forbidding hyperbolic phrase '{fw}'.",
                "configuration": {"forbidden_phrases": [fw], "case_sensitive": False},
                "source_reference": source_ref,
                "product_scope": "All",
                "region_scope": "Global",
                "channel_scope": "All",
            })

    # Disclaimer detection
    if any(k in clean_text.lower() for k in ["disclaimer", "terms apply", "subject to", "conditions"]):
        suggested_rules.append({
            "name": "Mandatory Campaign Disclaimer Check",
            "rule_type": "REQUIRED_DISCLAIMER",
            "severity": "Blocker",
            "description": f"Requires appropriate legal and qualification disclaimer identified in {filename}.",
            "configuration": {"required_terms": ["Terms apply", "Subject to"]},
            "source_reference": source_ref,
            "product_scope": "All",
            "region_scope": "Global",
            "channel_scope": "All",
        })

    # If no rules detected, propose a sensible default rule
    if not suggested_rules:
        suggested_rules.append({
            "name": f"Governance Compliance Rule from {filename}",
            "rule_type": "FORBIDDEN_PHRASE",
            "severity": "Warning",
            "description": f"Automated rule guardrail generated from {filename}.",
            "configuration": {"forbidden_phrases": ["unverified claim", "unsupported guarantee"]},
            "source_reference": source_ref,
            "product_scope": "All",
            "region_scope": "Global",
            "channel_scope": "All",
        })

    return {
        "suggested_facts": suggested_facts[:5],
        "suggested_guidelines": suggested_guidelines[:5],
        "suggested_terms": suggested_terms[:5],
        "suggested_rules": suggested_rules[:5],
    }
