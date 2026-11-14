"""The web terminal: the pty wrapper on this OS, and the WebSocket's checks."""

import asyncio
import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import make_app, signed_in
from fastapi.testclient import TestClient

from athena.api import terminal as terminal_api
from athena.containers.runtime import Runtime
from athena.platform.capabilities import Capability, CapabilityManifest
from athena.platform.store import CapabilityStore
from athena.terminal import shells
from athena.terminal.pty import PtySession

ENTER = "\r"


def py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


# ---------------------------------------------------------------- the pty itself


async def drain(pty: PtySession, until: str | None = None, timeout: float = 15) -> str:
    """Output until `until` shows up, or until the program exits."""
    out = ""

    async def loop() -> None:
        nonlocal out
        while (chunk := await pty.read()) is not None:
            out += chunk.decode("utf-8", "replace")
            if until and until in out:
                return

    await asyncio.wait_for(loop(), timeout)
    return out


def test_pty_output_and_exit_code() -> None:
    async def main() -> tuple[str, int]:
        pty = PtySession(py("print('hello from a pty'); raise SystemExit(3)"))
        try:
            return await drain(pty), await pty.wait()
        finally:
            await pty.close()

    out, code = asyncio.run(main())
    assert "hello from a pty" in out
    assert code == 3


def test_pty_input_and_resize() -> None:
    script = (
        "import os; name = input('name? '); s = os.get_terminal_size(); "
        "print('HI', name.upper(), s.columns, s.lines)"
    )

    async def main() -> str:
        pty = PtySession(py(script), cols=80, rows=24)
        try:
            await drain(pty, until="name?")
            pty.resize(100, 30)
            await pty.write("athena" + ENTER)
            return await drain(pty, until="30")
        finally:
            await pty.close()

    out = asyncio.run(main())
    assert "HI ATHENA 100 30" in out


def test_pty_close_kills_the_program() -> None:
    async def main() -> bool:
        pty = PtySession(py("import time; print('ready', flush=True); time.sleep(60)"))
        await drain(pty, until="ready")
        await pty.close()
        return pty.isalive()

    assert asyncio.run(main()) is False


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX job control")
def test_ctrl_c_interrupts_like_a_real_terminal() -> None:
    """The shell owns the pty as its controlling terminal, so Ctrl+C reaches the job."""

    async def main() -> tuple[str, int]:
        pty = PtySession(["/bin/sh"])
        try:
            await pty.write("sleep 30" + ENTER)
            await asyncio.sleep(0.5)
            await pty.write("\x03")
            await pty.write("echo after-$((40+2)); exit 7" + ENTER)
            return await drain(pty, timeout=10), await pty.wait()
        finally:
            await pty.close()

    out, code = asyncio.run(main())
    assert "after-42" in out
    assert code == 7


def test_missing_program_exits_127() -> None:
    async def main() -> tuple[str, int]:
        pty = PtySession(["athena-no-such-shell"])
        try:
            return await drain(pty), await pty.wait()
        finally:
            await pty.close()

    if sys.platform == "win32":
        with contextlib.suppress(Exception):  # ConPTY may refuse to spawn it at all
            out, code = asyncio.run(main())
            assert code != 0
        return
    out, code = asyncio.run(main())
    assert code == 127 and "athena-no-such-shell" in out


def test_container_shell_uses_the_runtime_cli() -> None:
    argv = shells.container_shell(Runtime("wsl-docker", ("wsl.exe", "-e", "docker")), "web")
    assert argv[:6] == ["wsl.exe", "-e", "docker", "exec", "-it", "-e"]
    assert argv[7:10] == ["web", "sh", "-c"]
    assert "exec bash" in argv[10]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX login shell")
def test_host_shell_is_a_login_shell() -> None:
    argv = shells.host_shell()
    assert argv[-1] == "-l" and Path(argv[0]).exists()


# ---------------------------------------------------------------- the WebSocket


