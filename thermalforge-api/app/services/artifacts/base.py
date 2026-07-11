from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ArtifactWriteResult:
    storage_uri: str
    sha256: str
    size_bytes: int
    mime_type: str


class ArtifactStore(Protocol):
    async def put_bytes(
        self,
        *,
        task_id: str,
        relative_path: str,
        payload: bytes,
        mime_type: str,
    ) -> ArtifactWriteResult: ...

    async def read_bytes(self, storage_uri: str) -> bytes: ...

    async def put_file(
        self,
        *,
        task_id: str,
        relative_path: str,
        source_path: Path,
        mime_type: str,
    ) -> ArtifactWriteResult: ...

    async def copy_to_file(self, storage_uri: str, destination: Path) -> None: ...

    async def healthcheck(self) -> None: ...
