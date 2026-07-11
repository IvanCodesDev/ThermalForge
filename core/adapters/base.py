"""隔离外部 Adapter 的公共结果边界。"""
from __future__ import annotations
from typing import Any, Protocol
from pydantic import BaseModel, ConfigDict, Field

class AdapterExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: str
    outputs: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

class Adapter(Protocol):
    def execute(self, handoff: BaseModel) -> AdapterExecutionResult: ...
