from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentSource(BaseModel):
    artifact_id: str
    filename: str
    mime_type: str
    sha256: str
    size_bytes: int
    page_count: int


class DocumentChunk(BaseModel):
    id: str
    source_artifact_id: str
    chunk_index: int
    text: str
    page_number: int | None = None
    section_path: list[str] = Field(default_factory=list)
    content_type: Literal["text", "ocr"] = "text"


class DocumentTable(BaseModel):
    id: str
    source_artifact_id: str
    rows: list[list[str]]
    page_number: int | None = None
    section_path: list[str] = Field(default_factory=list)


class DocumentImage(BaseModel):
    id: str
    source_artifact_id: str
    width: int
    height: int
    page_number: int | None = None
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)


class ParsedDocument(BaseModel):
    page_count: int
    chunks: list[DocumentChunk] = Field(default_factory=list)
    tables: list[DocumentTable] = Field(default_factory=list)
    images: list[DocumentImage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentBundle(BaseModel):
    schema_version: str = "1.0"
    task_id: str
    content_trust: Literal["untrusted"] = "untrusted"
    sources: list[DocumentSource]
    chunks: list[DocumentChunk]
    tables: list[DocumentTable]
    images: list[DocumentImage]
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
