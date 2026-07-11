import asyncio
import json
from time import perf_counter
from typing import Any

import httpx
from pydantic import ValidationError

from app.domain.errors import InvalidLLMOutput, LLMProviderUnavailable
from app.llm.base import (
    LLMResult,
    StructuredLLMRequest,
    StructuredOutput,
)


class OpenAICompatibleLLMProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._transport = transport

    async def generate_structured(
        self,
        request: StructuredLLMRequest[StructuredOutput],
    ) -> LLMResult[StructuredOutput]:
        started_at = perf_counter()
        schema = json.dumps(
            request.response_model.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        payload = {
            "model": self._model,
            "instructions": (
                f"{request.system_prompt}\n\n"
                "Return only one JSON object. It must validate against this JSON "
                f"Schema: {schema}"
            ),
            "input": request.user_prompt,
            "max_output_tokens": request.max_tokens,
        }
        response = await self._post(payload)
        text = self._extract_output_text(response)
        try:
            value = request.response_model.model_validate_json(
                self._strip_code_fence(text)
            )
        except (ValidationError, ValueError, TypeError) as error:
            raise InvalidLLMOutput() from error

        usage = response.get("usage")
        usage_payload = usage if isinstance(usage, dict) else {}
        request_id = response.get("id")
        return LLMResult(
            value=value,
            provider="openai_compatible",
            model=self._model,
            request_id=request_id if isinstance(request_id, str) else None,
            input_tokens=self._token_count(usage_payload.get("input_tokens")),
            output_tokens=self._token_count(usage_payload.get("output_tokens")),
            latency_ms=round((perf_counter() - started_at) * 1000),
        )

    async def _post(self, payload: dict[str, object]) -> dict[str, Any]:
        attempts = 0
        while True:
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = await client.post(
                        f"{self._base_url}/responses",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                response.raise_for_status()
                decoded = response.json()
                if not isinstance(decoded, dict):
                    raise InvalidLLMOutput()
                return decoded
            except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                if attempts >= self._max_retries:
                    raise LLMProviderUnavailable() from error
                attempts += 1
                await asyncio.sleep(min(0.25 * (2 ** (attempts - 1)), 1.0))
            except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
                raise LLMProviderUnavailable() from error
            except json.JSONDecodeError as error:
                raise InvalidLLMOutput() from error

    @staticmethod
    def _extract_output_text(response: dict[str, Any]) -> str:
        direct = response.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct

        chunks: list[str] = []
        output = response.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    text = part.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
        combined = "".join(chunks).strip()
        if not combined:
            raise InvalidLLMOutput()
        return combined

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        first_newline = stripped.find("\n")
        if first_newline < 0:
            raise InvalidLLMOutput()
        body = stripped[first_newline + 1 :]
        if body.endswith("```"):
            body = body[:-3]
        return body.strip()

    @staticmethod
    def _token_count(value: object) -> int:
        return value if isinstance(value, int) and not isinstance(value, bool) else 0
