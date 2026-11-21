from pathlib import Path

from fake_probe import FakeProbe

from athena.platform.detect import detect
from athena.platform.probe import RunResult


def caps(probe: FakeProbe) -> dict[str, object]:
    return {c.id: c for c in detect(probe).capabilities}


# ---------------------------------------------------------------- only OS-relevant ids


def test_each_os_reports_only_its_own_package_managers() -> None:
    linux = caps(FakeProbe(os="linux"))
    darwin = caps(FakeProbe(os="darwin"))
    windows = caps(FakeProbe(os="windows"))
    assert "packages.apt" in linux and "packages.winget" not in linux
    assert set(k for k in darwin if k.startswith("packages.")) == {"packages.brew"}
    assert {"packages.winget", "packages.scoop", "packages.choco"} <= set(windows)
    assert "packages.apt" not in windows and "packages.brew" not in windows


# ---------------------------------------------------------------- containers


def test_linux_docker_engine_ready() -> None:
    c = caps(FakeProbe(engines={"unix:///var/run/docker.sock": "28.4.0"}))["containers"]
    assert (c.status, c.provider, c.available) == ("ready", "docker-engine", True)
    assert "28.4.0" in c.detail


def test_linux_podman_socket_used_when_no_docker() -> None:
    c = caps(FakeProbe(engines={"unix:///run/podman/podman.sock": "5.6.0"}))["containers"]
    assert (c.status, c.provider) == ("ready", "podman")


def test_linux_docker_installed_but_down_is_stopped() -> None:
    c = caps(FakeProbe(binaries={"dockerd": "/usr/bin/dockerd"}))["containers"]
    assert (c.status, c.actions, c.available) == ("stopped", ["start"], False)


def test_linux_no_runtime_is_missing_with_setup() -> None:
    c = caps(FakeProbe())["containers"]
    assert (c.status, c.actions) == ("missing", ["setup"])


def test_macos_colima_running() -> None:
    sock = "unix:///Users/me/.colima/default/docker.sock"
    probe = FakeProbe(
        os="darwin",
        home_dir=Path("/Users/me"),
        binaries={"colima": "/opt/homebrew/bin/colima"},
        engines={sock: "28.1.1"},
    )
    c = caps(probe)["containers"]
    assert (c.status, c.provider) == ("ready", "colima")


def test_macos_colima_installed_not_running() -> None:
    probe = FakeProbe(os="darwin", binaries={"colima": "/opt/homebrew/bin/colima"})
    c = caps(probe)["containers"]
    assert (c.status, c.provider, c.actions) == ("stopped", "colima", ["start"])


def test_macos_without_colima_points_to_brew() -> None:
    c = caps(FakeProbe(os="darwin"))["containers"]
    assert c.status == "missing"
    assert "brew install colima" in c.detail


def test_windows_prefers_docker_in_wsl() -> None:
    probe = FakeProbe(
        os="windows",
        binaries={"wsl": "C:/Windows/System32/wsl.exe"},
        commands={
            (
                "wsl.exe",
                "-e",
                "sh",
                "-c",
                "docker version --format '{{.Server.Version}}'",
            ): RunResult(0, "28.4.0\n")
        },
        engines={"npipe:////./pipe/docker_engine": "27.0.0"},
    )
    c = caps(probe)["containers"]
    assert (c.status, c.provider) == ("ready", "wsl-docker")


def test_windows_rancher_desktop_via_docker_pipe() -> None:
    probe = FakeProbe(
        os="windows",
        binaries={"rdctl": "C:/Program Files/Rancher Desktop/resources/rdctl.exe"},
        engines={"npipe:////./pipe/docker_engine": "27.0.0"},
    )
    c = caps(probe)["containers"]
    assert (c.status, c.provider) == ("ready", "rancher-desktop")


def test_windows_nothing_installed() -> None:
    c = caps(FakeProbe(os="windows"))["containers"]
    assert c.status == "missing"
    assert "WSL2" in c.detail


# ---------------------------------------------------------------- package managers


def test_apt_needs_root_on_linux() -> None:
    probe = FakeProbe(binaries={"apt-get": "/usr/bin/apt-get"})
    assert caps(probe)["packages.apt"].status == "needs_privilege"


