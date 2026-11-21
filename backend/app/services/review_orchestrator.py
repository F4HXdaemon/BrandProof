import os
import re
import uuid
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from app.models.document import Document, DocumentVersion, DocumentChunk, DocumentStatus
from app.models.review import Review, ReviewStatus, Claim, ClaimStatus, Finding, FindingStatus
from app.models.knowledge import ApprovedAsset
from app.services.storage import get_storage
from app.services.extraction_service import extract_document_chunks, ExtractionError, ExtractionResult
from app.services.scoping_service import get_applicable_knowledge
from app.services.audit_service import record_audit_event
from app.services.rule_engine import DeterministicRuleEngine, FindingCandidate
from app.services.citation_gate import CitationGate
from app.services.risk_scoring import calculate_risk_score
from app.services.llm import get_llm_provider


MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
ALLOWED_EXTENSIONS = {".txt", ".text", ".md", ".markdown", ".docx", ".pdf"}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and remove invalid characters."""
    base = os.path.basename(filename.strip())
    # Keep alphanumeric, dot, underscore, and hyphen
    sanitized = re.sub(r"[^\w.\-]", "_", base)
    if not sanitized or sanitized.startswith("."):
        sanitized = f"document_{uuid.uuid4().hex[:8]}{os.path.splitext(base)[1] or '.txt'}"
    return sanitized


class ReviewOrchestrator:
    """
    Central orchestration service for BrandProof document ingestion & review lifecycle.
    Flow:
      1. Receive & validate document / pasted text
      2. Store raw file securely via StorageBackend
      3. Create Document & DocumentVersion (Version 1)
      4. Extract & normalize text into DocumentChunk records
      5. Resolve Applicable Knowledge based on Intent Card scopes
      6. Create Review linked with Intent Card & Scopes
      7. [Hook] Trigger Deterministic Checks (ready for rule engine phase)
      8. [Hook] Trigger AI Claim Analysis (ready for AI analysis phase)
      9. [Hook] Consolidate Findings
      10. Commit immutable Audit Events
    """

    def __init__(self, db: Session):
        self.db = db
        self.storage = get_storage()

    def validate_file_payload(self, file_bytes: bytes, filename: str, content_type: Optional[str]) -> None:
        """Enforces file size and extension restrictions."""
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError("Submitted file or text content is empty.")

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise ValueError(f"File size exceeds maximum allowed limit of {max_mb} MB.")

        ext = os.path.splitext(filename.lower())[1]
        if ext not in ALLOWED_EXTENSIONS:
            allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValueError(f"Unsupported file extension '{ext}'. Supported formats: {allowed_list}")

    def ingest_document(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: Optional[str],
        title: str,
        creator_id: Optional[str],
        organization_id: str,
        product: str = "All",
        region: str = "Global",
        channel: str = "All",
    ) -> Tuple[Document, DocumentVersion]:
        safe_filename = sanitize_filename(filename)
        self.validate_file_payload(file_bytes, safe_filename, content_type)

        stored_key, file_size = self.storage.save_file(
            file_data=file_bytes,
            filename=safe_filename,
            content_type=content_type,
        )

        record_audit_event(
            db=self.db,
            organization_id=organization_id,
            actor_id=creator_id,
            action="FILE_UPLOADED",
            entity_type="File",
            entity_id=stored_key,
            metadata={"filename": safe_filename, "size_bytes": file_size},
        )

        document = Document(
            organization_id=organization_id,
            creator_id=creator_id,
            title=title.strip() or os.path.splitext(safe_filename)[0],
            filename=safe_filename,
            file_type=content_type or os.path.splitext(safe_filename)[1],
            file_path=stored_key,
            file_size=file_size,
            product=product,
            region=region,
            channel=channel,
            status=DocumentStatus.DRAFT.value,
            processing_status="Extracting",
        )
        self.db.add(document)
        self.db.flush()

        record_audit_event(
            db=self.db,
            organization_id=organization_id,
            actor_id=creator_id,
            action="DOCUMENT_SUBMITTED",
            entity_type="Document",
            entity_id=document.id,
            metadata={"title": document.title, "filename": safe_filename},
        )

        version = DocumentVersion(
            document_id=document.id,
            created_by_id=creator_id,
            version_number=1,
            file_path=stored_key,
            file_size=file_size,
        )
        self.db.add(version)
        self.db.flush()

        try:
            extraction_result = extract_document_chunks(
                file_bytes=file_bytes,
                filename=safe_filename,
                content_type=content_type,
            )
            version.extracted_text = extraction_result.full_text

            for chunk_data in extraction_result.chunks:
                db_chunk = DocumentChunk(
                    document_version_id=version.id,
                    sequence=chunk_data.sequence,
                    chunk_type=chunk_data.chunk_type,
                    text=chunk_data.text,
                    page_number=chunk_data.page_number,
                    chunk_metadata=chunk_data.metadata,
                )
                self.db.add(db_chunk)

            document.status = DocumentStatus.DRAFT.value
            document.processing_status = "Ready"

            record_audit_event(
                db=self.db,
                organization_id=organization_id,
                actor_id=creator_id,
                action="PROCESSING_COMPLETED",
                entity_type="DocumentVersion",
                entity_id=version.id,
                metadata={
                    "chunks_count": extraction_result.total_chunks,
                    "words_count": extraction_result.total_words,
                    "page_count": extraction_result.page_count,
                },
            )

        except ExtractionError as e:
            err_msg = str(e)
            document.status = DocumentStatus.FAILED.value
            document.processing_status = "Failed"
            document.error_message = err_msg
            version.error_message = err_msg

            record_audit_event(
                db=self.db,
                organization_id=organization_id,
                actor_id=creator_id,
                action="PROCESSING_FAILED",
                entity_type="DocumentVersion",
                entity_id=version.id,
                metadata={"error": err_msg},
            )
        except Exception as e:
            err_msg = f"Unexpected processing error: {str(e)}"
            document.status = DocumentStatus.FAILED.value
            document.processing_status = "Failed"
            document.error_message = err_msg
            version.error_message = err_msg

            record_audit_event(
                db=self.db,
                organization_id=organization_id,
                actor_id=creator_id,
                action="PROCESSING_FAILED",
                entity_type="DocumentVersion",
                entity_id=version.id,
                metadata={"error": err_msg},
            )

        self.db.commit()
        self.db.refresh(document)
        self.db.refresh(version)
        return document, version

    def ingest_and_create_review(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: Optional[str],
        title: str,
        creator_id: str,
        organization_id: str,
        intent_card: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Review, Document, DocumentVersion]:
        """
        Executes full ingestion pipeline for an uploaded file or pasted text.
        Gracefully marks document/review as Failed if text extraction fails.
        """
        intent = intent_card or {}
        safe_filename = sanitize_filename(filename)

        # Scopes from Intent Card
        product = intent.get("product") or "All"
        region = intent.get("region") or "Global"
        channel = intent.get("channel") or "All"
        content_type_str = intent.get("content_type") or "General Marketing"
        intended_audience = intent.get("intended_audience") or "All Audiences"
        purpose = intent.get("purpose") or "Brand Compliance Review"

        # Validate file
        self.validate_file_payload(file_bytes, safe_filename, content_type)

        # 1. Save raw file via storage abstraction
        stored_key, file_size = self.storage.save_file(
            file_data=file_bytes,
            filename=safe_filename,
            content_type=content_type,
        )

        record_audit_event(
            db=self.db,
            organization_id=organization_id,
            actor_id=creator_id,
            action="FILE_UPLOADED",
            entity_type="File",
            entity_id=stored_key,
            metadata={"filename": safe_filename, "size_bytes": file_size},
        )

        # 2. Create Document record
        document = Document(
            organization_id=organization_id,
            creator_id=creator_id,
            title=title.strip() or os.path.splitext(safe_filename)[0],
            filename=safe_filename,
            file_type=content_type or os.path.splitext(safe_filename)[1],
            file_path=stored_key,
            file_size=file_size,
            product=product,
            region=region,
            channel=channel,
            status=DocumentStatus.EXTRACTING.value,
            processing_status="Extracting",
        )
        self.db.add(document)
        self.db.flush()

        record_audit_event(
            db=self.db,
            organization_id=organization_id,
            actor_id=creator_id,
            action="DOCUMENT_SUBMITTED",
            entity_type="Document",
            entity_id=document.id,
            metadata={"title": document.title, "filename": safe_filename},
        )

        # 3. Create DocumentVersion 1
        version = DocumentVersion(
            document_id=document.id,
            created_by_id=creator_id,
            version_number=1,
            file_path=stored_key,
            file_size=file_size,
        )
        self.db.add(version)
        self.db.flush()

        # 4. Create Review with Intent Card
        review = Review(
            organization_id=organization_id,
            document_id=document.id,
            version_id=version.id,
            reviewer_id=None,  # Assigned or unclaimed
            title=title.strip() or document.title,
            summary=f"Brand governance and compliance audit for '{document.title}'",
            intent_card=intent,
            product=product,
            region=region,
            channel=channel,
            content_type=content_type_str,
            intended_audience=intended_audience,
            purpose=purpose,
            status=ReviewStatus.NEEDS_REVIEW.value,
            processing_status="Extracting",
        )
        self.db.add(review)
        self.db.flush()

        # 5. Extract text and create DocumentChunk records
        extraction_result: Optional[ExtractionResult] = None
        try:
            extraction_result = extract_document_chunks(
                file_bytes=file_bytes,
                filename=safe_filename,
                content_type=content_type,
            )

            # Store full text on version
            version.extracted_text = extraction_result.full_text

            # Create individual DocumentChunk records
            for chunk_data in extraction_result.chunks:
                db_chunk = DocumentChunk(
                    document_version_id=version.id,
                    sequence=chunk_data.sequence,
                    chunk_type=chunk_data.chunk_type,
                    text=chunk_data.text,
                    page_number=chunk_data.page_number,
                    chunk_metadata=chunk_data.metadata,
                )
                self.db.add(db_chunk)

            # Update statuses to Ready
            document.status = DocumentStatus.NEEDS_REVIEW.value
            document.processing_status = "Ready"
            review.processing_status = "Ready"

            record_audit_event(
                db=self.db,
                organization_id=organization_id,
                actor_id=creator_id,
                action="PROCESSING_COMPLETED",
                entity_type="DocumentVersion",
                entity_id=version.id,
                metadata={
                    "chunks_count": extraction_result.total_chunks,
                    "words_count": extraction_result.total_words,
                    "page_count": extraction_result.page_count,
                },
            )

        except ExtractionError as e:
            # Graceful failure handling
            err_msg = str(e)
            document.status = DocumentStatus.FAILED.value
            document.processing_status = "Failed"
            document.error_message = err_msg
            version.error_message = err_msg
            review.processing_status = "Failed"
            review.error_message = err_msg

            record_audit_event(
                db=self.db,
                organization_id=organization_id,
                actor_id=creator_id,
                action="PROCESSING_FAILED",
                entity_type="DocumentVersion",
                entity_id=version.id,
                metadata={"error": err_msg},
            )

        except Exception as e:
            err_msg = f"Unexpected processing error: {str(e)}"
            document.status = DocumentStatus.FAILED.value
            document.processing_status = "Failed"
            document.error_message = err_msg
            version.error_message = err_msg
            review.processing_status = "Failed"
            review.error_message = err_msg

            record_audit_event(
                db=self.db,
                organization_id=organization_id,
                actor_id=creator_id,
                action="PROCESSING_FAILED",
                entity_type="DocumentVersion",
                entity_id=version.id,
                metadata={"error": err_msg},
            )

        # 6. Execute Full BrandProof Governance Audit
        if review.processing_status != "Failed":
            review.processing_status = "Processing"
            self.db.commit()
            try:
                self.run_full_audit(review, version)
                # Check for blockers
                has_blockers = any(
                    f.severity in ("Blocker", "Critical") and f.status in ("Open", "open")
                    for f in (review.findings or [])
                )
                review.processing_status = "Requires attention" if has_blockers else "Completed"
            except Exception as e:
                err_msg = f"Audit execution error: {str(e)}"
                review.processing_status = "Failed"
                review.error_message = err_msg
                record_audit_event(
                    db=self.db,
                    organization_id=organization_id,
                    actor_id=creator_id,
                    action="AUDIT_FAILED",
                    entity_type="Review",
                    entity_id=review.id,
                    metadata={"error": err_msg},
                )

        self.db.commit()
        self.db.refresh(review)
        self.db.refresh(document)
        self.db.refresh(version)

        record_audit_event(
            db=self.db,
            organization_id=organization_id,
            actor_id=creator_id,
            action="REVIEW_CREATED",
            entity_type="Review",
            entity_id=review.id,
            metadata={"title": review.title, "document_id": document.id},
        )

        return review, document, version

    def ingest_pasted_text(
        self,
        text_content: str,
        title: str,
        creator_id: str,
        organization_id: str,
        intent_card: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Review, Document, DocumentVersion]:
        """Wraps pasted text into a markdown virtual file and executes ingestion."""
        file_bytes = text_content.encode("utf-8")
        clean_title = title.strip() or "Pasted Marketing Draft"
        filename = f"{re.sub(r'[^a-zA-Z0-9_-]', '_', clean_title.lower())}.md"
        return self.ingest_and_create_review(
            file_bytes=file_bytes,
            filename=filename,
            content_type="text/markdown",
            title=clean_title,
            creator_id=creator_id,
            organization_id=organization_id,
            intent_card=intent_card,
        )

    def run_full_audit(self, review: Review, version: DocumentVersion) -> None:
        """
        Executes the integrated BrandProof audit pipeline:
        1. Knowledge scoping (Product, Region, Channel)
        2. Deterministic rule checking (Terms, Disclaimers, Forbidden Phrases, Numeric, Regex, Accessibility)
        3. Claim Extraction & Claim Ledger verification against approved Facts
        4. Tone & Voice review against brand guidelines
        5. Central CitationGate validation (NO VALID SOURCE = NO FINDING)
        6. Risk scoring & level calculation
        """
        context = {
            "product": review.product,
            "region": review.region,
            "channel": review.channel,
            "content_type": review.content_type,
        }

        # 1. Fetch scoped knowledge base
        knowledge = get_applicable_knowledge(
            db=self.db,
            organization_id=review.organization_id,
            product=review.product,
            region=review.region,
            channel=review.channel,
        )
        approved_assets = self.db.query(ApprovedAsset).filter(
            ApprovedAsset.organization_id == review.organization_id,
            ApprovedAsset.active == True
        ).all()
        knowledge["assets"] = approved_assets

        doc_text = version.extracted_text or ""
        doc_chunks = version.chunks or []

        candidate_findings: List[FindingCandidate] = []

        # 2. Run deterministic rule checkers
        engine = DeterministicRuleEngine()
        rule_candidates = engine.run_all(
            text=doc_text,
            chunks=doc_chunks,
            context=context,
            knowledge=knowledge,
        )
        candidate_findings.extend(rule_candidates)

        # 3. LLM / Fallback Claim Extraction & Verification Ledger
        llm = get_llm_provider()
        extracted_proposals = llm.extract_claims(doc_text)
        all_facts = knowledge.get("facts", []) + knowledge.get("expired_facts_excluded", [])

        # Clear previous claims for this version if re-auditing
        self.db.query(Claim).filter(
            Claim.review_id == review.id,
            Claim.document_version_id == version.id
        ).delete(synchronize_session=False)

        claims_count = 0
        for prop in extracted_proposals:
            analysis = llm.analyze_claim_against_facts(
                claim=prop.claim_text,
                facts=all_facts,
                context=context,
            )

            db_claim = Claim(
                organization_id=review.organization_id,
                review_id=review.id,
                document_id=review.document_id,
                document_version_id=version.id,
                claim_text=prop.claim_text,
                claim_type=prop.claim_type,
                page_number=prop.page_number,
                paragraph_number=prop.paragraph_number,
                confidence=prop.confidence,
                location_metadata=prop.location_metadata,
                status=analysis.status,
                matched_fact_id=analysis.matched_fact_id,
                reasoning=analysis.reasoning,
            )
            self.db.add(db_claim)
            self.db.flush()
            claims_count += 1

            # If claim has a conflict or expired fact violation, produce a candidate finding
            if analysis.status == ClaimStatus.CONFLICTS.value and analysis.matched_fact_id:
                matched_f = next((f for f in all_facts if f.id == analysis.matched_fact_id), None)
                if matched_f:
                    candidate_findings.append(
                        FindingCandidate(
                            finding_type="numeric_conflict",
                            severity="Blocker",
                            title=f"Factual Claim Conflict: '{matched_f.title}'",
                            message=analysis.reasoning or f"Claim contradicts canonical value '{matched_f.canonical_value}'.",
                            quoted_text=prop.claim_text,
                            page_number=prop.page_number,
                            source_type="fact",
                            source_id=matched_f.id,
                            source_reference=matched_f.source_reference,
                            suggested_replacement=matched_f.canonical_value,
                            checker="ClaimLedger",
                            confidence=analysis.confidence,
                            metadata={"claim_id": db_claim.id}
                        )
                    )
            elif analysis.status == ClaimStatus.EXPIRED.value and analysis.matched_fact_id:
                matched_f = next((f for f in all_facts if f.id == analysis.matched_fact_id), None)
                if matched_f:
                    candidate_findings.append(
                        FindingCandidate(
                            finding_type="expired_fact",
                            severity="High",
                            title=f"Expired Fact Cited: '{matched_f.title}'",
                            message=analysis.reasoning or f"Fact '{matched_f.title}' is expired.",
                            quoted_text=prop.claim_text,
                            page_number=prop.page_number,
                            source_type="fact",
                            source_id=matched_f.id,
                            source_reference=matched_f.source_reference,
                            suggested_replacement="Update with current approved data",
                            checker="ClaimLedger",
                            confidence=analysis.confidence,
                            metadata={"claim_id": db_claim.id}
                        )
                    )

        # 4. Tone & Brand Voice Review
        guidelines = knowledge.get("guidelines", [])
        tone_results = llm.review_tone(doc_text, guidelines)
        for tr in tone_results:
            matched_g = next((g for g in guidelines if g.id == tr.guideline_id), None)
            source_ref = getattr(matched_g, "source_reference", None) if matched_g else None
            candidate_findings.append(
                FindingCandidate(
                    finding_type="tone",
                    severity=tr.severity,
                    title=f"Tone Guideline Violation: {tr.principle}",
                    message=tr.reasoning,
                    quoted_text=tr.violation_snippet,
                    page_number=1,
                    source_type="guideline",
                    source_id=tr.guideline_id,
                    source_reference=source_ref or f"Brand Voice Guideline § {tr.principle}",
                    suggested_replacement=tr.suggested_fix,
                    checker="ToneReviewer",
                    confidence=0.9
                )
            )

        # 5. CitationGate: Central source validation & quarantine (NO VALID SOURCE = NO FINDING)
        gate = CitationGate(self.db, review.organization_id)
        valid_candidates, quarantined = gate.validate_and_filter(candidate_findings, context)

        # Clear existing open findings for this review version
        self.db.query(Finding).filter(
            Finding.review_id == review.id,
            Finding.document_version_id == version.id
        ).delete(synchronize_session=False)

        # Persist valid findings
        persisted_findings: List[Finding] = []
        for cand in valid_candidates:
            f = Finding(
                organization_id=review.organization_id,
                review_id=review.id,
                document_version_id=version.id,
                finding_type=cand.finding_type,
                severity=cand.severity,
                status=FindingStatus.OPEN.value,
                title=cand.title,
                message=cand.message,
                quoted_text=cand.quoted_text,
                start_offset=cand.start_offset,
                end_offset=cand.end_offset,
                page_number=cand.page_number or 1,
                source_type=cand.source_type,
                source_id=cand.source_id,
                source_reference=cand.source_reference,
                suggested_replacement=cand.suggested_replacement,
                checker=cand.checker,
                confidence=cand.confidence,
                claim_id=cand.metadata.get("claim_id") if cand.metadata else None,
            )
            if cand.source_type == "rule":
                f.rule_id = cand.source_id
            elif cand.source_type == "fact":
                f.fact_id = cand.source_id
            elif cand.source_type == "guideline":
                f.guideline_id = cand.source_id

            self.db.add(f)
            persisted_findings.append(f)

        self.db.flush()

        # 6. Risk Scoring & Summary Calculation
        risk_data = calculate_risk_score(persisted_findings)
        review.risk_score = risk_data["risk_score"]
        review.risk_level = risk_data["risk_level"]
        review.claims_count = claims_count
        review.findings_count = len(persisted_findings)
        review.processing_status = "Ready"

        review.status = ReviewStatus.NEEDS_REVIEW.value

    def create_new_version_with_fixes(
        self,
        review_id: str,
        new_text: str,
        change_reason: str,
        user_id: str,
    ) -> DocumentVersion:
        """
        Creates a new DocumentVersion (v2, v3, etc.) with applied fixes or revisions.
        Resets any previous approvals and triggers a clean re-audit.
        """
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise ValueError("Review not found")

        current_version = self.db.query(DocumentVersion).filter(
            DocumentVersion.id == review.version_id
        ).first()
        next_ver_num = (current_version.version_number + 1) if current_version else 2

        # Save virtual file in storage
        file_bytes = new_text.encode("utf-8")
        stored_key, file_size = self.storage.save_file(
            file_data=file_bytes,
            filename=f"revised_v{next_ver_num}.md",
            content_type="text/markdown",
        )

        new_version = DocumentVersion(
            document_id=review.document_id,
            created_by_id=user_id,
            version_number=next_ver_num,
            parent_version_id=current_version.id if current_version else None,
            change_reason=change_reason.strip() or f"Applied fixes for Review {review_id}",
            file_path=stored_key,
            file_size=file_size,
            extracted_text=new_text,
        )
        self.db.add(new_version)
        self.db.flush()

        # Extract and create chunks for the new version
        extraction_res = extract_document_chunks(
            file_bytes=file_bytes,
            filename=f"revised_v{next_ver_num}.md",
            content_type="text/markdown",
        )
        for chunk_data in extraction_res.chunks:
            db_chunk = DocumentChunk(
                document_version_id=new_version.id,
                sequence=chunk_data.sequence,
                chunk_type=chunk_data.chunk_type,
                text=chunk_data.text,
                page_number=chunk_data.page_number,
                chunk_metadata=chunk_data.metadata,
            )
            self.db.add(db_chunk)

        # Update Review to point to new version & reset approval state
        review.version_id = new_version.id
        review.status = ReviewStatus.NEEDS_REVIEW.value

        # Re-run full audit on the new version
        self.run_full_audit(review, new_version)

        self.db.commit()
        self.db.refresh(new_version)
        self.db.refresh(review)

        record_audit_event(
            db=self.db,
            organization_id=review.organization_id,
            actor_id=user_id,
            action="VERSION_CREATED",
            entity_type="DocumentVersion",
            entity_id=new_version.id,
            metadata={
                "version_number": new_version.version_number,
                "change_reason": change_reason,
                "review_id": review.id,
            }
        )

        return new_version
