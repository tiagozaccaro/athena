import asyncio
from collections import namedtuple
from pathlib import Path

import psutil
import pytest
from conftest import make_app, signed_in
from fastapi.testclient import TestClient

from athena import monitor
from athena.monitor import (
    DiskUsage,
    HostMonitor,
    Readings,
    Temperature,
    cpu_temperature,
    read_disks,
    read_host,
)

Part = namedtuple("Part", "device mountpoint fstype opts")
Usage = namedtuple("Usage", "total used free percent")


def readings(**over) -> Readings:
    base = dict(
        cpu_percent=12.34,
        mem_used=4_000,
        mem_total=16_000,
        swap_used=0,
        swap_total=2_000,
        net_rx=1_000,
        net_tx=500,
        disk_read=10_000,
        disk_write=20_000,
        temperatures=None,
    )
    return Readings(**(base | over))


class Feed:
    """A reader and clock that replay scripted readings."""

    def __init__(self, *steps: tuple[float, Readings]) -> None:
        self.steps = list(steps)
        self.now = 0.0

    def clock(self) -> float:
        self.now = self.steps[0][0]
        return self.now

    def read(self) -> Readings:
        return self.steps.pop(0)[1]


def make_monitor(feed: Feed, disks: list[DiskUsage] | None = None, interval: float = 2.0):
    return HostMonitor(
        reader=feed.read, disk_reader=lambda: disks or [], interval=interval, clock=feed.clock
    )


def test_rates_are_per_second_since_the_previous_sample() -> None:
    feed = Feed(
        (100.0, readings()),
        (102.0, readings(net_rx=3_000, net_tx=1_500, disk_read=14_000, disk_write=20_000)),
    )
    mon = make_monitor(feed)
    first = asyncio.run(mon.sample_once())
    assert (first.net_rx, first.net_tx, first.disk_read, first.disk_write) == (0, 0, 0, 0)
    assert first.cpu_percent == 12.3

    second = asyncio.run(mon.sample_once())
    assert second.net_rx == 1_000.0
    assert second.net_tx == 500.0
    assert second.disk_read == 2_000.0
    assert second.disk_write == 0.0
    assert [s.t for s in mon.history] == [100.0, 102.0]


def test_counter_reset_reports_zero_not_negative() -> None:
    feed = Feed((0.0, readings(net_rx=9_000)), (2.0, readings(net_rx=100)))
    mon = make_monitor(feed)
    asyncio.run(mon.sample_once())
    assert asyncio.run(mon.sample_once()).net_rx == 0.0


def test_missing_disk_counters_stay_none() -> None:
    feed = Feed(
        (0.0, readings(disk_read=None, disk_write=None)),
        (2.0, readings(disk_read=None, disk_write=None)),
    )
    mon = make_monitor(feed)
    assert asyncio.run(mon.sample_once()).disk_read is None
    assert asyncio.run(mon.sample_once()).disk_write is None


def test_history_keeps_about_an_hour() -> None:
    mon = HostMonitor(reader=readings, disk_reader=list, interval=1200.0)
    assert mon.history.maxlen == 3
    for _ in range(5):
        asyncio.run(mon.sample_once())
    assert len(mon.history) == 3


def test_disks_are_refreshed_slowly() -> None:
    calls = []

    def disks() -> list[DiskUsage]:
        calls.append(1)
        return []

    feed = Feed(*[(t, readings()) for t in (0.0, 2.0, 4.0, 31.0)])
    mon = HostMonitor(reader=feed.read, disk_reader=disks, clock=feed.clock)
    for _ in range(4):
        asyncio.run(mon.sample_once())
    assert len(calls) == 2


def test_cpu_temperature_prefers_cpu_sensors() -> None:
    temps = [
        Temperature(label="nvme · Composite", current=60),
        Temperature(label="coretemp · Package id 0", current=48),
        Temperature(label="coretemp · Core 1", current=51),
    ]
    assert cpu_temperature(temps) == 51
    assert cpu_temperature([Temperature(label="acpitz", current=40)]) == 40
    assert cpu_temperature(None) is None
    assert cpu_temperature([]) is None


def test_snapshot_and_host_include_temperatures_and_disks() -> None:
    disk = DiskUsage(
        mountpoint="/", device="/dev/sda1", fstype="ext4", total=10, used=4, free=6, percent=40
    )
    temps = [Temperature(label="coretemp · Core 0", current=45.5)]
    mon = make_monitor(Feed((5.0, readings(temperatures=temps, load_avg=[0.5, 0.4, 0.3]))), [disk])
    snap = asyncio.run(mon.snapshot())
    assert snap.disks == [disk]
    assert snap.temperatures == temps
    assert snap.load_avg == [0.5, 0.4, 0.3]
    assert snap.latest is not None and snap.latest.cpu_temp == 45.5
    assert len(snap.history) == 1
    assert snap.cpu_count >= 1


def test_events_stream_a_message_per_sample() -> None:
    async def scenario() -> list[str]:
        feed = Feed(*[(float(t), readings()) for t in range(3)])
        mon = make_monitor(feed)
        await mon.sample_once()
        stream = mon.events()
        first = await anext(stream)  # current state, sent right away
        task = asyncio.ensure_future(anext(stream))
        await asyncio.sleep(0)
        assert not task.done()  # waits for a new sample
        await mon.sample_once()
        second = await asyncio.wait_for(task, 1)
        await stream.aclose()
        return [first, second]

    first, second = asyncio.run(scenario())
    assert first.startswith("event: stats\ndata: {")
    assert '"t":0.0' in first
    assert '"t":1.0' in second


