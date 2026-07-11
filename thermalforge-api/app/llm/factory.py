from app.config import Settings
from app.domain.errors import LLMProviderUnavailable
from app.llm.anthropic import AnthropicLLMProvider
from app.llm.base import LLMProvider
from app.llm.fixture import FixtureLLMProvider
from app.llm.openai_compatible import OpenAICompatibleLLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fixture":
        return FixtureLLMProvider()

    if settings.llm_provider == "openai_compatible":
        if (
            settings.openai_api_key is None
            or not settings.openai_api_key.get_secret_value().strip()
        ):
            raise LLMProviderUnavailable()
        return OpenAICompatibleLLMProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    if (
        settings.anthropic_api_key is None
        or not settings.anthropic_api_key.get_secret_value().strip()
    ):
        raise LLMProviderUnavailable()
    return AnthropicLLMProvider(
        api_key=settings.anthropic_api_key.get_secret_value(),
        model=settings.anthropic_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
