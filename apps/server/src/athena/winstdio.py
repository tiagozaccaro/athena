"""Windows: give the server usable standard handles before it starts child processes.

The logon task runs `pythonw.exe`, which has no console. Its standard handles can be
values Windows won't duplicate (Task Scheduler passes them in), and `subprocess` copies
the parent's handle for every stream a caller doesn't redirect. A library that starts a
program without `stdin=DEVNULL` (python-on-whales runs `docker` that way) then fails with
`OSError: [WinError 6] The handle is invalid`, and `GET /api/containers` returned 500.

`fix_std_handles` points each standard handle that can't be duplicated at `NUL`, once,
for the whole process. Valid handles (a console, a redirect) are left alone.
"""

import os
import sys

STD_HANDLES = {"stdin": -10, "stdout": -11, "stderr": -12}
"""`STD_INPUT_HANDLE`, `STD_OUTPUT_HANDLE`, `STD_ERROR_HANDLE` (DWORD -10, -11, -12)."""

_kept_open: list[int] = []
"""The NUL file descriptors now behind the standard handles; never closed."""


def _usable(handle: int | None) -> bool:
    """Whether `subprocess` can pass this handle to a child (it duplicates it)."""
    import _winapi

    if not handle:
        return True  # none at all: subprocess makes its own pipe
    if handle == -1:
        # INVALID_HANDLE_VALUE, which is also the current-process pseudo-handle, so
        # DuplicateHandle would accept it and the child would get a process handle.
        return False
    process = _winapi.GetCurrentProcess()
    try:
        copy = _winapi.DuplicateHandle(
            process, handle, process, 0, 1, _winapi.DUPLICATE_SAME_ACCESS
        )
    except OSError:
        return False
    _winapi.CloseHandle(copy)
    return True


def fix_std_handles() -> list[str]:
    """Replace unusable standard handles with NUL. Returns the names replaced."""
    if sys.platform != "win32":
        return []
    import _winapi
    import ctypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetStdHandle.argtypes = [ctypes.c_ulong, ctypes.c_void_p]
    kernel32.SetStdHandle.restype = ctypes.c_int
    replaced: list[str] = []
    for name, std_id in STD_HANDLES.items():
        try:
            handle = _winapi.GetStdHandle(std_id)
        except OSError:
            handle = -1  # INVALID_HANDLE_VALUE
        if _usable(handle):
            continue
        fd = os.open(os.devnull, os.O_RDWR)
        os.set_inheritable(fd, False)
        if kernel32.SetStdHandle(std_id & 0xFFFFFFFF, msvcrt.get_osfhandle(fd)):
            _kept_open.append(fd)
            replaced.append(name)
        else:
            os.close(fd)
    return replaced
