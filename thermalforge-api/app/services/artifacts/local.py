import os
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import aiofiles

from app.domain.errors import ArtifactConflict, InvalidArtifactPath
from app.services.artifacts.base import ArtifactWriteResult


class LocalArtifactStore:
    _chunk_size = 1024 * 1024

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve_storage_path(self, storage_uri: str) -> Path:
        candidate = (self._root / storage_uri).resolve()
        if not candidate.is_relative_to(self._root):
            raise InvalidArtifactPath()
        return candidate

    async def put_bytes(
        self,
        *,
        task_id: str,
        relative_path: str,
        payload: bytes,
        mime_type: str,
    ) -> ArtifactWriteResult:
        task_root = (self._root / task_id).resolve()
        target = (task_root / relative_path).resolve()
        if not target.is_relative_to(task_root):
            raise InvalidArtifactPath()

        digest = sha256(payload).hexdigest()
        storage_uri = target.relative_to(self._root).as_posix()
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            async with aiofiles.open(target, "rb") as existing_file:
                existing_payload = await existing_file.read()
            if sha256(existing_payload).hexdigest() != digest:
                raise ArtifactConflict(storage_uri)
        else:
            async with aiofiles.open(target, "wb") as artifact_file:
                await artifact_file.write(payload)

        return ArtifactWriteResult(
            storage_uri=storage_uri,
            sha256=digest,
            size_bytes=len(payload),
            mime_type=mime_type,
        )

    async def read_bytes(self, storage_uri: str) -> bytes:
        target = self._resolve_storage_path(storage_uri)
        async with aiofiles.open(target, "rb") as artifact_file:
            return await artifact_file.read()

    async def _hash_file(self, path: Path) -> tuple[str, int]:
        digest = sha256()
        size_bytes = 0
        async with aiofiles.open(path, "rb") as source:
            while chunk := await source.read(self._chunk_size):
                digest.update(chunk)
                size_bytes += len(chunk)
        return digest.hexdigest(), size_bytes

    async def put_file(
        self,
        *,
        task_id: str,
        relative_path: str,
        source_path: Path,
        mime_type: str,
    ) -> ArtifactWriteResult:
        task_root = (self._root / task_id).resolve()
        target = (task_root / relative_path).resolve()
        if not target.is_relative_to(task_root):
            raise InvalidArtifactPath()

        digest, size_bytes = await self._hash_file(source_path)
        storage_uri = target.relative_to(self._root).as_posix()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing_digest, _ = await self._hash_file(target)
            if existing_digest != digest:
                raise ArtifactConflict(storage_uri)
            return ArtifactWriteResult(
                storage_uri=storage_uri,
                sha256=digest,
                size_bytes=size_bytes,
                mime_type=mime_type,
            )

        temporary_target = target.with_name(f".{target.name}.{uuid4().hex}.part")
        try:
            async with (
                aiofiles.open(source_path, "rb") as source,
                aiofiles.open(temporary_target, "wb") as destination,
            ):
                while chunk := await source.read(self._chunk_size):
                    await destination.write(chunk)
            temporary_target.replace(target)
        finally:
            if temporary_target.exists():
                temporary_target.unlink()

        return ArtifactWriteResult(
            storage_uri=storage_uri,
            sha256=digest,
            size_bytes=size_bytes,
            mime_type=mime_type,
        )

    async def copy_to_file(self, storage_uri: str, destination: Path) -> None:
        source_path = self._resolve_storage_path(storage_uri)
        destination.parent.mkdir(parents=True, exist_ok=True)
        async with (
            aiofiles.open(source_path, "rb") as source,
            aiofiles.open(destination, "wb") as target,
        ):
            while chunk := await source.read(self._chunk_size):
                await target.write(chunk)

    async def healthcheck(self) -> None:
        if not self._root.is_dir() or not os.access(self._root, os.W_OK):
            raise OSError("Artifact root is not writable.")
