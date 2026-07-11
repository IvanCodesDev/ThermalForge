"""ThermalForge 统一环境配置。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

REQUIRED_LLM_MODEL = "gpt-5.6-sol"
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """从项目根目录的 .env 读取外部模型配置。"""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL")
    openai_text_model: str = Field(default=REQUIRED_LLM_MODEL, validation_alias="OPENAI_TEXT_MODEL")

    @field_validator("openai_text_model")
    @classmethod
    def require_governed_model(cls, value: str) -> str:
        if value != REQUIRED_LLM_MODEL:
            raise ValueError(f"OPENAI_TEXT_MODEL 必须为 {REQUIRED_LLM_MODEL}")
        return value
    openai_image_model: str = Field(default="gpt-image-2", validation_alias="OPENAI_IMAGE_MODEL")

    hyper3d_api_key: str = Field(default="", validation_alias="HYPER3D_API_KEY")
    hyper3d_base_url: str = Field(default="https://api.hyper3d.com/api/v2", validation_alias="HYPER3D_BASE_URL")

    ai_request_timeout_seconds: float = Field(default=120.0, validation_alias="AI_REQUEST_TIMEOUT_SECONDS")
    ai_max_retries: int = Field(default=2, validation_alias="AI_MAX_RETRIES")

    cors_origins: str = Field(default="http://localhost:5173", validation_alias="CORS_ORIGINS")
    thermalforge_mode: Literal["real", "development"] = Field(
        default="real",
        validation_alias="THERMALFORGE_MODE",
    )
    database_path: str = Field(
        default=str(PROJECT_ROOT / "data" / "thermalforge.db"),
        validation_alias="THERMALFORGE_DB_PATH",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_real(self) -> bool:
        return self.thermalforge_mode == "real"


@lru_cache
def get_settings() -> Settings:
    return Settings()
