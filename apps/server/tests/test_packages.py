"""Package manager parsers against recorded output (tests/fixtures/packages/README.md),
plus the read flows with a fake runner. Runs on every OS."""

import asyncio
from pathlib import Path

import pytest

from athena.packages import MANAGERS
from athena.packages import apps as pk_apps
from athena.packages import linux as pk_linux
from athena.packages import windows as pk_win
from athena.packages.base import (
    PACKAGE_NAME,
    SEARCH_QUERY,
    CmdResult,
    PackageError,
    column_table,
)

FIX = Path(__file__).parent / "fixtures" / "packages"


def fx(path: str) -> str:
    return (FIX / path).read_text(encoding="utf-8")


# ---------------------------------------------------------------- apt


def test_apt_search() -> None:
    results = pk_linux.parse_apt_search(fx("apt/search.txt"))
    by = {r.name: r for r in results}
    assert by["gojq"].description == "pure Go implementation of jq (program)"
    assert by["fq"].description == "jq for binary formats (program)"
    assert all(r.version is None for r in results)


def test_dpkg_installed_skips_removed_and_trims_status() -> None:
    pkgs = pk_linux.parse_dpkg_installed(fx("apt/installed.txt"))
    by = {p.name: p for p in pkgs}
    assert by["apt"].version == "3.0.3"
    assert by["bsdutils"].version == "1:2.41.5-0+deb13u1"  # epoch kept
    assert by["apache2"].description == "Apache HTTP Server"
    removed = "rc \tgone\t1.0\tremoved package\n"
    assert pk_linux.parse_dpkg_installed(removed) == []
    held = "hi \tkept\t2.0\theld package\n"
    assert [p.name for p in pk_linux.parse_dpkg_installed(held)] == ["kept"]


def test_apt_upgrade_simulation() -> None:
    ups = pk_linux.parse_apt_upgrade_simulation(fx("apt/upgrade-simulate.txt"))
    by = {u.name: u for u in ups}
    assert len(ups) == 10
    assert (by["apt"].version, by["apt"].latest) == ("3.0.3", "3.0.4")
    assert by["zlib1g"].latest == "1:1.3.dfsg+really1.3.1-1+deb13u1"
    assert "Conf" not in by


def test_apt_commands() -> None:
    apt = pk_linux.Apt()
    assert apt.install_argv("jq")[:3] == ["apt-get", "install", "-y"]
    assert apt.install_argv("jq")[-1] == "jq"
    assert apt.upgrade_argv(None)[:3] == ["apt-get", "upgrade", "-y"]
    assert apt.upgrade_argv("jq")[:3] == ["apt-get", "install", "--only-upgrade"]
    assert apt.refresh_argv() == ["apt-get", "update"]
    assert apt.env["DEBIAN_FRONTEND"] == "noninteractive"


def test_apt_search_escapes_regex() -> None:
    assert pk_linux.literal_regex("g++") == r"g\+\+"
    assert pk_linux.literal_regex("libc6.1") == r"libc6\.1"


# ---------------------------------------------------------------- rpm / dnf / zypper


def test_rpm_installed() -> None:
    pkgs = pk_linux.parse_rpm_installed(fx("rpm-installed.txt"))
    by = {p.name: p for p in pkgs}
    assert by["bash"].version == "5.1.8-9.el9"
    assert by["bash"].description == "The GNU Bourne Again shell"
    assert "gpg-pubkey" not in by


@pytest.mark.parametrize("variant", ["dnf", "dnf4"])
def test_dnf_search_both_generations(variant: str) -> None:
    results = pk_linux.parse_dnf_search(fx(f"{variant}/search.txt"))
    jq = next(r for r in results if r.name == "jq")
    assert jq.description == "Command-line JSON processor"
    assert jq.version and jq.version.startswith("1.")
    assert len({r.name for r in results}) == len(results)


@pytest.mark.parametrize("variant", ["dnf", "dnf4"])
def test_dnf_upgrades_both_generations(variant: str) -> None:
    ups = pk_linux.parse_dnf_upgrades(fx(f"{variant}/upgradable.txt"))
    assert ups[0].name == "bash" and ups[0].latest


def test_dnf_upgradable_fills_installed_version() -> None:
    async def run(argv, env):
        if argv[0] == "rpm":
            return CmdResult(0, "bash\t5.3.14-1.fc45\tshell\n", "")
        return CmdResult(0, "bash\t5.3.15-2.fc45\n", "")

    ups = asyncio.run(pk_linux.Dnf(run).upgradable())
    assert (ups[0].version, ups[0].latest) == ("5.3.14-1.fc45", "5.3.15-2.fc45")


