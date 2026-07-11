from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.domain.enums import TaskStatus
from app.main import create_app
from app.services.tasks import TaskService


class RecordingTaskQueue:
    def __init__(self) -> None:
        self.dispatches: list[tuple[str, str]] = []

    async def enqueue_pipeline(self, task_id: str, dispatch_token: str) -> None:
        self.dispatches.append((task_id, dispatch_token))

    async def healthcheck(self) -> None:
        return None

    async def close(self) -> None:
        return None


def task_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'tasks.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        upload_temp_root=tmp_path / "uploads",
        queue_enabled=False,
        cors_origins=[],
    )


async def create_task(client: AsyncClient, *, key: str) -> dict[str, object]:
    project = (
        await client.post("/v1/projects", json={"name": f"启动测试-{key}"})
    ).json()
    response = await client.post(
        f"/v1/projects/{project['id']}/tasks",
        headers={"Idempotency-Key": key},
        json={"prompt": "分析全部输入文档"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_requires_a_source_document_before_start(tmp_path: Path) -> None:
    app = create_app(task_settings(tmp_path))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        queue = RecordingTaskQueue()
        app.state.task_queue = queue
        task = await create_task(client, key="missing-document")

        response = await client.post(f"/v1/tasks/{task['id']}/start")

    assert response.status_code == 409
    assert response.json()["code"] == "source_document_required"
    assert queue.dispatches == []


@pytest.mark.asyncio
async def test_rejects_start_for_a_cancelled_task(tmp_path: Path) -> None:
    app = create_app(task_settings(tmp_path))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        queue = RecordingTaskQueue()
        app.state.task_queue = queue
        task = await create_task(client, key="cancelled-start")
        await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("input.txt", b"Power 120 W", "text/plain")},
        )
        await client.post(f"/v1/tasks/{task['id']}/cancel")

        response = await client.post(f"/v1/tasks/{task['id']}/start")

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_state_transition"
    assert queue.dispatches == []


@pytest.mark.asyncio
async def test_uploads_multiple_documents_then_starts_idempotently(
    tmp_path: Path,
) -> None:
    app = create_app(task_settings(tmp_path))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        queue = RecordingTaskQueue()
        app.state.task_queue = queue
        task = await create_task(client, key="multiple-documents")

        first_upload = await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("thermal.txt", b"Motor power 120 W", "text/plain")},
        )
        second_upload = await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("limits.txt", b"Ambient 25 C", "text/plain")},
        )

        assert first_upload.status_code == 201
        assert second_upload.status_code == 201
        assert queue.dispatches == []

        first_start = await client.post(f"/v1/tasks/{task['id']}/start")
        repeated_start = await client.post(f"/v1/tasks/{task['id']}/start")
        late_upload = await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("late.txt", b"Late input", "text/plain")},
        )
        events = await client.get(
            f"/v1/tasks/{task['id']}/events",
            params={"follow": "false"},
        )
        artifacts = await client.get(f"/v1/tasks/{task['id']}/artifacts")

    assert first_start.status_code == 202
    assert repeated_start.status_code == 202
    assert late_upload.status_code == 409
    assert late_upload.json()["code"] == "task_already_started"
    assert first_start.json()["status"] == "uploaded"
    assert len(artifacts.json()) == 2
    assert events.text.count("event: task.started") == 1
    assert len(queue.dispatches) == 2
    assert queue.dispatches[0] == queue.dispatches[1]
    assert queue.dispatches[0][1].startswith("start:")


@pytest.mark.asyncio
async def test_retry_dispatch_is_stable_for_one_failure_and_changes_for_the_next(
    tmp_path: Path,
) -> None:
    app = create_app(task_settings(tmp_path))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        queue = RecordingTaskQueue()
        app.state.task_queue = queue
        task = await create_task(client, key="retry-dispatch")
        await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("input.txt", b"Power 120 W", "text/plain")},
        )

        async with app.state.database.session() as session:
            await TaskService(session).transition(task["id"], TaskStatus.FAILED)

        first_retry = await client.post(f"/v1/tasks/{task['id']}/retry")
        repeated_retry = await client.post(f"/v1/tasks/{task['id']}/retry")

        async with app.state.database.session() as session:
            await TaskService(session).transition(task["id"], TaskStatus.FAILED)

        next_retry = await client.post(f"/v1/tasks/{task['id']}/retry")

    assert first_retry.status_code == 200
    assert repeated_retry.status_code == 200
    assert next_retry.status_code == 200
    assert queue.dispatches[0] == queue.dispatches[1]
    assert queue.dispatches[2][1] != queue.dispatches[0][1]
    assert all(token.startswith("retry:") for _, token in queue.dispatches)


@pytest.mark.asyncio
async def test_cancelled_retry_replay_uses_the_same_dispatch_token(
    tmp_path: Path,
) -> None:
    app = create_app(task_settings(tmp_path))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        queue = RecordingTaskQueue()
        app.state.task_queue = queue
        task = await create_task(client, key="cancelled-retry")
        await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("input.txt", b"Power 120 W", "text/plain")},
        )
        await client.post(f"/v1/tasks/{task['id']}/cancel")

        first_retry = await client.post(f"/v1/tasks/{task['id']}/retry")
        replayed_retry = await client.post(f"/v1/tasks/{task['id']}/retry")

    assert first_retry.status_code == 200
    assert replayed_retry.status_code == 200
    assert queue.dispatches[0] == queue.dispatches[1]
    assert queue.dispatches[0][1].startswith("retry:event:")
