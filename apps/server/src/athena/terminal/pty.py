"""One async interface over a POSIX pty (Linux, macOS) and ConPTY (Windows, pywinpty).

POSIX doesn't use `pty.fork()`/ptyprocess: forking a multi-threaded server and running
Python in the child can deadlock it. Instead `subprocess.Popen` forks and execs in C
(`start_new_session=True` makes the child a session leader), and a two-line shim takes
the pty as its controlling terminal before exec'ing the shell, so job control and
Ctrl+C work.

A reader thread pulls output and hands it to the event loop through a bounded queue.
When the browser can't keep up the queue fills, the thread blocks and the program
stalls on its writes, so `yes` can't grow memory without limit.
"""

import asyncio
import contextlib
import logging
import os
import select
import signal
import subprocess
import sys
import threading
from collections.abc import Mapping
from pathlib import Path

log = logging.getLogger(__name__)

READ_SIZE = 64 * 1024
QUEUE_SIZE = 64
POLL_SECONDS = 0.2

# argv[1:] is the real command. Exit 127 like a shell when it can't be found.
CTTY_SHIM = (
    "import fcntl,os,sys,termios\n"
    "fcntl.ioctl(0, termios.TIOCSCTTY, 0)\n"
    "try: os.execvp(sys.argv[1], sys.argv[1:])\n"
    "except OSError as e: print(f'athena: {sys.argv[1]}: {e.strerror}', file=sys.stderr);"
    " sys.exit(127)\n"
)


class _Posix:
    def __init__(self, argv: list[str], cols: int, rows: int, cwd, env) -> None:
        import pty
        import termios

        self.master, slave = pty.openpty()
        try:
            termios.tcsetwinsize(slave, (rows, cols))
            self.proc = subprocess.Popen(
                [sys.executable, "-I", "-c", CTTY_SHIM, *argv],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                cwd=cwd,
                env=env,
                start_new_session=True,
                close_fds=True,
            )
        except BaseException:
            os.close(self.master)
            raise
        finally:
            os.close(slave)
        self.pid = self.proc.pid

    def read(self) -> bytes | None:
        """A chunk, b"" when nothing is ready yet, or None at the end."""
        ready, _, _ = select.select([self.master], [], [], POLL_SECONDS)
        if not ready:
            # A background job can keep the pty open after the shell exits.
            return None if self.proc.poll() is not None else b""
        try:
            data = os.read(self.master, READ_SIZE)
        except OSError:  # EIO on Linux once every slave fd is closed
            return None
        return data or None

    def write(self, data: str) -> None:
        view = memoryview(data.encode("utf-8"))
        while view:
            written = os.write(self.master, view)
            view = view[written:]

    def resize(self, cols: int, rows: int) -> None:
        import termios

        termios.tcsetwinsize(self.master, (rows, cols))

    def isalive(self) -> bool:
        return self.proc.poll() is None

    def exit_code(self) -> int:
        code = self.proc.wait()
        return 128 - code if code < 0 else code

    def terminate(self) -> None:
        """Hang up the whole session (the shell and its jobs), then kill what's left."""
        for sig, grace in ((signal.SIGHUP, 1.0), (signal.SIGKILL, 2.0)):
            if self.proc.poll() is not None:
                break
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(self.proc.pid, sig)
            with contextlib.suppress(subprocess.TimeoutExpired):
                self.proc.wait(grace)

    def close_fd(self) -> None:
        with contextlib.suppress(OSError):
            os.close(self.master)


class _Windows:
    def __init__(self, argv: list[str], cols: int, rows: int, cwd, env) -> None:
        from winpty import PtyProcess  # pyright: ignore[reportMissingImports]

        self.proc = PtyProcess.spawn(argv, cwd=cwd, env=env, dimensions=(rows, cols))
        self.pid = self.proc.pid

    def read(self) -> bytes | None:
        try:
            data = self.proc.read(READ_SIZE)
        except EOFError:
            return None
        if not data:
            return None if not self.proc.isalive() else b""
        return data.encode("utf-8", "replace")

    def write(self, data: str) -> None:
        self.proc.write(data)

    def resize(self, cols: int, rows: int) -> None:
        self.proc.setwinsize(rows, cols)

    def isalive(self) -> bool:
        return self.proc.isalive()

    def exit_code(self) -> int:
        for _ in range(100):  # the status lands a moment after the output ends
            if not self.proc.isalive():
                break
            threading.Event().wait(0.05)
        code = self.proc.exitstatus
        return code if code is not None else -1

    def terminate(self) -> None:
        if self.proc.isalive():
            self.proc.terminate(force=True)

    def close_fd(self) -> None:
        pass


class PtySession:
    def __init__(
        self,
        argv: list[str],
        *,
        cols: int = 80,
        rows: int = 24,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.argv = argv
        backend = _Windows if sys.platform == "win32" else _Posix
        self._pty = backend(
            argv, cols, rows, str(cwd) if cwd else None, dict(env) if env is not None else None
        )
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(QUEUE_SIZE)
        self._loop = asyncio.get_running_loop()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._pump, name="athena-pty", daemon=True)
        self._thread.start()

    @property
    def pid(self) -> int:
        return self._pty.pid

    def _pump(self) -> None:
        try:
            while not self._closed.is_set():
                data = self._pty.read()
                if data is None:
                    break
                if not data:
                    if sys.platform == "win32":
                        self._closed.wait(0.02)
                    continue
                if not self._put(data):
                    return
        except Exception:
            log.exception("terminal reader failed")
        finally:
            self._put(None)

    def _put(self, item: bytes | None) -> bool:
        """Hand one chunk to the loop, blocking while the queue is full. False once the
        session is closed (nobody reads any more) or the loop is gone."""
        try:
            fut = asyncio.run_coroutine_threadsafe(self._queue.put(item), self._loop)
        except RuntimeError:  # the loop is closed
            return False
        while True:
            try:
                fut.result(timeout=0.5)
                return True
            except TimeoutError:
                if self._closed.is_set():
                    fut.cancel()
                    return False
            except Exception:  # the loop shut down under us
                return False

    async def read(self) -> bytes | None:
        """The next chunk of output, or None once the program has exited."""
        return await self._queue.get()

    async def write(self, data: str) -> None:
        # In a thread: a program that isn't reading its input would block the loop.
        await asyncio.to_thread(self._pty.write, data)

    def resize(self, cols: int, rows: int) -> None:
        with contextlib.suppress(OSError):
            self._pty.resize(cols, rows)

    def isalive(self) -> bool:
        return self._pty.isalive()

    async def wait(self) -> int:
        """The exit code (128 + signal for a killed POSIX program)."""
        return await asyncio.to_thread(self._pty.exit_code)

    async def close(self) -> None:
        """Stop the program and its jobs, then the reader thread."""
        self._closed.set()
        await asyncio.to_thread(self._shutdown)

    def _shutdown(self) -> None:
        with contextlib.suppress(Exception):
            self._pty.terminate()
        self._thread.join(timeout=2)
        self._pty.close_fd()
