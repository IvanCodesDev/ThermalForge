from types import SimpleNamespace
from typing import Any

import pytest

import app.llm.anthropic as anthropic_adapter
from app.engineering.schemas import EngineeringBrief
from app.llm.anthropic import AnthropicLLMProvider
from app.llm.base import StructuredLLMRequest


class FakeMessages:
    def __init__(self) -> None:
        self.arguments: dict[str, Any] = {}

    async def parse(self, **kwargs: Any) -> Any:
        self.arguments = kwargs
        return SimpleNamespace(
            parsed_output=EngineeringBrief(
                project_title="结构化输出",
                overall_confidence=0.8,
            ),
            _request_id="request-123",
            usage=SimpleNamespace(input_tokens=42, output_tokens=24),
        )


class FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = FakeMessages()


@pytest.mark.asyncio
async def test_anthropic_adapter_uses_official_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeAnthropicClient()
    monkeypatch.setattr(
        anthropic_adapter,
        "AsyncAnthropic",
        lambda **_: client,
    )
    provider = AnthropicLLMProvider(
        api_key="test-key",
        model="claude-opus-4-8",
        timeout_seconds=30,
        max_retries=2,
    )

    result = await provider.generate_structured(
        StructuredLLMRequest(
            system_prompt="system",
            user_prompt="user",
            response_model=EngineeringBrief,
            prompt_version="test-v1",
        )
    )

    assert result.value.project_title == "结构化输出"
    assert result.request_id == "request-123"
    assert client.messages.arguments["model"] == "claude-opus-4-8"
    assert client.messages.arguments["thinking"] == {"type": "adaptive"}
    assert client.messages.arguments["output_config"] == {"effort": "high"}
    assert client.messages.arguments["output_format"] is EngineeringBrief
