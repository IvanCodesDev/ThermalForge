from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ArtifactKind, QualityStatus, TaskStatus
from app.models.base import Base, utc_now


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "idempotency_key",
            name="uq_task_project_idempotency",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=TaskStatus.CREATED.value,
        index=True,
    )
    stage: Mapped[str] = mapped_column(
        String(32),
        default=TaskStatus.CREATED.value,
    )
    prompt: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class StageRunModel(Base):
    __tablename__ = "stage_runs"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "stage",
            "attempt",
            name="uq_stage_run_attempt",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(32))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    error_code: Mapped[str | None] = mapped_column(String(100))


class ArtifactModel(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "kind",
            "version",
            name="uq_artifact_task_kind_version",
        ),
        UniqueConstraint(
            "task_id",
            "kind",
            "sha256",
            name="uq_artifact_task_kind_hash",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(120))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_uri: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(100))
    provider_model: Mapped[str | None] = mapped_column(String(160))
    provider_task_id: Mapped[str | None] = mapped_column(String(200))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )
    quality_status: Mapped[str] = mapped_column(
        String(20),
        default=QualityStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def artifact_kind(self) -> ArtifactKind:
        return ArtifactKind(self.kind)


class TaskEventModel(Base):
    __tablename__ = "task_events"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="uq_task_event_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


class ClarificationModel(Base):
    __tablename__ = "clarifications"
    __table_args__ = (
        Index(
            "ix_clarification_task_answered",
            "task_id",
            "answered_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
    )
    field_key: Mapped[str] = mapped_column(String(120))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
