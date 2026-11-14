"""System package managers on Linux: apt, dnf, zypper, pacman and apk.

They install system-wide, so detection reports `needs_privilege` unless Athena runs as
root (the default systemd service does). Output formats are pinned by fixtures in
tests/fixtures/packages/ (see its README for where each was captured).
"""

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import ClassVar

from athena.packages.base import (
    SEARCH_LIMIT,
    InstalledPackage,
    PackageManager,
    PackageRef,
    UpgradablePackage,
    nonblank,
)

# apt-cache and pacman take the query as a regular expression; users type plain text.
_REGEX_SPECIAL = re.compile(r"([.+*?()\[\]{}|^$\\])")


def literal_regex(query: str) -> str:
    return _REGEX_SPECIAL.sub(r"\\\1", query)


def _mark_installed(results: list[PackageRef], installed: list[InstalledPackage]) -> None:
    names = {p.name for p in installed}
    for r in results:
        r.installed = r.installed or r.name in names


# ------------------------------------------------------------------ rpm (dnf, zypper)

RPM_QF = "%{NAME}\t%{VERSION}-%{RELEASE}\t%{SUMMARY}\n"


def parse_rpm_installed(text: str) -> list[InstalledPackage]:
    out = []
    for line in nonblank(text):
        name, _, rest = line.partition("\t")
        version, _, summary = rest.partition("\t")
        if name == "gpg-pubkey":  # imported signing keys, not packages
            continue
        out.append(
            InstalledPackage(name=name, version=version or None, description=summary or None)
        )
    return out


# ------------------------------------------------------------------ apt


def parse_apt_search(text: str) -> list[PackageRef]:
    out = []
    for line in nonblank(text):
        name, sep, desc = line.partition(" - ")
        if sep:
            out.append(PackageRef(name=name.strip(), description=desc.strip()))
    return out


def parse_dpkg_installed(text: str) -> list[InstalledPackage]:
    out = []
    for line in nonblank(text):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        status, name, version = parts[0].strip(), parts[1], parts[2]
        # "ii" installed, "hi" held; "rc" means removed with config files left.
        if len(status) < 2 or status[1] != "i":
            continue
        desc = parts[3] if len(parts) > 3 else None
        out.append(InstalledPackage(name=name, version=version, description=desc or None))
    return out


_APT_INST = re.compile(r"^Inst (\S+) \[([^\]]+)\] \((\S+)")


def parse_apt_upgrade_simulation(text: str) -> list[UpgradablePackage]:
    """`apt-get -s upgrade`: "Inst name [installed] (candidate suite [arch])".

    Lines without "[installed]" are new dependencies, not upgrades.
    """
    out = []
    for line in text.splitlines():
        if m := _APT_INST.match(line):
            out.append(UpgradablePackage(name=m[1], version=m[2], latest=m[3]))
    return out


class Apt(PackageManager):
    id = "apt"
    label = "APT"
    can_refresh = True
    env: ClassVar[dict[str, str]] = {
        "DEBIAN_FRONTEND": "noninteractive",
        "APT_LISTCHANGES_FRONTEND": "none",
    }
    # Keep existing config files instead of stopping to ask.
    _DPKG_OPTS = (
        "-o",
        "Dpkg::Options::=--force-confdef",
        "-o",
        "Dpkg::Options::=--force-confold",
    )

    async def search(self, query: str) -> list[PackageRef]:
        out = await self.run(["apt-cache", "search", literal_regex(query)], "apt-cache search")
        results = parse_apt_search(out)[:SEARCH_LIMIT]
        _mark_installed(results, await self.installed())
        return results

    async def installed(self) -> list[InstalledPackage]:
        fmt = "${db:Status-Abbrev}\t${Package}\t${Version}\t${binary:Summary}\n"
        return parse_dpkg_installed(await self.run(["dpkg-query", "-W", "-f", fmt], "dpkg-query"))

    async def upgradable(self) -> list[UpgradablePackage]:
        out = await self.run(
            ["apt-get", "-s", "-o", "Debug::NoLocking=1", "upgrade"], "apt-get -s upgrade"
        )
        return parse_apt_upgrade_simulation(out)

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return ["apt-get", "install", "-y", *self._DPKG_OPTS, name]

    def uninstall_argv(self, name: str) -> list[str]:
        return ["apt-get", "remove", "-y", name]

    def upgrade_argv(self, name: str | None) -> list[str]:
        if name:
            return ["apt-get", "install", "--only-upgrade", "-y", *self._DPKG_OPTS, name]
        return ["apt-get", "upgrade", "-y", *self._DPKG_OPTS]

    def refresh_argv(self) -> list[str]:
        return ["apt-get", "update"]


# ------------------------------------------------------------------ dnf


