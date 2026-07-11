from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    prompt: str
    view_id: str


@dataclass(frozen=True, slots=True)
class ImageGenerationResult:
    payload: bytes
    mime_type: str
    provider: str
    model: str
    request_id: str | None
    latency_ms: int


class ImageGenerationProvider(Protocol):
    async def generate(
        self,
        request: ImageGenerationRequest,
    ) -> ImageGenerationResult: ...
