import asyncio
from typing import Any, cast

import pytest
from arq.connections import ArqRedis

from app.services.queue import ArqTaskQueue, InProcessTaskQueue


class RecordingArqPool:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def enqueue_job(
        self,
        *args: object,
        **kwargs: object,
    ) -> None:
        self.calls.append((args, kwargs))


class RecordingPipelineRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def run(self, task_id: str) -> None:
        self.calls.append(task_id)
        self.started.set()
        await self.release.wait()


@pytest.mark.asyncio
async def test_arq_job_ids_deduplicate_one_dispatch_but_allow_later_dispatches() -> None:
    pool = RecordingArqPool()
    queue = ArqTaskQueue(cast(ArqRedis, cast(Any, pool)))

    await queue.enqueue_pipeline("task-1", "start:2")
    await queue.enqueue_pipeline("task-1", "start:2")
    await queue.enqueue_pipeline("task-1", "retry:event:8")
    await queue.enqueue_pipeline("task-1", "clarification:clarification-1")

    job_ids = [str(kwargs["_job_id"]) for _, kwargs in pool.calls]
    assert job_ids == [
        "pipeline:task-1:start:2",
        "pipeline:task-1:start:2",
        "pipeline:task-1:retry:event:8",
        "pipeline:task-1:clarification:clarification-1",
    ]


@pytest.mark.asyncio
async def test_in_process_queue_deduplicates_dispatch_tokens() -> None:
    runner = RecordingPipelineRunner()
    queue = InProcessTaskQueue(runner)

    await queue.enqueue_pipeline("task-1", "start:2")
    await runner.started.wait()
    await queue.enqueue_pipeline("task-1", "start:2")

    runner.release.set()
    await queue.close()

    assert runner.calls == ["task-1"]


@pytest.mark.asyncio
async def test_in_process_queue_runs_distinct_dispatch_tokens() -> None:
    runner = RecordingPipelineRunner()
    runner.release.set()
    queue = InProcessTaskQueue(runner)

    await queue.enqueue_pipeline("task-1", "start:2")
    await queue.enqueue_pipeline("task-1", "retry:event:8")
    await asyncio.sleep(0)
    await queue.close()

    assert runner.calls == ["task-1", "task-1"]
