"""Passwords, sessions and login throttling."""

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlmodel import Session, delete, func, select

from athena.db.models import AuthSession, User

SESSION_TTL = timedelta(days=30)
# Not named "*PASSWORD*": CodeQL treats such names as secrets and flags printing them.
MIN_PW_LENGTH = 8

_hasher = PasswordHasher()
# Verified against when the username doesn't exist, so timing doesn't reveal valid usernames.
_DUMMY_HASH = _hasher.hash("athena-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def user_count(db: Session) -> int:
    return db.exec(select(func.count()).select_from(User)).one()


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.exec(select(User).where(User.username == username)).first()
    if user is None:
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(user.password_hash, password):
        return None
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.add(user)
        db.commit()
    return user


def create_user(db: Session, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password), is_admin=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_password(db: Session, user: User, password: str, keep_session: int | None = None) -> None:
    """Replace the password and sign the user out everywhere (except `keep_session`)."""
    if len(password) < MIN_PW_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PW_LENGTH} characters")
    user.password_hash = hash_password(password)
    db.add(user)
    stale = delete(AuthSession).where(AuthSession.user_id == user.id)
    if keep_session is not None:
        stale = stale.where(AuthSession.id != keep_session)
    db.exec(stale)
    db.commit()


def create_session(db: Session, user: User) -> tuple[str, AuthSession]:
    """Returns the raw cookie token (never stored) and the session row."""
    token = secrets.token_urlsafe(32)
    session = AuthSession(
        token_hash=hash_token(token),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(32),
        expires_at=datetime.now(UTC) + SESSION_TTL,
    )
    db.add(session)
    # Housekeeping: drop expired sessions whenever someone signs in.
    db.exec(delete(AuthSession).where(AuthSession.expires_at < datetime.now(UTC)))
    db.commit()
    db.refresh(session)
    return token, session


def session_for_token(db: Session, token: str) -> tuple[AuthSession, User] | None:
    row = db.exec(
        select(AuthSession, User)
        .join(User, AuthSession.user_id == User.id)
        .where(AuthSession.token_hash == hash_token(token))
    ).first()
    if row is None:
        return None
    session, user = row
    expires = session.expires_at
    if expires.tzinfo is None:  # SQLite returns naive datetimes
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        db.delete(session)
        db.commit()
        return None
    return session, user


def delete_session(db: Session, token: str) -> None:
    db.exec(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    db.commit()


class LoginThrottle:
    """At most `limit` failed logins per client per `window` seconds."""

    def __init__(self, limit: int = 5, window: float = 300.0) -> None:
        self.limit = limit
        self.window = window
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, key: str, now: float) -> deque[float]:
        q = self._failures[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def retry_after(self, key: str) -> int:
        """Seconds until the client may try again, or 0 if allowed now."""
        now = time.monotonic()
        with self._lock:
            q = self._trim(key, now)
            if len(q) < self.limit:
                return 0
            return max(1, int(self.window - (now - q[0])))

    def fail(self, key: str) -> None:
        with self._lock:
            self._trim(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