def test_apt_ready_as_root_with_version() -> None:
    probe = FakeProbe(
        root=True,
        binaries={"apt-get": "/usr/bin/apt-get"},
        commands={("/usr/bin/apt-get", "--version"): RunResult(0, "apt 2.7.14 (amd64)\n")},
    )
    c = caps(probe)["packages.apt"]
    assert (c.status, c.detail) == ("ready", "apt 2.7.14 (amd64)")


def test_flatpak_is_fine_without_root() -> None:
    probe = FakeProbe(binaries={"flatpak": "/usr/bin/flatpak"})
    assert caps(probe)["packages.flatpak"].status == "ready"


def test_brew_refuses_root() -> None:
    probe = FakeProbe(os="darwin", root=True, binaries={"brew": "/opt/homebrew/bin/brew"})
    assert caps(probe)["packages.brew"].status == "needs_privilege"


def test_missing_manager_is_not_available() -> None:
    c = caps(FakeProbe(os="windows"))["packages.choco"]
    assert (c.status, c.available) == ("missing", False)


# ---------------------------------------------------------------- terminal, cloud, builtins


def test_terminal_on_old_windows_is_unsupported() -> None:
    assert caps(FakeProbe(os="windows", build=17134))["terminal.host"].status == "unsupported"
    assert caps(FakeProbe(os="windows", build=26100))["terminal.host"].provider == "conpty"
    assert caps(FakeProbe(os="darwin"))["terminal.host"].provider == "pty"


def test_rclone_detection() -> None:
    assert caps(FakeProbe())["cloud.rclone"].actions == ["setup"]
    probe = FakeProbe(
        binaries={"rclone": "/usr/bin/rclone"},
        commands={("/usr/bin/rclone", "version"): RunResult(0, "rclone v1.71.0\n- os/version\n")},
    )
    c = caps(probe)["cloud.rclone"]
    assert (c.status, c.detail) == ("ready", "rclone v1.71.0")


def test_builtins_always_ready() -> None:
    c = caps(FakeProbe(os="windows"))
    assert c["files"].available and c["shares.webdav"].available


# ---------------------------------------------------------------- resilience


def test_a_crashing_detector_does_not_break_the_manifest(monkeypatch) -> None:
    import athena.platform.detect as detect_module

    def boom(probe):
        raise RuntimeError("bug")

    monkeypatch.setattr(detect_module, "detect_rclone", boom)
    c = caps(FakeProbe())
    assert "cloud.rclone" not in c
    assert "containers" in c


def test_real_probe_never_raises() -> None:
    """Smoke test against the real host this test runs on (Linux, macOS or Windows CI)."""
    manifest = detect()
    ids = {c.id for c in manifest.capabilities}
    assert {"containers", "terminal.host", "files"} <= ids
    assert manifest.os in {"linux", "darwin", "windows"}


def test_installed_tunnels_are_detected() -> None:
    # These detectors once returned an action the model refuses, so an installed
    # cloudflared, tailscale or ngrok vanished from the manifest.
    from athena.platform.detect import (
        detect_tunnel_cloudflare,
        detect_tunnel_ngrok,
        detect_tunnel_tailscale,
    )

    probe = FakeProbe(
        binaries={
            "cloudflared": "/usr/bin/cloudflared",
            "ngrok": "/usr/bin/ngrok",
            "tailscale": "/usr/bin/tailscale",
        },
        commands={
            ("/usr/bin/cloudflared", "version"): RunResult(0, "cloudflared 2026.11.0", ""),
            ("/usr/bin/ngrok", "version"): RunResult(0, "ngrok 3.20.0", ""),
            ("/usr/bin/tailscale", "status", "--json"): RunResult(
                0,
                '{"BackendState": "Running", "CurrentTailnet": {"MagicDNSSuffix": "t.ts.net"}}',
                "",
            ),
        },
    )
    assert detect_tunnel_cloudflare(probe).status == "ready"
    assert detect_tunnel_ngrok(probe).status == "ready"
    tailscale = detect_tunnel_tailscale(probe)
    assert (tailscale.status, tailscale.detail) == ("ready", "Logged in to t.ts.net")
    stopped = FakeProbe(binaries={"tailscale": "/usr/bin/tailscale"})
    assert detect_tunnel_tailscale(stopped).status == "stopped"


