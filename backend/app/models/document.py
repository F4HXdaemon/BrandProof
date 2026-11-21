import enum
from typing import Optional
from sqlalchemy import Column, String, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import BaseModelMixin


class DocumentStatus(str, enum.Enum):
    UPLOADED = "Uploaded"
    EXTRACTING = "Extracting"
    READY = "Ready"
    ANALYZING = "Analyzing"
    NEEDS_REVIEW = "Needs Review"
    CHANGES_REQUESTED = "Changes Requested"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    FAILED = "Failed"
    DRAFT = "Draft"
    PROCESSING = "Processing"


class Document(Base, BaseModelMixin):
    __tablename__ = "documents"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    creator_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)  # e.g. text/markdown, application/pdf, docx
    file_path = Column(String(500), nullable=False)  # Storage key or relative path
    file_size = Column(Integer, default=0, nullable=False)

    product = Column(String(100), default="All Products", nullable=False, index=True)
    region = Column(String(100), default="Global", nullable=False, index=True)
    channel = Column(String(100), default="Marketing", nullable=False, index=True)

    status = Column(String(50), default=DocumentStatus.DRAFT.value, nullable=False, index=True)
    processing_status = Column(String(50), default="Ready", nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="documents")
    creator = relationship("User", back_populates="created_documents", foreign_keys=[creator_id])
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan", order_by="DocumentVersion.version_number")
    reviews = relationship("Review", back_populates="document", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="document", cascade="all, delete-orphan")

    @property
    def created_by_id(self) -> Optional[str]:
        return self.creator_id

    @created_by_id.setter
    def created_by_id(self, val: Optional[str]):
        self.creator_id = val


class DocumentVersion(Base, BaseModelMixin):
    __tablename__ = "document_versions"

    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    version_number = Column(Integer, default=1, nullable=False)
    parent_version_id = Column(String(36), ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True)
    change_reason = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0, nullable=False)
    extracted_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="versions")
    created_by = relationship("User", foreign_keys=[created_by_id])
    reviews = relationship("Review", back_populates="version")
    chunks = relationship("DocumentChunk", back_populates="version", cascade="all, delete-orphan", order_by="DocumentChunk.sequence")

    @property
    def storage_path(self) -> str:
        return self.file_path

    @storage_path.setter
    def storage_path(self, val: str):
        self.file_path = val


class DocumentChunk(Base, BaseModelMixin):
    __tablename__ = "document_chunks"

    document_version_id = Column(String(36), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, default=0, nullable=False, index=True)
    chunk_type = Column(String(50), default="paragraph", nullable=False)  # heading, paragraph, table, raw
    text = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)  # PDF page index (1-based)
    chunk_metadata = Column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    version = relationship("DocumentVersion", back_populates="chunks")

    @property
    def metadata_dict(self):
        return self.chunk_metadata or {}
