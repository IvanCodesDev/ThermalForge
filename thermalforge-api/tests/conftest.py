import pytest


@pytest.fixture(autouse=True)
def isolate_image_provider_from_local_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unit and integration tests must not call a paid image provider."""
    monkeypatch.setenv("THERMALFORGE_IMAGE_PROVIDER", "fixture")
