import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


async def create_complete_task(client: AsyncClient, *, key: str) -> str:
    project = (
        await client.post("/v1/projects", json={"name": f"模型完成-{key}"})
    ).json()
    task = (
        await client.post(
            f"/v1/projects/{project['id']}/tasks",
            headers={"Idempotency-Key": key},
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
    return str(task["id"])


async def wait_for_terminal(client: AsyncClient, task_id: str) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for _ in range(500):
        snapshot = (await client.get(f"/v1/tasks/{task_id}")).json()
        if snapshot["status"] in {"ready", "failed", "cancelled"}:
            return snapshot
        await asyncio.sleep(0.01)
    return snapshot


def model_settings(tmp_path: Path, model_root: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'models.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        upload_temp_root=tmp_path / "uploads",
        model_asset_root=model_root,
        llm_provider="fixture",
        queue_enabled=False,
        cors_origins=[],
    )


@pytest.mark.asyncio
async def test_local_pipeline_reaches_ready_with_curated_model_artifacts(
    tmp_path: Path,
) -> None:
    model_root = tmp_path / "models"
    model_root.mkdir()
    (model_root / "foc-robot-arm.glb").write_bytes(b"whole-glb")
    (model_root / "foc-robot-arm-bang.glb").write_bytes(b"segmented-glb")
    app = create_app(model_settings(tmp_path, model_root))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        task_id = await create_complete_task(client, key="model-ready")
        await client.post(f"/v1/tasks/{task_id}/start")
        completed = await wait_for_terminal(client, task_id)
        artifacts = (await client.get(f"/v1/tasks/{task_id}/artifacts")).json()
        events = await client.get(
            f"/v1/tasks/{task_id}/events",
            params={"follow": "false"},
        )

    assert completed["status"] == "ready"
    model_artifacts = [
        artifact
        for artifact in artifacts
        if artifact["kind"] in {"raw_model", "normalized_model"}
    ]
    assert [artifact["kind"] for artifact in model_artifacts] == [
        "raw_model",
        "normalized_model",
    ]
    assert all(
        artifact["metadata"]["source"] == "curated_reference"
        for artifact in model_artifacts
    )
    assert model_artifacts[1]["metadata"]["node_names"] == [
        "root.0",
        "root.1",
        "root.2",
    ]
    assert "event: task.ready" in events.text


@pytest.mark.asyncio
async def test_missing_curated_models_fail_instead_of_stalling(
    tmp_path: Path,
) -> None:
    model_root = tmp_path / "missing-models"
    model_root.mkdir()
    app = create_app(model_settings(tmp_path, model_root))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        task_id = await create_complete_task(client, key="model-missing")
        await client.post(f"/v1/tasks/{task_id}/start")
        completed = await wait_for_terminal(client, task_id)
        events = await client.get(
            f"/v1/tasks/{task_id}/events",
            params={"follow": "false"},
        )

    assert completed["status"] == "failed"
    assert "event: model.completion.failed" in events.text
