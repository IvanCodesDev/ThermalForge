from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base


class Database:
    def __init__(self, database_url: str) -> None:
        self._ensure_sqlite_parent(database_url)
        self.engine: AsyncEngine = create_async_engine(database_url, future=True)
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

        if database_url.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", self._enable_sqlite_fk)

    @staticmethod
    def _ensure_sqlite_parent(database_url: str) -> None:
        prefix = "sqlite+aiosqlite:///"
        if not database_url.startswith(prefix):
            return
        database_path = database_url.removeprefix(prefix)
        if database_path == ":memory:":
            return
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _enable_sqlite_fk(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def ping(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()
