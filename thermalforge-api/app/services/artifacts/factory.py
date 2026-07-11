from app.config import Settings
from app.services.artifacts.base import ArtifactStore
from app.services.artifacts.local import LocalArtifactStore
from app.services.artifacts.s3 import S3ArtifactStore


def build_artifact_store(settings: Settings) -> ArtifactStore:
    if settings.artifact_backend == "s3":
        return S3ArtifactStore(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
        )
    return LocalArtifactStore(settings.artifact_root)
