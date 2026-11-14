"""The rclone sidecar: `rclone rcd` as a child process, driven over its HTTP API.

It listens on 127.0.0.1 with a random port, user and password, so only Athena can talk
to it, and uses Athena's own config file (`<data-dir>/rclone/rclone.conf`), never the
host user's. It's started on the first call and restarted if it has died; the server
stops it on shutdown. `--rc-serve` lets Athena stream a remote's files for downloads.

The calls are blocking HTTP requests run in a worker thread (stdlib only), so the
client works from any event loop, including the ones tests create.
"""

import asyncio
import base64
import contextlib
import json
import logging
import os
import secrets
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

log = logging.getLogger(__name__)

START_TIMEOUT = 15.0
CALL_TIMEOUT = 300.0
READ_CHUNK = 1024 * 1024
# The host's own rclone settings mustn't change how Athena's rclone behaves.
DROPPED_ENV = ("RCLONE_CONFIG", "RCLONE_RC_", "RCLONE_PASSWORD_COMMAND", "RCLONE_CONFIG_PASS")


class RcloneError(Exception):
    """rclone refused or failed a call; `status` is the HTTP status to answer with."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class RcloneUnavailable(RcloneError):
    def __init__(self, message: str) -> None:
        super().__init__(503, message)


@dataclass
class Download:
    """An open file from `--rc-serve`: headers to pass on and the body as chunks."""

    size: int | None
    chunks: AsyncIterator[bytes]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(DROPPED_ENV)}
    env["LC_ALL"] = "C.UTF-8"
    return env


def _error_of(body: bytes, fallback: str) -> str:
    try:
        data = json.loads(body)
    except ValueError:
        return body.decode(errors="replace").strip() or fallback
    return str(data.get("error") or fallback) if isinstance(data, dict) else fallback


class Rclone:
    """One `rclone rcd` for the server. `binary` finds the executable at call time."""

    def __init__(
        self, data_dir: Path, binary: Callable[[], str | None] = lambda: shutil.which("rclone")
    ) -> None:
        self.dir = data_dir / "rclone"
        self.config = self.dir / "rclone.conf"
        self._binary = binary
        self._proc: subprocess.Popen[bytes] | None = None
        self._base = ""
        self._auth = ""
        self._lock = threading.Lock()

    # --- Process -----------------------------------------------------------------------

    def _running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _start(self) -> None:
        binary = self._binary()
        if not binary:
            raise RcloneUnavailable("rclone isn't installed on this host")
        self.dir.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            self.dir.chmod(0o700)
        user = "athena"
        password = secrets.token_urlsafe(24)
        last = "rclone didn't start"
        for _ in range(3):
            port = _free_port()
            argv = [
                binary,
                "rcd",
                f"--rc-addr=127.0.0.1:{port}",
                f"--rc-user={user}",
                f"--rc-pass={password}",
                "--rc-serve",
                f"--config={self.config}",
                f"--cache-dir={self.dir / 'cache'}",
                "--log-level=NOTICE",
            ]
            log_file = (self.dir / "rclone.log").open("ab")
            try:
                proc = subprocess.Popen(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    env=_clean_env(),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as exc:
                raise RcloneUnavailable(f"Couldn't start rclone: {exc}") from exc
            finally:
                log_file.close()
            self._proc = proc
            self._base = f"http://127.0.0.1:{port}"
            self._auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
            deadline = time.monotonic() + START_TIMEOUT
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    last = (
                        f"rclone exited with code {proc.returncode} (see {self.dir / 'rclone.log'})"
                    )
                    break
                try:
                    self._post("core/version", {}, timeout=2)
                except (OSError, RcloneError):
                    time.sleep(0.1)
                    continue
                log.info("rclone rcd started on 127.0.0.1:%d (pid %d)", port, proc.pid)
                return
            else:
                last = "rclone didn't answer in time"
                self._kill()
        self._proc = None
        raise RcloneUnavailable(last)

    def _kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(5)

    def _ensure(self) -> None:
        with self._lock:
            if not self._running():
                self._start()

    def stop(self) -> None:
        with self._lock:
            self._kill()

    # --- Calls -------------------------------------------------------------------------

    def _post(self, method: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self._base}/{method}",
            data=json.dumps(params).encode(),
            headers={"Authorization": self._auth, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            message = _error_of(exc.read(), exc.reason or "rclone failed")
            raise RcloneError(exc.code, message) from exc
        data = json.loads(body or b"{}")
        return data if isinstance(data, dict) else {}

    def call_sync(
        self, method: str, params: dict[str, Any] | None = None, timeout: float = CALL_TIMEOUT
    ) -> dict[str, Any]:
        self._ensure()
        try:
            return self._post(method, params or {}, timeout)
        except urllib.error.URLError as exc:
            # The process may have died between the check and the call: try once more.
            with self._lock:
                if self._running():
                    raise RcloneUnavailable(f"rclone didn't answer: {exc.reason}") from exc
                self._start()
            return self._post(method, params or {}, timeout)
        except TimeoutError as exc:
            raise RcloneError(504, "rclone took too long to answer") from exc

    async def call(
        self, method: str, params: dict[str, Any] | None = None, timeout: float = CALL_TIMEOUT
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self.call_sync, method, params, timeout)

    async def download(self, fs: str, path: str) -> Download:
        """Open `path` on `fs` ("name:") for reading through `--rc-serve`."""

        def open_() -> Any:
            self._ensure()
            url = f"{self._base}/{quote(f'[{fs}]')}/{quote(path)}"
            request = urllib.request.Request(url, headers={"Authorization": self._auth})
            try:
                return urllib.request.urlopen(request, timeout=CALL_TIMEOUT)
            except urllib.error.HTTPError as exc:
                raise RcloneError(
                    exc.code, _error_of(exc.read(), "Couldn't open the file")
                ) from exc

        response = await asyncio.to_thread(open_)
        length = response.headers.get("Content-Length")

        async def chunks() -> AsyncIterator[bytes]:
            try:
                while data := await asyncio.to_thread(response.read, READ_CHUNK):
                    yield data
            finally:
                response.close()

        return Download(size=int(length) if length and length.isdigit() else None, chunks=chunks())
