from hashlib import sha256
from pathlib import Path

import pytest

from app.domain.errors import InvalidArtifactPath
from app.services.artifacts.local import LocalArtifactStore
from app.services.artifacts.s3 import S3ArtifactStore


@pytest.mark.asyncio
async def test_writes_and_reads_immutable_artifacts(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    payload = b"thermalforge-document"

    artifact = await store.put_bytes(
        task_id="task-1",
        relative_path="documents/source.txt",
        payload=payload,
        mime_type="text/plain",
    )

    assert artifact.sha256 == sha256(payload).hexdigest()
    assert artifact.size_bytes == len(payload)
    assert artifact.mime_type == "text/plain"
    assert await store.read_bytes(artifact.storage_uri) == payload


@pytest.mark.asyncio
async def test_rejects_paths_outside_the_artifact_root(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)

    with pytest.raises(InvalidArtifactPath):
        await store.put_bytes(
            task_id="task-1",
            relative_path="../../secret.txt",
            payload=b"blocked",
            mime_type="text/plain",
        )


@pytest.mark.asyncio
async def test_streams_files_into_and_out_of_local_storage(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "store")
    source = tmp_path / "source.bin"
    restored = tmp_path / "restored.bin"
    payload = b"thermalforge" * 200_000
    source.write_bytes(payload)

    artifact = await store.put_file(
        task_id="task-stream",
        relative_path="documents/source.bin",
        source_path=source,
        mime_type="application/octet-stream",
    )
    await store.copy_to_file(artifact.storage_uri, restored)

    assert artifact.size_bytes == len(payload)
    assert artifact.sha256 == sha256(payload).hexdigest()
    assert restored.read_bytes() == payload


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str, dict[str, str]]] = {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        payload, content_type, metadata = self.objects[(Bucket, Key)]
        return {
            "ContentLength": len(payload),
            "ContentType": content_type,
            "Metadata": metadata,
        }

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
        Metadata: dict[str, str],
    ) -> None:
        self.objects[(Bucket, Key)] = (Body, ContentType, Metadata)

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        payload, _, _ = self.objects[(Bucket, Key)]

        class Body:
            def read(self) -> bytes:
                return payload

        return {"Body": Body()}


@pytest.mark.asyncio
async def test_s3_store_uses_content_hash_metadata() -> None:
    client = FakeS3Client()
    store = S3ArtifactStore(bucket="thermalforge", client=client)

    artifact = await store.put_bytes(
        task_id="task-2",
        relative_path="models/final.glb",
        payload=b"glb-payload",
        mime_type="model/gltf-binary",
    )

    assert artifact.storage_uri == "s3://thermalforge/task-2/models/final.glb"
    assert await store.read_bytes(artifact.storage_uri) == b"glb-payload"
