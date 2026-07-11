import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import TaskStatus
from app.repositories.stage_runs import StageRunRepository
from app.repositories.tasks import TaskRepository
from app.services.tasks import TaskService


class TaskExecutionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tasks = TaskRepository(session)
        self._stage_runs = StageRunRepository(session)

    async def run_bootstrap(self, task_id: str) -> None:
        task = await TaskService(self._session).get_task(task_id)
        if TaskStatus(task.status) == TaskStatus.CANCELLED:
            return

        stage_run = await self._stage_runs.start(
            task_id=task_id,
            stage="bootstrap",
        )
        await self._tasks.append_event(
            task_id=task_id,
            event_type="stage.bootstrap.started",
            payload={"stage_run_id": stage_run.id, "attempt": stage_run.attempt},
        )
        await self._session.commit()

        # Yield once so a cancellation committed by the API can be observed.
        await asyncio.sleep(0)
        await self._session.refresh(task)
        if TaskStatus(task.status) == TaskStatus.CANCELLED:
            await self._stage_runs.cancel(stage_run)
            await self._tasks.append_event(
                task_id=task_id,
                event_type="stage.bootstrap.cancelled",
                payload={"stage_run_id": stage_run.id},
            )
            await self._session.commit()
            return

        await self._stage_runs.complete(stage_run)
        await self._tasks.append_event(
            task_id=task_id,
            event_type="stage.bootstrap.completed",
            payload={"stage_run_id": stage_run.id},
        )
        await self._session.commit()
