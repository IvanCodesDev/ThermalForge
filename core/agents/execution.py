"""受治理的 LLM Agent 执行与不可变审计记录。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Awaitable, Callable
from uuid import UUID

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel

from core.agents.contracts import ExecutionContext, ExecutionRecord
from core.agents.registry import AgentRegistry
from core.config import PROJECT_ROOT, REQUIRED_LLM_MODEL
from core.persistence import DocumentNotFoundError, SQLiteDocumentStore

Provider = Callable[[str, str, dict[str, Any]], Awaitable[dict[str, Any]]]
ToolAdapter = Callable[[dict[str, Any], ExecutionContext], Any]
QualityGateHandler = Callable[[dict[str, Any], dict[str, Any], ExecutionContext], bool]


class AgentExecutionError(RuntimeError):
    def __init__(self, message: str, *, code: str = "execution_error") -> None:
        super().__init__(message)
        self.code = code


class ToolAdapterRegistry:
    """Runtime implementations for declared Agent tools."""

    def __init__(self) -> None:
        self._items: dict[str, ToolAdapter] = {}

    def register(self, tool_id: str, adapter: ToolAdapter) -> None:
        if tool_id in self._items:
            raise ValueError(f"tool adapter {tool_id} already registered")
        self._items[tool_id] = adapter

    def execute(
        self,
        tool_ids: tuple[str, ...],
        payload: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for tool_id in tool_ids:
            adapter = self._items.get(tool_id)
            if adapter is None:
                raise AgentExecutionError(
                    f"required tool adapter {tool_id} is not configured",
                    code="missing_tool_adapter",
                )
            outputs[tool_id] = adapter(payload, context)
        return outputs


class QualityGateRegistry:
    """Executable quality gates; required gates fail closed when absent."""

    def __init__(self) -> None:
        self._items: dict[str, QualityGateHandler] = {}

    def register(self, gate_id: str, handler: QualityGateHandler) -> None:
        if gate_id in self._items:
            raise ValueError(f"quality gate {gate_id} already registered")
        self._items[gate_id] = handler

    def evaluate(
        self,
        gate_id: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
        context: ExecutionContext,
    ) -> None:
        handler = self._items.get(gate_id)
        if handler is None:
            raise AgentExecutionError(
                f"required quality gate {gate_id} is not configured",
                code="missing_quality_gate",
            )
        if not handler(input_payload, output_payload, context):
            raise AgentExecutionError(
                f"quality gate {gate_id} failed",
                code="quality_gate_failed",
            )


def build_default_tool_adapters() -> ToolAdapterRegistry:
    """Adapters expose only the already validated server-side payload."""
    registry = ToolAdapterRegistry()
    registry.register("source_content_reader", lambda payload, context: payload)
    registry.register("engineering_schema_reader", lambda payload, context: payload)
    registry.register("simulation_result_reader", lambda payload, context: payload)
    registry.register("optimization_feedback_reader", lambda payload, context: payload)
    registry.register("optimization_plan_reader", lambda payload, context: payload)
    registry.register("foc_demo_snapshot_reader", lambda payload, context: payload.get("source_snapshot", {}))
    return registry


def build_default_quality_gates() -> QualityGateRegistry:
    registry = QualityGateRegistry()
    registry.register("strict_output", lambda input_payload, output_payload, context: True)
    registry.register(
        "evidence_only",
        lambda input_payload, output_payload, context: (
            isinstance(output_payload.get("specification"), dict)
            and isinstance(output_payload["specification"].get("unresolved"), list)
        ),
    )
    registry.register(
        "confirmed_spec",
        lambda input_payload, output_payload, context: context.engineering_revision is not None,
    )
    registry.register("reproducible", lambda input_payload, output_payload, context: bool(output_payload))
    registry.register(
        "feasibility_check",
        lambda input_payload, output_payload, context: (
            isinstance(output_payload.get("instructions"), list)
            and len(output_payload["instructions"]) > 0
        ),
    )
    registry.register(
        "confirmed_plan",
        lambda input_payload, output_payload, context: bool(output_payload),
    )
    registry.register(
        "multiview_complete",
        lambda input_payload, output_payload, context: (
            {item.get("id") for item in output_payload.get("views", []) if isinstance(item, dict)}
            == {"mother_three_quarter", "front", "left", "rear", "top", "elbow_section"}
        ),
    )
    return registry


class AgentExecutionService:
    """执行注册 Agent，并在成功或失败时保留完整审计。"""

    def __init__(
        self,
        registry: AgentRegistry,
        provider: Provider,
        *,
        tools: ToolAdapterRegistry | None = None,
        quality_gates: QualityGateRegistry | None = None,
        store: SQLiteDocumentStore | None = None,
    ) -> None:
        self.registry = registry
        self.provider = provider
        self.tools = tools or ToolAdapterRegistry()
        self.quality_gates = quality_gates or QualityGateRegistry()
        if store is None and registry.settings.is_real:
            configured = Path(registry.settings.database_path)
            store = SQLiteDocumentStore(configured if configured.is_absolute() else PROJECT_ROOT / configured)
        self._store = store
        self._records: dict[UUID, ExecutionRecord] = {}
        self._lock = RLock()

    async def execute(self, agent_id: str, payload: BaseModel, context: ExecutionContext) -> dict[str, Any]:
        definition = self.registry.get(agent_id)
        if definition.model != REQUIRED_LLM_MODEL:
            raise RuntimeError("Agent 有效模型不符合治理要求")
        prompt = self.registry.prompts.get(definition.prompt_id)
        input_payload = payload.model_dump(mode="json")
        try:
            Draft202012Validator(definition.input_schema).validate(input_payload)
        except JsonSchemaValidationError as exc:
            raise AgentExecutionError(
                f"input_schema validation failed: {exc.message}",
                code="invalid_input",
            ) from exc

        tool_outputs = self.tools.execute(definition.tools, input_payload, context)
        started = ExecutionRecord(
            agent_id=definition.id, agent_version=definition.version,
            prompt_id=prompt.id, prompt_version=prompt.version, prompt_hash=prompt.sha256,
            model=REQUIRED_LLM_MODEL, skills=definition.skills, tools=definition.tools,
            status="started", context=context,
        )
        self._save(started)
        attempts = 0
        last_error: Exception | None = None
        while attempts < definition.retry_policy.max_attempts:
            attempts += 1
            try:
                output = await self.provider(
                    REQUIRED_LLM_MODEL,
                    prompt.template,
                    {
                        "input": input_payload,
                        "tool_outputs": tool_outputs,
                        "context": context.model_dump(mode="json"),
                    },
                )
                if not isinstance(output, dict):
                    raise AgentExecutionError("provider output must be an object", code="invalid_output")
                try:
                    Draft202012Validator(definition.output_schema).validate(output)
                except JsonSchemaValidationError as exc:
                    raise AgentExecutionError(
                        f"output_schema validation failed: {exc.message}",
                        code="invalid_output",
                    ) from exc
                for gate in definition.quality_gates:
                    if gate.required:
                        self.quality_gates.evaluate(gate.id, input_payload, output, context)
                self._save(started.model_copy(update={
                    "status": "succeeded",
                    "completed_at": datetime.now(timezone.utc),
                    "metadata": {"attempts": attempts},
                }))
                return output
            except Exception as exc:
                last_error = exc
                code = exc.code if isinstance(exc, AgentExecutionError) else type(exc).__name__
                retryable = code in definition.retry_policy.retryable_errors
                if attempts >= definition.retry_policy.max_attempts or not retryable:
                    break

        assert last_error is not None
        self._save(started.model_copy(update={
            "status": "failed",
            "completed_at": datetime.now(timezone.utc),
            "error": str(last_error),
            "metadata": {"attempts": attempts},
        }))
        if isinstance(last_error, AgentExecutionError):
            raise last_error
        raise AgentExecutionError(str(last_error), code="provider_error") from last_error

    def get(self, execution_id: UUID) -> ExecutionRecord:
        with self._lock:
            if self._store is not None:
                try:
                    return ExecutionRecord.model_validate_json(json.dumps(
                        self._store.get("agent_execution", str(execution_id))
                    ))
                except DocumentNotFoundError as exc:
                    raise KeyError(str(exc)) from exc
            record = self._records.get(execution_id)
            if record is None:
                raise KeyError(f"execution {execution_id} 不存在")
            return record.model_copy(deep=True)

    def list(self, project_id: str | None = None, revision: int | None = None) -> list[ExecutionRecord]:
        with self._lock:
            records = (
                [ExecutionRecord.model_validate_json(json.dumps(item)) for item in self._store.list_latest("agent_execution")]
                if self._store is not None
                else list(self._records.values())
            )
        return [r.model_copy(deep=True) for r in records if (project_id is None or r.context.project_id == project_id) and (revision is None or r.context.engineering_revision == revision)]

    def _save(self, record: ExecutionRecord) -> None:
        with self._lock:
            if self._store is not None:
                self._store.put_next("agent_execution", str(record.id), record.model_dump(mode="json"))
                return
            self._records[record.id] = record