# ---------------------------------------------------------------- host readers


def fake_partitions(monkeypatch, parts: list[Part], usage: dict[str, Usage | Exception]) -> None:
    def disk_usage(path: str) -> Usage:
        value = usage[path]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(psutil, "disk_partitions", lambda all=False: parts)
    monkeypatch.setattr(psutil, "disk_usage", disk_usage)


def test_macos_apfs_volumes_collapse_to_root(monkeypatch) -> None:
    shared = Usage(500, 20, 44, 0)
    fake_partitions(
        monkeypatch,
        [
            Part("/dev/disk3s1s1", "/", "apfs", "ro,local,rootfs,dovolfs,journaled"),
            Part("/dev/disk3s6", "/System/Volumes/VM", "apfs", "rw,noexec,local,dontbrowse"),
            Part("/dev/disk3s5", "/System/Volumes/Data", "apfs", "rw,local,dontbrowse"),
            Part("/dev/disk3s3", "/Volumes/Recovery", "apfs", "rw,local,dontbrowse"),
            Part("/dev/disk5s1", "/Volumes/Installer", "hfs", "ro,nosuid,local"),
            Part("/dev/disk9s1", "/Volumes/Backup", "apfs", "rw,local,journaled"),
            Part("/dev/disk4", "/private/var/run/com.apple.x/mnt/y", "apfs", "ro,local"),
        ],
        {"/": shared, "/Volumes/Backup": Usage(2_000, 0, 1_500, 0)},
    )
    disks = read_disks()
    assert [d.mountpoint for d in disks] == ["/", "/Volumes/Backup"]
    root = disks[0]
    assert (root.total, root.free, root.used, root.percent) == (500, 44, 456, 91.2)


def test_linux_skips_snaps_and_pseudo_filesystems(monkeypatch) -> None:
    fake_partitions(
        monkeypatch,
        [
            Part("/dev/sda2", "/", "ext4", "rw,relatime"),
            Part("/dev/sda1", "/boot/efi", "vfat", "rw"),
            Part("/dev/loop3", "/snap/core22/1380", "squashfs", "ro,nodev"),
            Part("/dev/sdb1", "/srv/media", "ext4", "rw"),
            Part("/dev/sda2", "/var/lib/docker/overlay2", "ext4", "rw"),
            Part("tmpfs", "/run", "tmpfs", "rw"),
        ],
        {"/": Usage(100, 50, 50, 50), "/srv/media": Usage(4_000, 1_000, 3_000, 25)},
    )
    assert [d.mountpoint for d in read_disks()] == ["/", "/srv/media"]


def test_windows_skips_cdrom_and_unreadable_drives(monkeypatch) -> None:
    fake_partitions(
        monkeypatch,
        [
            Part("C:\\", "C:\\", "NTFS", "rw,fixed"),
            Part("D:\\", "D:\\", "", "cdrom"),
            Part("E:\\", "E:\\", "", "rw,removable"),
            Part("F:\\", "F:\\", "FAT32", "rw,removable"),
        ],
        {
            "C:\\": Usage(1_000, 400, 600, 40),
            "E:\\": PermissionError("device not ready"),
            "F:\\": Usage(0, 0, 0, 0),
        },
    )
    assert [d.mountpoint for d in read_disks()] == ["C:\\"]


def test_loopback_and_container_bridges_are_not_counted() -> None:
    names = ["lo", "lo0", "eth0", "en0", "veth12ab", "docker0", "br-1f2e", "Wi-Fi"]
    names += ["Loopback Pseudo-Interface 1", "vEthernet (WSL)"]
    counted = [n for n in names if monitor._counted_nic(n)]
    assert counted == ["eth0", "en0", "Wi-Fi"]


def test_read_host_works_on_this_machine() -> None:
    r = read_host()
    assert r.mem_total > 0
    assert 0 <= r.mem_used <= r.mem_total
    assert r.net_rx >= 0
    assert r.temperatures is None or isinstance(r.temperatures, list)


def test_read_disks_works_on_this_machine() -> None:
    disks = read_disks()
    assert disks, "every host has at least one disk"
    assert all(d.total > 0 and 0 <= d.percent <= 100 for d in disks)


# ---------------------------------------------------------------- API


def test_stats_require_a_session(tmp_path: Path) -> None:
    client = TestClient(make_app(tmp_path))
    assert client.get("/api/system/stats").status_code == 401
    assert client.get("/api/system/stats/stream").status_code == 401


def test_stats_snapshot(tmp_path: Path) -> None:
    client = signed_in(TestClient(make_app(tmp_path)))
    res = client.get("/api/system/stats")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["interval"] == 2.0
    assert len(body["history"]) == 1
    assert body["latest"]["mem_total"] > 0
    assert body["disks"]


@pytest.mark.parametrize("path", ["/api/system/stats", "/api/system/stats/stream"])
def test_stats_routes_are_in_openapi(tmp_path: Path, path: str) -> None:
    schema = TestClient(make_app(tmp_path)).get("/api/openapi.json").json()
    assert path in schema["paths"]