def test_dnf_passes_real_tabs_and_newlines() -> None:
    seen = []

    async def run(argv, env):
        seen.append(argv)
        return CmdResult(0, "", "")

    asyncio.run(pk_linux.Dnf(run).search("jq"))
    qf = seen[0][seen[0].index("--qf") + 1]
    assert "\t" in qf and qf.endswith("\n") and "\\t" not in qf
    assert seen[0][-1] == "*jq*"


def test_zypper_search_and_updates() -> None:
    results = pk_linux.parse_zypper_search(fx("zypper/search.xml"))
    by = {r.name: r for r in results}
    assert by["jq"].description == "A lightweight and flexible command-line JSON processor"
    assert by["jq"].installed is False
    ups = pk_linux.parse_zypper_updates(fx("zypper/list-updates.xml"))
    assert [(u.name, u.version, u.latest) for u in ups] == [
        ("openSUSE-build-key", "1.0-68.1", "1.0-69.1")
    ]


def test_zypper_no_matches_is_not_an_error() -> None:
    async def run(argv, env):
        return CmdResult(104, "<?xml version='1.0'?><stream></stream>", "")

    assert asyncio.run(pk_linux.Zypper(run).search("zzz")) == []


# ---------------------------------------------------------------- pacman


def test_pacman_search() -> None:
    results = pk_linux.parse_pacman_search(fx("pacman/search.txt"))
    by = {r.name: r for r in results}
    assert (by["jq"].version, by["jq"].source) == ("1.8.2-1", "extra")
    assert by["jq"].description == "Command-line JSON processor"
    installed = pk_linux.parse_pacman_search(fx("pacman/search-installed.txt"))
    assert installed[0].name == "bash" and installed[0].installed
    grouped = "core/gcc 15.2.1-1 (base-devel) [installed: 15.1.0-1]\n    The GNU Compiler\n"
    gcc = pk_linux.parse_pacman_search(grouped)[0]
    assert (gcc.name, gcc.version, gcc.installed) == ("gcc", "15.2.1-1", True)


def test_pacman_installed_and_upgrades() -> None:
    pkgs = pk_linux.parse_pacman_installed(fx("pacman/installed.txt"))
    assert {p.name: p.version for p in pkgs}["bash"] == "5.3.20-1"
    ups = pk_linux.parse_pacman_upgrades(fx("pacman/upgradable.txt"))
    assert (ups[0].name, ups[0].version, ups[0].latest) == ("bash", "5.3.19-1", "5.3.20-1")


def test_pacman_only_upgrades_everything() -> None:
    pacman = pk_linux.Pacman()
    assert pacman.can_upgrade_one is False
    assert pacman.install_argv("jq") == ["pacman", "-Syu", "--noconfirm", "--needed", "jq"]
    assert pacman.upgrade_argv(None) == ["pacman", "-Syu", "--noconfirm"]


# ---------------------------------------------------------------- apk


def test_apk_parsers() -> None:
    results = pk_linux.parse_apk_search(fx("apk/search.txt"))
    by = {r.name: r for r in results}
    assert by["jq"].version == "1.8.2-r0"
    assert by["perl-jq-lite"].version == "2.45-r0"
    assert by["acf-jquery"].description == "jquery libraries for ACF"
    pkgs = pk_linux.parse_apk_installed(fx("apk/installed.txt"))
    names = {p.name: p.version for p in pkgs}
    assert names["busybox-binsh"] == "1.37.0-r31"
    assert not any(n.startswith(".") for n in names)  # virtual packages skipped
    ups = {u.name: u for u in pk_linux.parse_apk_upgradable(fx("apk/upgradable.txt"))}
    assert (ups["zlib"].version, ups["zlib"].latest) == ("1.3.2-r1", "1.4-r0")


# ---------------------------------------------------------------- brew


def test_brew_search_names() -> None:
    names = pk_apps.parse_brew_search(fx("brew/search.txt"))
    assert names[:3] == ["gojq", "ijq", "jq"]
    assert "jquake" in names and "" not in names


