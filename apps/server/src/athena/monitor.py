"""Live host statistics: CPU, memory, disks, network and temperatures via psutil.

A background task samples the host every `interval` seconds and keeps about an hour
of history in a ring buffer, so the dashboard can draw sparklines the moment it
opens. Clients then follow new samples over Server-Sent Events.

psutil works on Linux, macOS and Windows, so this needs no capability. Metrics a host
can't report (temperatures outside Linux, disk I/O counters on some machines) are
`None` and the UI hides them.
"""

import asyncio
import contextlib
import logging
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import psutil
from pydantic import BaseModel

log = logging.getLogger(__name__)

INTERVAL = 2.0
HISTORY_SECONDS = 3600
DISKS_EVERY = 30.0  # partitions and usage change slowly; listing them can be slow on Windows

# Pseudo, image and snapshot filesystems that aren't storage a user manages.
SKIP_FSTYPES = {
    "squashfs", "tmpfs", "devtmpfs", "overlay", "iso9660", "udf", "autofs",
    "devfs", "nullfs", "ramfs", "efivarfs", "fuse.snapfuse",
}  # fmt: skip
SKIP_MOUNT_PREFIXES = ("/snap/", "/private/var/run/", "/var/lib/docker/", "/boot/efi")
# Interfaces whose traffic is local or duplicates a real NIC's (container bridges).
SKIP_NIC_PREFIXES = (
    "lo", "loopback", "veth", "docker", "br-", "cni", "flannel", "virbr", "vethernet",
)  # fmt: skip
CPU_SENSORS = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal", "soc_thermal")


class StatsSample(BaseModel):
    """One sample of the fast-changing metrics. Rates are per second since the last sample."""

    t: float  # Unix time
    cpu_percent: float
    mem_used: int
    mem_total: int
    swap_used: int
    swap_total: int
    net_rx: float  # bytes/s
    net_tx: float
    disk_read: float | None  # bytes/s; None when the host has no disk I/O counters
    disk_write: float | None
    cpu_temp: float | None  # °C; None when the host has no CPU sensor


class DiskUsage(BaseModel):
    mountpoint: str
    device: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float


class Temperature(BaseModel):
    label: str
    current: float
    high: float | None = None
    critical: float | None = None


class HostStats(BaseModel):
    interval: float
    boot_time: float
    cpu_count: int
    cpu_count_physical: int | None
    load_avg: list[float] | None  # 1, 5, 15 minutes; None on Windows
    disks: list[DiskUsage]
    temperatures: list[Temperature] | None  # None when the host can't report them
    latest: StatsSample | None


class StatsSnapshot(HostStats):
    history: list[StatsSample]


@dataclass
class Counters:
    """Cumulative counters from the previous sample, for computing rates."""

    t: float
    net_rx: int
    net_tx: int
    disk_read: int | None
    disk_write: int | None


@dataclass
class Readings:
    """Raw readings from the host, separated from psutil so tests can feed their own."""

    cpu_percent: float
    mem_used: int
    mem_total: int
    swap_used: int
    swap_total: int
    net_rx: int
    net_tx: int
    disk_read: int | None
    disk_write: int | None
    temperatures: list[Temperature] | None
    load_avg: list[float] | None = None


# ------------------------------------------------------------------ psutil readers


def _counted_nic(name: str) -> bool:
    return not name.lower().startswith(SKIP_NIC_PREFIXES)


