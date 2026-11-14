"""The web terminal over a WebSocket (docs/mvp-design.md §4.2, §7).

    WS /api/terminal/ws?target=host | container:<id or name>

WebSocket routes can't use the `require_user` dependency (it reads an HTTP request) and
browsers can't set headers on a WebSocket, so this route checks for itself:

1. The session cookie must be valid (close 4401).
2. The first message must be `{"type": "auth", "csrf": <token>, "cols", "rows"}` with the
   session's CSRF token. A cross-site page can't read the token, so it can't open a
   shell even if a browser did send the cookie (close 4403).
3. The user must be an admin (4403), the terminal on in system settings (4409), and the
   target's capabilities ready (4404 / 4409).

Then output goes to the browser as binary frames, and the browser sends
`{"type": "input", "data"}` and `{"type": "resize", "cols", "rows"}` as text frames. When
the program exits the server sends `{"type": "exit", "code"}` and closes with 1000.
Signing out (or the session expiring) closes open terminals within a minute; turning
the terminal off in settings closes them at once.
"""

import asyncio
import contextlib
import json
import logging
import time
from dataclasses import dataclass

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session

from athena import audit, system_settings
from athena.auth.deps import COOKIE_NAME
from athena.auth.service import session_for_token
from athena.containers.runtime import RuntimeUnavailableError, runtime_from
from athena.containers.service import ContainerNotFoundError, check_ref
from athena.platform.store import CapabilityStore
from athena.terminal import shells
from athena.terminal.pty import PtySession

log = logging.getLogger(__name__)
router = APIRouter(prefix="/terminal", tags=["terminal"])

MAX_SESSIONS = 10
AUTH_TIMEOUT = 10.0
SESSION_CHECK_SECONDS = 60.0
MAX_INPUT = 64 * 1024


class Closed(Exception):  # a control-flow signal for closing the socket
    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


class AuthMessage(BaseModel):
    type: str = Field(pattern=r"^auth$")
    csrf: str = Field(max_length=256)
    cols: int = Field(default=80, ge=1, le=1000)
    rows: int = Field(default=24, ge=1, le=1000)


@dataclass
class Plan:
    argv: list[str]
    target: str
    """For the audit log: "host" or "container:<ref>"."""


async def _plan(ws: WebSocket, target: str) -> Plan:
    store: CapabilityStore = ws.app.state.capabilities
    caps = {c.id: c for c in (await store.get()).capabilities}
    term = caps.get("terminal.host")
    if term is None or not term.available:
        raise Closed(4409, (term.detail if term else None) or "This host has no terminal support")
    if target == "host":
        return Plan(ws.app.state.terminal_shell(), "host")
    if target.startswith("container:"):
        try:
            ref = check_ref(target.removeprefix("container:"))
            runtime = runtime_from(caps.get("containers"))
        except ContainerNotFoundError as exc:
            raise Closed(4404, str(exc)) from exc
        except RuntimeUnavailableError as exc:
            raise Closed(4409, str(exc)) from exc
        return Plan(shells.container_shell(runtime, ref), f"container:{ref}")
    raise Closed(4404, f"Unknown terminal target: {target[:64]!r}")


def _signed_in(db: Session, token: str | None) -> bool:
    return bool(token) and session_for_token(db, token) is not None


