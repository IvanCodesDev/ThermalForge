from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_task_queue
from app.engineering.schemas import ClarificationAnswer, ClarificationRead
from app.services.clarifications import ClarificationService
from app.services.queue import TaskQueue

router = APIRouter(prefix="/v1/tasks", tags=["clarifications"])


@router.get("/{task_id}/clarification", response_model=ClarificationRead)
async def get_clarification(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClarificationRead:
    clarification = await ClarificationService(session).get_current(task_id)
    return ClarificationRead.model_validate(clarification)


@router.post("/{task_id}/clarification", response_model=ClarificationRead)
async def answer_clarification(
    task_id: str,
    body: ClarificationAnswer,
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[TaskQueue, Depends(get_task_queue)],
) -> ClarificationRead:
    clarification = await ClarificationService(session).answer(
        task_id=task_id,
        answer=body.answer,
    )
    await queue.enqueue_pipeline(
        task_id,
        f"clarification:{clarification.id}",
    )
    return ClarificationRead.model_validate(clarification)
