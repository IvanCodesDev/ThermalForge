from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ArtifactKind, TaskStatus
from app.domain.errors import EntityNotFound, InvalidStateTransition, SourceDocumentRequired
from app.models import TaskEventModel, TaskModel
from app.repositories.artifacts import ArtifactRepository
from app.repositories.projects import ProjectRepository
from app.repositories.stage_runs import StageRunRepository
from app.repositories.tasks import TaskRepository
from app.services.task_state_machine import TaskStateMachine


@dataclass(frozen=True, slots=True)
class TaskCreationResult:
    task: TaskModel
    created: bool


@dataclass(frozen=True, slots=True)
class TaskDispatchResult:
    task: TaskModel
    dispatch_token: str
    should_enqueue: bool = True


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._projects = ProjectRepository(session)
        self._tasks = TaskRepository(session)
        self._state_machine = TaskStateMachine()

    async def create_task(
        self,
        *,
        project_id: str,
        prompt: str,
        idempotency_key: str,
    ) -> TaskCreationResult:
        project = await self._projects.get(project_id)
        if project is None:
            raise EntityNotFound("project", project_id)

        existing = await self._tasks.get_by_idempotency_key(
            project_id=project_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return TaskCreationResult(task=existing, created=False)

        task = await self._tasks.create(
            project_id=project_id,
            prompt=prompt,
            idempotency_key=idempotency_key,
        )
        await self._tasks.append_event(
            task_id=task.id,
            event_type="task.created",
            payload={"status": TaskStatus.CREATED.value},
        )

        try:
            await self._session.commit()
        except IntegrityError:
            # The unique key resolves concurrent retries to the first committed task.
            await self._session.rollback()
            concurrent_task = await self._tasks.get_by_idempotency_key(
                project_id=project_id,
                idempotency_key=idempotency_key,
            )
            if concurrent_task is None:
                raise
            return TaskCreationResult(task=concurrent_task, created=False)

        await self._session.refresh(task)
        return TaskCreationResult(task=task, created=True)

    async def get_task(self, task_id: str) -> TaskModel:
        task = await self._tasks.get(task_id)
        if task is None:
            raise EntityNotFound("task", task_id)
        return task

    async def get_task_for_update(self, task_id: str) -> TaskModel:
        task = await self._tasks.get_for_update(task_id)
        if task is None:
            raise EntityNotFound("task", task_id)
        return task

    async def cancel_task(self, task_id: str) -> TaskModel:
        task = await self.get_task(task_id)
        current = TaskStatus(task.status)
        if current == TaskStatus.CANCELLED:
            return task

        target = self._state_machine.transition(current, TaskStatus.CANCELLED)
        task.status = target.value
        task.stage = target.value
        await self._tasks.append_event(
            task_id=task.id,
            event_type="task.cancelled",
            payload={"status": target.value},
        )
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def start_task(self, task_id: str) -> TaskDispatchResult:
        task = await self.get_task_for_update(task_id)
        current = TaskStatus(task.status)
        artifacts = await ArtifactRepository(self._session).list_for_task(task_id)
        if not any(
            artifact.kind == ArtifactKind.SOURCE_DOCUMENT.value
            for artifact in artifacts
        ):
            raise SourceDocumentRequired()

        started_event = await self._tasks.get_latest_event(
            task_id=task_id,
            event_type="task.started",
        )
        if started_event is None:
            if current != TaskStatus.UPLOADED:
                raise InvalidStateTransition(
                    current.value,
                    TaskStatus.PARSING.value,
                )
            started_event = await self._tasks.append_event(
                task_id=task.id,
                event_type="task.started",
                payload={
                    "status": current.value,
                    "source_document_count": sum(
                        artifact.kind == ArtifactKind.SOURCE_DOCUMENT.value
                        for artifact in artifacts
                    ),
                },
            )
            await self._session.commit()
            await self._session.refresh(task)
        elif current in {
            TaskStatus.CREATED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }:
            raise InvalidStateTransition(
                current.value,
                TaskStatus.PARSING.value,
            )

        return TaskDispatchResult(
            task=task,
            dispatch_token=f"start:{started_event.sequence}",
            should_enqueue=current == TaskStatus.UPLOADED,
        )

    async def retry_task(self, task_id: str) -> TaskDispatchResult:
        task = await self.get_task(task_id)
        artifacts = await ArtifactRepository(self._session).list_for_task(task_id)
        failed_stage = await StageRunRepository(
            self._session
        ).get_latest_failed(task_id)
        if failed_stage is not None:
            retry_target = TaskStatus(failed_stage.stage)
        else:
            retry_target = (
                TaskStatus.UPLOADED
                if any(
                    artifact.kind == ArtifactKind.SOURCE_DOCUMENT.value
                    for artifact in artifacts
                )
                else TaskStatus.CREATED
            )
        events = await self._tasks.list_events(task_id=task_id)
        retry_source_event = next(
            (
                event
                for event in reversed(events)
                if event.payload.get("status")
                in {TaskStatus.FAILED.value, TaskStatus.CANCELLED.value}
            ),
            None,
        )
        target = self._state_machine.transition(
            TaskStatus(task.status),
            retry_target,
        )
        task.status = target.value
        task.stage = target.value
        await self._tasks.append_event(
            task_id=task.id,
            event_type="task.retried",
            payload={"status": target.value},
        )
        await self._session.commit()
        await self._session.refresh(task)
        retry_source = (
            f"event:{retry_source_event.sequence}"
            if retry_source_event is not None
            else f"stage-run:{failed_stage.id}"
            if failed_stage is not None
            else f"stage:{retry_target.value}"
        )
        return TaskDispatchResult(
            task=task,
            dispatch_token=f"retry:{retry_source}",
        )

    async def transition(
        self,
        task_id: str,
        target: TaskStatus,
        *,
        event_type: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> TaskModel:
        task = await self.get_task(task_id)
        resolved_target = self._state_machine.transition(
            TaskStatus(task.status),
            target,
        )
        task.status = resolved_target.value
        task.stage = resolved_target.value
        await self._tasks.append_event(
            task_id=task.id,
            event_type=event_type or f"task.{resolved_target.value}",
            payload={"status": resolved_target.value, **(payload or {})},
        )
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def list_events(
        self,
        task_id: str,
        *,
        after_sequence: int = 0,
    ) -> list[TaskEventModel]:
        await self.get_task(task_id)
        return await self._tasks.list_events(
            task_id=task_id,
            after_sequence=after_sequence,
        )
