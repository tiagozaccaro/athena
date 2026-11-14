"""Package managers: search, installed, upgradable, and install/uninstall/upgrade jobs.

Only managers in the capability manifest (`packages.<id>`) are offered, and changes need
the capability to be `ready` (docs/mvp-design.md §3). Each manager runs one job at a
time, so two operations never fight over apt's or dnf's lock.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field

from athena import audit
from athena.auth.deps import Authed, DbSession
from athena.jobs import Job, JobManager, JobOut, run_or_fail
from athena.packages import MANAGERS
from athena.packages.base import (
    PACKAGE_NAME,
    SEARCH_QUERY,
    InstalledPackage,
    PackageError,
    PackageManager,
    PackageRef,
    UpgradablePackage,
    command_env,
    resolve,
)
from athena.platform.capabilities import Capability, Status
from athena.platform.store import CapabilityStore

router = APIRouter(prefix="/packages", tags=["packages"])

ManagerId = Annotated[str, Path(pattern=r"^[a-z]{2,16}$")]
PackageName = Annotated[str, Field(pattern=PACKAGE_NAME.pattern)]


class ManagerOut(BaseModel):
    id: str
    label: str
    status: Status
    available: bool
    detail: str | None = None
    """The version when ready, or why it isn't (e.g. needs root)."""
    can_upgrade_one: bool
    can_refresh: bool
    note: str | None = None


class InstallIn(BaseModel):
    name: PackageName
    source: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")] | None = None
    """Flatpak remote, Scoop bucket, or "cask" for Homebrew casks."""


class NameIn(BaseModel):
    name: PackageName


class UpgradeIn(BaseModel):
    name: PackageName | None = None
    """Leave out to upgrade everything."""


async def _capabilities(request: Request) -> list[Capability]:
    store: CapabilityStore = request.app.state.capabilities
    return (await store.get()).capabilities


def _out(cap: Capability, cls: type[PackageManager]) -> ManagerOut:
    return ManagerOut(
        id=cls.id,
        label=cls.label,
        status=cap.status,
        available=cap.available,
        detail=cap.detail,
        can_upgrade_one=cls.can_upgrade_one,
        can_refresh=cls.can_refresh,
        note=cls.note,
    )


async def _manager(request: Request, manager: str) -> PackageManager:
    cls = MANAGERS.get(manager)
    caps = {c.id: c for c in await _capabilities(request)}
    cap = caps.get(f"packages.{manager}")
    if cls is None or cap is None or cap.status == "missing":
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{manager} isn't installed on this host")
    if not cap.available:
        raise HTTPException(status.HTTP_409_CONFLICT, cap.detail or f"{cls.label} isn't ready")
    return cls(request.app.state.package_runner)


async def _read(coro):
    try:
        return await coro
    except PackageError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@router.get("", operation_id="listPackageManagers")
async def list_managers(request: Request) -> list[ManagerOut]:
    """The package managers found on this host (ready or not), in detection order."""
    return [
        _out(cap, MANAGERS[cap.id.removeprefix("packages.")])
        for cap in await _capabilities(request)
        if cap.id.startswith("packages.")
        and cap.status != "missing"
        and cap.id.removeprefix("packages.") in MANAGERS
    ]


@router.get("/{manager}/search", operation_id="searchPackages")
async def search(
    manager: ManagerId,
    request: Request,
    q: Annotated[str, Query(pattern=SEARCH_QUERY.pattern)],
) -> list[PackageRef]:
    return await _read((await _manager(request, manager)).search(q.strip()))


@router.get("/{manager}/installed", operation_id="listInstalledPackages")
async def installed(manager: ManagerId, request: Request) -> list[InstalledPackage]:
    return await _read((await _manager(request, manager)).installed())


@router.get("/{manager}/upgradable", operation_id="listUpgradablePackages")
async def upgradable(manager: ManagerId, request: Request) -> list[UpgradablePackage]:
    """From the package lists as last refreshed (apt, dnf and others cache them)."""
    return await _read((await _manager(request, manager)).upgradable())


# ---------------------------------------------------------------- changes (jobs)

Action = Literal["install", "uninstall", "upgrade", "refresh"]


def _start(
    request: Request,
    pm: PackageManager,
    action: Action,
    argv: list[str],
    title: str,
    user: Authed,
    db: DbSession,
    target: str,
) -> JobOut:
    busy: dict[str, str] = request.app.state.package_jobs
    jobs: JobManager = request.app.state.jobs
    current = busy.get(pm.id)
    if current and (job := jobs.get(current)) and job.status == "running":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{pm.label} is busy: {job.title}. Wait for it to finish."
        )

    async def body(job: Job) -> None:
        try:
            await run_or_fail(job, resolve(argv), title, env=command_env(pm.env))
        finally:
            busy.pop(pm.id, None)

    audit.record(db, user.user.username, f"package.{action}", f"{pm.id}:{target}")
    job = jobs.start(title, body)
    busy[pm.id] = job.id
    return job.out()


@router.post(
    "/{manager}/install", operation_id="installPackage", status_code=status.HTTP_202_ACCEPTED
)
async def install(
    manager: ManagerId, body: InstallIn, request: Request, user: Authed, db: DbSession
) -> JobOut:
    pm = await _manager(request, manager)
    argv = pm.install_argv(body.name, body.source)
    return _start(request, pm, "install", argv, f"Install {body.name}", user, db, body.name)


@router.post(
    "/{manager}/uninstall", operation_id="uninstallPackage", status_code=status.HTTP_202_ACCEPTED
)
async def uninstall(
    manager: ManagerId, body: NameIn, request: Request, user: Authed, db: DbSession
) -> JobOut:
    pm = await _manager(request, manager)
    argv = pm.uninstall_argv(body.name)
    return _start(request, pm, "uninstall", argv, f"Uninstall {body.name}", user, db, body.name)


@router.post(
    "/{manager}/upgrade", operation_id="upgradePackages", status_code=status.HTTP_202_ACCEPTED
)
async def upgrade(
    manager: ManagerId, body: UpgradeIn, request: Request, user: Authed, db: DbSession
) -> JobOut:
    pm = await _manager(request, manager)
    if body.name and not pm.can_upgrade_one:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{pm.label} can only upgrade everything at once. {pm.note or ''}".strip(),
        )
    title = f"Upgrade {body.name}" if body.name else f"Upgrade all {pm.label} packages"
    target = body.name or "*"
    return _start(request, pm, "upgrade", pm.upgrade_argv(body.name), title, user, db, target)


@router.post(
    "/{manager}/refresh", operation_id="refreshPackageLists", status_code=status.HTTP_202_ACCEPTED
)
async def refresh(manager: ManagerId, request: Request, user: Authed, db: DbSession) -> JobOut:
    """Update the package lists (apt update, dnf makecache…) so search and upgrades are current."""
    pm = await _manager(request, manager)
    argv = pm.refresh_argv()
    if argv is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{pm.label} has no separate list refresh")
    return _start(request, pm, "refresh", argv, f"Refresh {pm.label} package lists", user, db, "-")
