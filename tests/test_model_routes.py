from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from core.api.app import app
from core.api.routes.models import get_hyper3d_client, get_openai_client
from core.config import Settings
from core.providers.hyper3d import Hyper3DClient
from core.providers.openai_models import OpenAIModelsClient


def test_settings_load_project_env_from_any_working_directory():
    settings = Settings()
    assert settings.openai_text_model == "gpt-5.6-sol"
    assert settings.openai_image_model == "gpt-image-2"
    assert settings.hyper3d_base_url == "https://api.hyper3d.com/api/v2"


def test_missing_keys_are_reported_without_leaking_secrets():
    client = TestClient(app)
    response = client.get("/models/config")
    assert response.status_code == 200
    payload = response.json()
    assert "api_key" not in str(payload).lower()
    assert payload["openai"]["text_model"]
    assert payload["openai"]["image_model"]


def test_openai_routes_forward_expected_payloads():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        if request.url.path.endswith("/responses"):
            assert payload["model"] == "gpt-5.6-sol"
            assert payload["input"] == "生成一个摘要"
            return httpx.Response(200, json={"id": "resp_test", "output": []})
        assert request.url.path.endswith("/images/generations")
        assert payload["model"] == "gpt-image-2"
        return httpx.Response(200, json={"data": [{"b64_json": "aW1hZ2U="}]})

    settings = Settings(
        OPENAI_API_KEY="test-openai-key",
        OPENAI_BASE_URL="https://openai.test/v1",
        OPENAI_TEXT_MODEL="gpt-5.6-sol",
    )
    transport = httpx.MockTransport(handler)
    app.dependency_overrides[get_openai_client] = lambda: OpenAIModelsClient(settings, transport)
    client = TestClient(app)
    try:
        text = client.post("/models/gpt-5.5/responses", json={"input": "生成一个摘要"})
        image = client.post(
            "/models/gpt-image-2/generations",
            json={"prompt": "机器人热管理外壳产品图"},
        )
    finally:
        app.dependency_overrides.clear()

    assert text.status_code == 200
    assert text.json()["id"] == "resp_test"
    assert image.status_code == 200
    assert image.json()["data"][0]["b64_json"] == "aW1hZ2U="


def test_generic_text_route_uses_configured_model_without_exposing_provider_name():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        assert request.url.path == "/v1/responses"
        assert payload["model"] == "gpt-5.6-sol"
        return httpx.Response(200, json={"id": "resp_generic", "status": "completed"})

    settings = Settings(
        OPENAI_API_KEY="test-openai-key",
        OPENAI_BASE_URL="https://openai.test/v1",
        OPENAI_TEXT_MODEL="gpt-5.6-sol",
    )
    app.dependency_overrides[get_openai_client] = lambda: OpenAIModelsClient(
        settings,
        httpx.MockTransport(handler),
    )
    client = TestClient(app)
    try:
        response = client.post("/models/text/responses", json={"input": "生成工程摘要"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == "resp_generic"


def test_hyper3d_submit_status_and_download():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rodin"):
            assert b'name="prompt"' in request.content
            return httpx.Response(
                200,
                json={
                    "error": None,
                    "message": "Submitted.",
                    "uuid": "task-1",
                    "jobs": {"uuids": ["job-1"], "subscription_key": "sub-1"},
                },
            )
        if request.url.path.endswith("/bang"):
            assert b'name="asset_id"' in request.content
            assert b'name="strength"' in request.content
            return httpx.Response(
                200,
                json={
                    "error": None,
                    "message": "Submitted.",
                    "uuid": "bang-task-1",
                    "jobs": {"uuids": ["bang-job-1"], "subscription_key": "bang-sub-1"},
                },
            )
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"jobs": [{"uuid": "job-1", "status": "Done"}]})
        assert request.url.path.endswith("/download")
        return httpx.Response(200, json={"list": [{"url": "https://asset.test/model.glb", "name": "model.glb"}]})

    settings = Settings(
        HYPER3D_API_KEY="test-hyper3d-key",
        HYPER3D_BASE_URL="https://hyper3d.test/api/v2",
    )
    transport = httpx.MockTransport(handler)
    app.dependency_overrides[get_hyper3d_client] = lambda: Hyper3DClient(settings, transport)
    client = TestClient(app)
    try:
        submit = client.post("/models/hyper3d/tasks", json={"prompt": "散热器外壳", "options": {}})
        bang = client.post(
            "/models/hyper3d/bang",
            json={"asset_id": "task-1", "strength": 6, "geometry_file_format": "glb"},
        )
        status = client.post("/models/hyper3d/status", json={"subscription_key": "sub-1"})
        download = client.post("/models/hyper3d/download", json={"task_uuid": "task-1"})
    finally:
        app.dependency_overrides.clear()

    assert submit.status_code == 200
    assert submit.json()["uuid"] == "task-1"
    assert bang.status_code == 200
    assert bang.json()["uuid"] == "bang-task-1"
    assert status.status_code == 200
    assert download.status_code == 200
    assert download.json()["list"][0]["name"] == "model.glb"


def test_hyper3d_balance_is_checked_without_spending_generation_credits():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/check_balance")
        return httpx.Response(200, json={"balance": 8})

    settings = Settings(
        HYPER3D_API_KEY="test-hyper3d-key",
        HYPER3D_BASE_URL="https://hyper3d.test/api/v2",
    )
    app.dependency_overrides[get_hyper3d_client] = lambda: Hyper3DClient(
        settings,
        httpx.MockTransport(handler),
    )
    client = TestClient(app)
    try:
        response = client.get("/models/hyper3d/balance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"balance": 8}
