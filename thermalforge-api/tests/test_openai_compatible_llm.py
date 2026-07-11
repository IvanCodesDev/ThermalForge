import json

import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.domain.errors import InvalidLLMOutput, LLMProviderUnavailable
from app.llm.base import StructuredLLMRequest
from app.llm.factory import build_llm_provider
from app.llm.openai_compatible import OpenAICompatibleLLMProvider


class StructuredAnswer(BaseModel):
    title: str
    value: int


def request() -> StructuredLLMRequest[StructuredAnswer]:
    return StructuredLLMRequest(
        system_prompt="Use only supplied facts.",
        user_prompt='{"source":"verified"}',
        response_model=StructuredAnswer,
        prompt_version="test-v1",
        max_tokens=500,
    )


@pytest.mark.asyncio
async def test_generates_and_validates_responses_api_output() -> None:
    seen: dict[str, object] = {}

    async def handler(http_request: httpx.Request) -> httpx.Response:
        seen["url"] = str(http_request.url)
        seen["authorization"] = http_request.headers["Authorization"]
        seen["payload"] = json.loads(http_request.content)
        return httpx.Response(
            200,
            json={
                "id": "resp-1",
                "output_text": '{"title":"verified","value":7}',
                "usage": {"input_tokens": 12, "output_tokens": 8},
            },
        )

    provider = OpenAICompatibleLLMProvider(
        api_key="test-secret",
        base_url="https://gateway.example/v1/",
        model="gpt-5.6-sol",
        timeout_seconds=10,
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )

    result = await provider.generate_structured(request())

    assert result.value == StructuredAnswer(title="verified", value=7)
    assert result.provider == "openai_compatible"
    assert result.model == "gpt-5.6-sol"
    assert result.request_id == "resp-1"
    assert result.input_tokens == 12
    assert result.output_tokens == 8
    assert seen["url"] == "https://gateway.example/v1/responses"
    assert seen["authorization"] == "Bearer test-secret"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["input"] == '{"source":"verified"}'
    assert "Use only supplied facts." in str(payload["instructions"])
    assert '"title"' in str(payload["instructions"])


@pytest.mark.asyncio
async def test_extracts_fenced_json_from_response_content_blocks() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": '```json\n{"title":"nested","value":3}\n```',
                            }
                        ]
                    }
                ]
            },
        )
    )
    provider = OpenAICompatibleLLMProvider(
        api_key="test-secret",
        base_url="https://gateway.example/v1",
        model="gpt-5.6-sol",
        timeout_seconds=10,
        max_retries=0,
        transport=transport,
    )

    result = await provider.generate_structured(request())

    assert result.value.title == "nested"


@pytest.mark.asyncio
async def test_rejects_invalid_structured_output() -> None:
    provider = OpenAICompatibleLLMProvider(
        api_key="test-secret",
        base_url="https://gateway.example/v1",
        model="gpt-5.6-sol",
        timeout_seconds=10,
        max_retries=0,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"output_text": "{}"})
        ),
    )

    with pytest.raises(InvalidLLMOutput):
        await provider.generate_structured(request())


@pytest.mark.asyncio
async def test_maps_upstream_errors_without_exposing_response_body() -> None:
    provider = OpenAICompatibleLLMProvider(
        api_key="test-secret",
        base_url="https://gateway.example/v1",
        model="gpt-5.6-sol",
        timeout_seconds=10,
        max_retries=0,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                401,
                json={"error": "test-secret must never escape"},
            )
        ),
    )

    with pytest.raises(LLMProviderUnavailable) as captured:
        await provider.generate_structured(request())

    assert "test-secret" not in str(captured.value)


def test_factory_requires_key_for_openai_compatible_provider() -> None:
    with pytest.raises(LLMProviderUnavailable):
        build_llm_provider(
            Settings(
                llm_provider="openai_compatible",
                openai_api_key=None,
            )
        )
