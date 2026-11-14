"""Cloud remotes: rclone's backends, the remotes in Athena's rclone config, and the
non-interactive config flow that creates and edits them (docs/mvp-design.md §4.4).

rclone asks follow-up questions while it configures some backends (OAuth sign-in,
picking a drive, ...). Each answer is sent back with the `state` rclone gave, until it
returns an empty state. Athena answers "use a browser on this machine?" with no, so
OAuth always goes through `rclone authorize` on the person's own computer: a browser
sign-in on the server's 127.0.0.1 wouldn't reach someone using Athena over the LAN.
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from athena.cloud.rclone import Rclone, RcloneError
from athena.files.ops import MAX_ENTRIES, FileEntry, Listing
from athena.files.paths import BadPath, NotFound

REMOTE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.+@ -]{0,63}$")
# Backends that would reach the host's own disks (or memory) outside the file manager's
# locations, so the UI doesn't offer them and the API won't create them.
HIDDEN_TYPES = {"local", "alias", "memory", "cache", "tardigrade"}
# rclone's Option.Hide bit for "don't show in the configurator".
HIDE_CONFIGURATOR = 1
AUTO_ANSWERS = {"config_is_local": "false"}
KEEP = ""
"""A secret sent empty when editing keeps its current value."""


class OptionExample(BaseModel):
    value: str
    help: str = ""


class ProviderOption(BaseModel):
    name: str
    help: str = ""
    type: str = "string"
    required: bool = False
    password: bool = False
    """Shown as a password field. Never sent back by the API."""
    sensitive: bool = False
    advanced: bool = False
    default: str = ""
    examples: list[OptionExample] = []
    exclusive: bool = False
    """Only one of `examples` may be chosen."""
    provider: str | None = None
    """For backends with sub-providers (s3): the `provider` values this option applies
    to, comma separated, or starting with `!` for the ones it doesn't."""


class Provider(BaseModel):
    name: str
    description: str
    options: list[ProviderOption]


class RemoteOut(BaseModel):
    name: str
    type: str
    description: str
    """The backend's name, e.g. "Google Drive"."""


class RemoteDetail(RemoteOut):
    values: dict[str, str]
    """Current settings, without secrets."""
    secrets: list[str]
    """Settings that are set but not shown (passwords, tokens). Send them empty to keep."""


class ConfigQuestion(BaseModel):
    state: str
    """Send back with the answer."""
    option: ProviderOption
    error: str = ""
    """Why the previous answer was refused."""


class ConfigStep(BaseModel):
    remote: str
    done: bool
    question: ConfigQuestion | None = None
    """The next question. None with `error` set: the answer was refused, so ask the
    same question again."""
    error: str = ""


# --- Names and paths -------------------------------------------------------------------


def check_remote_name(name: str) -> str:
    if not REMOTE_NAME.fullmatch(name) or name.endswith(" "):
        raise BadPath(
            "Use letters, digits, spaces and _ . + @ - (up to 64), not starting with - or a space"
        )
    return name


def check_path(path: str) -> str:
    """A `/`-separated path inside a remote: no `..`, `.` or empty parts, no backslashes.
    rclone itself would let "name:.." leave an alias's folder."""
    path = path.strip("/")
    if not path:
        return ""
    if "\\" in path or "\0" in path:
        raise BadPath("Paths can't contain backslashes")
    for part in path.split("/"):
        if part in ("", ".", ".."):
            raise BadPath("That path isn't allowed")
    return path


def fs_of(remote: str, path: str = "") -> str:
    """The rclone fs string for a folder on a remote."""
    return f"{check_remote_name(remote)}:{check_path(path)}"


def join(folder: str, name: str) -> str:
    return f"{folder}/{name}" if folder else name


# --- Providers -------------------------------------------------------------------------


