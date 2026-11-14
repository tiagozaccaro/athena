"""Encryption of secrets stored in the database (AI provider keys, docs/mvp-design.md §7).

The key is a Fernet key in `<data-dir>/secret.key` (mode 0600), created on first use.
This keeps keys out of database copies and backups; it doesn't protect against someone
who can read the data folder, since the key lives there too.
"""

import contextlib
import os
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

KEY_FILE = "secret.key"


class SecretError(Exception):
    """A stored secret can't be decrypted (the key file was replaced or lost)."""


class SecretBox:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / KEY_FILE
        self._fernet: Fernet | None = None
        self._lock = threading.Lock()

    def _key(self) -> Fernet:
        with self._lock:
            if self._fernet is None:
                self._fernet = Fernet(self._load_or_create())
            return self._fernet

    def _load_or_create(self) -> bytes:
        if self.path.is_file():
            return self.path.read_bytes().strip()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        # O_EXCL: if another process created it first, use theirs.
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return self.path.read_bytes().strip()
        with os.fdopen(fd, "wb") as handle:
            handle.write(key)
        with contextlib.suppress(OSError):  # Windows ignores POSIX modes
            self.path.chmod(0o600)
        return key

    def encrypt(self, value: str) -> str:
        return self._key().encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            return self._key().decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise SecretError(
                f"Can't decrypt a stored secret. Was {KEY_FILE} in the data folder replaced? "
                "Enter the key again."
            ) from exc