def parse_tab_rows(text: str, columns: int) -> list[list[str]]:
    """Tab-separated rows from our own --qf formats (dnf4 adds a blank line after each)."""
    rows = []
    for line in nonblank(text):
        cells = line.split("\t")
        if len(cells) >= columns - 1:
            rows.append((cells + [""] * columns)[:columns])
    return rows


def parse_dnf_search(text: str) -> list[PackageRef]:
    seen: dict[str, PackageRef] = {}
    for name, evr, summary in parse_tab_rows(text, 3):
        seen.setdefault(
            name, PackageRef(name=name, version=evr or None, description=summary or None)
        )
    return list(seen.values())


def parse_dnf_upgrades(text: str) -> list[UpgradablePackage]:
    seen: dict[str, UpgradablePackage] = {}
    for name, evr in parse_tab_rows(text, 2):
        seen.setdefault(name, UpgradablePackage(name=name, latest=evr or None))
    return list(seen.values())


class Dnf(PackageManager):
    """dnf4 and dnf5. repoquery's --qf works the same in both when given real tabs and
    newlines; `dnf search`'s human output differs between them, so it isn't used."""

    id = "dnf"
    label = "DNF"
    can_refresh = True

    async def search(self, query: str) -> list[PackageRef]:
        qf = "%{name}\t%{evr}\t%{summary}\n"
        out = await self.run(
            ["dnf", "-q", "repoquery", "--latest-limit=1", "--qf", qf, f"*{query}*"],
            "dnf repoquery",
        )
        results = parse_dnf_search(out)[:SEARCH_LIMIT]
        _mark_installed(results, await self.installed())
        return results

    async def installed(self) -> list[InstalledPackage]:
        return parse_rpm_installed(await self.run(["rpm", "-qa", "--qf", RPM_QF], "rpm -qa"))

    async def upgradable(self) -> list[UpgradablePackage]:
        out, installed = await asyncio.gather(
            self.run(
                [
                    "dnf",
                    "-q",
                    "repoquery",
                    "--upgrades",
                    "--latest-limit=1",
                    "--qf",
                    "%{name}\t%{evr}\n",
                ],
                "dnf repoquery --upgrades",
            ),
            self.installed(),
        )
        current = {p.name: p.version for p in installed}
        ups = parse_dnf_upgrades(out)
        for u in ups:
            u.version = current.get(u.name)
        return ups

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return ["dnf", "install", "-y", name]

    def uninstall_argv(self, name: str) -> list[str]:
        return ["dnf", "remove", "-y", name]

    def upgrade_argv(self, name: str | None) -> list[str]:
        return ["dnf", "upgrade", "-y", *([name] if name else [])]

    def refresh_argv(self) -> list[str]:
        return ["dnf", "makecache"]


# ------------------------------------------------------------------ zypper


def _xml_root(text: str) -> ET.Element:
    start = text.find("<?xml")
    return ET.fromstring(text[start:] if start >= 0 else text)


def parse_zypper_search(text: str) -> list[PackageRef]:
    out = []
    for s in _xml_root(text).iter("solvable"):
        if s.get("kind", "package") != "package":
            continue
        out.append(
            PackageRef(
                name=s.get("name", ""),
                description=s.get("summary") or None,
                installed=s.get("status") == "installed",
            )
        )
    return [p for p in out if p.name]


def parse_zypper_updates(text: str) -> list[UpgradablePackage]:
    out = []
    for u in _xml_root(text).iter("update"):
        if u.get("kind", "package") != "package" or not u.get("name"):
            continue
        out.append(
            UpgradablePackage(
                name=u.get("name", ""),
                version=u.get("edition-old") or None,
                latest=u.get("edition") or None,
            )
        )
    return out


class Zypper(PackageManager):
    id = "zypper"
    label = "zypper"
    can_refresh = True
    _Z = ("zypper", "--non-interactive")

    async def search(self, query: str) -> list[PackageRef]:
        # Exit code 104 means "no matches".
        out = await self.run([*self._Z, "--xmlout", "search", query], "zypper search", (0, 104))
        return parse_zypper_search(out)[:SEARCH_LIMIT]

    async def installed(self) -> list[InstalledPackage]:
        return parse_rpm_installed(await self.run(["rpm", "-qa", "--qf", RPM_QF], "rpm -qa"))

    async def upgradable(self) -> list[UpgradablePackage]:
        out = await self.run([*self._Z, "--xmlout", "list-updates"], "zypper list-updates")
        return parse_zypper_updates(out)

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return [*self._Z, "install", "--auto-agree-with-licenses", name]

    def uninstall_argv(self, name: str) -> list[str]:
        return [*self._Z, "remove", name]

    def upgrade_argv(self, name: str | None) -> list[str]:
        return [*self._Z, "update", "--auto-agree-with-licenses", *([name] if name else [])]

    def refresh_argv(self) -> list[str]:
        return [*self._Z, "refresh"]


# ------------------------------------------------------------------ pacman