def test_brew_info_and_installed() -> None:
    info = {r.name: r for r in pk_apps.parse_brew_info(fx("brew/info-search.json"))}
    assert info["gojq"].description == "Pure Go implementation of jq"
    assert info["gojq"].source == "formula" and info["gojq"].version
    assert info["jquake"].source == "cask" and info["jquake"].title == "JQuake"
    inst = {p.name: p for p in pk_apps.parse_brew_installed(fx("brew/info-installed.json"))}
    assert inst["docker"].version == "29.9.2"
    assert inst["jquake"].version == "1.8.4" and inst["jquake"].source == "cask"


def test_brew_outdated() -> None:
    ups = {u.name: u for u in pk_apps.parse_brew_outdated(fx("brew/outdated.json"))}
    assert (ups["docker"].version, ups["docker"].latest) == ("29.9.2", "29.9.3")
    assert ups["jquake"].latest == "1.8.5"


def test_brew_search_enriches_top_results() -> None:
    calls = []

    async def run(argv, env):
        calls.append(argv)
        if argv[1] == "search":
            return CmdResult(0, fx("brew/search.txt"), "")
        return CmdResult(0, fx("brew/info-search.json"), "")

    results = asyncio.run(pk_apps.Brew(run).search("jq"))
    by = {r.name: r for r in results}
    assert by["gojq"].description and by["ijq"].description is None
    assert calls[1][:3] == ["brew", "info", "--json=v2"]
    assert pk_apps.Brew().install_argv("jquake", "cask") == ["brew", "install", "--cask", "jquake"]


def test_brew_no_results() -> None:
    async def run(argv, env):
        return CmdResult(1, "", "Error: No formulae or casks found for zzz.")

    assert asyncio.run(pk_apps.Brew(run).search("zzz")) == []


# ---------------------------------------------------------------- flatpak / snap


def test_flatpak_parsers() -> None:
    results = pk_apps.parse_flatpak_search(fx("flatpak/search.txt"))
    calc = next(r for r in results if r.name == "org.gnome.Calculator")
    assert (calc.title, calc.version, calc.source) == ("Calculator", "51.1", "flathub")
    assert pk_apps.parse_flatpak_search(fx("flatpak/search-none.txt")) == []
    inst = pk_apps.parse_flatpak_installed(fx("flatpak/installed.txt"))
    assert inst[1].name == "org.kde.kalk" and inst[1].version == "26.08.2"
    assert pk_apps.parse_flatpak_installed(fx("flatpak/installed-empty.txt")) == []
    ups = pk_apps.parse_flatpak_updates(fx("flatpak/updates.txt"))
    assert (ups[0].name, ups[0].latest) == ("org.kde.kalk", "26.08.3")
    assert pk_apps.Flatpak().install_argv("org.kde.kalk", None)[-2:] == ["flathub", "org.kde.kalk"]


def test_snap_parsers() -> None:
    found = {r.name: r for r in pk_apps.parse_snap_find(fx("snap/find.txt"))}
    assert found["jq"].version == "1.5+dfsg-1"
    assert found["jq"].source == "mvo"  # verified mark stripped
    assert found["yq"].description == "A lightweight and portable command-line YAML processor"
    inst = {p.name: p for p in pk_apps.parse_snap_list(fx("snap/list.txt"))}
    assert inst["lxd"].version == "5.21.2-2f4ba6b" and inst["core22"].source == "canonical"
    ups = pk_apps.parse_snap_refresh_list(fx("snap/refresh-list.txt"))
    assert (ups[0].name, ups[0].latest) == ("lxd", "5.21.3-c5ae129")


# ---------------------------------------------------------------- windows


def test_winget_search_strips_progress_and_reads_columns() -> None:
    results = {r.name: r for r in pk_win.parse_winget_search(fx("winget/search.txt"))}
    assert results["jqlang.jq"].title == "jq"
    assert results["jqlang.jq"].version == "1.7.1"
    assert results["itchyny.gojq"].source == "winget"
    assert results["yamafaktory.jql"].title == "JSON Query Language CLI"
    assert pk_win.parse_winget_search(fx("winget/none.txt")) == []


def test_winget_list_and_upgrade() -> None:
    installed, upgradable = pk_win.parse_winget_list(fx("winget/list.txt"))
    by = {p.name: p for p in installed}
    assert by["Git.Git"].version == "2.45.1"
    assert by["Microsoft.VCRedist.2015+.x64"].title == "Microsoft Visual C++ 2015-2…"
    assert by["ARP\\Machine\\X64\\SomeLocalApp"].source is None
    assert [(u.name, u.latest) for u in upgradable] == [("Git.Git", "2.46.0")]
    _, ups = pk_win.parse_winget_list(fx("winget/upgrade.txt"))
    assert [u.name for u in ups] == ["Git.Git"]  # footer line ignored


