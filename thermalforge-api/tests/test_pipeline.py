import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_local_start_executes_pipeline_without_redis(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'pipeline.db').as_posix()}",
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
            await client.post("/v1/projects", json={"name": "本地流水线"})
        ).json()
        task = (
            await client.post(
                f"/v1/projects/{project['id']}/tasks",
                headers={"Idempotency-Key": "local-pipeline"},
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

        started = await client.post(f"/v1/tasks/{task['id']}/start")
        assert started.status_code == 202

        status = started.json()["status"]
        for _ in range(500):
            if status in {"ready", "awaiting_input", "failed"}:
                break
            await asyncio.sleep(0.01)
            status = (await client.get(f"/v1/tasks/{task['id']}")).json()["status"]

        artifacts = (
            await client.get(f"/v1/tasks/{task['id']}/artifacts")
        ).json()
        image_manifest_response = await client.get(
            f"/v1/tasks/{task['id']}/image-manifest"
        )
        if image_manifest_response.status_code == 200:
            image_manifest = image_manifest_response.json()
            image_download = await client.get(image_manifest["images"][0]["url"])
        else:
            image_manifest = None
            image_download = None

    assert status == "ready"
    assert len(
        [
            artifact
            for artifact in artifacts
            if artifact["kind"] in {"concept_image", "multiview_image"}
        ]
    ) == 6
    assert image_manifest is not None
    assert [image["view_id"] for image in image_manifest["images"]] == [
        "mother_three_quarter",
        "front",
        "left",
        "rear",
        "top",
        "elbow_section",
    ]
    assert image_download is not None
    assert image_download.status_code == 200
    assert image_download.content.startswith(b"\x89PNG\r\n\x1a\n")
