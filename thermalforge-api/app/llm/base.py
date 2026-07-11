from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class StructuredLLMRequest[ResponseModel: BaseModel]:
    system_prompt: str
    user_prompt: str
    response_model: type[ResponseModel]
    prompt_version: str
    max_tokens: int = 16_000


@dataclass(frozen=True, slots=True)
class LLMResult[ResponseModel: BaseModel]:
    value: ResponseModel
    provider: str
    model: str
    request_id: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: int


class LLMProvider(Protocol):
    async def generate_structured(
        self,
        request: StructuredLLMRequest[StructuredOutput],
    ) -> LLMResult[StructuredOutput]: ...
