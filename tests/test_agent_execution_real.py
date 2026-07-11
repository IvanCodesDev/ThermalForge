from __future__ import annotations

import asyncio
from hashlib import sha256

import pytest
from pydantic import BaseModel

from core.agents.contracts import (
    AgentDefinition,
    ExecutionContext,
    PromptDefinition,
    QualityGate,
    RetryPolicy,
    SkillDefinition,
    ToolDefinition,
)
from core.agents.execution import (
    AgentExecutionError,
    AgentExecutionService,
    QualityGateRegistry,
    ToolAdapterRegistry,
)
from core.agents.registry import AgentRegistry, PromptRegistry, SkillRegistry
from core.config import Settings
from core.persistence import SQLiteDocumentStore


class InputPayload(BaseModel):
    name: object


def registry(*, with_gate: bool = False, retries: int = 1) -> AgentRegistry:
    template = "Return a valid JSON object"
    prompt = PromptDefinition(
        id="real.v1",
        version="1.0.0",
        template=template,
        sha256=sha256(template.encode()).hexdigest(),
    )
    tool = ToolDefinition(id="source_reader", description="Read validated input")
    gate = (QualityGate(id="must_pass", description="must pass"),) if with_gate else ()
    definition = AgentDefinition(
        id="real_agent",
        version="1.0.0",
        model="gpt-5.6-sol",
        role="test",
        prompt_id=prompt.id,
        input_schema={
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "string"}},
            "additionalProperties": False,
        },
        skills=("real_skill",),
        tools=(tool.id,),
        quality_gates=gate,
        retry_policy=RetryPolicy(max_attempts=retries, retryable_errors=("invalid_output",)),
    )
    return AgentRegistry(
        Settings(OPENAI_TEXT_MODEL="gpt-5.6-sol"),
        PromptRegistry((prompt,)),
        SkillRegistry((SkillDefinition(id="real_skill", version="1", description="real"),)),
        (tool,),
        (definition,),
    )


def adapters() -> ToolAdapterRegistry:
    result = ToolAdapterRegistry()
    result.register("source_reader", lambda payload, context: payload)
    return result


def test_execution_rejects_invalid_input_before_provider() -> None:
    calls = 0

    async def provider(model, prompt, payload):
        nonlocal calls
        calls += 1
        return {"answer": "should not run"}

    service = AgentExecutionService(registry=registry(), provider=provider, tools=adapters())
    with pytest.raises(AgentExecutionError, match="input_schema"):
        asyncio.run(service.execute("real_agent", InputPayload(name=123), ExecutionContext(project_id="p-1")))
    assert calls == 0


def test_execution_runs_real_adapter_validates_output_and_retries_invalid_output() -> None:
    calls = 0

    async def provider(model, prompt, payload):
        nonlocal calls
        calls += 1
        assert payload["tool_outputs"]["source_reader"] == {"name": "motor"}
        return {} if calls == 1 else {"answer": "verified"}

    service = AgentExecutionService(registry=registry(retries=2), provider=provider, tools=adapters())
    result = asyncio.run(service.execute("real_agent", InputPayload(name="motor"), ExecutionContext(project_id="p-1")))

    assert result == {"answer": "verified"}
    assert calls == 2
    records = service.list(project_id="p-1")
    assert len(records) == 1
    assert records[0].status == "succeeded"
    assert records[0].metadata["attempts"] == 2


def test_execution_fails_closed_when_tool_adapter_is_missing() -> None:
    async def provider(model, prompt, payload):
        return {"answer": "no"}

    service = AgentExecutionService(
        registry=registry(),
        provider=provider,
        tools=ToolAdapterRegistry(),
    )
    with pytest.raises(AgentExecutionError, match="adapter"):
        asyncio.run(service.execute("real_agent", InputPayload(name="motor"), ExecutionContext(project_id="p-1")))


def test_execution_enforces_required_quality_gate() -> None:
    async def provider(model, prompt, payload):
        return {"answer": "candidate"}

    gates = QualityGateRegistry()
    gates.register("must_pass", lambda input_payload, output_payload, context: False)
    service = AgentExecutionService(
        registry=registry(with_gate=True),
        provider=provider,
        tools=adapters(),
        quality_gates=gates,
    )
    with pytest.raises(AgentExecutionError, match="quality gate must_pass"):
        asyncio.run(service.execute("real_agent", InputPayload(name="motor"), ExecutionContext(project_id="p-1")))
    assert service.list(project_id="p-1")[0].status == "failed"


def test_execution_record_survives_service_restart(tmp_path) -> None:
    async def provider(model, prompt, payload):
        return {"answer": "verified"}

    store = SQLiteDocumentStore(tmp_path / "thermalforge.db")
    first = AgentExecutionService(registry(), provider, tools=adapters(), store=store)
    asyncio.run(first.execute("real_agent", InputPayload(name="motor"), ExecutionContext(project_id="p-1")))
    execution_id = first.list(project_id="p-1")[0].id

    restarted = AgentExecutionService(
        registry(), provider, tools=adapters(),
        store=SQLiteDocumentStore(tmp_path / "thermalforge.db"),
    )
    assert restarted.get(execution_id).status == "succeeded"
