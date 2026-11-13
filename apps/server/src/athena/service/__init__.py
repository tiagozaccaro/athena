"""Registers Athena to start automatically, per OS.

- Linux: a systemd system unit, run as root (see docs/mvp-design.md §3 Privilege model).
- macOS: a launchd agent for the logged-in user.
- Windows: a Scheduled Task that starts at logon for the current user.

Each backend turns a request into a plan of steps, so the same code drives real runs,
--dry-run output and tests.
"""

from athena.service.plan import Plan, ServiceSpec, execute
from athena.service.platforms import build_install, build_status, build_uninstall

__all__ = ["Plan", "ServiceSpec", "build_install", "build_status", "build_uninstall", "execute"]