def _str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _option(raw: dict[str, Any]) -> ProviderOption:
    return ProviderOption(
        name=raw.get("Name", ""),
        help=raw.get("Help") or "",
        type=raw.get("Type") or "string",
        required=bool(raw.get("Required")),
        password=bool(raw.get("IsPassword")),
        sensitive=bool(raw.get("Sensitive")),
        advanced=bool(raw.get("Advanced")),
        default=raw.get("DefaultStr") if raw.get("DefaultStr") is not None else "",
        examples=[
            OptionExample(value=_str(e.get("Value")), help=e.get("Help") or "")
            for e in raw.get("Examples") or []
        ],
        exclusive=bool(raw.get("Exclusive")),
        provider=raw.get("Provider") or None,
    )


def parse_providers(data: dict[str, Any]) -> list[Provider]:
    providers = []
    for raw in data.get("providers") or []:
        name = raw.get("Name") or raw.get("Prefix")
        if not name or name in HIDDEN_TYPES or raw.get("Hide"):
            continue
        options = [
            _option(o)
            for o in raw.get("Options") or []
            if not (int(o.get("Hide") or 0) & HIDE_CONFIGURATOR)
        ]
        providers.append(
            Provider(name=name, description=raw.get("Description") or name, options=options)
        )
    return sorted(providers, key=lambda p: p.description.lower())


async def providers(rclone: Rclone) -> list[Provider]:
    return parse_providers(await rclone.call("config/providers"))


async def _provider(rclone: Rclone, type_: str) -> Provider | None:
    return next((p for p in await providers(rclone) if p.name == type_), None)


# --- Remotes ---------------------------------------------------------------------------


async def remotes(rclone: Rclone) -> list[RemoteOut]:
    dump = await rclone.call("config/dump")
    names = {p.name: p.description for p in await providers(rclone)}
    out = []
    for name, section in sorted(dump.items(), key=lambda kv: kv[0].lower()):
        type_ = str(section.get("type", "")) if isinstance(section, dict) else ""
        if type_ in HIDDEN_TYPES:
            continue
        out.append(RemoteOut(name=name, type=type_, description=names.get(type_, type_)))
    return out


async def _section(rclone: Rclone, name: str) -> dict[str, Any]:
    check_remote_name(name)
    dump = await rclone.call("config/dump")
    section = dump.get(name)
    if not isinstance(section, dict) or section.get("type") in HIDDEN_TYPES:
        raise NotFound(f"There's no remote called {name}")
    return section


async def exists(rclone: Rclone, name: str) -> bool:
    try:
        await _section(rclone, name)
    except NotFound:
        return False
    return True


async def remote(rclone: Rclone, name: str) -> RemoteDetail:
    section = await _section(rclone, name)
    type_ = str(section.get("type", ""))
    provider = await _provider(rclone, type_)
    shown = (
        {o.name for o in provider.options if not (o.password or o.sensitive)} if provider else set()
    )
    values: dict[str, str] = {}
    secrets: list[str] = []
    for key, value in section.items():
        if key == "type":
            continue
        # Anything not known to be harmless (passwords, OAuth tokens, keys) stays hidden.
        if key in shown:
            values[key] = _str(value)
        else:
            secrets.append(key)
    return RemoteDetail(
        name=name,
        type=type_,
        description=provider.description if provider else type_,
        values=values,
        secrets=sorted(secrets),
    )


def _clean(parameters: dict[str, str]) -> dict[str, str]:
    out = {}
    for key, value in parameters.items():
        if not re.fullmatch(r"[a-z0-9_]{1,64}", key) or key == "type":
            raise BadPath(f"Unknown setting {key!r}")
        out[key] = value
    return out


