from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


def build_settings(tmp_path: Path) -> Settings:
    database_path = (tmp_path / "thermalforge.db").as_posix()
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{database_path}",
        artifact_root=tmp_path / "artifacts",
        queue_enabled=False,
        cors_origins=[],
    )


@pytest.fixture
async def api_client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    app = create_app(build_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        yield client


@pytest.mark.asyncio
async def test_health_checks_report_the_database_ready(api_client: AsyncClient) -> None:
    live_response = await api_client.get("/health/live")
    ready_response = await api_client.get("/health/ready")

    assert live_response.json() == {"status": "alive"}
    assert ready_response.json() == {
        "status": "ready",
        "checks": {
            "database": "ready",
            "queue": "ready",
            "artifact_store": "ready",
        },
    }


@pytest.mark.asyncio
async def test_creates_idempotent_projects_and_tasks(api_client: AsyncClient) -> None:
    project_response = await api_client.post(
        "/v1/projects",
        json={"name": "膝关节热增强"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    task_response = await api_client.post(
        f"/v1/projects/{project_id}/tasks",
        headers={"Idempotency-Key": "demo-task-1"},
        json={"prompt": "降低热点温度并保持外壳可拆卸"},
    )
    repeated_response = await api_client.post(
        f"/v1/projects/{project_id}/tasks",
        headers={"Idempotency-Key": "demo-task-1"},
        json={"prompt": "这次请求不会创建第二个任务"},
    )

    assert task_response.status_code == 201
    assert repeated_response.status_code == 201
    assert repeated_response.json()["id"] == task_response.json()["id"]
    assert task_response.json()["status"] == "created"

    task_id = task_response.json()["id"]
    artifacts_response = await api_client.get(f"/v1/tasks/{task_id}/artifacts")
    assert artifacts_response.status_code == 200
    assert artifacts_response.json() == []

    replay_response = await api_client.get(
        f"/v1/tasks/{task_id}/events",
        params={"follow": "false"},
    )
    assert replay_response.status_code == 200
    assert "event: task.created" in replay_response.text
    assert "id: 1" in replay_response.text


@pytest.mark.asyncio
async def test_cancels_a_task_and_records_the_event(api_client: AsyncClient) -> None:
    project = (
        await api_client.post("/v1/projects", json={"name": "取消测试"})
    ).json()
    task = (
        await api_client.post(
            f"/v1/projects/{project['id']}/tasks",
            headers={"Idempotency-Key": "cancel-task"},
            json={"prompt": "生成散热外壳"},
        )
    ).json()

    cancelled_response = await api_client.post(f"/v1/tasks/{task['id']}/cancel")

    assert cancelled_response.status_code == 200
    assert cancelled_response.json()["status"] == "cancelled"

    replay = await api_client.get(
        f"/v1/tasks/{task['id']}/events",
        params={"follow": "false"},
    )
    assert "event: task.cancelled" in replay.text

    resumed = await api_client.get(
        f"/v1/tasks/{task['id']}/events",
        headers={"Last-Event-ID": "1"},
        params={"follow": "false"},
    )
    assert "event: task.created" not in resumed.text
    assert "id: 2" in resumed.text
    assert "event: task.cancelled" in resumed.text


@pytest.mark.asyncio
async def test_persists_tasks_across_application_restarts(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    first_app: FastAPI = create_app(settings)

    async with (
        first_app.router.lifespan_context(first_app),
        AsyncClient(
            transport=ASGITransport(app=first_app),
            base_url="http://test",
        ) as client,
    ):
        project = (
            await client.post("/v1/projects", json={"name": "持久化测试"})
        ).json()
        task = (
            await client.post(
                f"/v1/projects/{project['id']}/tasks",
                headers={"Idempotency-Key": "persistent-task"},
                json={"prompt": "保存任务"},
            )
        ).json()

    second_app: FastAPI = create_app(settings)
    async with (
        second_app.router.lifespan_context(second_app),
        AsyncClient(
            transport=ASGITransport(app=second_app),
            base_url="http://test",
        ) as client,
    ):
        response = await client.get(f"/v1/tasks/{task['id']}")

    assert response.status_code == 200
    assert response.json()["prompt"] == "保存任务"
