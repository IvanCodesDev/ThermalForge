from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.domain.enums import ArtifactKind, QualityStatus
from app.main import create_app
from app.models import ArtifactModel
from app.repositories.artifacts import ArtifactRepository


def viewer_settings(tmp_path: Path) -> Settings:
    model_root = tmp_path / "model-library"
    model_root.mkdir()
    (model_root / "foc-robot-arm.glb").write_bytes(b"whole-library-model")
    (model_root / "foc-robot-arm-bang.glb").write_bytes(
        b"segmented-library-model"
    )
    (model_root / "hyper3d-robot-arm.glb").write_bytes(b"hyper3d-library-model")
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'viewer.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        upload_temp_root=tmp_path / "uploads",
        model_asset_root=model_root,
        queue_enabled=False,
        cors_origins=[],
    )


async def create_task(client: AsyncClient, suffix: str) -> str:
    project = (
        await client.post("/v1/projects", json={"name": f"Viewer {suffix}"})
    ).json()
    task = (
        await client.post(
            f"/v1/projects/{project['id']}/tasks",
            headers={"Idempotency-Key": f"viewer-{suffix}"},
            json={"prompt": "Render the approved model"},
        )
    ).json()
    return str(task["id"])


async def create_model_artifact(
    app: FastAPI,
    *,
    task_id: str,
    kind: ArtifactKind,
    filename: str,
    payload: bytes,
    mime_type: str,
    quality_status: QualityStatus,
    metadata: dict[str, object] | None = None,
) -> ArtifactModel:
    stored = await app.state.artifact_store.put_bytes(
        task_id=task_id,
        relative_path=f"models/{filename}",
        payload=payload,
        mime_type=mime_type,
    )
    async with app.state.database.session() as session:
        artifact = await ArtifactRepository(session).create(
            task_id=task_id,
            kind=kind,
            stored=stored,
            metadata={"filename": filename, **(metadata or {})},
            quality_status=quality_status,
        )
        await session.commit()
        await session.refresh(artifact)
        return artifact


@pytest.fixture
async def viewer_client(
    tmp_path: Path,
) -> AsyncIterator[tuple[FastAPI, AsyncClient]]:
    app = create_app(viewer_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        yield app, client


@pytest.mark.asyncio
async def test_manifest_prefers_latest_approved_normalized_model(
    viewer_client: tuple[FastAPI, AsyncClient],
) -> None:
    app, client = viewer_client
    task_id = await create_task(client, "preferred")
    raw = await create_model_artifact(
        app,
        task_id=task_id,
        kind=ArtifactKind.RAW_MODEL,
        filename="source.stl",
        payload=b"solid source\nendsolid source",
        mime_type="model/stl",
        quality_status=QualityStatus.APPROVED,
    )
    approved = await create_model_artifact(
        app,
        task_id=task_id,
        kind=ArtifactKind.NORMALIZED_MODEL,
        filename="assembly.glb",
        payload=b"glTF-approved",
        mime_type="model/gltf-binary",
        quality_status=QualityStatus.APPROVED,
        metadata={
            "transform": {
                "translation": [1, 2, 3],
                "rotation": [0, 0, 0, 1],
                "scale": [0.001, 0.001, 0.001],
            }
        },
    )
    await create_model_artifact(
        app,
        task_id=task_id,
        kind=ArtifactKind.NORMALIZED_MODEL,
        filename="unreviewed.glb",
        payload=b"glTF-pending",
        mime_type="model/gltf-binary",
        quality_status=QualityStatus.PENDING,
    )

    response = await client.get(f"/v1/tasks/{task_id}/viewer-manifest")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "task_id": task_id,
        "asset": {
            "artifact_id": approved.id,
            "kind": "normalized_model",
            "url": f"/v1/tasks/{task_id}/models/{approved.id}/content",
            "format": "glb",
            "mime_type": "model/gltf-binary",
            "sha256": approved.sha256,
            "size_bytes": len(b"glTF-approved"),
            "transform": {
                "translation": [1.0, 2.0, 3.0],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "scale": [0.001, 0.001, 0.001],
            },
        },
        "variants": [
            {
                "id": "normalized_model",
                "label": "标准化模型",
                "asset": {
                    "artifact_id": approved.id,
                    "kind": "normalized_model",
                    "url": f"/v1/tasks/{task_id}/models/{approved.id}/content",
                    "format": "glb",
                    "mime_type": "model/gltf-binary",
                    "sha256": approved.sha256,
                    "size_bytes": len(b"glTF-approved"),
                    "transform": {
                        "translation": [1.0, 2.0, 3.0],
                        "rotation": [0.0, 0.0, 0.0, 1.0],
                        "scale": [0.001, 0.001, 0.001],
                    },
                },
                "supports_explosion": False,
                "parts": [
                    {
                        "id": "normalized_model-whole",
                        "label": "标准化模型",
                        "description": "当前资产未提供可验证的分件节点。",
                        "binding": "whole_asset",
                        "node_names": [],
                        "explode": None,
                    }
                ],
            },
            {
                "id": "raw_model",
                "label": "原始模型",
                "asset": {
                    "artifact_id": raw.id,
                    "kind": "raw_model",
                    "url": f"/v1/tasks/{task_id}/models/{raw.id}/content",
                    "format": "stl",
                    "mime_type": "model/stl",
                    "sha256": raw.sha256,
                    "size_bytes": len(b"solid source\nendsolid source"),
                    "transform": {
                        "translation": [0.0, 0.0, 0.0],
                        "rotation": [0.0, 0.0, 0.0, 1.0],
                        "scale": [1.0, 1.0, 1.0],
                    },
                },
                "supports_explosion": False,
                "parts": [
                    {
                        "id": "raw_model-whole",
                        "label": "原始模型",
                        "description": "当前资产未提供可验证的分件节点。",
                        "binding": "whole_asset",
                        "node_names": [],
                        "explode": None,
                    }
                ],
            },
        ],
        "notices": [],
    }