async def _step(rclone: Rclone, name: str, result: dict[str, Any]) -> ConfigStep:
    """Turn rclone's answer into the next question, answering the automatic ones."""
    for _ in range(10):
        state = result.get("State") or ""
        if not state:
            return ConfigStep(remote=name, done=True)
        option = result.get("Option") or {}
        if not option:
            # rclone refused the answer and wants the same question again.
            message = (result.get("Error") or "rclone refused that answer").strip()
            return ConfigStep(remote=name, done=False, error=message)
        answer = AUTO_ANSWERS.get(option.get("Name", ""))
        if answer is None:
            return ConfigStep(
                remote=name,
                done=False,
                question=ConfigQuestion(
                    state=state, option=_option(option), error=result.get("Error") or ""
                ),
            )
        result = await _continue(rclone, name, state, answer)
    raise RcloneError(502, "rclone kept asking the same question")


async def _continue(rclone: Rclone, name: str, state: str, answer: str) -> dict[str, Any]:
    return await rclone.call(
        "config/update",
        {
            "name": name,
            "parameters": {},
            "opt": {
                "nonInteractive": True,
                "obscure": True,
                "continue": True,
                "state": state,
                "result": answer,
            },
        },
    )


async def create(rclone: Rclone, name: str, type_: str, parameters: dict[str, str]) -> ConfigStep:
    check_remote_name(name)
    if type_ in HIDDEN_TYPES or await _provider(rclone, type_) is None:
        raise BadPath(f"Unknown storage type {type_!r}")
    if name in (await rclone.call("config/dump")):
        raise BadPath(f"There's already a remote called {name}")
    params = {k: v for k, v in _clean(parameters).items() if v != ""}
    result = await rclone.call(
        "config/create",
        {
            "name": name,
            "type": type_,
            "parameters": params,
            "opt": {"nonInteractive": True, "obscure": True},
        },
    )
    return await _step(rclone, name, result)


async def update(rclone: Rclone, name: str, parameters: dict[str, str]) -> ConfigStep:
    detail = await remote(rclone, name)
    params = {
        k: v for k, v in _clean(parameters).items() if not (k in detail.secrets and v == KEEP)
    }
    result = await rclone.call(
        "config/update",
        {"name": name, "parameters": params, "opt": {"nonInteractive": True, "obscure": True}},
    )
    return await _step(rclone, name, result)


async def answer(rclone: Rclone, name: str, state: str, value: str) -> ConfigStep:
    await _section(rclone, name)
    return await _step(rclone, name, await _continue(rclone, name, state, value))


async def delete(rclone: Rclone, name: str) -> None:
    await _section(rclone, name)
    await rclone.call("config/delete", {"name": name})


# --- Browsing --------------------------------------------------------------------------


def _modified(value: Any) -> datetime | None:
    if not isinstance(value, str) or value.startswith("2000-01-01"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def entry_of(item: dict[str, Any]) -> FileEntry:
    is_dir = bool(item.get("IsDir"))
    size = item.get("Size")
    name = str(item.get("Name", ""))
    return FileEntry(
        name=name,
        path=str(item.get("Path", name)),
        kind="dir" if is_dir else "file",
        size=size if not is_dir and isinstance(size, int) and size >= 0 else None,
        modified=_modified(item.get("ModTime")),
        hidden=name.startswith("."),
    )


def listing_of(path: str, data: dict[str, Any]) -> Listing:
    items = [entry_of(i) for i in data.get("list") or []]
    items.sort(key=lambda e: (e.kind != "dir", e.name.lower()))
    return Listing(path=path, entries=items[:MAX_ENTRIES], truncated=len(items) > MAX_ENTRIES)


async def list_dir(rclone: Rclone, name: str, path: str) -> Listing:
    await _section(rclone, name)
    path = check_path(path)
    data = await rclone.call("operations/list", {"fs": fs_of(name), "remote": path})
    return listing_of(path, data)


async def stat(rclone: Rclone, name: str, path: str) -> FileEntry | None:
    """The entry at `path`, or None if there's nothing there."""
    path = check_path(path)
    if not path:
        return FileEntry(name=name, path="", kind="dir")
    data = await rclone.call("operations/stat", {"fs": fs_of(name), "remote": path})
    item = data.get("item")
    return entry_of(item) if isinstance(item, dict) else None
