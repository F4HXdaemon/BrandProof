import io
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pypdf
import docx


class ExtractionError(Exception):
    """Raised when document extraction fails due to format corruption or parsing error."""
    pass


@dataclass
class ExtractedChunk:
    text: str
    sequence: int
    chunk_type: str = "paragraph"  # heading, paragraph, table, raw
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    full_text: str
    chunks: List[ExtractedChunk]
    total_chunks: int
    total_words: int
    total_chars: int
    page_count: Optional[int] = None


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def extract_from_txt(file_bytes: bytes, filename: str = "document.txt") -> ExtractionResult:
    """Extracts text and structural chunks from TXT / Markdown file bytes."""
    decoded_text = ""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            decoded_text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if not decoded_text and file_bytes:
        raise ExtractionError(f"Could not decode text file '{filename}' with supported UTF-8/Latin-1 encodings.")

    # Normalize line breaks
    normalized = decoded_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ExtractionResult(full_text="", chunks=[], total_chunks=0, total_words=0, total_chars=0, page_count=1)

    raw_paragraphs = re.split(r"\n\s*\n+", normalized)
    chunks: List[ExtractedChunk] = []
    full_paragraphs: List[str] = []

    for seq, raw_p in enumerate(raw_paragraphs):
        p_text = raw_p.strip()
        if not p_text:
            continue

        chunk_type = "paragraph"
        meta: Dict[str, Any] = {
            "word_count": count_words(p_text),
            "char_count": len(p_text),
        }

        # Detect Markdown headings
        if p_text.startswith("#"):
            match = re.match(r"^(#{1,6})\s+(.*)$", p_text)
            if match:
                chunk_type = "heading"
                meta["heading_level"] = len(match.group(1))
                meta["heading_title"] = match.group(2).strip()

        chunks.append(ExtractedChunk(
            text=p_text,
            sequence=len(chunks),
            chunk_type=chunk_type,
            page_number=1,
            metadata=meta,
        ))
        full_paragraphs.append(p_text)

    assembled_text = "\n\n".join(full_paragraphs)
    return ExtractionResult(
        full_text=assembled_text,
        chunks=chunks,
        total_chunks=len(chunks),
        total_words=count_words(assembled_text),
        total_chars=len(assembled_text),
        page_count=1,
    )


def extract_from_docx(file_bytes: bytes, filename: str = "document.docx") -> ExtractionResult:
    """Extracts text, headings, paragraphs, and tables from DOCX file bytes."""
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
    except Exception as e:
        raise ExtractionError(f"Failed to parse DOCX file '{filename}': {str(e)}")

    chunks: List[ExtractedChunk] = []
    full_elements: List[str] = []

    # 1. Extract paragraphs & headings
    for p in doc.paragraphs:
        p_text = p.text.strip()
        if not p_text:
            continue

        style_name = (p.style.name if p.style and p.style.name else "").lower()
        chunk_type = "paragraph"
        meta: Dict[str, Any] = {
            "word_count": count_words(p_text),
            "char_count": len(p_text),
            "docx_style": p.style.name if p.style else "Normal",
        }

        if "heading" in style_name:
            chunk_type = "heading"
            level_match = re.search(r"\d+", style_name)
            meta["heading_level"] = int(level_match.group(0)) if level_match else 1

        chunks.append(ExtractedChunk(
            text=p_text,
            sequence=len(chunks),
            chunk_type=chunk_type,
            page_number=1,
            metadata=meta,
        ))
        full_elements.append(p_text)

    # 2. Extract tables
    for t_idx, table in enumerate(doc.tables):
        table_rows = []
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                table_rows.append(" | ".join(row_cells))

        if table_rows:
            table_text = "\n".join(table_rows)
            chunks.append(ExtractedChunk(
                text=table_text,
                sequence=len(chunks),
                chunk_type="table",
                page_number=1,
                metadata={
                    "table_index": t_idx + 1,
                    "rows_count": len(table_rows),
                    "word_count": count_words(table_text),
                    "char_count": len(table_text),
                },
            ))
            full_elements.append(table_text)

    assembled_text = "\n\n".join(full_elements)
    return ExtractionResult(
        full_text=assembled_text,
        chunks=chunks,
        total_chunks=len(chunks),
        total_words=count_words(assembled_text),
        total_chars=len(assembled_text),
        page_count=1,
    )


def extract_from_pdf(file_bytes: bytes, filename: str = "document.pdf") -> ExtractionResult:
    """Extracts text and page-indexed chunks from PDF file bytes."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise ExtractionError(f"Failed to read PDF file '{filename}': {str(e)}")

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise ExtractionError(f"PDF file '{filename}' is password-protected and cannot be read.")

    chunks: List[ExtractedChunk] = []
    full_page_texts: List[str] = []
    page_count = len(reader.pages)

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        page_text = ""
        try:
            page_text = page.extract_text() or ""
        except Exception as e:
            page_text = f"[Error extracting text from page {page_num}: {str(e)}]"

        clean_page_text = page_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if clean_page_text:
            full_page_texts.append(clean_page_text)
            # Break page text into paragraph chunks
            paragraphs = re.split(r"\n\s*\n+", clean_page_text)
            for p in paragraphs:
                p_clean = p.strip()
                if not p_clean:
                    continue
                chunks.append(ExtractedChunk(
                    text=p_clean,
                    sequence=len(chunks),
                    chunk_type="paragraph",
                    page_number=page_num,
                    metadata={
                        "page_number": page_num,
                        "word_count": count_words(p_clean),
                        "char_count": len(p_clean),
                    },
                ))

    assembled_text = "\n\n".join(full_page_texts)
    return ExtractionResult(
        full_text=assembled_text,
        chunks=chunks,
        total_chunks=len(chunks),
        total_words=count_words(assembled_text),
        total_chars=len(assembled_text),
        page_count=page_count,
    )


def extract_document_chunks(
    file_bytes: bytes,
    filename: str,
    content_type: Optional[str] = None,
) -> ExtractionResult:
    """
    Unified extraction entrypoint for TXT, MD, DOCX, and PDF.
    Validates file format, normalizes text into sequence chunks,
    and returns an ExtractionResult.
    """
    if not file_bytes:
        raise ExtractionError(f"File '{filename}' is empty (0 bytes).")

    ext = os.path.splitext(filename.lower())[1]

    if ext in [".txt", ".text", ".md", ".markdown"] or (content_type and "text" in content_type):
        return extract_from_txt(file_bytes, filename)
    elif ext == ".docx" or (content_type and "wordprocessingml" in content_type):
        return extract_from_docx(file_bytes, filename)
    elif ext == ".pdf" or (content_type and "pdf" in content_type):
        return extract_from_pdf(file_bytes, filename)
    else:
        raise ExtractionError(
            f"Unsupported document format '{ext or content_type}'. Supported formats: .txt, .md, .docx, .pdf"
        )


def prepare_image_ocr_interface(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Architectural placeholder for future image OCR extraction phase.
    Equipped with PIL / pytesseract interface definitions.
    """
    return {
        "status": "ready_for_ocr",
        "filename": filename,
        "byte_size": len(file_bytes),
        "engine": "pytesseract",
        "description": "Image OCR pipeline prepared for future computer vision claim analysis phase.",
    }
