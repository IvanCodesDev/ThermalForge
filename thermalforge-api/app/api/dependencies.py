from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import Database
from app.documents.ocr import OcrProvider
from app.services.artifacts.base import ArtifactStore
from app.services.queue import TaskQueue


def get_database(request: Request) -> Database:
    return cast(Database, request.app.state.database)


def get_task_queue(request: Request) -> TaskQueue:
    return cast(TaskQueue, request.app.state.task_queue)


def get_artifact_store(request: Request) -> ArtifactStore:
    return cast(ArtifactStore, request.app.state.artifact_store)


def get_ocr_provider(request: Request) -> OcrProvider:
    return cast(OcrProvider, request.app.state.ocr_provider)


def get_application_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = get_database(request)
    async with database.session() as session:
        yield session
