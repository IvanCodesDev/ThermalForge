import struct
import zlib
from hashlib import sha256
from time import perf_counter

from app.imaging.base import ImageGenerationRequest, ImageGenerationResult


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _fixture_png(view_id: str) -> bytes:
    color = sha256(view_id.encode()).digest()[:3]
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    scanline = b"\x00" + color
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(scanline))
        + _chunk(b"IEND", b"")
    )


class FixtureImageProvider:
    async def generate(
        self,
        request: ImageGenerationRequest,
    ) -> ImageGenerationResult:
        started_at = perf_counter()
        return ImageGenerationResult(
            payload=_fixture_png(request.view_id),
            mime_type="image/png",
            provider="fixture",
            model="deterministic-image-fixture-v1",
            request_id=None,
            latency_ms=round((perf_counter() - started_at) * 1000),
        )
