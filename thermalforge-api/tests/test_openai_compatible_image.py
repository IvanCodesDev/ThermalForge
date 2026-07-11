import base64
import json

import httpx
import pytest

from app.domain.errors import ImageProviderUnavailable, InvalidImageOutput
from app.imaging.base import ImageGenerationRequest
from app.imaging.openai_compatible import OpenAICompatibleImageProvider


@pytest.mark.asyncio
async def test_openai_compatible_image_provider_decodes_png_output() -> None:
    png = b"\x89PNG\r\n\x1a\nfixture-image"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/images/generations"
        assert request.headers["authorization"] == "Bearer test-image-key"
        payload = json.loads(request.content)
        assert payload == {
            "model": "gpt-image-2",
            "prompt": "Render the same robot from the front.",
            "n": 1,
            "size": "1024x1024",
            "quality": "high",
            "output_format": "png",
            "background": "opaque",
        }
        return httpx.Response(
            200,
            json={
                "id": "image-request-1",
                "data": [{"b64_json": base64.b64encode(png).decode()}],
            },
        )

    provider = OpenAICompatibleImageProvider(
        api_key="test-image-key",
        base_url="https://images.example/v1",
        model="gpt-image-2",
        timeout_seconds=10,
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )

    result = await provider.generate(
        ImageGenerationRequest(
            prompt="Render the same robot from the front.",
            view_id="front",
        )
    )

    assert result.payload == png
    assert result.mime_type == "image/png"
    assert result.provider == "openai_compatible"
    assert result.model == "gpt-image-2"
    assert result.request_id == "image-request-1"


@pytest.mark.asyncio
async def test_openai_compatible_image_provider_rejects_invalid_base64() -> None:
    provider = OpenAICompatibleImageProvider(
        api_key="test-image-key",
        base_url="https://images.example/v1",
        model="gpt-image-2",
        timeout_seconds=10,
        max_retries=0,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"data": [{"b64_json": "not valid base64!"}]},
            )
        ),
    )

    with pytest.raises(InvalidImageOutput):
        await provider.generate(
            ImageGenerationRequest(prompt="Render a robot.", view_id="front")
        )


@pytest.mark.asyncio
async def test_openai_compatible_image_provider_maps_upstream_errors() -> None:
    provider = OpenAICompatibleImageProvider(
        api_key="test-image-key",
        base_url="https://images.example/v1",
        model="gpt-image-2",
        timeout_seconds=10,
        max_retries=0,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                429,
                json={"error": {"message": "quota exceeded"}},
            )
        ),
    )

    with pytest.raises(ImageProviderUnavailable) as raised:
        await provider.generate(
            ImageGenerationRequest(prompt="Render a robot.", view_id="front")
        )

    assert "test-image-key" not in str(raised.value)
