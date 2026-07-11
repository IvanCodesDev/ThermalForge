from typing import cast
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StageRunModel
from app.models.base import utc_now


class StageRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start(
        self,
        *,
        task_id: str,
        stage: str,
        input_artifact_ids: list[str] | None = None,
    ) -> StageRunModel:
        attempt_statement = select(
            func.coalesce(func.max(StageRunModel.attempt), 0) + 1
        ).where(
            StageRunModel.task_id == task_id,
            StageRunModel.stage == stage,
        )
        attempt = int((await self._session.scalar(attempt_statement)) or 1)
        stage_run = StageRunModel(
            id=str(uuid4()),
            task_id=task_id,
            stage=stage,
            attempt=attempt,
            status="running",
            input_artifact_ids=input_artifact_ids or [],
            output_artifact_ids=[],
        )
        self._session.add(stage_run)
        await self._session.flush()
        return stage_run

    async def complete(
        self,
        stage_run: StageRunModel,
        *,
        output_artifact_ids: list[str] | None = None,
    ) -> None:
        stage_run.status = "completed"
        stage_run.finished_at = utc_now()
        stage_run.output_artifact_ids = output_artifact_ids or []
        await self._session.flush()

    async def cancel(self, stage_run: StageRunModel) -> None:
        stage_run.status = "cancelled"
        stage_run.finished_at = utc_now()
        await self._session.flush()

    async def fail(self, stage_run: StageRunModel, error_code: str) -> None:
        stage_run.status = "failed"
        stage_run.error_code = error_code
        stage_run.finished_at = utc_now()
        await self._session.flush()

    async def list_for_task(self, task_id: str) -> list[StageRunModel]:
        statement = (
            select(StageRunModel)
            .where(StageRunModel.task_id == task_id)
            .order_by(StageRunModel.started_at, StageRunModel.attempt)
        )
        return list((await self._session.scalars(statement)).all())

    async def get_latest_failed(self, task_id: str) -> StageRunModel | None:
        statement = (
            select(StageRunModel)
            .where(
                StageRunModel.task_id == task_id,
                StageRunModel.status == "failed",
            )
            .order_by(StageRunModel.finished_at.desc())
            .limit(1)
        )
        return cast(
            StageRunModel | None,
            await self._session.scalar(statement),
        )