_PACMAN_HEAD = re.compile(r"^(\S+)/(\S+) (\S+)(.*)$")


def parse_pacman_search(text: str) -> list[PackageRef]:
    """`pacman -Ss`: "repo/name version [(groups)] [[installed[: old]]]" then an indented
    description line."""
    out: list[PackageRef] = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")):
            if out and out[-1].description is None:
                out[-1].description = line.strip()
            continue
        if m := _PACMAN_HEAD.match(line):
            out.append(
                PackageRef(name=m[2], version=m[3], source=m[1], installed="[installed" in m[4])
            )
    return out


def parse_pacman_installed(text: str) -> list[InstalledPackage]:
    out = []
    for line in nonblank(text):
        if line.startswith(("warning:", "error:")):
            continue
        name, _, version = line.partition(" ")
        out.append(InstalledPackage(name=name, version=version or None))
    return out


def parse_pacman_upgrades(text: str) -> list[UpgradablePackage]:
    out = []
    for line in nonblank(text):
        m = re.match(r"^(\S+) (\S+) -> (\S+)", line)
        if m:
            out.append(UpgradablePackage(name=m[1], version=m[2], latest=m[3]))
    return out


class Pacman(PackageManager):
    id = "pacman"
    label = "pacman"
    can_upgrade_one = False
    note = (
        "Arch doesn't support partial upgrades, so installing a package also upgrades "
        "the rest of the system first."
    )

    async def search(self, query: str) -> list[PackageRef]:
        # Exit code 1 means "no matches".
        out = await self.run(["pacman", "-Ss", literal_regex(query)], "pacman -Ss", (0, 1))
        return parse_pacman_search(out)[:SEARCH_LIMIT]

    async def installed(self) -> list[InstalledPackage]:
        return parse_pacman_installed(await self.run(["pacman", "-Q"], "pacman -Q"))

    async def upgradable(self) -> list[UpgradablePackage]:
        # Uses the last synced database (installs sync it); exit code 1 means none.
        return parse_pacman_upgrades(await self.run(["pacman", "-Qu"], "pacman -Qu", (0, 1)))

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return ["pacman", "-Syu", "--noconfirm", "--needed", name]

    def uninstall_argv(self, name: str) -> list[str]:
        return ["pacman", "-R", "--noconfirm", name]

    def upgrade_argv(self, name: str | None) -> list[str]:
        return ["pacman", "-Syu", "--noconfirm"]


# ------------------------------------------------------------------ apk

_APK_NAME_VERSION = re.compile(r"^(.+?)-(\d[^-\s]*-r\d+)$")


def split_apk(token: str) -> tuple[str, str] | None:
    """ "jq-1.8.2-r0" → ("jq", "1.8.2-r0"); None for virtual packages without a release."""
    m = _APK_NAME_VERSION.match(token)
    return (m[1], m[2]) if m else None


def parse_apk_search(text: str) -> list[PackageRef]:
    out = []
    for line in nonblank(text):
        token, _, desc = line.partition(" - ")
        if split := split_apk(token.strip()):
            out.append(
                PackageRef(name=split[0], version=split[1], description=desc.strip() or None)
            )
    return out


def parse_apk_installed(text: str) -> list[InstalledPackage]:
    out = []
    for line in nonblank(text):
        if line.startswith("."):  # virtual dependency groups (.postgresql-rundeps-…)
            continue
        if split := split_apk(line.split(" ", 1)[0]):
            out.append(InstalledPackage(name=split[0], version=split[1]))
    return out


def parse_apk_upgradable(text: str) -> list[UpgradablePackage]:
    out = []
    for line in nonblank(text):
        new = split_apk(line.split(" ", 1)[0])
        m = re.search(r"\[upgradable from: (\S+)\]", line)
        old = split_apk(m[1]) if m else None
        if new:
            out.append(
                UpgradablePackage(name=new[0], version=old[1] if old else None, latest=new[1])
            )
    return out


class Apk(PackageManager):
    id = "apk"
    label = "apk"
    can_refresh = True

    async def search(self, query: str) -> list[PackageRef]:
        results = parse_apk_search(await self.run(["apk", "search", "-v", query], "apk search"))
        results = results[:SEARCH_LIMIT]
        _mark_installed(results, await self.installed())
        return results

    async def installed(self) -> list[InstalledPackage]:
        return parse_apk_installed(await self.run(["apk", "list", "--installed"], "apk list"))

    async def upgradable(self) -> list[UpgradablePackage]:
        return parse_apk_upgradable(await self.run(["apk", "list", "--upgradable"], "apk list"))

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return ["apk", "add", name]

    def uninstall_argv(self, name: str) -> list[str]:
        return ["apk", "del", name]

    def upgrade_argv(self, name: str | None) -> list[str]:
        return ["apk", "upgrade", *([name] if name else [])]

    def refresh_argv(self) -> list[str]:
        return ["apk", "update"]
