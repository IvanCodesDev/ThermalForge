from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import TaskStatus
from app.domain.errors import (
    ClarificationNotFound,
    InvalidClarificationAnswer,
    InvalidStateTransition,
)
from app.models import ClarificationModel
from app.repositories.clarifications import ClarificationRepository
from app.services.tasks import TaskService


class ClarificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = ClarificationRepository(session)
        self._tasks = TaskService(session)

    async def get_current(self, task_id: str) -> ClarificationModel:
        await self._tasks.get_task(task_id)
        clarification = await self._repository.get_current(task_id)
        if clarification is None:
            raise ClarificationNotFound()
        return clarification

    async def answer(
        self,
        *,
        task_id: str,
        answer: str,
    ) -> ClarificationModel:
        task = await self._tasks.get_task(task_id)
        if TaskStatus(task.status) != TaskStatus.AWAITING_INPUT:
            raise InvalidStateTransition(
                task.status,
                TaskStatus.BRIEFING.value,
            )

        normalized_answer = answer.strip()
        if not normalized_answer:
            raise InvalidClarificationAnswer()

        clarification = await self.get_current(task_id)
        await self._repository.answer(clarification, normalized_answer)
        await self._session.commit()
        await self._session.refresh(clarification)
        await self._tasks.transition(
            task_id,
            TaskStatus.BRIEFING,
            event_type="engineering_brief.clarification_answered",
            payload={"clarification_id": clarification.id},
        )
        return clarification
