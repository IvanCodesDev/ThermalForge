from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.documents.schemas import DocumentBundle
from app.domain.enums import TaskStatus
from app.main import create_app
from app.services.tasks import TaskService
from app.workers.worker import run_pipeline


def document_settings(tmp_path: Path, *, max_upload_bytes: int = 20 * 1024 * 1024) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'documents.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        upload_temp_root=tmp_path / "uploads",
        max_upload_bytes=max_upload_bytes,
        queue_enabled=False,
        cors_origins=[],
    )


@pytest.mark.asyncio
async def test_uploads_deduplicates_and_parses_a_markdown_document(
    tmp_path: Path,
) -> None:
    app = create_app(document_settings(tmp_path))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        project = (
            await client.post("/v1/projects", json={"name": "文档解析"})
        ).json()
        task = (
            await client.post(
                f"/v1/projects/{project['id']}/tasks",
                headers={"Idempotency-Key": "document-task"},
                json={"prompt": "分析机器人膝关节"},
            )
        ).json()
        payload = (
            "# 热设计约束\n\n"
            "电机持续功率为 120 W，外壳安装空间为 180 mm × 90 mm。\n\n"
            "## 制造限制\n\n外壳必须可拆卸，不允许修改原厂孔位。"
        ).encode()

        uploaded = await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("requirements.md", payload, "text/markdown")},
        )
        duplicate = await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("requirements.md", payload, "text/markdown")},
        )

        assert uploaded.status_code == 201
        assert duplicate.status_code == 201
        assert duplicate.json()["id"] == uploaded.json()["id"]
        assert uploaded.json()["kind"] == "source_document"

        task_after_upload = await client.get(f"/v1/tasks/{task['id']}")
        assert task_after_upload.json()["status"] == "uploaded"

        await run_pipeline(
            {
                "database": app.state.database,
                "artifact_store": app.state.artifact_store,
                "ocr_provider": app.state.ocr_provider,
                "settings": app.state.settings,
            },
            task["id"],
        )

        completed_task = await client.get(f"/v1/tasks/{task['id']}")
        artifacts = await client.get(f"/v1/tasks/{task['id']}/artifacts")

        assert completed_task.json()["status"] == "briefing"
        assert [artifact["kind"] for artifact in artifacts.json()] == [
            "source_document",
            "parsed_document",
        ]

        parsed_artifact = artifacts.json()[-1]
        parsed_payload = await app.state.artifact_store.read_bytes(
            parsed_artifact["storage_uri"]
        )
        bundle = DocumentBundle.model_validate_json(parsed_payload)

    assert bundle.content_trust == "untrusted"
    assert bundle.sources[0].filename == "requirements.md"
    assert any("持续功率为 120 W" in chunk.text for chunk in bundle.chunks)
    assert all(
        chunk.source_artifact_id == uploaded.json()["id"] for chunk in bundle.chunks
    )


@pytest.mark.asyncio
async def test_rejects_oversized_and_executable_uploads(tmp_path: Path) -> None:
    app = create_app(document_settings(tmp_path, max_upload_bytes=16))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        project = (
            await client.post("/v1/projects", json={"name": "上传校验"})
        ).json()
        task = (
            await client.post(
                f"/v1/projects/{project['id']}/tasks",
                headers={"Idempotency-Key": "upload-validation"},
                json={"prompt": "校验文件"},
            )
        ).json()

        oversized = await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("large.txt", b"x" * 17, "text/plain")},
        )
        executable = await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("renamed.txt", b"MZ" + b"\x00" * 12, "text/plain")},
        )

    assert oversized.status_code == 413
    assert oversized.json()["code"] == "upload_too_large"
    assert executable.status_code == 415
    assert executable.json()["code"] == "unsupported_document_type"


@pytest.mark.asyncio
async def test_retries_failed_parsing_from_the_uploaded_artifact(
    tmp_path: Path,
) -> None:
    app = create_app(document_settings(tmp_path))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        project = (
            await client.post("/v1/projects", json={"name": "解析重试"})
        ).json()
        task = (
            await client.post(
                f"/v1/projects/{project['id']}/tasks",
                headers={"Idempotency-Key": "document-retry"},
                json={"prompt": "解析后重试"},
            )
        ).json()
        await client.post(
            f"/v1/tasks/{task['id']}/documents",
            files={"file": ("input.txt", b"Power 120 W", "text/plain")},
        )
        async with app.state.database.session() as session:
            await TaskService(session).transition(task["id"], TaskStatus.FAILED)

        retried = await client.post(f"/v1/tasks/{task['id']}/retry")

    assert retried.status_code == 200
    assert retried.json()["status"] == "uploaded"
