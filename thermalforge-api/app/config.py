from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="THERMALFORGE_",
        extra="ignore",
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "sqlite+aiosqlite:///./.data/thermalforge.db"
    auto_create_schema: bool = True
    artifact_backend: Literal["local", "s3"] = "local"
    artifact_root: Path = Path(".data/artifacts")
    model_asset_root: Path = Path("../frontend/public/models")
    whole_model_filename: str = "foc-robot-arm.glb"
    segmented_model_filename: str = "foc-robot-arm-bang.glb"
    hyper3d_model_filename: str = "hyper3d-robot-arm.glb"
    upload_temp_root: Path = Path(".data/uploads")
    max_upload_bytes: int = 20 * 1024 * 1024
    upload_chunk_bytes: int = 1024 * 1024
    max_archive_entries: int = 2_000
    max_archive_uncompressed_bytes: int = 100 * 1024 * 1024
    max_image_pixels: int = 50_000_000
    document_chunk_chars: int = 1_600
    document_chunk_overlap_chars: int = 200
    llm_provider: Literal["anthropic", "openai_compatible", "fixture"] = "fixture"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.6-sol"
    image_provider: Literal["openai_compatible", "fixture"] = "fixture"
    openai_image_model: str = "gpt-image-2"
    image_timeout_seconds: float = 180
    image_max_retries: int = 2
    llm_timeout_seconds: float = 120
    llm_max_retries: int = 2
    llm_max_tokens: int = 16_000
    redis_url: str = "redis://127.0.0.1:6379/0"
    queue_enabled: bool = False
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    s3_endpoint_url: str | None = None
    s3_bucket: str = "thermalforge-artifacts"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
