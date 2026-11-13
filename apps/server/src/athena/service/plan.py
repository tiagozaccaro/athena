"""Steps that make up a service install/uninstall, and their executor."""

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ServiceSpec:
    """What the service runs."""

    python: Path  # interpreter of the installed athena-server (sys.executable)
    data_dir: Path
    port: int


@dataclass(frozen=True)
class WriteFile:
    path: Path
    content: str

    def describe(self) -> str:
        return f"write {self.path}"


@dataclass(frozen=True)
class RemoveFile:
    path: Path

    def describe(self) -> str:
        return f"remove {self.path}"


@dataclass(frozen=True)
class MakeDir:
    path: Path

    def describe(self) -> str:
        return f"mkdir {self.path}"


@dataclass(frozen=True)
class Run:
    argv: list[str]
    # Failures are ignored for steps like "stop the old service", which fail when
    # there is nothing to stop.
    ignore_errors: bool = False

    def describe(self) -> str:
        return " ".join(f'"{a}"' if " " in a else a for a in self.argv)


Step = WriteFile | RemoveFile | MakeDir | Run


@dataclass
class Plan:
    summary: str
    steps: list[Step] = field(default_factory=list)


Runner = Callable[[list[str]], int]


def _default_runner(argv: list[str]) -> int:
    return subprocess.run(argv, check=False).returncode


def execute(
    plan: Plan, *, dry_run: bool = False, runner: Runner = _default_runner, out=sys.stdout
) -> int:
    """Run (or print, with dry_run) each step. Returns a process exit code."""
    print(f"==> {plan.summary}", file=out)
    for step in plan.steps:
        if dry_run:
            print(f"  [dry-run] {step.describe()}", file=out)
            continue
        if isinstance(step, WriteFile):
            step.path.parent.mkdir(parents=True, exist_ok=True)
            step.path.write_text(step.content, encoding="utf-8")
        elif isinstance(step, RemoveFile):
            step.path.unlink(missing_ok=True)
        elif isinstance(step, MakeDir):
            step.path.mkdir(parents=True, exist_ok=True)
        else:
            code = runner(step.argv)
            if code != 0 and not step.ignore_errors:
                print(f"error: command failed ({code}): {step.describe()}", file=sys.stderr)
                return code
    return 0