def read_host() -> Readings:
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    rx = tx = 0
    for name, nic in psutil.net_io_counters(pernic=True).items():
        if _counted_nic(name):
            rx += nic.bytes_recv
            tx += nic.bytes_sent
    try:
        disk = psutil.disk_io_counters()
    except (OSError, RuntimeError):  # Windows without diskperf, some containers
        disk = None
    try:
        load = [round(x, 2) for x in psutil.getloadavg()] if hasattr(psutil, "getloadavg") else None
    except OSError:
        load = None
    return Readings(
        cpu_percent=psutil.cpu_percent(interval=None),
        # total - available is what users mean by "used" (psutil's `used` excludes caches
        # differently per OS).
        mem_used=mem.total - mem.available,
        mem_total=mem.total,
        swap_used=swap.used,
        swap_total=swap.total,
        net_rx=rx,
        net_tx=tx,
        disk_read=disk.read_bytes if disk else None,
        disk_write=disk.write_bytes if disk else None,
        temperatures=read_temperatures(),
        load_avg=load if load and any(load) else None,
    )


def read_temperatures() -> list[Temperature] | None:
    if not hasattr(psutil, "sensors_temperatures"):  # macOS, Windows
        return None
    try:
        sensors = psutil.sensors_temperatures()
    except (OSError, RuntimeError):
        return None
    out: list[Temperature] = []
    for chip, entries in sensors.items():
        for i, entry in enumerate(entries):
            if entry.current is None or entry.current <= 0:
                continue
            label = entry.label or (chip if len(entries) == 1 else f"{chip} {i + 1}")
            if entry.label and not entry.label.lower().startswith(chip.lower()):
                label = f"{chip} · {entry.label}"
            out.append(
                Temperature(
                    label=label,
                    current=round(entry.current, 1),
                    high=entry.high or None,
                    critical=entry.critical or None,
                )
            )
    return out


def cpu_temperature(temps: list[Temperature] | None) -> float | None:
    """The hottest CPU sensor, or the hottest sensor of any kind if none looks like a CPU."""
    if not temps:
        return None
    cpu = [t.current for t in temps if t.label.lower().startswith(CPU_SENSORS)]
    return max(cpu or [t.current for t in temps])


def _shown_partition(part: Any) -> bool:
    opts = set(part.opts.split(","))
    if part.fstype.lower() in SKIP_FSTYPES:
        return False
    if part.mountpoint.startswith(SKIP_MOUNT_PREFIXES):
        return False
    if "dontbrowse" in opts:  # macOS hidden system volumes
        return False
    if "cdrom" in opts:  # Windows optical drives
        return False
    # Read-only mounts are disk images and snaps, except the sealed macOS system volume.
    return not ("ro" in opts and part.mountpoint != "/")


def read_disks() -> list[DiskUsage]:
    disks: list[DiskUsage] = []
    seen: set[tuple[int, int]] = set()
    try:
        parts = psutil.disk_partitions(all=False)
    except OSError:
        return []
    # Shortest mount point first, so "/" wins over volumes in the same APFS container.
    for part in sorted(parts, key=lambda p: (len(p.mountpoint), p.mountpoint)):
        if not _shown_partition(part):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (OSError, PermissionError):  # empty card readers, unmounted network drives
            continue
        if usage.total == 0:
            continue
        # APFS volumes (and bind mounts) share one pool: same total and free space.
        key = (usage.total, usage.free)
        if key in seen:
            continue
        seen.add(key)
        # On APFS `used` counts only this volume; total - free is the whole disk.
        used = usage.total - usage.free
        disks.append(
            DiskUsage(
                mountpoint=part.mountpoint,
                device=part.device,
                fstype=part.fstype,
                total=usage.total,
                used=used,
                free=usage.free,
                percent=round(used / usage.total * 100, 1),
            )
        )
    return disks


# ------------------------------------------------------------------ monitor


def _rate(now: int | None, before: int | None, dt: float) -> float | None:
    if now is None or before is None:
        return None
    # Counters reset when an interface goes away or a disk is removed: report 0, not negative.
    return max(0.0, (now - before) / dt)


