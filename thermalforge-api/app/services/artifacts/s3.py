import asyncio
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, cast

import boto3
from botocore.exceptions import ClientError

from app.domain.errors import ArtifactConflict, InvalidArtifactPath
from app.services.artifacts.base import ArtifactWriteResult


class S3Client(Protocol):
    def head_bucket(self, **kwargs: object) -> dict[str, object]: ...

    def head_object(self, **kwargs: object) -> dict[str, object]: ...

    def put_object(self, **kwargs: object) -> object: ...

    def get_object(self, **kwargs: object) -> dict[str, object]: ...

    def upload_file(self, *args: object, **kwargs: object) -> object: ...

    def download_file(self, *args: object, **kwargs: object) -> object: ...


class S3ArtifactStore:
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        client: S3Client | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = client or cast(
            S3Client,
            boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            ),
        )

    @staticmethod
    def _build_key(task_id: str, relative_path: str) -> str:
        path = PurePosixPath(relative_path)
        if (
            not task_id
            or "/" in task_id
            or "\\" in task_id
            or path.is_absolute()
            or ".." in path.parts
        ):
            raise InvalidArtifactPath()
        return f"{task_id}/{path.as_posix()}"

    async def _head(self, key: str) -> dict[str, object] | None:
        try:
            return await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._bucket,
                Key=key,
            )
        except KeyError:
            return None
        except ClientError as error:
            error_code = str(error.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    async def put_bytes(
        self,
        *,
        task_id: str,
        relative_path: str,
        payload: bytes,
        mime_type: str,
    ) -> ArtifactWriteResult:
        key = self._build_key(task_id, relative_path)
        digest = sha256(payload).hexdigest()
        existing = await self._head(key)

        if existing is not None:
            metadata = cast(dict[str, str], existing.get("Metadata", {}))
            if metadata.get("sha256") != digest:
                raise ArtifactConflict(f"s3://{self._bucket}/{key}")
        else:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=payload,
                ContentType=mime_type,
                Metadata={"sha256": digest},
            )

        return ArtifactWriteResult(
            storage_uri=f"s3://{self._bucket}/{key}",
            sha256=digest,
            size_bytes=len(payload),
            mime_type=mime_type,
        )

    async def read_bytes(self, storage_uri: str) -> bytes:
        prefix = f"s3://{self._bucket}/"
        if not storage_uri.startswith(prefix):
            raise InvalidArtifactPath()
        key = storage_uri.removeprefix(prefix)
        if not key or ".." in PurePosixPath(key).parts:
            raise InvalidArtifactPath()

        response = await asyncio.to_thread(
            self._client.get_object,
            Bucket=self._bucket,
            Key=key,
        )
        body = cast(Any, response["Body"])
        return cast(bytes, await asyncio.to_thread(body.read))

    @staticmethod
    def _hash_file(path: Path) -> tuple[str, int]:
        digest = sha256()
        size_bytes = 0
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
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
        key = self._build_key(task_id, relative_path)
        digest, size_bytes = await asyncio.to_thread(self._hash_file, source_path)
        existing = await self._head(key)

        if existing is not None:
            metadata = cast(dict[str, str], existing.get("Metadata", {}))
            if metadata.get("sha256") != digest:
                raise ArtifactConflict(f"s3://{self._bucket}/{key}")
        else:
            await asyncio.to_thread(
                self._client.upload_file,
                str(source_path),
                self._bucket,
                key,
                ExtraArgs={
                    "ContentType": mime_type,
                    "Metadata": {"sha256": digest},
                },
            )

        return ArtifactWriteResult(
            storage_uri=f"s3://{self._bucket}/{key}",
            sha256=digest,
            size_bytes=size_bytes,
            mime_type=mime_type,
        )

    async def copy_to_file(self, storage_uri: str, destination: Path) -> None:
        prefix = f"s3://{self._bucket}/"
        if not storage_uri.startswith(prefix):
            raise InvalidArtifactPath()
        key = storage_uri.removeprefix(prefix)
        if not key or ".." in PurePosixPath(key).parts:
            raise InvalidArtifactPath()
        destination.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            self._client.download_file,
            self._bucket,
            key,
            str(destination),
        )

    async def healthcheck(self) -> None:
        await asyncio.to_thread(
            self._client.head_bucket,
            Bucket=self._bucket,
        )
