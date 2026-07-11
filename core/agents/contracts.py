"""正式 Agent、Prompt、Skill、Tool 与执行审计契约。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RetryPolicy(StrictContract):
    max_attempts: int = Field(default=1, ge=1, le=10)
    backoff_seconds: float = Field(default=0.0, ge=0)
    retryable_errors: tuple[str, ...] = ()


class QualityGate(StrictContract):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required: bool = True


class PromptDefinition(StrictContract):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    template: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SkillDefinition(StrictContract):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ToolDefinition(StrictContract):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required_permissions: tuple[str, ...] = ()
    adapter_only: bool = False


class ToolPolicy(StrictContract):
    allowed_tools: tuple[str, ...] = ()
    denied_permissions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def reject_duplicates(self) -> "ToolPolicy":
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("allowed_tools 不得重复")
        if len(set(self.denied_permissions)) != len(self.denied_permissions):
            raise ValueError("denied_permissions 不得重复")
        return self


class AgentDefinition(StrictContract):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    role: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    skills: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    quality_gates: tuple[QualityGate, ...] = ()
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class ExecutionContext(StrictContract):
    project_id: str = Field(min_length=1)
    pipeline_id: UUID | None = None
    engineering_revision: int | None = Field(default=None, ge=1)
    input_artifact_ids: tuple[str, ...] = ()


class ExecutionRecord(StrictContract):
    id: UUID = Field(default_factory=uuid4)
    agent_id: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: Literal["gpt-5.6-sol"]
    skills: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    status: Literal["started", "succeeded", "failed"]
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    context: ExecutionContext
    output_artifact_ids: tuple[str, ...] = ()
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