@pytest.mark.asyncio
async def test_manifest_exposes_metadata_backed_segmented_parts(
    viewer_client: tuple[FastAPI, AsyncClient],
) -> None:
    app, client = viewer_client
    task_id = await create_task(client, "segmented")
    await create_model_artifact(
        app,
        task_id=task_id,
        kind=ArtifactKind.RAW_MODEL,
        filename="whole.glb",
        payload=b"whole",
        mime_type="model/gltf-binary",
        quality_status=QualityStatus.APPROVED,
        metadata={"variant": "whole", "source": "curated_reference"},
    )
    segmented = await create_model_artifact(
        app,
        task_id=task_id,
        kind=ArtifactKind.NORMALIZED_MODEL,
        filename="segmented.glb",
        payload=b"segmented",
        mime_type="model/gltf-binary",
        quality_status=QualityStatus.APPROVED,
        metadata={
            "variant": "segmented",
            "source": "curated_reference",
            "node_names": ["root.0", "root.1", "root.2"],
        },
    )

    response = await client.get(f"/v1/tasks/{task_id}/viewer-manifest")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["asset"]["artifact_id"] == segmented.id
    assert [variant["id"] for variant in manifest["variants"]] == [
        "segmented",
        "whole",
    ]
    assert manifest["variants"][0]["supports_explosion"] is True
    assert [
        part["node_names"][0] for part in manifest["variants"][0]["parts"]
    ] == ["root.0", "root.1", "root.2"]
    assert all(
        part["binding"] == "node_names"
        for part in manifest["variants"][0]["parts"]
    )
    assert "概念参考模型" in manifest["notices"][0]


@pytest.mark.asyncio
async def test_download_is_scoped_to_approved_models_in_the_same_task(
    viewer_client: tuple[FastAPI, AsyncClient],
) -> None:
    app, client = viewer_client
    owner_task_id = await create_task(client, "owner")
    other_task_id = await create_task(client, "other")
    payload = b"solid model\nendsolid model"
    artifact = await create_model_artifact(
        app,
        task_id=owner_task_id,
        kind=ArtifactKind.RAW_MODEL,
        filename="model.stl",
        payload=payload,
        mime_type="model/stl",
        quality_status=QualityStatus.APPROVED,
    )
    pending = await create_model_artifact(
        app,
        task_id=owner_task_id,
        kind=ArtifactKind.NORMALIZED_MODEL,
        filename="pending.glb",
        payload=b"pending",
        mime_type="model/gltf-binary",
        quality_status=QualityStatus.PENDING,
    )

    download = await client.get(
        f"/v1/tasks/{owner_task_id}/models/{artifact.id}/content"
    )
    cross_task = await client.get(
        f"/v1/tasks/{other_task_id}/models/{artifact.id}/content"
    )
    unapproved = await client.get(
        f"/v1/tasks/{owner_task_id}/models/{pending.id}/content"
    )

    assert download.status_code == 200
    assert download.content == payload
    assert download.headers["content-type"] == "model/stl"
    assert download.headers["etag"] == f'"{artifact.sha256}"'
    assert cross_task.status_code == 404
    assert cross_task.json()["code"] == "viewer_model_not_found"
    assert unapproved.status_code == 404
    assert unapproved.json()["code"] == "viewer_model_not_found"


@pytest.mark.asyncio
async def test_manifest_reports_missing_and_unsupported_models(
    viewer_client: tuple[FastAPI, AsyncClient],
) -> None:
    app, client = viewer_client
    empty_task_id = await create_task(client, "empty")

    missing = await client.get(f"/v1/tasks/{empty_task_id}/viewer-manifest")

    assert missing.status_code == 404
    assert missing.json()["code"] == "viewer_model_not_found"

    step_task_id = await create_task(client, "step")
    await create_model_artifact(
        app,
        task_id=step_task_id,
        kind=ArtifactKind.RAW_MODEL,
        filename="assembly.step",
        payload=b"ISO-10303-21",
        mime_type="model/step",
        quality_status=QualityStatus.APPROVED,
    )

    unsupported = await client.get(f"/v1/tasks/{step_task_id}/viewer-manifest")

    assert unsupported.status_code == 415
    assert unsupported.json()["code"] == "unsupported_viewer_model_format"


@pytest.mark.asyncio
async def test_viewer_library_lists_and_serves_distinct_curated_models(
    viewer_client: tuple[FastAPI, AsyncClient],
) -> None:
    _, client = viewer_client

    response = await client.get("/v1/viewer-library")

    assert response.status_code == 200
    models = response.json()["models"]
    assert [model["id"] for model in models] == [
        "foc-segmented",
        "foc-whole",
        "hyper3d-original",
    ]
    assert models[0]["supports_explosion"] is True
    assert [
        part["node_names"][0] for part in models[0]["parts"]
    ] == ["root.0", "root.1", "root.2"]
    assert all("概念网格" in model["notices"][0] for model in models)
    assert len({model["asset"]["sha256"] for model in models}) == 3

    download = await client.get(
        "/v1/viewer-library/foc-segmented/content"
    )

    assert download.status_code == 200
    assert download.content == b"segmented-library-model"
    assert download.headers["content-type"] == "model/gltf-binary"
    assert download.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.asyncio
async def test_viewer_library_rejects_unknown_model_ids(
    viewer_client: tuple[FastAPI, AsyncClient],
) -> None:
    _, client = viewer_client

    response = await client.get("/v1/viewer-library/not-configured/content")

    assert response.status_code == 404
    assert response.json()["code"] == "viewer_model_not_found"