def test_winget_no_match_exit_code_is_empty() -> None:
    async def run(argv, env):
        return CmdResult(-1978335212, fx("winget/none.txt"), "")

    assert asyncio.run(pk_win.Winget(run).search("zzz")) == []


def test_scoop_parsers() -> None:
    results = {r.name: r for r in pk_win.parse_scoop_search(fx("scoop/search.txt"))}
    assert results["gojq"].version == "0.12.16" and results["jid"].source == "main"
    inst = {p.name: p for p in pk_win.parse_scoop_export(fx("scoop/export.json"))}
    assert inst["git"].version == "2.45.2"
    ups = pk_win.parse_scoop_status(fx("scoop/status.txt"))
    assert [(u.name, u.version, u.latest) for u in ups] == [("git", "2.45.2", "2.46.0")]
    assert pk_win.Scoop().upgrade_argv(None) == ["scoop", "update", "*"]
    assert pk_win.Scoop().install_argv("jq", "main") == ["scoop", "install", "main/jq"]


def test_choco_parsers() -> None:
    assert next((r.name, r.version) for r in pk_win.parse_choco_search(fx("choco/search.txt"))) == (
        "jq",
        "1.7.1",
    )
    assert {p.name for p in pk_win.parse_choco_list(fx("choco/list.txt"))} == {"chocolatey", "jq"}
    ups = pk_win.parse_choco_outdated(fx("choco/outdated.txt"))
    assert (ups[0].name, ups[0].version, ups[0].latest) == ("jq", "1.6", "1.7.1")
    assert pk_win.Choco().upgrade_argv(None)[:3] == ["choco", "upgrade", "all"]


# ---------------------------------------------------------------- shared


def test_column_table_uses_dash_groups_for_headers_with_spaces() -> None:
    rows = column_table(fx("scoop/status.txt"), min_columns=3)
    assert rows[0][:3] == ["git", "2.45.2", "2.46.0"]


def test_read_failures_raise_with_the_tool_message() -> None:
    async def run(argv, env):
        return CmdResult(100, "", "E: Could not open lock file /var/lib/dpkg/lock-frontend\n")

    with pytest.raises(PackageError, match="lock-frontend"):
        asyncio.run(pk_linux.Apt(run).installed())


def test_names_and_queries_cannot_be_options() -> None:
    for ok in ["jq", "libc6:arm64", "g++", "homebrew/cask/firefox", "Git.Git", "org.kde.kalk"]:
        assert PACKAGE_NAME.match(ok), ok
    for bad in ["-rf", "--all", "", "a b", "x;rm", "$(id)"]:
        assert not PACKAGE_NAME.match(bad), bad
    assert SEARCH_QUERY.match("media server")
    assert not SEARCH_QUERY.match("--help")


def test_every_detected_manager_has_an_implementation() -> None:
    import re

    import athena.platform.detect as detect

    source = Path(detect.__file__).read_text()
    assert set(re.findall(r'PackageManagerSpec\("(\w+)"', source)) == set(MANAGERS)


# ---------------------------------------------------------------- real tools (read-only)

# Which binary shows a manager is present, for the real read tests below. They only read
# (installed list and a search), so they run wherever the tool exists: Homebrew on the
# macOS runner and dev Macs, apt on the Ubuntu runner, Chocolatey on the Windows runner.
# That checks the hand-written Windows fixtures against the real thing in CI.
REAL_PROBE = {"apt": "dpkg-query", "brew": "brew", "choco": "choco", "winget": "winget"}


@pytest.mark.parametrize("manager_id", sorted(REAL_PROBE))
def test_real_tool_reads(manager_id: str) -> None:
    import shutil

    if not shutil.which(REAL_PROBE[manager_id]):
        pytest.skip(f"{manager_id} isn't on this machine")
    pm = MANAGERS[manager_id]()
    installed = asyncio.run(pm.installed())
    assert installed, f"{manager_id} reports nothing installed"
    assert all(p.name and not any(c.isspace() for c in p.name) for p in installed)
    if manager_id in ("apt", "brew"):  # searches that work from local package data
        found = asyncio.run(pm.search("jq"))
        assert any(r.name == "jq" for r in found), [r.name for r in found][:10]
