"""On-disk layout and checks for apps.

<data-dir>/apps/<name>/compose.yaml       the app definition
<data-dir>/apps/<name>/compose.prev.yaml  the previous version, kept on every edit
<data-dir>/apps/<name>/data/              exposed to compose as ${ATHENA_APP_DATA}
"""

import os
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from athena.containers.runtime import Runtime

# Compose project names: lowercase letters, digits, dash and underscore; start alnum.
APP_NAME = r"^[a-z0-9][a-z0-9_-]{0,62}$"
_NAME_RE = re.compile(APP_NAME)
MAX_COMPOSE_BYTES = 256 * 1024


class InvalidComposeError(ValueError):
    pass


def check_name(name: str) -> str:
    if not _NAME_RE.match(name):
        raise ValueError(
            "Use 1 to 63 lowercase letters, digits, dashes or underscores, starting with a "
            "letter or digit"
        )
    return name


def parse_compose(text: str) -> dict[str, Any]:
    """Structural checks before handing the file to `docker compose config`."""
    if len(text.encode()) > MAX_COMPOSE_BYTES:
        raise InvalidComposeError("The compose file is larger than 256 KB")
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        raise InvalidComposeError(f"Invalid YAML{where}: {getattr(exc, 'problem', exc)}") from exc
    if not isinstance(doc, dict):
        raise InvalidComposeError("The compose file must be a YAML mapping")
    services = doc.get("services")
    if not isinstance(services, dict) or not services:
        raise InvalidComposeError("The compose file needs at least one service under `services`")
    for name, service in services.items():
        if not isinstance(service, dict) or not (service.get("image") or service.get("build")):
            raise InvalidComposeError(f"Service `{name}` needs an `image`")
    return doc


class AppStore:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "apps"

    def dir(self, name: str) -> Path:
        return self.root / check_name(name)

    def compose_path(self, name: str) -> Path:
        return self.dir(name) / "compose.yaml"

    def read(self, name: str) -> str:
        path = self.compose_path(name)
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def write(self, name: str, text: str) -> Path:
        path = self.compose_path(name)
        (path.parent / "data").mkdir(parents=True, exist_ok=True)
        if path.is_file():
            shutil.copyfile(path, path.with_name("compose.prev.yaml"))
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        return path

    def remove(self, name: str, delete_data: bool) -> None:
        directory = self.dir(name)
        if delete_data:
            shutil.rmtree(directory, ignore_errors=True)
            return
        for file in ("compose.yaml", "compose.prev.yaml"):
            (directory / file).unlink(missing_ok=True)
        # Keep data/ and anything else the user put there; only tidy up empty dirs.
        for path in (directory / "data", directory):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()

    def env(self, name: str) -> dict[str, str]:
        return {**os.environ, "ATHENA_APP_DATA": str(self.dir(name) / "data")}


def compose(runtime: Runtime, name: str, path: Path, *args: str) -> list[str]:
    return runtime.command("compose", "--project-name", name, "--file", str(path), *args)
