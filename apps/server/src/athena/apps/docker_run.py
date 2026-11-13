"""Convert a `docker run …` command into a compose file (docs/mvp-design.md §4.1).

The same idea as composerize: tokenize with shlex, map known flags to compose keys,
and report anything that couldn't be converted so the user can review it.
"""

import re
import shlex
from dataclasses import dataclass, field
from typing import Any

import yaml

# Flags that take a value: flag -> (compose key, kind). Kinds: "str", "list", "map".
_VALUE_FLAGS: dict[str, tuple[str, str]] = {
    "--name": ("container_name", "str"),
    "-p": ("ports", "list"),
    "--publish": ("ports", "list"),
    "-v": ("volumes", "list"),
    "--volume": ("volumes", "list"),
    "-e": ("environment", "list"),
    "--env": ("environment", "list"),
    "--env-file": ("env_file", "list"),
    "--restart": ("restart", "str"),
    "--network": ("networks", "network"),
    "--net": ("networks", "network"),
    "-h": ("hostname", "str"),
    "--hostname": ("hostname", "str"),
    "-w": ("working_dir", "str"),
    "--workdir": ("working_dir", "str"),
    "-u": ("user", "str"),
    "--user": ("user", "str"),
    "--entrypoint": ("entrypoint", "str"),
    "--cap-add": ("cap_add", "list"),
    "--cap-drop": ("cap_drop", "list"),
    "--device": ("devices", "list"),
    "-l": ("labels", "list"),
    "--label": ("labels", "list"),
    "-m": ("mem_limit", "str"),
    "--memory": ("mem_limit", "str"),
    "--cpus": ("cpus", "str"),
    "--add-host": ("extra_hosts", "list"),
    "--dns": ("dns", "list"),
    "--pull": ("pull_policy", "str"),
    "--platform": ("platform", "str"),
    "--shm-size": ("shm_size", "str"),
    "--tmpfs": ("tmpfs", "list"),
    "--expose": ("expose", "list"),
    "--security-opt": ("security_opt", "list"),
    "--sysctl": ("sysctls", "list"),
    "--ulimit": ("ulimits", "ulimit"),
    "--log-driver": ("logging.driver", "logging"),
    "--log-opt": ("logging.options", "logging"),
    "--stop-signal": ("stop_signal", "str"),
    "--stop-timeout": ("stop_grace_period", "seconds"),
    "--pid": ("pid", "str"),
    "--ipc": ("ipc", "str"),
    "--group-add": ("group_add", "list"),
}

# Boolean flags: flag -> (compose key, value), or None to drop silently.
_BOOL_FLAGS: dict[str, tuple[str, Any] | None] = {
    "-d": None,
    "--detach": None,
    "--privileged": ("privileged", True),
    "--init": ("init", True),
    "--read-only": ("read_only", True),
    "-i": ("stdin_open", True),
    "--interactive": ("stdin_open", True),
    "-t": ("tty", True),
    "--tty": ("tty", True),
}

_NAME_RE = re.compile(r"[^a-z0-9_-]+")


@dataclass
class Conversion:
    compose: str
    service: str
    warnings: list[str] = field(default_factory=list)


class ConversionError(ValueError):
    pass


def _strip_prefix(tokens: list[str]) -> list[str]:
    """Drop `sudo`, `docker`/`podman` and `run` (or `container run`)."""
    i = 0
    if i < len(tokens) and tokens[i] == "sudo":
        i += 1
    if i < len(tokens) and tokens[i] in ("docker", "podman"):
        i += 1
    if i < len(tokens) and tokens[i] == "container":
        i += 1
    if i < len(tokens) and tokens[i] == "run":
        i += 1
    if i == 0:
        raise ConversionError("Paste a full command, e.g. `docker run -d -p 8080:80 nginx`")
    return tokens[i:]


def _split_combined(token: str) -> list[str]:
    """`-it` -> `-i -t`; `-dit` -> `-d -i -t`. Only for single-letter boolean flags."""
    if re.fullmatch(r"-[a-zA-Z]{2,}", token) and all(f"-{c}" in _BOOL_FLAGS for c in token[1:]):
        return [f"-{c}" for c in token[1:]]
    return [token]


def service_name(image: str, container_name: str | None) -> str:
    base = container_name or image.split("/")[-1].split(":")[0].split("@")[0]
    name = _NAME_RE.sub("-", base.lower()).strip("-_")
    return name or "app"


def convert(command: str) -> Conversion:
    try:
        raw = shlex.split(command.replace("\\\n", " "), posix=True)
    except ValueError as exc:
        raise ConversionError(f"Couldn't parse the command: {exc}") from exc
    tokens: list[str] = []
    for token in _strip_prefix(raw):
        tokens.extend(_split_combined(token))

    svc: dict[str, Any] = {}
    warnings: list[str] = []
    image: str | None = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token.startswith("-") or token == "-":
            image = token
            command_args = tokens[i + 1 :]
            if command_args:
                svc["command"] = command_args
            break

        flag, eq, inline = token.partition("=")
        if flag in _BOOL_FLAGS:
            mapped = _BOOL_FLAGS[flag]
            if mapped:
                svc[mapped[0]] = mapped[1]
            i += 1
            continue
        if flag == "--rm":
            warnings.append("--rm has no compose equivalent and was ignored")
            i += 1
            continue
        if flag not in _VALUE_FLAGS:
            # Unknown flag: it takes a value only if the next token isn't a flag and
            # something still follows it (the image must come after any value).
            takes_value = not eq and i + 2 < len(tokens) and not tokens[i + 1].startswith("-")
            warnings.append(f"{flag} isn't supported and was ignored")
            i += 1 if eq or not takes_value else 2
            continue

        if eq:
            value = inline
            i += 1
        elif i + 1 < len(tokens):
            value = tokens[i + 1]
            i += 2
        else:
            raise ConversionError(f"{flag} needs a value")

        key, kind = _VALUE_FLAGS[flag]
        if kind == "str":
            svc[key] = value
        elif kind == "list":
            svc.setdefault(key, []).append(value)
        elif kind == "seconds":
            svc[key] = f"{value}s"
        elif kind == "network":
            if value in ("host", "none", "bridge") or value.startswith("container:"):
                svc["network_mode"] = value
            else:
                svc.setdefault("networks", []).append(value)
        elif kind == "ulimit":
            name, _, limits = value.partition("=")
            soft, _, hard = limits.partition(":")
            svc.setdefault("ulimits", {})[name] = (
                {"soft": int(soft), "hard": int(hard)} if hard else int(soft)
            )
        elif kind == "logging":
            logging = svc.setdefault("logging", {})
            if key.endswith("driver"):
                logging["driver"] = value
            else:
                opt, _, val = value.partition("=")
                logging.setdefault("options", {})[opt] = val

    if not image:
        raise ConversionError("No image found in the command")

    name = service_name(image, svc.get("container_name"))
    service: dict[str, Any] = {"image": image, **svc}
    doc: dict[str, Any] = {"services": {name: service}}
    networks = [n for n in service.get("networks", [])]
    if networks:
        doc["networks"] = {n: {"external": True} for n in networks}
        warnings.append(
            "Networks were marked external: create them first, or remove `external: true`"
        )
    named_volumes = sorted(
        {
            v.split(":")[0]
            for v in service.get("volumes", [])
            if ":" in v
            and not v.split(":")[0].startswith(("/", ".", "~", "$"))
            and not re.match(r"^[A-Za-z]:[\\/]", v)
        }
    )
    if named_volumes:
        doc["volumes"] = {v: {} for v in named_volumes}

    text = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return Conversion(compose=text, service=name, warnings=warnings)