def manifest_store(*caps: Capability) -> CapabilityStore:
    terminal = Capability(id="terminal.host", label="Terminal", status="ready", provider="pty")
    found = [terminal, *caps] if not any(c.id == "terminal.host" for c in caps) else list(caps)
    manifest = CapabilityManifest(
        os="linux", os_version="test", arch="x86_64", detected_at=datetime.now(UTC),
        capabilities=found,
    )  # fmt: skip
    return CapabilityStore(detector=lambda: manifest)


@pytest.fixture
def client_for(tmp_path: Path):
    with contextlib.ExitStack() as stack:

        def factory(store: CapabilityStore | None = None, shell=None) -> TestClient:
            app = make_app(tmp_path, store=store or manifest_store())
            app.state.terminal_shell = shell or (lambda: py("print(input().upper())"))
            return signed_in(stack.enter_context(TestClient(app)))

        yield factory


def hello(client: TestClient, **extra) -> str:
    return json.dumps(
        {"type": "auth", "csrf": client.headers["X-CSRF-Token"], "cols": 80, "rows": 24, **extra}
    )


def closed_with(ws) -> tuple[int, str]:
    """The server's close code and reason, skipping any output before it."""
    while True:
        message = ws.receive()
        if message["type"] == "websocket.close":
            return message["code"], message.get("reason", "")


def read_until_exit(ws) -> tuple[str, int]:
    out = ""
    while True:
        message = ws.receive()
        if message.get("bytes"):
            out += message["bytes"].decode("utf-8", "replace")
        elif message.get("text"):
            event = json.loads(message["text"])
            if event["type"] == "exit":
                return out, event["code"]
        elif message["type"] == "websocket.close":
            raise AssertionError(f"closed before exit: {message}")


def audit_rows(client: TestClient) -> list[tuple]:
    with client.app.state.db.engine.connect() as conn:
        return list(conn.exec_driver_sql("SELECT action, target, detail FROM audit_log"))


def test_host_session_round_trip_is_audited(client_for) -> None:
    client = client_for()
    with client.websocket_connect("/api/terminal/ws?target=host") as ws:
        ws.send_text(hello(client))
        ready = json.loads(ws.receive_text())
        assert ready["type"] == "ready"
        ws.send_text(json.dumps({"type": "resize", "cols": 120, "rows": 40}))
        ws.send_text(json.dumps({"type": "input", "data": "shout" + ENTER}))
        out, code = read_until_exit(ws)
    assert "SHOUT" in out
    assert code == 0
    rows = audit_rows(client)
    assert ("terminal.open", "host", None) in rows
    close = next(r for r in rows if r[0] == "terminal.close")
    assert close[1] == "host" and close[2].startswith("exit 0")


def test_needs_a_session(client_for, tmp_path: Path) -> None:
    client = TestClient(make_app(tmp_path, store=manifest_store()))
    with client.websocket_connect("/api/terminal/ws") as ws:
        assert closed_with(ws) == (4401, "Not signed in")


def test_needs_the_csrf_token_first(client_for) -> None:
    client = client_for()
    with client.websocket_connect("/api/terminal/ws") as ws:
        ws.send_text(hello(client, csrf="wrong"))
        assert closed_with(ws)[0] == 4403
    with client.websocket_connect("/api/terminal/ws") as ws:
        ws.send_text("not json")
        assert closed_with(ws)[0] == 4403
    assert not [r for r in audit_rows(client) if r[0] == "terminal.open"]


def test_admins_only(client_for) -> None:
    client = client_for()
    with client.app.state.db.engine.begin() as conn:
        conn.exec_driver_sql("UPDATE users SET is_admin = 0")
    with client.websocket_connect("/api/terminal/ws") as ws:
        ws.send_text(hello(client))
        assert closed_with(ws) == (4403, "Only admins can open a terminal")


