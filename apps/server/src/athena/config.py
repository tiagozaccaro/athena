"""Runtime settings, read from ATHENA_* environment variables and CLI flags."""

import sys
from pathlib import Path

from platformdirs import user_data_dir
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PORT = 8420


def default_data_dir() -> Path:
    """Per-OS data directory. Matches what scripts/install.sh and install.ps1 pass."""
    if sys.platform.startswith("linux"):
        return Path("/var/lib/athena")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Athena"
    return Path(user_data_dir("Athena", appauthor=False)) / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATHENA_")

    host: str = "0.0.0.0"
    port: int = DEFAULT_PORT
    data_dir: Path = default_data_dir()
    # Directory with the exported web UI. Defaults to the copy bundled in the wheel.
    web_dir: Path = Path(__file__).parent / "web"
