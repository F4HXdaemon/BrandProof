"""
Risk Scoring Engine for BrandProof Reviews.

Computes a deterministic, transparent composite risk score based on open findings:
- Info: 1 pt
- Warning: 3 pts
- High: 7 pts
- Blocker: 15 pts

Risk Levels:
- Low: 0 - 4 pts
- Medium: 5 - 14 pts
- High: 15 - 29 pts (or any open Blocker)
- Critical: 30+ pts (or multiple Blockers)
"""
from typing import List, Dict, Any
from app.models.knowledge import SeverityLevel


SEVERITY_WEIGHTS = {
    "Info": 1.0,
    "Warning": 3.0,
    "High": 7.0,
    "Blocker": 15.0,
    # Legacy aliases
    "Critical": 15.0,
    "Medium": 3.0,
    "Low": 1.0,
}


def calculate_risk_score(findings: List[Any]) -> Dict[str, Any]:
    """
    Computes numerical risk score and categorical risk level from a list of findings or finding candidates.
    Only active / open findings contribute to risk.
    """
    breakdown = {
        "Blocker": 0,
        "High": 0,
        "Warning": 0,
        "Info": 0,
    }
    total_score = 0.0

    for finding in findings:
        # Check if finding is dismissed or fixed
        status = getattr(finding, "status", "Open")
        if hasattr(status, "value"):
            status = status.value
        status_str = str(status).lower()
        if status_str in {"dismissed", "fixed", "waived", "resolved"}:
            continue

        raw_sev = getattr(finding, "severity", "Info")
        if hasattr(raw_sev, "value"):
            raw_sev = raw_sev.value
        sev_str = str(raw_sev).capitalize()

        # Map to standard 4 severities
        if sev_str in {"Blocker", "Critical"}:
            canonical_sev = "Blocker"
        elif sev_str == "High":
            canonical_sev = "High"
        elif sev_str in {"Warning", "Medium"}:
            canonical_sev = "Warning"
        else:
            canonical_sev = "Info"

        breakdown[canonical_sev] += 1
        total_score += SEVERITY_WEIGHTS.get(canonical_sev, 1.0)

    # Determine Risk Level
    has_blockers = breakdown["Blocker"] > 0
    if total_score >= 30.0 or breakdown["Blocker"] >= 2:
        risk_level = "Critical"
    elif total_score >= 15.0 or has_blockers:
        risk_level = "High"
    elif total_score >= 5.0:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "risk_score": round(total_score, 1),
        "risk_level": risk_level,
        "breakdown": breakdown,
        "has_blockers": has_blockers,
        "open_findings_count": sum(breakdown.values()),
    }
