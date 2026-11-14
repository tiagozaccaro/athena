"""Copy, move and sync jobs through rclone, with progress and cancel.

Each step is an rclone call started with `_async`, all in one stats group named after
the Athena job, so `core/stats` adds up the whole job. The job polls rclone's job
status and stats, reports progress, and stops rclone's job when it's cancelled.
"""

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from athena.cloud.rclone import Rclone, RcloneError
from athena.jobs import Job

log = logging.getLogger(__name__)

POLL_SECONDS = 1.0
LOG_EVERY_SECONDS = 15.0
PREVIEW_NAMES = 100


@dataclass
class Step:
    """One rclone call: `sync/copy`, `operations/copyfile`, ..."""

    label: str
    method: str
    params: dict[str, Any] = field(default_factory=dict)


class SyncPreview(BaseModel):
    copy_count: int
    """Files that are new or changed at the source."""
    delete_count: int
    """Files at the destination that aren't at the source; sync deletes them."""
    deletes: list[str]
    """The first of those, relative to the destination."""


def size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} TB"


def _duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60} s"
    return f"{seconds // 3600} h {seconds % 3600 // 60} min"


def progress_of(stats: dict[str, Any]) -> tuple[float | None, str]:
    """A fraction and a line like "12.0 MB of 50.0 MB · 2.0 MB/s · 19 s left · 1 of 3
    files" from `core/stats`."""
    done = float(stats.get("bytes") or 0)
    total = float(stats.get("totalBytes") or 0)
    parts = [f"{size(done)} of {size(total)}" if total else size(done)]
    speed = float(stats.get("speed") or 0)
    if speed > 0:
        parts.append(f"{size(speed)}/s")
    eta = stats.get("eta")
    if isinstance(eta, int | float) and eta > 0:
        parts.append(f"{_duration(eta)} left")
    files = int(stats.get("totalTransfers") or 0)
    if files:
        parts.append(f"{int(stats.get('transfers') or 0)} of {files} files")
    deletes = int(stats.get("deletes") or 0)
    if deletes:
        parts.append(f"{deletes} deleted")
    return (done / total if total else None), " · ".join(parts)


async def run(job: Job, rclone: Rclone, steps: list[Step]) -> None:
    group = f"athena-{job.id}"
    current: dict[str, int | None] = {"id": None}

    async def stop() -> None:
        if current["id"] is not None:
            with contextlib.suppress(RcloneError):
                await rclone.call("job/stop", {"jobid": current["id"]})

    job.cancel_hook = stop
    failed = 0
    stats: dict[str, Any] = {}
    try:
        for step in steps:
            if job.cancelled:
                break
            await job.log(step.label)
            started = await rclone.call(
                step.method, {**step.params, "_async": True, "_group": group}
            )
            current["id"] = int(started["jobid"])
            if job.cancelled:
                await stop()
            logged = time.monotonic()
            while True:
                await asyncio.sleep(POLL_SECONDS)
                status = await rclone.call("job/status", {"jobid": current["id"]})
                stats = await rclone.call("core/stats", {"group": group})
                fraction, text = progress_of(stats)
                await job.set_progress(fraction, text)
                if status.get("finished"):
                    break
                if time.monotonic() - logged > LOG_EVERY_SECONDS:
                    logged = time.monotonic()
                    await job.log(f"  {text}")
            current["id"] = None
            if not status.get("success") and not job.cancelled:
                failed += 1
                await job.log(f"  failed: {status.get('error') or 'rclone reported an error'}")
    finally:
        with contextlib.suppress(RcloneError):
            await rclone.call("core/stats-delete", {"group": group})
    if job.cancelled:
        raise RuntimeError("Cancelled")
    if stats:
        await job.log(f"Done: {progress_of(stats)[1]}")
        await job.set_progress(1.0, progress_of(stats)[1])
    if failed:
        raise RuntimeError(
            f"{failed} of {len(steps)} items failed" if len(steps) > 1 else "The transfer failed"
        )


async def preview_sync(rclone: Rclone, src: str, dst: str) -> SyncPreview:
    """What `sync src dst` would change, comparing sizes only (no hashing)."""
    try:
        data = await rclone.call(
            "operations/check",
            {
                "srcFs": src,
                "dstFs": dst,
                "missingOnSrc": True,
                "missingOnDst": True,
                "differ": True,
                "_config": {"SizeOnly": True},
            },
        )
    except RcloneError as exc:
        if exc.status != 404 and "directory not found" not in exc.message:
            raise
        # Nothing at the destination yet: everything is copied, nothing deleted.
        data = await rclone.call("operations/size", {"fs": src})
        return SyncPreview(copy_count=int(data.get("count") or 0), delete_count=0, deletes=[])
    deletes = sorted(data.get("missingOnSrc") or [])
    copies = len(data.get("missingOnDst") or []) + len(data.get("differ") or [])
    return SyncPreview(
        copy_count=copies, delete_count=len(deletes), deletes=deletes[:PREVIEW_NAMES]
    )
