import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles, read_upload_file_bounded
from app.models.user import User, UserRole
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.schemas.document_and_review import DocumentOut, DocumentVersionOut, DocumentChunkOut
from app.services.storage import get_storage, StorageError
from app.services.audit_service import record_audit_event
from app.services.review_orchestrator import ReviewOrchestrator

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    product: Optional[str] = Form("All Products"),
    region: Optional[str] = Form("Global"),
    channel: Optional[str] = Form("Marketing"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    orchestrator = ReviewOrchestrator(db)
    file_bytes = await read_upload_file_bounded(file)
    try:
        doc, ver = orchestrator.ingest_document(
            file_bytes=file_bytes,
            filename=file.filename or "upload.txt",
            content_type=file.content_type,
            title=title or file.filename or "Untitled Document",
            creator_id=current_user.id,
            organization_id=current_user.organization_id,
            product=product or "All Products",
            region=region or "Global",
            channel=channel or "Marketing",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    doc_out = DocumentOut.model_validate(doc)
    if doc.creator:
        doc_out.creator_name = doc.creator.full_name
    doc_out.versions = [_map_version_out(v) for v in doc.versions]
    return doc_out


def _map_version_out(v: DocumentVersion) -> DocumentVersionOut:
    chunks_out = [
        DocumentChunkOut(
            id=c.id,
            document_version_id=c.document_version_id,
            sequence=c.sequence,
            chunk_type=c.chunk_type,
            text=c.text,
            page_number=c.page_number,
            metadata=c.chunk_metadata or {},
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in (v.chunks or [])
    ]
    return DocumentVersionOut(
        id=v.id,
        document_id=v.document_id,
        version_number=v.version_number,
        file_path=v.file_path,
        file_size=v.file_size,
        extracted_text=v.extracted_text,
        error_message=v.error_message,
        created_by_id=v.created_by_id,
        created_at=v.created_at,
        updated_at=v.updated_at,
        chunks=chunks_out,
    )


@router.get("", response_model=List[DocumentOut])
def list_documents(
    status: Optional[str] = None,
    product: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Document).filter(Document.organization_id == current_user.organization_id)
    if status:
        query = query.filter(Document.status == status)
    if product:
        query = query.filter(Document.product == product)

    docs = query.order_by(Document.created_at.desc()).all()
    results = []
    for d in docs:
        doc_out = DocumentOut.model_validate(d)
        if d.creator:
            doc_out.creator_name = d.creator.full_name
        doc_out.versions = [_map_version_out(v) for v in d.versions]
        results.append(doc_out)
    return results


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == current_user.organization_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_out = DocumentOut.model_validate(doc)
    if doc.creator:
        doc_out.creator_name = doc.creator.full_name
    doc_out.versions = [_map_version_out(v) for v in doc.versions]
    return doc_out


@router.get("/{document_id}/chunks", response_model=List[DocumentChunkOut])
def get_document_chunks(
    document_id: str,
    version_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == current_user.organization_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    target_version = None
    if version_id:
        target_version = db.query(DocumentVersion).filter(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == doc.id
        ).first()
    else:
        target_version = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == doc.id
        ).order_by(DocumentVersion.version_number.desc()).first()

    if not target_version:
        return []

    return [
        DocumentChunkOut(
            id=c.id,
            document_version_id=c.document_version_id,
            sequence=c.sequence,
            chunk_type=c.chunk_type,
            text=c.text,
            page_number=c.page_number,
            metadata=c.chunk_metadata or {},
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in target_version.chunks
    ]


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == current_user.organization_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    storage = get_storage()
    file_bytes = storage.get_file(doc.file_path)
    if not file_bytes:
        raise HTTPException(status_code=404, detail="Stored file content not found")

    return Response(
        content=file_bytes,
        media_type=doc.file_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'}
    )


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes a document and all associated versions, cleaning up underlying object storage.
    Enforces organization-level data isolation and role permissions.
    """
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == current_user.organization_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Only creator, brand manager, or admin can delete
    if current_user.role not in [UserRole.ADMIN.value, UserRole.BRAND_MANAGER.value] and doc.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")

    storage = get_storage()
    paths_to_delete = set()
    if doc.file_path:
        paths_to_delete.add(doc.file_path)
    for v in (doc.versions or []):
        if v.file_path:
            paths_to_delete.add(v.file_path)

    failed_paths = []
    for fpath in paths_to_delete:
        try:
            storage.delete_file(fpath)
        except StorageError as se:
            failed_paths.append((fpath, str(se)))
        except Exception as e:
            failed_paths.append((fpath, str(e)))

    if failed_paths:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage cleanup failed for {len(failed_paths)} file(s). Database deletion was aborted to prevent orphaned private data."
        )

    doc_title = doc.title
    db.delete(doc)
    db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="DOCUMENT_DELETED",
        entity_type="Document",
        entity_id=document_id,
        metadata={"title": doc_title}
    )

    return {"status": "success", "message": f"Document '{doc_title}' deleted successfully."}