def test_can_be_turned_off(client_for) -> None:
    client = client_for()
    assert client.get("/api/settings/system").json() == {"terminal_enabled": True}
    res = client.put("/api/settings/system", json={"terminal_enabled": False})
    assert res.status_code == 200
    with client.websocket_connect("/api/terminal/ws") as ws:
        ws.send_text(hello(client))
        code, reason = closed_with(ws)
    assert code == 4409 and "turned off" in reason
    assert ("settings.terminal", "off", None) in audit_rows(client)


def test_unsupported_host(client_for) -> None:
    old = Capability(
        id="terminal.host", label="Terminal", status="unsupported",
        detail="Needs Windows 10 1809 or later",
    )  # fmt: skip
    client = client_for(manifest_store(old))
    with client.websocket_connect("/api/terminal/ws") as ws:
        ws.send_text(hello(client))
        assert closed_with(ws) == (4409, "Needs Windows 10 1809 or later")


def test_bad_targets(client_for) -> None:
    client = client_for()
    for target, code in [
        ("nope", 4404),
        ("container:-it", 4404),
        ("container:a;b", 4404),
        ("container:web", 4409),  # no container runtime on this host
    ]:
        with client.websocket_connect(f"/api/terminal/ws?target={target}") as ws:
            ws.send_text(hello(client))
            assert closed_with(ws)[0] == code, target


def test_container_shell_goes_through_the_runtime(client_for, monkeypatch) -> None:
    containers = Capability(id="containers", label="Containers", status="ready",
                            provider="wsl-docker")  # fmt: skip
    monkeypatch.setattr(
        terminal_api.shells,
        "container_shell",
        lambda runtime, ref: py(f"print({' '.join([*runtime.cli, ref])!r})"),
    )
    client = client_for(manifest_store(containers))
    with client.websocket_connect("/api/terminal/ws?target=container:web-1") as ws:
        ws.send_text(hello(client))
        assert json.loads(ws.receive_text())["type"] == "ready"
        out, code = read_until_exit(ws)
    assert "wsl.exe -e docker web-1" in out and code == 0
    assert ("terminal.open", "container:web-1", None) in audit_rows(client)


def test_signing_out_closes_open_terminals(client_for) -> None:
    client = client_for(shell=lambda: py("import time; time.sleep(60)"))
    client.app.state.terminal_session_check = 0.1
    with client.websocket_connect("/api/terminal/ws") as ws:
        ws.send_text(hello(client))
        assert json.loads(ws.receive_text())["type"] == "ready"
        assert client.post("/api/auth/logout").status_code == 204
        assert closed_with(ws) == (4401, "Signed out")
    assert client.app.state.terminal_sessions == {}


def test_turning_it_off_closes_open_terminals(client_for) -> None:
    client = client_for(shell=lambda: py("import time; time.sleep(60)"))
    with client.websocket_connect("/api/terminal/ws") as ws:
        ws.send_text(hello(client))
        assert json.loads(ws.receive_text())["type"] == "ready"
        assert client.put("/api/settings/system", json={"terminal_enabled": False}).is_success
        assert closed_with(ws) == (4409, "The terminal was turned off in Settings")
    close = next(r for r in audit_rows(client) if r[0] == "terminal.close")
    assert close[2].startswith("The terminal was turned off")


def test_session_limit(client_for, monkeypatch) -> None:
    monkeypatch.setattr(terminal_api, "MAX_SESSIONS", 0)
    client = client_for()
    with client.websocket_connect("/api/terminal/ws") as ws:
        ws.send_text(hello(client))
        assert closed_with(ws)[0] == 4429


def test_system_settings_need_an_admin(client_for) -> None:
    client = client_for()
    with client.app.state.db.engine.begin() as conn:
        conn.exec_driver_sql("UPDATE users SET is_admin = 0")
    assert client.put("/api/settings/system", json={"terminal_enabled": False}).status_code == 403
