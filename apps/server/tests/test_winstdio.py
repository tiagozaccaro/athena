"""athena/winstdio.py: usable standard handles for child processes on Windows."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from athena.winstdio import fix_std_handles

CHILD = """
import json, subprocess, sys
from athena.winstdio import fix_std_handles

def spawn():
    try:
        r = subprocess.run(["cmd", "/c", "echo", "hi"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, check=True)
        return r.stdout.decode().strip()
    except OSError as exc:
        return f"winerror {getattr(exc, 'winerror', None)}"

before = spawn()
replaced = fix_std_handles()
after = spawn()
again = fix_std_handles()
with open(sys.argv[1], "w") as f:
    json.dump({"before": before, "replaced": replaced, "after": after, "again": again}, f)
"""


def test_does_nothing_off_windows():
    if sys.platform == "win32":
        pytest.skip("Windows has its own test")
    assert fix_std_handles() == []


@pytest.mark.skipif(sys.platform != "win32", reason="Windows standard handles")
def test_a_child_with_an_invalid_stdin_handle_can_start_programs(tmp_path):
    """Starts pythonw.exe with a stdin handle Windows won't duplicate, as the logon task
    can, and checks a library-style subprocess call fails before the fix and works after.
    """
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.is_file() else Path(sys.executable)
    script = tmp_path / "child.py"
    script.write_text(CHILD)
    result = tmp_path / "result.json"
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESTDHANDLES
    info.hStdInput = 0x0BAD_0BAD  # not a handle this process has
    info.hStdOutput = 0
    info.hStdError = 0
    proc = subprocess.Popen([str(exe), str(script), str(result)], startupinfo=info)
    assert proc.wait(timeout=60) == 0
    seen = json.loads(result.read_text())
    assert seen["before"] == "winerror 6", seen  # the bug, reproduced
    assert seen["replaced"] == ["stdin"], seen
    assert seen["after"] == "hi", seen
    assert seen["again"] == [], seen  # a second call changes nothing
