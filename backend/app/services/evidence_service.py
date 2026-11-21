import io
import os
import re
import uuid
import hashlib
import zipfile
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image
from pypdf import PdfReader
import docx
from sqlalchemy.orm import Session
from app.models.evidence import Evidence, EvidenceStatus, ReviewEvidence
from app.models.review import Review
from app.services.storage import get_storage, StorageError
from app.services.audit_service import record_audit_event

MAX_EVIDENCE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
ALLOWED_EVIDENCE_EXTENSIONS = {".pdf", ".docx", ".txt", ".text", ".md", ".markdown", ".png", ".jpg", ".jpeg"}


class EvidenceValidationError(ValueError):
    """Raised when evidence content validation fails."""
    pass


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and remove dangerous characters."""
    base = os.path.basename(filename.strip())
    # Keep alphanumeric, dot, underscore, hyphen
    sanitized = re.sub(r"[^\w.\-]", "_", base)
    if not sanitized or sanitized.startswith("."):
        sanitized = f"evidence_{uuid.uuid4().hex[:8]}{os.path.splitext(base)[1] or '.txt'}"
    return sanitized


def validate_file_content(file_bytes: bytes, filename: str, declared_content_type: Optional[str] = None) -> Tuple[str, str]:
    """
    Validates file size, extension, and deeply inspects magic bytes / content integrity.
    Never trusts filename or browser-provided MIME type alone.
    Returns (normalized_content_type, normalized_extension).
    """
    if not file_bytes or len(file_bytes) == 0:
        raise EvidenceValidationError("Submitted file is completely empty (0 bytes).")

    if len(file_bytes) > MAX_EVIDENCE_SIZE_BYTES:
        max_mb = MAX_EVIDENCE_SIZE_BYTES // (1024 * 1024)
        raise EvidenceValidationError(f"File size exceeds maximum allowed limit of {max_mb} MB.")

    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EVIDENCE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EVIDENCE_EXTENSIONS))
        raise EvidenceValidationError(f"Unsupported file extension '{ext}'. Supported formats: {allowed}")

    # Deep magic-byte and content validation
    # 1. PDF
    if ext == ".pdf":
        if not file_bytes.startswith(b"%PDF-"):
            raise EvidenceValidationError("Invalid PDF file: Missing standard %PDF- header.")
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            # Access pages count to verify header and trailer cross-reference table
            _ = len(reader.pages)
        except Exception as e:
            raise EvidenceValidationError(f"Corrupted or invalid PDF content: {str(e)}")
        return "application/pdf", ".pdf"

    # 2. PNG
    elif ext == ".png":
        if not file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise EvidenceValidationError("Invalid PNG file: Header does not match PNG signature.")
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                img.verify()
                if img.format != "PNG":
                    raise EvidenceValidationError(f"Declared PNG but image format is {img.format}.")
        except Exception as e:
            raise EvidenceValidationError(f"Corrupted or unreadable PNG image: {str(e)}")
        return "image/png", ".png"

    # 3. JPEG / JPG
    elif ext in [".jpg", ".jpeg"]:
        if not file_bytes.startswith(b"\xff\xd8\xff"):
            raise EvidenceValidationError("Invalid JPEG file: Header does not match JPEG signature.")
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                img.verify()
                if img.format not in ["JPEG", "MPO"]:
                    raise EvidenceValidationError(f"Declared JPEG but image format is {img.format}.")
        except Exception as e:
            raise EvidenceValidationError(f"Corrupted or unreadable JPEG image: {str(e)}")
        return "image/jpeg", ext

    # 4. DOCX
    elif ext == ".docx":
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise EvidenceValidationError("Invalid DOCX file: Missing standard PK zip container header.")
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                names = z.namelist()
                if not any("word/" in n or "[Content_Types].xml" in n for n in names):
                    raise EvidenceValidationError("Invalid DOCX file: Missing Word document structure inside archive.")
            doc = docx.Document(io.BytesIO(file_bytes))
            _ = len(doc.paragraphs)
        except Exception as e:
            raise EvidenceValidationError(f"Corrupted or unreadable DOCX document: {str(e)}")
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"

    # 5. TXT / Markdown
    elif ext in [".txt", ".text", ".md", ".markdown"]:
        # Verify no binary null bytes
        if b"\x00" in file_bytes[:4096]:
            raise EvidenceValidationError("Invalid text document: Contains binary null bytes.")
        try:
            decoded = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                decoded = file_bytes.decode("latin-1")
            except Exception:
                raise EvidenceValidationError("Invalid text document: Content cannot be decoded as text.")

        # Check printable character ratio
        printable_count = sum(1 for c in decoded if c.isprintable() or c in "\n\r\t")
        if len(decoded) > 0 and (printable_count / len(decoded)) < 0.85:
            raise EvidenceValidationError("Invalid text document: High density of non-printable binary characters.")

        mime = "text/markdown" if ext in [".md", ".markdown"] else "text/plain"
        return mime, ext

    raise EvidenceValidationError(f"Unsupported file format '{ext}'.")


def extract_evidence_text(file_bytes: bytes, ext: str) -> Optional[str]:
    """Extracts readable text from document where practical for claim auditing and preview."""
    try:
        if ext in [".txt", ".text", ".md", ".markdown"]:
            return file_bytes.decode("utf-8", errors="replace")[:50000]

        elif ext == ".pdf":
            reader = PdfReader(io.BytesIO(file_bytes))
            texts = []
            for p in reader.pages[:20]:  # Up to 20 pages
                t = p.extract_text()
                if t:
                    texts.append(t)
            return "\n\n".join(texts)[:50000] if texts else None

        elif ext == ".docx":
            doc = docx.Document(io.BytesIO(file_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)[:50000] if paragraphs else None

        elif ext in [".png", ".jpg", ".jpeg"]:
            with Image.open(io.BytesIO(file_bytes)) as img:
                return f"Image asset: {img.format} format, {img.width}x{img.height} px, mode {img.mode}"
    except Exception:
        pass
    return None


class EvidenceService:
    def __init__(self, db: Session):
        self.db = db
        self.storage = get_storage()

    def upload_evidence(
        self,
        file_bytes: bytes,
        filename: str,
        organization_id: str,
        uploaded_by_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        source_reference: Optional[str] = None,
        product_scope: str = "All",
        region_scope: str = "Global",
        channel_scope: str = "All",
        valid_from: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        review_id: Optional[str] = None,
    ) -> Evidence:
        """
        Validates content bytes, stores file safely, registers Evidence record,
        and optionally associates it with an Evaluation / Review.
        """
        safe_name = sanitize_filename(filename)
        mime_type, safe_ext = validate_file_content(file_bytes, safe_name)

        # Compute SHA-256
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        # Save to StorageBackend
        stored_key, file_size = self.storage.save_file(
            file_data=file_bytes,
            filename=safe_name,
            content_type=mime_type,
        )

        extracted_text = extract_evidence_text(file_bytes, safe_ext)

        # Determine initial validation status
        status = EvidenceStatus.VALIDATED.value
        if expires_at:
            now = datetime.now(timezone.utc)
            exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                status = EvidenceStatus.EXPIRED.value

        evidence = Evidence(
            organization_id=organization_id,
            uploaded_by_id=uploaded_by_id,
            title=(title or os.path.splitext(safe_name)[0]).strip(),
            filename=safe_name,
            file_type=mime_type,
            file_extension=safe_ext,
            file_path=stored_key,
            file_size=file_size,
            file_hash=sha256_hash,
            status=status,
            extracted_text=extracted_text,
            description=description.strip() if description else None,
            source_reference=(source_reference or f"Evidence Document: {safe_name}").strip(),
            product_scope=product_scope.strip() or "All",
            region_scope=region_scope.strip() or "Global",
            channel_scope=channel_scope.strip() or "All",
            valid_from=valid_from,
            expires_at=expires_at,
        )
        self.db.add(evidence)
        self.db.flush()

        # If review_id provided, associate with evaluation
        if review_id:
            review = self.db.query(Review).filter(
                Review.id == review_id,
                Review.organization_id == organization_id
            ).first()
            if review:
                assoc = ReviewEvidence(
                    organization_id=organization_id,
                    review_id=review.id,
                    evidence_id=evidence.id,
                    relevance_notes=f"Associated at evidence upload: {evidence.title}",
                )
                self.db.add(assoc)

        self.db.commit()
        self.db.refresh(evidence)

        record_audit_event(
            db=self.db,
            organization_id=organization_id,
            actor_id=uploaded_by_id,
            action="EVIDENCE_UPLOADED",
            entity_type="Evidence",
            entity_id=evidence.id,
            metadata={
                "filename": safe_name,
                "file_type": mime_type,
                "file_size": file_size,
                "status": status,
                "review_id": review_id,
            }
        )

        return evidence

    def associate_evidence_with_review(
        self,
        evidence_id: str,
        review_id: str,
        organization_id: str,
        actor_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ReviewEvidence:
        """Associates an existing evidence document with an evaluation, enforcing organization isolation."""
        evidence = self.db.query(Evidence).filter(
            Evidence.id == evidence_id,
            Evidence.organization_id == organization_id
        ).first()
        if not evidence:
            raise ValueError(f"Evidence document '{evidence_id}' not found or belongs to another organization.")

        review = self.db.query(Review).filter(
            Review.id == review_id,
            Review.organization_id == organization_id
        ).first()
        if not review:
            raise ValueError(f"Evaluation '{review_id}' not found or belongs to another organization.")

        existing = self.db.query(ReviewEvidence).filter(
            ReviewEvidence.evidence_id == evidence.id,
            ReviewEvidence.review_id == review.id
        ).first()
        if existing:
            if notes:
                existing.relevance_notes = notes
                self.db.commit()
            return existing

        assoc = ReviewEvidence(
            organization_id=organization_id,
            review_id=review.id,
            evidence_id=evidence.id,
            relevance_notes=notes or f"Associated with evaluation '{review.title}'",
        )
        self.db.add(assoc)
        self.db.commit()
        self.db.refresh(assoc)

        record_audit_event(
            db=self.db,
            organization_id=organization_id,
            actor_id=actor_id,
            action="EVIDENCE_ASSOCIATED",
            entity_type="ReviewEvidence",
            entity_id=assoc.id,
            metadata={"evidence_id": evidence.id, "review_id": review.id}
        )
        return assoc

    def delete_evidence(self, evidence_id: str, organization_id: str, actor_id: Optional[str] = None) -> bool:
        """
        Safely deletes evidence and its associated object storage file.
        Fails safely without leaving orphaned or broken records.
        """
        evidence = self.db.query(Evidence).filter(
            Evidence.id == evidence_id,
            Evidence.organization_id == organization_id
        ).first()
        if not evidence:
            return False

        # 1. Delete physical file from storage backend
        if evidence.file_path:
            try:
                self.storage.delete_file(evidence.file_path)
            except StorageError as se:
                raise RuntimeError(f"Storage deletion failed for evidence file: {str(se)}. Database record preserved.")
            except Exception as e:
                raise RuntimeError(f"Unexpected error deleting evidence file: {str(e)}. Database record preserved.")

        # 2. Delete database record (cascades to ReviewEvidence associations)
        doc_title = evidence.title
        self.db.delete(evidence)
        self.db.commit()

        record_audit_event(
            db=self.db,
            organization_id=organization_id,
            actor_id=actor_id,
            action="EVIDENCE_DELETED",
            entity_type="Evidence",
            entity_id=evidence_id,
            metadata={"title": doc_title}
        )
        return True
