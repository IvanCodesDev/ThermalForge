import asyncio
import base64
import binascii
import json
from time import perf_counter
from typing import Any

import httpx

from app.domain.errors import ImageProviderUnavailable, InvalidImageOutput
from app.imaging.base import ImageGenerationRequest, ImageGenerationResult

_MAX_IMAGE_BYTES = 25 * 1024 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class OpenAICompatibleImageProvider:
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

    async def generate(
        self,
        request: ImageGenerationRequest,
    ) -> ImageGenerationResult:
        started_at = perf_counter()
        response = await self._post(
            {
                "model": self._model,
                "prompt": request.prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "high",
                "output_format": "png",
                "background": "opaque",
            }
        )
        payload = self._decode_image(response)
        request_id = response.get("id")
        return ImageGenerationResult(
            payload=payload,
            mime_type="image/png",
            provider="openai_compatible",
            model=self._model,
            request_id=request_id if isinstance(request_id, str) else None,
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
                        f"{self._base_url}/images/generations",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                response.raise_for_status()
                decoded = response.json()
                if not isinstance(decoded, dict):
                    raise InvalidImageOutput()
                return decoded
            except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                if attempts >= self._max_retries:
                    raise ImageProviderUnavailable() from error
                attempts += 1
                await asyncio.sleep(min(0.25 * (2 ** (attempts - 1)), 1.0))
            except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
                raise ImageProviderUnavailable() from error
            except json.JSONDecodeError as error:
                raise InvalidImageOutput() from error

    @staticmethod
    def _decode_image(response: dict[str, Any]) -> bytes:
        data = response.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise InvalidImageOutput()
        encoded = data[0].get("b64_json")
        if not isinstance(encoded, str) or not encoded:
            raise InvalidImageOutput()
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise InvalidImageOutput() from error
        if (
            not payload.startswith(_PNG_SIGNATURE)
            or len(payload) > _MAX_IMAGE_BYTES
        ):
            raise InvalidImageOutput()
        return payload
