"""Container operations on top of a `Runtime`. Blocking: call from a worker thread."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from python_on_whales import Container
from python_on_whales.exceptions import DockerException, NoSuchContainer

from athena.containers.runtime import Runtime

# Container ids and names: never let a value that starts with "-" reach the CLI as a flag.
CONTAINER_REF = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$"
_REF_RE = re.compile(CONTAINER_REF)

PROJECT_LABEL = "com.docker.compose.project"
SERVICE_LABEL = "com.docker.compose.service"

Action = Literal["start", "stop", "restart"]


class ContainerOut(BaseModel):
    id: str
    name: str
    image: str
    state: str
    """running, exited, paused, created, restarting or dead."""
    exit_code: int | None
    created: datetime | None
    started_at: datetime | None
    ports: list[str]
    """Published ports, e.g. "8080→80/tcp"."""
    project: str | None
    """Compose project, if the container belongs to one."""
    service: str | None


class ContainerError(RuntimeError):
    pass


class ContainerNotFoundError(ContainerError):
    pass


def check_ref(ref: str) -> str:
    if not _REF_RE.match(ref):
        raise ContainerNotFoundError(f"Invalid container reference: {ref!r}")
    return ref


def _ports(container: Container) -> list[str]:
    published: list[str] = []
    for private, bindings in sorted((container.network_settings.ports or {}).items()):
        for binding in bindings or []:
            host_port = binding.get("HostPort")
            if host_port and f"{host_port}→{private}" not in published:
                published.append(f"{host_port}→{private}")
    return published


def to_out(container: Container) -> ContainerOut:
    labels = container.config.labels or {}
    state = container.state
    started = state.started_at if state.running else None
    return ContainerOut(
        id=container.id[:12],
        name=container.name.lstrip("/"),
        image=container.config.image or "",
        state=state.status or "unknown",
        exit_code=None if state.running else state.exit_code,
        created=container.created,
        started_at=started,
        ports=_ports(container),
        project=labels.get(PROJECT_LABEL),
        service=labels.get(SERVICE_LABEL),
    )


def list_containers(runtime: Runtime) -> list[ContainerOut]:
    try:
        containers = runtime.client().container.list(all=True)
    except DockerException as exc:
        raise ContainerError(_message(exc)) from exc
    return sorted((to_out(c) for c in containers), key=lambda c: (c.project or "~", c.name))


def get_container(runtime: Runtime, ref: str) -> ContainerOut:
    try:
        return to_out(runtime.client().container.inspect(check_ref(ref)))
    except NoSuchContainer as exc:
        raise ContainerNotFoundError(f"No container {ref!r}") from exc
    except DockerException as exc:
        raise ContainerError(_message(exc)) from exc


def act(runtime: Runtime, ref: str, action: Action) -> ContainerOut:
    containers = runtime.client().container
    try:
        {"start": containers.start, "stop": containers.stop, "restart": containers.restart}[action](
            check_ref(ref)
        )
    except NoSuchContainer as exc:
        raise ContainerNotFoundError(f"No container {ref!r}") from exc
    except DockerException as exc:
        raise ContainerError(_message(exc)) from exc
    return get_container(runtime, ref)


def remove(runtime: Runtime, ref: str, force: bool) -> None:
    try:
        runtime.client().container.remove(check_ref(ref), force=force)
    except NoSuchContainer as exc:
        raise ContainerNotFoundError(f"No container {ref!r}") from exc
    except DockerException as exc:
        raise ContainerError(_message(exc)) from exc


def logs(runtime: Runtime, ref: str, tail: int) -> list[str]:
    try:
        text = runtime.client().container.logs(check_ref(ref), tail=tail, timestamps=False)
    except NoSuchContainer as exc:
        raise ContainerNotFoundError(f"No container {ref!r}") from exc
    except DockerException as exc:
        raise ContainerError(_message(exc)) from exc
    return str(text).splitlines()


def follow_logs_command(runtime: Runtime, ref: str, tail: int) -> list[str]:
    return runtime.command("logs", "--follow", "--tail", str(tail), check_ref(ref))


def _message(exc: DockerException) -> str:
    stderr = (getattr(exc, "stderr", None) or "").strip()
    return stderr.splitlines()[-1] if stderr else str(exc).strip().splitlines()[0]
