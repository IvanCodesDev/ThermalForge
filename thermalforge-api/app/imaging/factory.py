from app.config import Settings
from app.domain.errors import ImageProviderUnavailable
from app.imaging.base import ImageGenerationProvider
from app.imaging.fixture import FixtureImageProvider
from app.imaging.openai_compatible import OpenAICompatibleImageProvider


def build_image_provider(settings: Settings) -> ImageGenerationProvider:
    if settings.image_provider == "fixture":
        return FixtureImageProvider()

    if (
        settings.openai_api_key is None
        or not settings.openai_api_key.get_secret_value().strip()
    ):
        raise ImageProviderUnavailable()
    return OpenAICompatibleImageProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        base_url=settings.openai_base_url,
        model=settings.openai_image_model,
        timeout_seconds=settings.image_timeout_seconds,
        max_retries=settings.image_max_retries,
    )
