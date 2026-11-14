"""The web terminal: a host shell or a container shell in a pseudo-terminal.

`pty.py` wraps ptyprocess (POSIX) and pywinpty/ConPTY (Windows) behind one async
interface; `shells.py` picks what to run. The WebSocket lives in `athena.api.terminal`.
"""
