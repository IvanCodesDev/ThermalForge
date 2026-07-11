from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_artifact_store,
    get_database,
    get_task_queue,
)
from app.db import Database
from app.services.artifacts.base import ArtifactStore
from app.services.queue import TaskQueue

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/ready")
async def ready(
    database: Annotated[Database, Depends(get_database)],
    queue: Annotated[TaskQueue, Depends(get_task_queue)],
    artifact_store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> dict[str, object]:
    checks = {
        "database": "ready",
        "queue": "ready",
        "artifact_store": "ready",
    }
    try:
        await database.ping()
        await queue.healthcheck()
        await artifact_store.healthcheck()
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_unavailable") from error
    return {"status": "ready", "checks": checks}
