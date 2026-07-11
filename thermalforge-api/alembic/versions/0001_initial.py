"""Create the Phase 1 task orchestration schema."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "idempotency_key",
            name="uq_task_project_idempotency",
        ),
    )
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "clarifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("field_key", sa.String(length=120), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clarification_task_answered",
        "clarifications",
        ["task_id", "answered_at"],
    )
    op.create_index(
        "ix_clarifications_task_id",
        "clarifications",
        ["task_id"],
    )

    op.create_table(
        "stage_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_artifact_ids", sa.JSON(), nullable=False),
        sa.Column("output_artifact_ids", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id",
            "stage",
            "attempt",
            name="uq_stage_run_attempt",
        ),
    )
    op.create_index("ix_stage_runs_task_id", "stage_runs", ["task_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("provider_model", sa.String(length=160), nullable=True),
        sa.Column("provider_task_id", sa.String(length=200), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("quality_status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id",
            "kind",
            "sha256",
            name="uq_artifact_task_kind_hash",
        ),
        sa.UniqueConstraint(
            "task_id",
            "kind",
            "version",
            name="uq_artifact_task_kind_version",
        ),
    )
    op.create_index("ix_artifacts_sha256", "artifacts", ["sha256"])
    op.create_index("ix_artifacts_task_id", "artifacts", ["task_id"])

    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id",
            "sequence",
            name="uq_task_event_sequence",
        ),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_events_task_id", table_name="task_events")
    op.drop_table("task_events")
    op.drop_index(
        "ix_clarifications_task_id",
        table_name="clarifications",
    )
    op.drop_index(
        "ix_clarification_task_answered",
        table_name="clarifications",
    )
    op.drop_table("clarifications")
    op.drop_index("ix_artifacts_task_id", table_name="artifacts")
    op.drop_index("ix_artifacts_sha256", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_stage_runs_task_id", table_name="stage_runs")
    op.drop_table("stage_runs")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("projects")
