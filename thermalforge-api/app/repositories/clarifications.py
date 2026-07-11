from typing import cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClarificationModel
from app.models.base import utc_now


class ClarificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        task_id: str,
        field_key: str,
        question: str,
    ) -> ClarificationModel:
        clarification = ClarificationModel(
            id=str(uuid4()),
            task_id=task_id,
            field_key=field_key,
            question=question,
        )
        self._session.add(clarification)
        await self._session.flush()
        return clarification

    async def get_current(self, task_id: str) -> ClarificationModel | None:
        statement = (
            select(ClarificationModel)
            .where(
                ClarificationModel.task_id == task_id,
                ClarificationModel.answered_at.is_(None),
            )
            .order_by(ClarificationModel.created_at.desc())
            .limit(1)
        )
        return cast(
            ClarificationModel | None,
            await self._session.scalar(statement),
        )

    async def list_answered(self, task_id: str) -> list[ClarificationModel]:
        statement = (
            select(ClarificationModel)
            .where(
                ClarificationModel.task_id == task_id,
                ClarificationModel.answered_at.is_not(None),
            )
            .order_by(ClarificationModel.created_at)
        )
        return list(await self._session.scalars(statement))

    async def answer(
        self,
        clarification: ClarificationModel,
        answer: str,
    ) -> ClarificationModel:
        clarification.answer = answer
        clarification.answered_at = utc_now()
        await self._session.flush()
        return clarification
