import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_database, get_session, get_task_queue
from app.db import Database
from app.domain.schemas import ArtifactRead, TaskCreate, TaskEventRead, TaskRead
from app.repositories.artifacts import ArtifactRepository
from app.services.queue import TaskQueue
from app.services.tasks import TaskService

router = APIRouter(tags=["tasks"])


@router.post(
    "/v1/projects/{project_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    project_id: str,
    request: TaskCreate,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=160),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TaskRead:
    result = await TaskService(session).create_task(
        project_id=project_id,
        prompt=request.prompt,
        idempotency_key=idempotency_key,
    )
    return TaskRead.model_validate(result.task)


@router.get("/v1/tasks/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TaskRead:
    task = await TaskService(session).get_task(task_id)
    return TaskRead.model_validate(task)


@router.post("/v1/tasks/{task_id}/cancel", response_model=TaskRead)
async def cancel_task(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TaskRead:
    task = await TaskService(session).cancel_task(task_id)
    return TaskRead.model_validate(task)


@router.post(
    "/v1/tasks/{task_id}/start",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_task(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[TaskQueue, Depends(get_task_queue)],
) -> TaskRead:
    result = await TaskService(session).start_task(task_id)
    if result.should_enqueue:
        await queue.enqueue_pipeline(task_id, result.dispatch_token)
    return TaskRead.model_validate(result.task)


@router.post("/v1/tasks/{task_id}/retry", response_model=TaskRead)
async def retry_task(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[TaskQueue, Depends(get_task_queue)],
) -> TaskRead:
    result = await TaskService(session).retry_task(task_id)
    await queue.enqueue_pipeline(task_id, result.dispatch_token)
    return TaskRead.model_validate(result.task)


@router.get("/v1/tasks/{task_id}/artifacts", response_model=list[ArtifactRead])
async def list_task_artifacts(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ArtifactRead]:
    await TaskService(session).get_task(task_id)
    artifacts = await ArtifactRepository(session).list_for_task(task_id)
    return [ArtifactRead.model_validate(artifact) for artifact in artifacts]


@router.get("/v1/tasks/{task_id}/events", response_class=StreamingResponse)
async def stream_task_events(
    task_id: str,
    request: Request,
    database: Annotated[Database, Depends(get_database)],
    follow: bool = Query(default=True),
    last_event_id: Annotated[
        int | None,
        Header(alias="Last-Event-ID", ge=0),
    ] = None,
) -> StreamingResponse:
    async with database.session() as session:
        await TaskService(session).get_task(task_id)

    async def event_stream() -> AsyncIterator[str]:
        current_sequence = last_event_id or 0
        idle_cycles = 0

        while True:
            async with database.session() as session:
                events = await TaskService(session).list_events(
                    task_id,
                    after_sequence=current_sequence,
                )

            for event in events:
                current_sequence = event.sequence
                payload = json.dumps(
                    TaskEventRead.model_validate(event).payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield (
                    f"id: {event.sequence}\n"
                    f"event: {event.event_type}\n"
                    f"data: {payload}\n\n"
                )
                idle_cycles = 0

            if not follow or await request.is_disconnected():
                break

            idle_cycles += 1
            if idle_cycles >= 30:
                yield ": keepalive\n\n"
                idle_cycles = 0
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