@router.websocket("/ws")
async def terminal_ws(ws: WebSocket, target: str = "host") -> None:
    await ws.accept()
    sessions: dict[int, asyncio.Event] = ws.app.state.terminal_sessions
    token = ws.cookies.get(COOKIE_NAME)
    pty: PtySession | None = None
    try:
        with Session(ws.app.state.db.engine) as db:
            found = session_for_token(db, token) if token else None
            if found is None:
                raise Closed(4401, "Not signed in")
            auth_session, user = found
            hello = await _hello(ws)
            if hello.csrf != auth_session.csrf_token:
                raise Closed(4403, "Missing or invalid CSRF token")
            if not user.is_admin:
                raise Closed(4403, "Only admins can open a terminal")
            if not system_settings.load(db).terminal_enabled:
                raise Closed(4409, "The terminal is turned off in Settings → System")
            plan = await _plan(ws, target)
            if len(sessions) >= MAX_SESSIONS:
                raise Closed(4429, f"Too many terminals open (the limit is {MAX_SESSIONS})")
            username = user.username

        try:
            pty = PtySession(
                plan.argv,
                cols=hello.cols,
                rows=hello.rows,
                cwd=shells.home(),
                env=shells.shell_env(),
            )
        except Exception as exc:  # OSError, or pywinpty's own error on Windows
            raise Closed(4500, f"Couldn't start {plan.argv[0]}: {exc}") from exc
        stop = sessions[pty.pid] = asyncio.Event()
        with Session(ws.app.state.db.engine) as db:
            audit.record(db, username, "terminal.open", plan.target)
        started = time.monotonic()
        await ws.send_text(json.dumps({"type": "ready", "command": plan.argv[0]}))
        detail = "closed by the browser"
        try:
            code = await _bridge(ws, pty, token, stop)
            if code is not None:
                detail = f"exit {code}"
        except Closed as closed:
            detail = closed.reason
            raise
        finally:
            elapsed = int(time.monotonic() - started)
            with Session(ws.app.state.db.engine) as db:
                audit.record(db, username, "terminal.close", plan.target, f"{detail}, {elapsed}s")
    except Closed as closed:
        with contextlib.suppress(Exception):
            await ws.close(closed.code, closed.reason)
    except WebSocketDisconnect:
        pass
    finally:
        if pty is not None:
            sessions.pop(pty.pid, None)
            await pty.close()


async def _hello(ws: WebSocket) -> AuthMessage:
    try:
        raw = await asyncio.wait_for(ws.receive_text(), AUTH_TIMEOUT)
        return AuthMessage.model_validate_json(raw)
    except TimeoutError as exc:
        raise Closed(4403, "No auth message") from exc
    except ValidationError as exc:
        raise Closed(4403, "Missing or invalid CSRF token") from exc


def close_all(app) -> None:
    """End every open terminal (the terminal was just turned off)."""
    for stop in app.state.terminal_sessions.values():
        stop.set()


async def _bridge(
    ws: WebSocket, pty: PtySession, token: str | None, stop: asyncio.Event
) -> int | None:
    """Pump both ways until the program exits (its code) or the browser leaves (None)."""

    async def output() -> int:
        while (chunk := await pty.read()) is not None:
            await ws.send_bytes(chunk)
        code = await pty.wait()
        await ws.send_text(json.dumps({"type": "exit", "code": code}))
        await ws.close(1000, f"exited with code {code}")
        return code

    async def browser() -> None:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                return
            text = message.get("text")
            if not text or len(text) > MAX_INPUT:
                continue
            try:
                event = json.loads(text)
            except ValueError:
                continue
            if event.get("type") == "input" and isinstance(event.get("data"), str):
                await pty.write(event["data"])
            elif event.get("type") == "resize":
                cols, rows = event.get("cols"), event.get("rows")
                if isinstance(cols, int) and isinstance(rows, int):
                    pty.resize(max(1, min(cols, 1000)), max(1, min(rows, 1000)))

    async def still_signed_in() -> None:
        while True:
            await asyncio.sleep(ws.app.state.terminal_session_check)
            with Session(ws.app.state.db.engine) as db:
                if not _signed_in(db, token):
                    raise Closed(4401, "Signed out")

    async def turned_off() -> None:
        await stop.wait()
        raise Closed(4409, "The terminal was turned off in Settings")

    out_task = asyncio.create_task(output())
    tasks = {
        out_task,
        asyncio.create_task(browser()),
        asyncio.create_task(still_signed_in()),
        asyncio.create_task(turned_off()),
    }
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    for task in done:
        exc = task.exception() if not task.cancelled() else None
        if isinstance(exc, Closed):
            raise exc
        if exc is not None and not isinstance(exc, WebSocketDisconnect):
            log.warning("terminal session ended with an error: %s", exc)
    if out_task in done and not out_task.cancelled() and out_task.exception() is None:
        return out_task.result()
    return None