# ---------------------------------------------------------------- local AI servers

MODELS = {"object": "list", "data": [{"id": "m1"}]}


def _local(probe: FakeProbe) -> dict[str, tuple[str, str | None, str | None]]:
    from athena.platform.detect import detect_local_ai

    return {c.id: (c.status, c.provider, c.endpoint) for c in detect_local_ai(probe)}


def test_nothing_running_or_installed_adds_nothing():
    assert _local(FakeProbe()) == {}


def test_servers_on_their_own_port_are_found():
    probe = FakeProbe(
        http={
            "http://127.0.0.1:5001/v1/models": MODELS,
            "http://127.0.0.1:13305/api/v1/models": MODELS,
            "http://127.0.0.1:12434/engines/v1/models": MODELS,
        }
    )
    assert _local(probe) == {
        "ai.local.koboldcpp": ("ready", "koboldcpp", "http://127.0.0.1:5001/v1"),
        "ai.local.lemonade": ("ready", "lemonade", "http://127.0.0.1:13305/api/v1"),
        "ai.local.docker-model-runner": (
            "ready",
            "docker-model-runner",
            "http://127.0.0.1:12434/engines/v1",
        ),
    }


def test_a_shared_port_is_told_apart_by_fingerprint():
    llama = FakeProbe(
        http={"http://127.0.0.1:8080/v1/models": MODELS, "http://127.0.0.1:8080/props": {}}
    )
    assert _local(llama) == {
        "ai.local.llama-cpp": ("ready", "llama-cpp", "http://127.0.0.1:8080/v1")
    }
    local_ai = FakeProbe(
        http={
            "http://127.0.0.1:8080/v1/models": MODELS,
            "http://127.0.0.1:8080/.well-known/localai.json": {"version": "v3"},
        }
    )
    assert list(_local(local_ai)) == ["ai.local.localai"]
    textgen = FakeProbe(
        http={
            "http://127.0.0.1:5000/v1/models": MODELS,
            "http://127.0.0.1:5000/v1/internal/model/info": {"model_name": "x"},
        }
    )
    assert list(_local(textgen)) == ["ai.local.text-generation-webui"]


def test_a_shared_port_without_fingerprint_uses_the_installed_binary():
    probe = FakeProbe(
        binaries={"mlx_lm.server": "/opt/homebrew/bin/mlx_lm.server"},
        http={"http://127.0.0.1:8080/v1/models": MODELS},
    )
    assert list(_local(probe)) == ["ai.local.mlx-lm"]


def test_an_unknown_server_is_a_generic_openai_compatible_one():
    # Something answers on 8000, but not vLLM's /version: don't call it vLLM.
    probe = FakeProbe(http={"http://127.0.0.1:8000/v1/models": MODELS})
    assert _local(probe) == {
        "ai.local.port-8000": ("ready", "openai-compatible", "http://127.0.0.1:8000/v1")
    }


def test_installed_but_not_answering_is_stopped():
    probe = FakeProbe(binaries={"llama-server": "/usr/bin/llama-server", "vllm": "/usr/bin/vllm"})
    assert _local(probe) == {
        "ai.local.llama-cpp": ("stopped", "llama-cpp", "http://127.0.0.1:8080/v1"),
        "ai.local.vllm": ("stopped", "vllm", "http://127.0.0.1:8000/v1"),
    }


def test_an_html_page_or_error_is_not_a_server():
    probe = FakeProbe(http={"http://127.0.0.1:8080/v1/models": {"error": "nope"}})
    assert _local(probe) == {}


def test_every_local_server_is_a_kind_with_a_default_url():
    from athena.assistant.kinds import LOCAL_KINDS
    from athena.platform.detect import LOCAL_AI_SERVERS, _kind_url

    kinds = {k.id for k in LOCAL_KINDS}
    for server in LOCAL_AI_SERVERS:
        assert server.kind in kinds
        assert _kind_url(server.kind)[1].startswith("http://127.0.0.1:")
    # Every local kind but Ollama (which has ai.ollama) is detected.
    assert kinds - {s.kind for s in LOCAL_AI_SERVERS} == {"ollama"}
