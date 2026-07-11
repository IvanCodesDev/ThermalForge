import asyncio
import logging
from typing import Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

logger = logging.getLogger(__name__)


class TaskQueue(Protocol):
    async def enqueue_pipeline(self, task_id: str, dispatch_token: str) -> None: ...

    async def healthcheck(self) -> None: ...

    async def close(self) -> None: ...


class PipelineRunner(Protocol):
    async def run(self, task_id: str) -> None: ...


class InProcessTaskQueue:
    def __init__(self, runner: PipelineRunner) -> None:
        self._runner = runner
        self._seen_dispatches: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    async def enqueue_pipeline(self, task_id: str, dispatch_token: str) -> None:
        dispatch_id = f"{task_id}:{dispatch_token}"
        if dispatch_id in self._seen_dispatches:
            return

        self._seen_dispatches.add(dispatch_id)
        task = asyncio.create_task(
            self._runner.run(task_id),
            name=f"thermalforge-pipeline:{task_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._observe_completion)

    async def healthcheck(self) -> None:
        return None

    async def close(self) -> None:
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _observe_completion(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            logger.exception("In-process pipeline execution failed")


class ArqTaskQueue:
    def __init__(self, pool: ArqRedis) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, redis_url: str) -> "ArqTaskQueue":
        pool = await create_pool(RedisSettings.from_dsn(redis_url))
        return cls(pool)

    async def enqueue_pipeline(self, task_id: str, dispatch_token: str) -> None:
        await self._pool.enqueue_job(
            "run_pipeline",
            task_id,
            _job_id=f"pipeline:{task_id}:{dispatch_token}",
        )

    async def healthcheck(self) -> None:
        await self._pool.ping()

    async def close(self) -> None:
        await self._pool.aclose()
