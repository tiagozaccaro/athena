"""A scripted Probe for detection tests: describe a host, get deterministic answers."""

from dataclasses import dataclass, field
from pathlib import Path

from athena.platform.capabilities import OsName
from athena.platform.probe import Probe, RunResult


@dataclass
class FakeProbe(Probe):
    os: OsName = "linux"
    binaries: dict[str, str] = field(default_factory=dict)
    """name -> path, for `which`."""
    commands: dict[tuple[str, ...], RunResult] = field(default_factory=dict)
    """argv (with argv[0] as given) -> result. Unknown commands fail."""
    engines: dict[str, str] = field(default_factory=dict)
    """Docker API endpoint -> engine version."""
    paths: set[str] = field(default_factory=set)
    root: bool = False
    home_dir: Path = Path("/home/me")
    build: int = 26100

    def which(self, name: str) -> str | None:
        return self.binaries.get(name)

    def run(self, argv: list[str], timeout: float = 5.0) -> RunResult:
        return self.commands.get(tuple(argv), RunResult(-1, "", "not scripted"))

    def exists(self, path: str | Path) -> bool:
        return str(path) in self.paths

    def home(self) -> Path:
        return self.home_dir

    def is_root(self) -> bool:
        return self.root

    def windows_build(self) -> int:
        return self.build

    def docker_version(self, endpoint: str, timeout: float = 2.0) -> str | None:
        return self.engines.get(endpoint)
