"""Background jobs for long operations (pulls, compose up, starting a runtime).

A job collects output lines and a final status. Clients follow it over Server-Sent
Events. Jobs live in memory: a restart forgets them, which is fine for progress
reporting. Durable records of who did what go to the audit log.
"""

import asyncio
import json
import logging
import secrets
import subprocess
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

JobStatus = Literal["running", "succeeded", "failed"]
MAX_LINES = 5000
KEEP_FINISHED = 100


class JobOut(BaseModel):
    id: str
    title: str
    status: JobStatus
    lines: list[str] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class Job:
    def __init__(self, title: str) -> None:
        self.id = secrets.token_hex(8)
        self.title = title
        self.status: JobStatus = "running"
        self.lines: list[str] = []
        self.error: str | None = None
        self.started_at = datetime.now(UTC)
        self.finished_at: datetime | None = None
        self._changed = asyncio.Condition()

    def out(self) -> JobOut:
        return JobOut(
            id=self.id,
            title=self.title,
            status=self.status,
            lines=list(self.lines),
            error=self.error,
            started_at=self.started_at,
            finished_at=self.finished_at,
        )

    async def log(self, line: str) -> None:
        async with self._changed:
            self.lines.append(line.rstrip("\r\n"))
            if len(self.lines) > MAX_LINES:
                del self.lines[: len(self.lines) - MAX_LINES]
            self._changed.notify_all()

    async def finish(self, error: str | None = None) -> None:
        async with self._changed:
            self.status = "failed" if error else "succeeded"
            self.error = error
            self.finished_at = datetime.now(UTC)
            self._changed.notify_all()

    async def events(self) -> AsyncIterator[str]:
        """SSE stream: every line so far, then new lines, then a final `status` event."""
        sent = 0
        while True:
            async with self._changed:
                if sent >= len(self.lines) and self.status == "running":
                    await self._changed.wait()
                new = self.lines[sent:]
                sent = len(self.lines)
                done = self.status != "running"
            for line in new:
                yield f"event: log\ndata: {json.dumps(line)}\n\n"
            if done:
                payload = {"status": self.status, "error": self.error}
                yield f"event: status\ndata: {json.dumps(payload)}\n\n"
                return

    async def run_command(self, argv: list[str], env: Mapping[str, str] | None = None) -> int:
        """Run a command, streaming its combined output into the job. Returns the exit code."""
        await self.log(f"$ {' '.join(argv)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.DEVNULL,
                env=dict(env) if env is not None else None,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            await self.log(f"error: {exc}")
            return -1
        assert proc.stdout is not None
        async for raw in proc.stdout:
            await self.log(raw.decode(errors="replace"))
        return await proc.wait()


JobBody = Callable[[Job], Awaitable[None]]


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def start(self, title: str, body: JobBody) -> Job:
        """Run `body(job)` in the background. Raise inside it (or return) to finish."""
        job = Job(title)
        self._jobs[job.id] = job
        self._prune()

        async def runner() -> None:
            try:
                await body(job)
            except Exception as exc:
                log.exception("job %s (%s) failed", job.id, title)
                await job.finish(str(exc) or exc.__class__.__name__)
            else:
                if job.status == "running":
                    await job.finish()

        task = asyncio.create_task(runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def _prune(self) -> None:
        finished = [j for j in self._jobs.values() if j.status != "running"]
        for job in sorted(finished, key=lambda j: j.started_at)[:-KEEP_FINISHED]:
            self._jobs.pop(job.id, None)


class CommandFailedError(RuntimeError):
    pass


async def run_or_fail(
    job: Job, argv: list[str], what: str, env: Mapping[str, str] | None = None
) -> None:
    code = await job.run_command(argv, env=env)
    if code != 0:
        raise CommandFailedError(f"{what} failed (exit code {code})")
