from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ArtifactKind, QualityStatus, TaskStatus


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime


class TaskCreate(BaseModel):
    prompt: str = Field(default="", max_length=10_000)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: TaskStatus
    stage: TaskStatus
    prompt: str
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class TaskEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    sequence: int
    event_type: str
    payload: dict[str, object]
    created_at: datetime


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    task_id: str
    kind: ArtifactKind
    version: int
    mime_type: str
    sha256: str
    size_bytes: int
    storage_uri: str
    metadata: dict[str, object] = Field(
        default_factory=dict,
        validation_alias="metadata_json",
    )
    quality_status: QualityStatus
    created_at: datetime


class ErrorBody(BaseModel):
    code: str
    message: str
    stage: str | None = None
    retryable: bool
    trace_id: str | None = None
