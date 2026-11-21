import io
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
from app.models.review import Review, ReviewStatus
from app.models.document import DocumentVersion


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw total page count and footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Running header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, 762, "BrandProof™ Governance & Verification Platform — Audit Report")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(36, 756, 576, 756)

        # Running footer
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 42, 576, 42)

        footer_text = "CONFIDENTIAL • INTERNAL BRAND GOVERNANCE AUDIT • NOT LEGAL ADVICE"
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawString(36, 30, footer_text)
        self.drawRightString(576, 30, page_str)
        self.restoreState()


class ReportGenerator:
    """Generates publication-quality PDF audit reports for BrandProof evaluations."""

    def __init__(self, review: Review, db: Session):
        self.review = review
        self.db = db
        self.org_name = review.organization.name if review.organization else "Organization"
        self.doc_version = (
            db.query(DocumentVersion).filter(DocumentVersion.id == review.version_id).first()
            if review.version_id else None
        )

    def generate_pdf(self) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=46,
            bottomMargin=54,
        )

        styles = getSampleStyleSheet()

        # Custom Palette
        c_primary = colors.HexColor("#0F766E")      # Deep Teal
        c_ink = colors.HexColor("#0F172A")          # Slate 900
        c_ink_soft = colors.HexColor("#475569")     # Slate 600
        c_bg_light = colors.HexColor("#F8FAFC")     # Slate 50
        c_border = colors.HexColor("#E2E8F0")       # Slate 200
        c_rose = colors.HexColor("#BE123C")         # Rose 700
        c_amber = colors.HexColor("#B45309")        # Amber 700
        c_emerald = colors.HexColor("#047857")      # Emerald 700

        # Custom Typography
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=c_ink,
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=c_ink_soft,
        )
        section_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=c_primary,
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=c_ink,
        )
        body_bold = ParagraphStyle(
            "BodyBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=13,
            textColor=c_ink,
        )
        table_cell = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=c_ink,
        )
        table_cell_bold = ParagraphStyle(
            "TableCellBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=c_ink,
        )
        callout_style = ParagraphStyle(
            "Callout",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=c_ink_soft,
        )

        story = []

        # 1. Header Banner Table
        header_data = [
            [
                Paragraph("<b>BRANDPROOF™ GOVERNANCE PLATFORM</b>", subtitle_style),
                Paragraph(f"<b>REPORT DATE:</b> {datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M UTC')}", subtitle_style),
            ],
            [
                Paragraph("<b>BRAND EVALUATION & VERIFICATION AUDIT REPORT</b>", title_style),
                Paragraph(f"<b>ORGANISATION:</b> {self.org_name}", subtitle_style),
            ]
        ]
        header_table = Table(header_data, colWidths=[360, 180])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 8))

        # Thin divider
        sep_table = Table([[""]], colWidths=[540], rowHeights=[2])
        sep_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), c_primary)]))
        story.append(sep_table)
        story.append(Spacer(1, 10))

        # 2. Executive Metadata & Telemetry Card
        created_str = self.review.created_at.strftime("%b %d, %Y") if self.review.created_at else "N/A"
        version_num = self.doc_version.version_number if self.doc_version else 1
        intent = self.review.intent_card or {}
        supporting_notes = intent.get("supporting_evidence") or "None documented at intake"

        # Risk Color & Health Grade
        risk_color = c_emerald
        if self.review.risk_level in ["High", "Critical"]:
            risk_color = c_rose
        elif self.review.risk_level == "Medium":
            risk_color = c_amber

        base_score = max(0, 100 - (self.review.risk_score or 0))
        if base_score < 60 or self.review.risk_level == "Critical":
            grade = "F"
        elif base_score < 70 or self.review.risk_level == "High":
            grade = "C"
        elif base_score < 85 or self.review.risk_level == "Medium":
            grade = "B"
        elif base_score < 95:
            grade = "A"
        else:
            grade = "A+"

        meta_data = [
            [
                Paragraph("<b>Campaign / Evaluation:</b>", body_style),
                Paragraph(self.review.title or "Untitled Evaluation", body_bold),
                Paragraph("<b>Evaluation ID:</b>", body_style),
                Paragraph(f"<font name='Courier'>{self.review.id}</font>", body_style),
            ],
            [
                Paragraph("<b>Target Scope:</b>", body_style),
                Paragraph(f"{self.review.product or 'All Products'} • {self.review.region or 'Global'} • {self.review.channel or 'All Channels'}", body_style),
                Paragraph("<b>Document Version:</b>", body_style),
                Paragraph(f"Version {version_num} (Snapshot)", body_style),
            ],
            [
                Paragraph("<b>Content Category:</b>", body_style),
                Paragraph(self.review.content_type or "General Marketing", body_style),
                Paragraph("<b>Evaluation Date:</b>", body_style),
                Paragraph(created_str, body_style),
            ],
            [
                Paragraph("<b>Brand Health Grade:</b>", body_style),
                Paragraph(f"<font color='{risk_color.hexval()}'><b>Grade {grade} ({base_score}% Compliance)</b></font>", body_bold),
                Paragraph("<b>Governed Risk Score:</b>", body_style),
                Paragraph(f"<font color='{risk_color.hexval()}'><b>{self.review.risk_score} pts ({self.review.risk_level} Risk)</b></font>", body_bold),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[110, 170, 110, 150])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
            ("BOX", (0, 0), (-1, -1), 0.5, c_border),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 12))

        # 3. Reviewed Content Draft Section
        story.append(Paragraph("1. REVIEWED MARKETING CONTENT", section_style))
        content_text = (
            self.doc_version.extracted_text
            if (self.doc_version and self.doc_version.extracted_text)
            else (self.review.summary or "No draft text content recorded.")
        )
        clean_content = content_text[:3000].replace("\n", "<br/>")
        content_box = Table([[Paragraph(clean_content, table_cell)]], colWidths=[540])
        content_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
            ("BOX", (0, 0), (-1, -1), 0.5, c_border),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(content_box)
        story.append(Spacer(1, 12))

        # 4. Identified Claims Ledger
        claims = self.review.claims or []
        story.append(Paragraph(f"2. IDENTIFIED MARKETING CLAIMS & VERIFICATION LEDGER ({len(claims)})", section_style))

        if claims:
            claims_table_data = [
                [
                    Paragraph("<b>#</b>", table_cell_bold),
                    Paragraph("<b>Extracted Claim Statement</b>", table_cell_bold),
                    Paragraph("<b>Type</b>", table_cell_bold),
                    Paragraph("<b>Verification Status</b>", table_cell_bold),
                    Paragraph("<b>Citation / Fact Support</b>", table_cell_bold),
                ]
            ]
            for idx, c in enumerate(claims, 1):
                st_color = c_ink_soft
                st_name = str(c.status).upper()
                if "SUPPORT" in st_name or "VERIF" in st_name:
                    st_color = c_emerald
                elif "CONFLICT" in st_name or "DISPUT" in st_name:
                    st_color = c_rose
                elif "EXPIRED" in st_name:
                    st_color = c_amber

                sources = []
                if c.evidence:
                    sources.append(f"<b>Doc:</b> {c.evidence.title}")
                elif c.evidence_id:
                    sources.append(f"Evidence ID: {c.evidence_id[:8]}")
                if c.matched_fact:
                    sources.append(f"<b>Fact:</b> {c.matched_fact.title}")
                elif c.matched_fact_id:
                    sources.append(f"Fact ID: {c.matched_fact_id[:8]}")

                fact_ref = "<br/>".join(sources) if sources else "None (Unbacked claim)"

                claims_table_data.append([
                    Paragraph(str(idx), table_cell),
                    Paragraph(f"&ldquo;{c.claim_text or c.text}&rdquo;", table_cell),
                    Paragraph(c.claim_type or "Factual", table_cell),
                    Paragraph(f"<font color='{st_color.hexval()}'><b>{st_name}</b></font>", table_cell),
                    Paragraph(fact_ref, table_cell),
                ])

            claim_t = Table(claims_table_data, colWidths=[20, 210, 80, 100, 130])
            claim_t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), c_bg_light),
                ("BOX", (0, 0), (-1, -1), 0.5, c_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(claim_t)
        else:
            story.append(Paragraph("<i>No discrete factual claims identified in submitted text.</i>", body_style))
        story.append(Spacer(1, 12))

        # 5. Governance Findings & CitationGate Source Traces
        findings = self.review.findings or []
        story.append(Paragraph(f"3. GOVERNANCE FINDINGS & CITATIONGATE AUDIT ({len(findings)})", section_style))

        if findings:
            findings_data = [
                [
                    Paragraph("<b>Sev.</b>", table_cell_bold),
                    Paragraph("<b>Finding Title & Quoted Violation</b>", table_cell_bold),
                    Paragraph("<b>Suggested Fix / Replacement</b>", table_cell_bold),
                    Paragraph("<b>CitationGate Source Reference</b>", table_cell_bold),
                ]
            ]
            for f in findings:
                sev_color = c_ink_soft
                if f.severity in ["Blocker", "Critical"]:
                    sev_color = c_rose
                elif f.severity in ["High"]:
                    sev_color = colors.HexColor("#C2410C")
                elif f.severity in ["Warning", "Medium"]:
                    sev_color = c_amber

                title_p = f"<b>{f.title or f.finding_type}</b>"
                if f.quoted_text:
                    title_p += f"<br/><font color='#64748B'>Quoted:</font> &ldquo;{f.quoted_text}&rdquo;"
                if f.message:
                    title_p += f"<br/><font color='#475569'>{f.message}</font>"

                fix_p = f.suggested_replacement or f.suggestion or "No automatic fix"
                source_p = f.source_reference or f"{f.source_type or 'rule'}:{f.source_id or 'none'}"

                findings_data.append([
                    Paragraph(f"<font color='{sev_color.hexval()}'><b>{f.severity}</b></font>", table_cell),
                    Paragraph(title_p, table_cell),
                    Paragraph(fix_p, table_cell),
                    Paragraph(source_p, table_cell),
                ])

            find_t = Table(findings_data, colWidths=[50, 220, 130, 140])
            find_t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), c_bg_light),
                ("BOX", (0, 0), (-1, -1), 0.5, c_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(find_t)
        else:
            story.append(Paragraph("<i>No compliance or brand guideline violations identified.</i>", body_style))
        story.append(Spacer(1, 12))

        # 6. Supporting Evidence Documents
        evidence_assocs = self.review.evidence_associations or []
        story.append(Paragraph(f"4. ASSOCIATED EVIDENCE DOCUMENTS ({len(evidence_assocs)})", section_style))

        if evidence_assocs:
            ev_data = [
                [
                    Paragraph("<b>Document Title / Filename</b>", table_cell_bold),
                    Paragraph("<b>Type</b>", table_cell_bold),
                    Paragraph("<b>Status</b>", table_cell_bold),
                    Paragraph("<b>Source / Verification Reference</b>", table_cell_bold),
                    Paragraph("<b>Upload Date</b>", table_cell_bold),
                ]
            ]
            for ea in evidence_assocs:
                ev = ea.evidence
                if not ev:
                    continue
                ev_status_color = c_emerald if ev.effective_status == "Validated" else (c_amber if ev.effective_status == "Expired" else c_rose)
                up_date = ev.created_at.strftime("%b %d, %Y") if ev.created_at else "N/A"
                ev_data.append([
                    Paragraph(f"<b>{ev.title}</b><br/>{ev.filename}", table_cell),
                    Paragraph(ev.file_extension.upper(), table_cell),
                    Paragraph(f"<font color='{ev_status_color.hexval()}'><b>{ev.effective_status}</b></font>", table_cell),
                    Paragraph(ev.source_reference or "Document Evidence", table_cell),
                    Paragraph(up_date, table_cell),
                ])
            ev_t = Table(ev_data, colWidths=[160, 50, 80, 160, 90])
            ev_t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), c_bg_light),
                ("BOX", (0, 0), (-1, -1), 0.5, c_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(ev_t)
        else:
            story.append(Paragraph(f"<i>No separate document files uploaded. Intake reference notes: '{supporting_notes}'.</i>", body_style))
        story.append(Spacer(1, 12))

        # 7. Human Review & Approval Decisions
        approvals = self.review.approvals or []
        story.append(Paragraph("5. HUMAN REVIEW & APPROVAL STATUS", section_style))

        if approvals:
            appr_data = [
                [
                    Paragraph("<b>Decision</b>", table_cell_bold),
                    Paragraph("<b>Approver Name & Role</b>", table_cell_bold),
                    Paragraph("<b>Decision Date</b>", table_cell_bold),
                    Paragraph("<b>Override Justification / Comments</b>", table_cell_bold),
                ]
            ]
            for a in approvals:
                dec_color = c_emerald if a.status == "Approved" else (c_amber if a.status == "Changes Requested" else c_rose)
                dec_date = a.decided_at.strftime("%b %d, %Y %H:%M UTC") if a.decided_at else "N/A"
                comments_text = a.comments or "No comments entered."
                if a.is_override:
                    comments_text = f"<font color='{c_rose.hexval()}'><b>[BLOCKER OVERRIDE AUTHORIZED]</b></font><br/><b>Rationale:</b> {a.override_reason}<br/><b>Note:</b> {comments_text}"

                appr_data.append([
                    Paragraph(f"<font color='{dec_color.hexval()}'><b>{a.status.upper()}</b></font>", table_cell),
                    Paragraph(a.approver.full_name if a.approver else "Reviewer", table_cell),
                    Paragraph(dec_date, table_cell),
                    Paragraph(comments_text, table_cell),
                ])
            appr_t = Table(appr_data, colWidths=[90, 120, 110, 220])
            appr_t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), c_bg_light),
                ("BOX", (0, 0), (-1, -1), 0.5, c_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(appr_t)
        else:
            story.append(Paragraph("<b>STATUS: PENDING HUMAN REVIEW</b> — No formal sign-off decision has been recorded yet.", body_style))
        story.append(Spacer(1, 14))

        # 8. Integrity Statement & Legal Disclaimer (Requirements 6 & 7)
        disclaimer_text = (
            "<b>IMPORTANT NOTICE & AUDIT INTEGRITY STATEMENT:</b><br/>"
            "This report reflects the evaluation state of the referenced marketing asset as of the report generation date. "
            "Verification is performed through CitationGate deterministic source tracing against active organization knowledge. "
            "<b>This document is intended strictly for internal brand governance, quality assurance, and workflow audit purposes. "
            "It does NOT constitute legal advice, government approval, regulatory clearance, or a guarantee that the marketing "
            "content is legally compliant under regional advertising standards.</b> "
            "If draft copy or governance knowledge is modified after this date, an updated evaluation report must be generated."
        )
        disc_box = Table([[Paragraph(disclaimer_text, callout_style)]], colWidths=[540])
        disc_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#FECACA")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(disc_box)

        # Build document with NumberedCanvas
        doc.build(story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()

    def get_report_json(self) -> Dict[str, Any]:
        """Returns structured report data for programmatic and audit consumption."""
        base_score = max(0, 100 - (self.review.risk_score or 0))
        if base_score < 60 or self.review.risk_level == "Critical":
            grade = "F"
        elif base_score < 70 or self.review.risk_level == "High":
            grade = "C"
        elif base_score < 85 or self.review.risk_level == "Medium":
            grade = "B"
        elif base_score < 95:
            grade = "A"
        else:
            grade = "A+"

        claims_data = [
            {
                "claim_id": c.id,
                "claim_text": c.claim_text or c.text,
                "claim_type": c.claim_type,
                "status": c.status,
                "confidence": c.confidence,
                "matched_fact_id": c.matched_fact_id,
                "matched_fact_title": c.matched_fact.title if c.matched_fact else None,
                "evidence_id": c.evidence_id,
                "evidence_title": c.evidence.title if c.evidence else None,
                "reasoning": c.reasoning,
            }
            for c in (self.review.claims or [])
        ]
        findings_data = [
            {
                "finding_id": f.id,
                "finding_type": f.finding_type,
                "severity": f.severity,
                "status": f.status,
                "title": f.title,
                "message": f.message,
                "quoted_text": f.quoted_text,
                "suggested_fix": f.suggested_replacement or f.suggestion,
                "source_type": f.source_type,
                "source_reference": f.source_reference,
            }
            for f in (self.review.findings or [])
        ]
        evidence_data = [
            {
                "evidence_id": ea.evidence.id,
                "title": ea.evidence.title,
                "filename": ea.evidence.filename,
                "file_type": ea.evidence.file_type,
                "status": ea.evidence.effective_status,
                "source_reference": ea.evidence.source_reference,
                "relevance_notes": ea.relevance_notes,
            }
            for ea in (self.review.evidence_associations or [])
            if ea.evidence
        ]
        approvals_data = [
            {
                "approval_id": a.id,
                "status": a.status,
                "approver_name": a.approver.full_name if a.approver else None,
                "decided_at": a.decided_at.isoformat() if a.decided_at else None,
                "comments": a.comments,
                "is_override": a.is_override,
                "override_reason": a.override_reason,
            }
            for a in (self.review.approvals or [])
        ]

        # Fingerprint
        raw_sig = f"{self.review.id}:{self.review.updated_at}:{len(findings_data)}:{len(claims_data)}"
        version_hash = hashlib.sha256(raw_sig.encode()).hexdigest()[:16]

        return {
            "report_title": "BrandProof Brand Evaluation & Verification Audit Report",
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
            "report_version_fingerprint": version_hash,
            "evaluation_id": self.review.id,
            "campaign_title": self.review.title,
            "organization_name": self.org_name,
            "evaluation_status": self.review.status,
            "brand_health_grade": grade,
            "compliance_score": base_score,
            "risk_score": self.review.risk_score,
            "risk_level": self.review.risk_level,
            "scopes": {
                "product": self.review.product,
                "region": self.review.region,
                "channel": self.review.channel,
                "content_type": self.review.content_type,
                "intended_audience": self.review.intended_audience,
                "purpose": self.review.purpose,
            },
            "reviewed_content": self.doc_version.extracted_text if self.doc_version else self.review.summary,
            "claims": claims_data,
            "findings": findings_data,
            "evidence_documents": evidence_data,
            "approvals": approvals_data,
            "disclaimer": (
                "This report is for internal brand governance and workflow verification only. "
                "It does NOT constitute legal advice or guarantee legal advertising compliance."
            ),
        }