class HostMonitor:
    def __init__(
        self,
        reader: Callable[[], Readings] = read_host,
        disk_reader: Callable[[], list[DiskUsage]] = read_disks,
        interval: float = INTERVAL,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.interval = interval
        self._reader = reader
        self._disk_reader = disk_reader
        self._clock = clock
        self.history: deque[StatsSample] = deque(maxlen=max(1, int(HISTORY_SECONDS / interval)))
        self._prev: Counters | None = None
        self._disks: list[DiskUsage] = []
        self._disks_at = float("-inf")
        self._temps: list[Temperature] | None = None
        self._load: list[float] | None = None
        self._seq = 0  # bumped on every sample, so streams know when to send
        self._changed = asyncio.Condition()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None

    # -- sampling

    def _sample_sync(self) -> StatsSample:
        now = self._clock()
        r = self._reader()
        if now - self._disks_at >= DISKS_EVERY:
            self._disks = self._disk_reader()
            self._disks_at = now
        prev, self._prev = (
            self._prev,
            Counters(now, r.net_rx, r.net_tx, r.disk_read, r.disk_write),
        )
        dt = now - prev.t if prev else 0.0
        if prev and dt > 0:
            net_rx = _rate(r.net_rx, prev.net_rx, dt) or 0.0
            net_tx = _rate(r.net_tx, prev.net_tx, dt) or 0.0
            disk_read = _rate(r.disk_read, prev.disk_read, dt)
            disk_write = _rate(r.disk_write, prev.disk_write, dt)
        else:  # first sample: no rates yet
            net_rx = net_tx = 0.0
            disk_read = 0.0 if r.disk_read is not None else None
            disk_write = 0.0 if r.disk_write is not None else None
        self._temps = r.temperatures
        self._load = r.load_avg
        return StatsSample(
            t=round(now, 3),
            cpu_percent=round(r.cpu_percent, 1),
            mem_used=r.mem_used,
            mem_total=r.mem_total,
            swap_used=r.swap_used,
            swap_total=r.swap_total,
            net_rx=round(net_rx, 1),
            net_tx=round(net_tx, 1),
            disk_read=None if disk_read is None else round(disk_read, 1),
            disk_write=None if disk_write is None else round(disk_write, 1),
            cpu_temp=cpu_temperature(r.temperatures),
        )

    async def sample_once(self) -> StatsSample:
        """Take one sample (off the event loop), store it and wake stream subscribers."""
        async with self._lock:
            sample = await asyncio.to_thread(self._sample_sync)
        async with self._changed:
            self.history.append(sample)
            self._seq += 1
            self._changed.notify_all()
        return sample

    async def _run(self) -> None:
        # psutil's CPU percent is measured since the previous call; prime it.
        with contextlib.suppress(Exception):
            await asyncio.to_thread(psutil.cpu_percent, None)
        while True:
            started = time.monotonic()
            try:
                await self.sample_once()
            except Exception:
                log.exception("host stats sample failed")
            await asyncio.sleep(max(0.1, self.interval - (time.monotonic() - started)))

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    # -- reading

    def host(self) -> HostStats:
        try:
            boot = psutil.boot_time()
        except OSError:
            boot = 0.0
        return HostStats(
            interval=self.interval,
            boot_time=boot,
            cpu_count=psutil.cpu_count() or 1,
            cpu_count_physical=psutil.cpu_count(logical=False),
            load_avg=self._load,
            disks=self._disks,
            temperatures=self._temps,
            latest=self.history[-1] if self.history else None,
        )

    async def snapshot(self) -> StatsSnapshot:
        if not self.history:  # not started yet (tests, or the very first request)
            await self.sample_once()
        return StatsSnapshot(**self.host().model_dump(), history=list(self.history))

    async def events(self) -> AsyncIterator[str]:
        """SSE stream: a `stats` event (HostStats JSON) after every new sample."""
        seen = self._seq
        if self.history:
            yield f"event: stats\ndata: {self.host().model_dump_json()}\n\n"
        while True:
            async with self._changed:
                await self._changed.wait_for(lambda s=seen: self._seq != s)
                seen = self._seq
            yield f"event: stats\ndata: {self.host().model_dump_json()}\n\n"
