"""Container runtime access (docs/mvp-design.md §3, §4.1).

Every runtime is driven through a Docker-compatible CLI (via python-on-whales for
structured reads, and direct subprocesses for streamed operations). One code path
covers Docker Engine, Colima, Podman, Rancher Desktop and Docker inside WSL2, which
has no socket reachable from Windows.
"""
