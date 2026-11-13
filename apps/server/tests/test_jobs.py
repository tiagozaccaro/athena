import asyncio
import json
import sys

import pytest

from athena.jobs import Job, JobManager, run_or_fail


async def collect(job: Job) -> list[tuple[str, object]]:
    events = []
    async for chunk in job.events():
        kind, data = chunk.strip().split("\n")
        events.append((kind.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def test_job_streams_lines_then_status() -> None:
    async def scenario() -> list[tuple[str, object]]:
        manager = JobManager()

        async def body(job: Job) -> None:
            await job.log("one")
            await asyncio.sleep(0.01)
            await job.log("two")

        job = manager.start("test", body)
        events = await collect(job)
        assert manager.get(job.id) is job
        return events

    events = asyncio.run(scenario())
    assert events == [
        ("log", "one"),
        ("log", "two"),
        ("status", {"status": "succeeded", "error": None}),
    ]


def test_failed_body_marks_job_failed() -> None:
    async def scenario() -> Job:
        manager = JobManager()

        async def body(job: Job) -> None:
            raise RuntimeError("boom")

        job = manager.start("test", body)
        await collect(job)
        return job

    job = asyncio.run(scenario())
    assert job.status == "failed"
    assert job.error == "boom"


def test_run_command_streams_output_and_exit_code() -> None:
    async def scenario() -> tuple[Job, int]:
        job = Job("cmd")
        code = await job.run_command(
            [sys.executable, "-c", "print('hello'); import sys; sys.exit(3)"]
        )
        return job, code

    job, code = asyncio.run(scenario())
    assert code == 3
    assert job.lines[0].startswith("$ ")
    assert "hello" in job.lines


def test_run_or_fail_raises_on_nonzero() -> None:
    async def scenario() -> None:
        await run_or_fail(Job("x"), [sys.executable, "-c", "raise SystemExit(1)"], "Thing")

    with pytest.raises(RuntimeError, match="Thing failed"):
        asyncio.run(scenario())


def test_missing_binary_is_reported_not_raised() -> None:
    async def scenario() -> tuple[Job, int]:
        job = Job("x")
        return job, await job.run_command(["definitely-not-a-real-binary-athena"])

    job, code = asyncio.run(scenario())
    assert code == -1
    assert job.lines[-1].startswith("error:")
