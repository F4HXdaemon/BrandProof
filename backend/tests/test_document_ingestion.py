import io
import pytest
import docx
from pypdf import PdfWriter


def test_txt_extraction():
    from app.services.extraction_service import extract_from_txt

    raw_text = (
        "# Executive Summary\n\n"
        "BrandProof guarantees that every marketing claim traces strictly to an approved source of truth.\n\n"
        "## Core Principles\n\n"
        "AI proposes. Evidence decides. People approve.\n\n"
        "NO VALID SOURCE = NO FINDING."
    )
    result = extract_from_txt(raw_text.encode("utf-8"), "manifesto.md")

    assert result.total_chunks == 5
    assert result.chunks[0].chunk_type == "heading"
    assert result.chunks[0].metadata.get("heading_level") == 1
    assert result.chunks[0].text == "# Executive Summary"

    assert result.chunks[1].chunk_type == "paragraph"
    assert "every marketing claim" in result.chunks[1].text

    assert result.chunks[2].chunk_type == "heading"
    assert result.chunks[2].metadata.get("heading_level") == 2

    assert result.chunks[3].chunk_type == "paragraph"
    assert result.chunks[4].text == "NO VALID SOURCE = NO FINDING."
    assert [c.sequence for c in result.chunks] == [0, 1, 2, 3, 4]


def test_docx_extraction():
    from app.services.extraction_service import extract_from_docx

    # Generate an in-memory docx document
    doc = docx.Document()
    doc.add_heading("Northstar Cloud SLA Agreement", level=1)
    doc.add_paragraph("This document details the availability SLA of 99.99% monthly uptime.")

    # Add a table
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Target"
    table.cell(1, 0).text = "Monthly Uptime"
    table.cell(1, 1).text = "99.99%"

    docx_stream = io.BytesIO()
    doc.save(docx_stream)
    docx_bytes = docx_stream.getvalue()

    result = extract_from_docx(docx_bytes, "sla.docx")
    assert result.total_chunks >= 3
    assert result.chunks[0].chunk_type == "heading"
    assert result.chunks[0].text == "Northstar Cloud SLA Agreement"
    assert result.chunks[1].chunk_type == "paragraph"
    assert "99.99%" in result.chunks[1].text
    assert result.chunks[2].chunk_type == "table"
    assert "Monthly Uptime" in result.chunks[2].text


def test_pdf_extraction():
    from app.services.extraction_service import extract_from_pdf

    # Generate an in-memory PDF with pypdf
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)

    pdf_stream = io.BytesIO()
    writer.write(pdf_stream)
    pdf_bytes = pdf_stream.getvalue()

    result = extract_from_pdf(pdf_bytes, "blank.pdf")
    assert result.page_count == 2


def test_invalid_upload_handling(client, creator_token):
    # 1. Invalid file extension
    files = {"file": ("malicious.exe", io.BytesIO(b"binary content"), "application/x-msdownload")}
    data = {
        "title": "Malicious Executable",
        "product": "All",
        "region": "Global",
        "channel": "All",
    }
    res = client.post(
        "/api/v1/reviews/new",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res.status_code == 400
    assert "Unsupported file extension" in res.json()["detail"]

    # 2. Empty payload (neither file nor pasted text)
    res_empty = client.post(
        "/api/v1/reviews/new",
        data={"title": "Empty submission"},
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res_empty.status_code == 400


def test_review_orchestrator_flow(client, creator_token):
    pasted_content = (
        "# Q2 Product Launch\n\n"
        "Northstar Pro cuts employee onboarding time by 25% with zero manual configuration.\n\n"
        "Backed by our SOC-2 Type II audit report."
    )

    data = {
        "title": "Q2 Launch Campaign Draft",
        "product": "Northstar Pro",
        "region": "India",
        "channel": "Advertisement",
        "content_type": "Ad Copy",
        "intended_audience": "Enterprise IT leaders",
        "purpose": "Promote faster employee onboarding",
        "pasted_text": pasted_content,
    }

    # 1. Submit review via orchestrator
    res = client.post(
        "/api/v1/reviews/new",
        data=data,
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res.status_code == 200
    review_data = res.json()
    assert review_data["title"] == "Q2 Launch Campaign Draft"
    assert review_data["product"] == "Northstar Pro"
    assert review_data["region"] == "India"
    assert review_data["channel"] == "Advertisement"
    assert review_data["processing_status"] == "Ready"
    assert review_data["intent_card"]["purpose"] == "Promote faster employee onboarding"

    doc_id = review_data["document_id"]
    review_id = review_data["id"]

    # 2. Verify Document Chunks
    res_chunks = client.get(
        f"/api/v1/documents/{doc_id}/chunks",
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res_chunks.status_code == 200
    chunks = res_chunks.json()
    assert len(chunks) == 3
    assert chunks[0]["chunk_type"] == "heading"
    assert chunks[1]["chunk_type"] == "paragraph"
    assert "25%" in chunks[1]["text"]

    # 3. Verify Secure File Download
    res_download = client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res_download.status_code == 200
    assert "attachment" in res_download.headers.get("content-disposition", "")
    assert b"Northstar Pro cuts employee onboarding" in res_download.content

    # 4. Verify Review Filter by Product
    res_filter = client.get(
        "/api/v1/reviews?product=Northstar Pro",
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res_filter.status_code == 200
    review_ids = [r["id"] for r in res_filter.json()]
    assert review_id in review_ids


def test_multipart_file_upload_review_flow(client, creator_token):
    file_content = (
        "# Security Overview\n\n"
        "Our ISO 27001 certified platform is the #1 onboarding solution.\n\n"
        "Guarantees immediate productivity improvements across all regions."
    ).encode("utf-8")

    files = {"file": ("security_overview.md", io.BytesIO(file_content), "text/markdown")}
    data = {
        "title": "Security Whitepaper Draft",
        "product": "Northstar Pro",
        "region": "India",
        "channel": "Whitepaper",
        "content_type": "Technical Whitepaper",
        "intended_audience": "CISOs and Security Teams",
        "purpose": "Demonstrate compliance posture",
    }

    res = client.post(
        "/api/v1/reviews/new",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res.status_code == 200
    review_data = res.json()
    assert review_data["title"] == "Security Whitepaper Draft"
    assert review_data["status"] == "Needs Review"
    assert review_data["processing_status"] == "Ready"
    assert review_data["document"] is not None
    assert len(review_data["document"]["versions"]) > 0
    assert len(review_data["document"]["versions"][0]["chunks"]) == 3
