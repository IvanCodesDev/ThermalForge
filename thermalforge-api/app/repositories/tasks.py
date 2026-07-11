from typing import cast
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import TaskStatus
from app.models import TaskEventModel, TaskModel


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: str,
        prompt: str,
        idempotency_key: str,
    ) -> TaskModel:
        task = TaskModel(
            id=str(uuid4()),
            project_id=project_id,
            prompt=prompt.strip(),
            idempotency_key=idempotency_key,
            status=TaskStatus.CREATED.value,
            stage=TaskStatus.CREATED.value,
        )
        self._session.add(task)
        await self._session.flush()
        return task

    async def get(self, task_id: str) -> TaskModel | None:
        return await self._session.get(TaskModel, task_id)

    async def get_for_update(self, task_id: str) -> TaskModel | None:
        statement = (
            select(TaskModel)
            .where(TaskModel.id == task_id)
            .with_for_update()
        )
        return cast(TaskModel | None, await self._session.scalar(statement))

    async def get_by_idempotency_key(
        self,
        *,
        project_id: str,
        idempotency_key: str,
    ) -> TaskModel | None:
        statement = select(TaskModel).where(
            TaskModel.project_id == project_id,
            TaskModel.idempotency_key == idempotency_key,
        )
        return cast(TaskModel | None, await self._session.scalar(statement))

    async def append_event(
        self,
        *,
        task_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> TaskEventModel:
        sequence_statement = select(
            func.coalesce(func.max(TaskEventModel.sequence), 0) + 1
        ).where(TaskEventModel.task_id == task_id)
        sequence = int((await self._session.scalar(sequence_statement)) or 1)
        event = TaskEventModel(
            task_id=task_id,
            sequence=sequence,
            event_type=event_type,
            payload=payload,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_events(
        self,
        *,
        task_id: str,
        after_sequence: int = 0,
    ) -> list[TaskEventModel]:
        statement = (
            select(TaskEventModel)
            .where(
                TaskEventModel.task_id == task_id,
                TaskEventModel.sequence > after_sequence,
            )
            .order_by(TaskEventModel.sequence)
        )
        return list((await self._session.scalars(statement)).all())

    async def get_latest_event(
        self,
        *,
        task_id: str,
        event_type: str,
    ) -> TaskEventModel | None:
        statement = (
            select(TaskEventModel)
            .where(
                TaskEventModel.task_id == task_id,
                TaskEventModel.event_type == event_type,
            )
            .order_by(TaskEventModel.sequence.desc())
            .limit(1)
        )
        return cast(TaskEventModel | None, await self._session.scalar(statement))
