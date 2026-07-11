from time import perf_counter

import anthropic
from anthropic import AsyncAnthropic

from app.domain.errors import InvalidLLMOutput, LLMProviderUnavailable
from app.llm.base import (
    LLMResult,
    StructuredLLMRequest,
    StructuredOutput,
)


class AnthropicLLMProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self._client = AsyncAnthropic(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        self._model = model

    async def generate_structured(
        self,
        request: StructuredLLMRequest[StructuredOutput],
    ) -> LLMResult[StructuredOutput]:
        started_at = perf_counter()
        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=request.max_tokens,
                thinking={"type": "adaptive"},
                output_config={"effort": "high"},
                system=request.system_prompt,
                messages=[{"role": "user", "content": request.user_prompt}],
                output_format=request.response_model,
            )
        except (
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.APIStatusError,
        ) as error:
            raise LLMProviderUnavailable() from error

        parsed = response.parsed_output
        if parsed is None:
            raise InvalidLLMOutput()

        return LLMResult(
            value=parsed,
            provider="anthropic",
            model=self._model,
            request_id=response._request_id,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=round((perf_counter() - started_at) * 1000),
        )
