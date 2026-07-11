import asyncio
from dataclasses import dataclass
from typing import Protocol

from rapidocr import RapidOCR


@dataclass(frozen=True, slots=True)
class OcrResult:
    text: str
    confidence: float | None


class OcrProvider(Protocol):
    async def extract_text(self, image: bytes) -> OcrResult: ...


class RapidOcrProvider:
    def __init__(self) -> None:
        self._engine: RapidOCR | None = None
        self._lock = asyncio.Lock()

    def _extract_sync(self, image: bytes) -> OcrResult:
        if self._engine is None:
            self._engine = RapidOCR()

        result = self._engine(image)
        texts = tuple(result.txts or ())
        scores = tuple(float(score) for score in (result.scores or ()))
        confidence = sum(scores) / len(scores) if scores else None
        return OcrResult(
            text="\n".join(text.strip() for text in texts if text.strip()),
            confidence=confidence,
        )

    async def extract_text(self, image: bytes) -> OcrResult:
        # The inference session is shared to avoid repeatedly loading model weights.
        async with self._lock:
            return await asyncio.to_thread(self._extract_sync, image)
