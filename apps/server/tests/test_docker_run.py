import pytest
import yaml

from athena.apps.docker_run import ConversionError, convert


def svc(command: str) -> tuple[dict, dict, list[str]]:
    result = convert(command)
    doc = yaml.safe_load(result.compose)
    return doc, doc["services"][result.service], result.warnings


def test_common_flags() -> None:
    doc, s, warnings = svc(
        "docker run -d --name jellyfin --restart unless-stopped "
        "-p 8096:8096 -p 8920:8920/tcp -v /srv/media:/media:ro -v config:/config "
        "-e TZ=Europe/Lisbon --env PUID=1000 jellyfin/jellyfin:10.10"
    )
    assert s == {
        "image": "jellyfin/jellyfin:10.10",
        "container_name": "jellyfin",
        "restart": "unless-stopped",
        "ports": ["8096:8096", "8920:8920/tcp"],
        "volumes": ["/srv/media:/media:ro", "config:/config"],
        "environment": ["TZ=Europe/Lisbon", "PUID=1000"],
    }
    assert doc["volumes"] == {"config": {}}
    assert warnings == []


def test_service_name_from_image_when_unnamed() -> None:
    result = convert("docker run nginx:1.29-alpine")
    assert result.service == "nginx"


def test_command_after_image() -> None:
    _, s, _ = svc("docker run --rm -it busybox:1.37 sh -c 'echo hi'")
    assert s["command"] == ["sh", "-c", "echo hi"]
    assert s["tty"] is True and s["stdin_open"] is True


def test_equals_syntax_and_line_continuations() -> None:
    _, s, _ = svc("docker run \\\n  --name=web \\\n  --publish=80:80 \\\n  nginx")
    assert s["container_name"] == "web"
    assert s["ports"] == ["80:80"]


def test_rm_and_unknown_flags_warn() -> None:
    _, s, warnings = svc("docker run --rm --gpus all --weird-flag nginx")
    assert s == {"image": "nginx"}
    assert any("--rm" in w for w in warnings)
    assert any("--gpus" in w for w in warnings)
    assert any("--weird-flag" in w for w in warnings)


def test_host_network_and_custom_network() -> None:
    _, s, _ = svc("docker run --network host nginx")
    assert s["network_mode"] == "host"
    doc, s, warnings = svc("docker run --net proxy nginx")
    assert s["networks"] == ["proxy"]
    assert doc["networks"] == {"proxy": {"external": True}}
    assert any("external" in w for w in warnings)


def test_ulimits_logging_and_misc() -> None:
    _, s, _ = svc(
        "podman run --privileged --cap-add NET_ADMIN --ulimit nofile=1024:2048 "
        "--log-driver json-file --log-opt max-size=10m --stop-timeout 30 "
        "--add-host host.docker.internal:host-gateway nginx"
    )
    assert s["privileged"] is True
    assert s["cap_add"] == ["NET_ADMIN"]
    assert s["ulimits"] == {"nofile": {"soft": 1024, "hard": 2048}}
    assert s["logging"] == {"driver": "json-file", "options": {"max-size": "10m"}}
    assert s["stop_grace_period"] == "30s"
    assert s["extra_hosts"] == ["host.docker.internal:host-gateway"]


def test_sudo_and_container_run_prefixes() -> None:
    assert convert("sudo docker container run nginx").service == "nginx"


def test_bind_mounts_are_not_named_volumes() -> None:
    doc, _, _ = svc("docker run -v ./data:/data -v $HOME/x:/x -v 'C:\\data:/d' nginx")
    assert "volumes" not in doc


@pytest.mark.parametrize(
    "bad",
    ["nginx", "docker run", "docker run -p", "docker run 'unterminated"],
)
def test_errors(bad: str) -> None:
    with pytest.raises(ConversionError):
        convert(bad)
