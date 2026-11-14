# Package manager output fixtures

Parser tests in `tests/test_packages.py` run against these files on every OS.

| Manager | How it was captured |
|---|---|
| brew | Real output, Homebrew 7.0.13 on macOS (2026-11-14). Trimmed to a few entries; the installed cask was replaced with the real `jquake` record from `brew info`, marked installed and outdated, so no personal app list is published. |
| apt | Real output, Debian 13 (apt 3.0.3) in a container. |
| apk | Real output, Alpine 3.24 (apk-tools 3.0.8) in a container. |
| dnf | Real output, Fedora (dnf5 5.4.7) in a container. `upgradable.txt` uses the same `repoquery --qf` format from an `--installed` query, because the image had no updates. |
| dnf4 | Real output, CentOS Stream 9 (dnf 4.14) in a container (note the blank line dnf4 adds after each record). Same note for `upgradable.txt`. |
| rpm-installed.txt | Real `rpm -qa --qf` output (CentOS Stream 9); used by dnf and zypper. |
| zypper | Real `--xmlout` output, openSUSE Tumbleweed (zypper 1.14.102). |
| pacman | Real output, Arch Linux (pacman 7.1.0) in a container. `upgradable.txt` is hand-written in the documented `pacman -Qu` format (`name old -> new`); the image had no updates. |
| flatpak | `search*.txt` are real (Flatpak 1.16.6). `installed.txt` and `updates.txt` are hand-written in the same `--columns` tab format; a fresh container has nothing installed. |
| snap, winget, scoop, choco | Hand-written from each tool's documented output (snapd can't run in a container, and the Windows tools need Windows). Replace them with real captures when a host is available. |
