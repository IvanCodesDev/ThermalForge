from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.workers.worker import run_pipeline


@pytest.mark.asyncio
async def test_worker_completes_the_dependency_free_bootstrap_stage(
    tmp_path: Path,
) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'worker.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        queue_enabled=False,
        cors_origins=[],
    )
    app = create_app(settings)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        project = (
            await client.post("/v1/projects", json={"name": "Worker 测试"})
        ).json()
        task = (
            await client.post(
                f"/v1/projects/{project['id']}/tasks",
                headers={"Idempotency-Key": "worker-stage"},
                json={"prompt": "验证任务骨架"},
            )
        ).json()

        await run_pipeline({"database": app.state.database}, task["id"])

        events = await client.get(
            f"/v1/tasks/{task['id']}/events",
            params={"follow": "false"},
        )

    assert "event: stage.bootstrap.started" in events.text
    assert "event: stage.bootstrap.completed" in events.text


@pytest.mark.asyncio
async def test_worker_does_not_start_a_cancelled_task(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'cancelled-worker.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        queue_enabled=False,
        cors_origins=[],
    )
    app = create_app(settings)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        project = (
            await client.post("/v1/projects", json={"name": "Worker 取消测试"})
        ).json()
        task = (
            await client.post(
                f"/v1/projects/{project['id']}/tasks",
                headers={"Idempotency-Key": "cancel-before-worker"},
                json={"prompt": "不要执行"},
            )
        ).json()
        await client.post(f"/v1/tasks/{task['id']}/cancel")

        await run_pipeline({"database": app.state.database}, task["id"])
        events = await client.get(
            f"/v1/tasks/{task['id']}/events",
            params={"follow": "false"},
        )

    assert "event: task.cancelled" in events.text
    assert "stage.bootstrap.started" not in events.text


@pytest.mark.asyncio
async def test_worker_runs_documents_through_the_local_brief_fixture(
    tmp_path: Path,
) -> None:
    settings = Settings(
        environment="test",
        database_url=(
            f"sqlite+aiosqlite:///{(tmp_path / 'brief-worker.db').as_posix()}"
        ),
        artifact_root=tmp_path / "artifacts",
        upload_temp_root=tmp_path / "uploads",
        llm_provider="fixture",
        queue_enabled=False,
        cors_origins=[],
    )
    app = create_app(settings)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        project = (
            await client.post("/v1/projects", json={"name": "Worker 摘要测试"})
        ).json()
        task = (
            await client.post(
                f"/v1/projects/{project['id']}/tasks",
                headers={"Idempotency-Key": "worker-brief"},
                json={"prompt": "保持原厂孔位，外壳可拆卸"},
            )
        ).json()
        await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={
                "file": (
                    "constraints.txt",
                    (
                        "电机持续功率 120 W，环境温度 25°C，"
                        "可用空间 180 mm × 90 mm × 70 mm。"
                    ).encode(),
                    "text/plain",
                )
            },
        )

        await run_pipeline(
            {
                "database": app.state.database,
                "artifact_store": app.state.artifact_store,
                "ocr_provider": app.state.ocr_provider,
                "llm_provider": app.state.llm_provider,
                "settings": app.state.settings,
            },
            task["id"],
        )
        completed = await client.get(f"/v1/tasks/{task['id']}")
        artifacts = await client.get(f"/v1/tasks/{task['id']}/artifacts")

    assert completed.json()["status"] == "ready"
    assert [artifact["kind"] for artifact in artifacts.json()] == [
        "source_document",
        "parsed_document",
        "engineering_brief",
        "thermal_analysis",
        "thermal_design",
        "concept_image",
        "multiview_image",
        "multiview_image",
        "multiview_image",
        "multiview_image",
        "multiview_image",
        "raw_model",
        "normalized_model",
    ]
