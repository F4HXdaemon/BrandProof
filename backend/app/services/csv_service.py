import csv
import io
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.models.knowledge import Fact, Term, FactStatus
from app.services.audit_service import record_audit_event


def parse_date(date_str: str) -> datetime:
    """Parse common date formats or ISO strings."""
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Try fromisoformat
    try:
        dt = datetime.fromisoformat(date_str)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        raise ValueError(f"Unrecognized date format: '{date_str}'. Expected YYYY-MM-DD.")


def import_facts_from_csv(
    csv_content: str,
    organization_id: str,
    owner_id: str,
    db: Session,
) -> Dict[str, Any]:
    """
    Parses, validates, and imports Facts from CSV text.
    Enforces required fields: title, canonical_value, source_reference.
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    if not reader.fieldnames:
        return {"imported_count": 0, "errors": ["CSV file is empty or missing headers."], "imported_items": []}

    # Normalize header mapping
    header_map = {name.strip().lower().replace(" ", "_"): name for name in reader.fieldnames}

    def get_val(row, key, default=""):
        actual_key = header_map.get(key)
        if actual_key and actual_key in row and row[actual_key]:
            return row[actual_key].strip()
        return default

    errors: List[str] = []
    imported_items: List[Dict[str, Any]] = []

    for row_idx, row in enumerate(reader, start=2):  # row 1 is header
        title = get_val(row, "title") or get_val(row, "fact")
        canonical_val = get_val(row, "canonical_value") or get_val(row, "value") or get_val(row, "canonical")
        source_ref = get_val(row, "source_reference") or get_val(row, "source") or get_val(row, "reference")
        desc = get_val(row, "description")
        product = get_val(row, "product_scope") or get_val(row, "product", "All")
        region = get_val(row, "region_scope") or get_val(row, "region", "Global")
        channel = get_val(row, "channel_scope") or get_val(row, "channel", "All")
        status_val = get_val(row, "status", FactStatus.APPROVED.value)
        expiry_str = get_val(row, "expires_at") or get_val(row, "expiry") or get_val(row, "expiry_date")

        # Validation
        if not title:
            errors.append(f"Row {row_idx}: 'title' is required.")
            continue
        if not canonical_val:
            errors.append(f"Row {row_idx}: 'canonical_value' is required for '{title}'.")
            continue
        if not source_ref:
            errors.append(f"Row {row_idx}: 'source_reference' is required for '{title}' (NO VALID SOURCE = NO FINDING).")
            continue

        expires_at = None
        if expiry_str:
            try:
                expires_at = parse_date(expiry_str)
            except ValueError as ve:
                errors.append(f"Row {row_idx}: Invalid date for '{title}' - {str(ve)}")
                continue

        fact = Fact(
            organization_id=organization_id,
            owner_id=owner_id,
            title=title,
            canonical_value=canonical_val,
            description=desc or None,
            source_reference=source_ref,
            product_scope=product,
            region_scope=region,
            channel_scope=channel,
            expires_at=expires_at,
            status=status_val if status_val in [s.value for s in FactStatus] else FactStatus.APPROVED.value,
        )
        db.add(fact)
        imported_items.append({"title": title, "canonical_value": canonical_val, "source": source_ref})

    if imported_items:
        db.commit()
        record_audit_event(
            db=db,
            organization_id=organization_id,
            actor_id=owner_id,
            action="FACTS_CSV_IMPORTED",
            entity_type="Fact",
            entity_id=organization_id,
            metadata={"imported_count": len(imported_items), "errors_count": len(errors)}
        )

    return {
        "imported_count": len(imported_items),
        "total_attempted": len(imported_items) + len(errors),
        "errors": errors,
        "failed_count": len(errors),
        "imported_items": imported_items,
    }


def import_terms_from_csv(
    csv_content: str,
    organization_id: str,
    actor_id: str,
    db: Session,
) -> Dict[str, Any]:
    """
    Parses, validates, and imports Brand Terminology from CSV text.
    Expected headers: approved_term, disallowed_variants, replacement, notes.
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    if not reader.fieldnames:
        return {"imported_count": 0, "errors": ["CSV file is empty or missing headers."], "imported_items": []}

    header_map = {name.strip().lower().replace(" ", "_"): name for name in reader.fieldnames}

    def get_val(row, key, default=""):
        actual_key = header_map.get(key)
        if actual_key and actual_key in row and row[actual_key]:
            return row[actual_key].strip()
        return default

    errors: List[str] = []
    imported_items: List[Dict[str, Any]] = []

    for row_idx, row in enumerate(reader, start=2):
        approved = get_val(row, "approved_term") or get_val(row, "term") or get_val(row, "approved")
        disallowed_raw = get_val(row, "disallowed_variants") or get_val(row, "disallowed") or get_val(row, "variants")
        replacement = get_val(row, "replacement", approved)
        notes = get_val(row, "notes")
        product = get_val(row, "product_scope") or get_val(row, "product", "All")
        region = get_val(row, "region_scope") or get_val(row, "region", "Global")
        channel = get_val(row, "channel_scope") or get_val(row, "channel", "All")

        if not approved:
            errors.append(f"Row {row_idx}: 'approved_term' is required.")
            continue

        # Split disallowed variants by pipe, comma, or semicolon
        variants = []
        if disallowed_raw:
            delimiter = "|" if "|" in disallowed_raw else (";" if ";" in disallowed_raw else ",")
            variants = [v.strip() for v in disallowed_raw.split(delimiter) if v.strip()]

        term = Term(
            organization_id=organization_id,
            approved_term=approved,
            disallowed_variants=variants,
            replacement=replacement or approved,
            notes=notes or None,
            product_scope=product,
            region_scope=region,
            channel_scope=channel,
            active=True,
        )
        db.add(term)
        imported_items.append({"approved_term": approved, "variants_count": len(variants)})

    if imported_items:
        db.commit()
        record_audit_event(
            db=db,
            organization_id=organization_id,
            actor_id=actor_id,
            action="TERMS_CSV_IMPORTED",
            entity_type="Term",
            entity_id=organization_id,
            metadata={"imported_count": len(imported_items), "errors_count": len(errors)}
        )

    return {
        "imported_count": len(imported_items),
        "total_attempted": len(imported_items) + len(errors),
        "errors": errors,
        "failed_count": len(errors),
        "imported_items": imported_items,
    }
