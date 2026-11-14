"""Package managers by capability id (`packages.<id>`), see docs/mvp-design.md §3."""

from athena.packages.apps import Brew, Flatpak, Snap
from athena.packages.base import PackageManager
from athena.packages.linux import Apk, Apt, Dnf, Pacman, Zypper
from athena.packages.windows import Choco, Scoop, Winget

MANAGERS: dict[str, type[PackageManager]] = {
    m.id: m for m in (Apt, Dnf, Pacman, Zypper, Apk, Flatpak, Snap, Brew, Winget, Scoop, Choco)
}
