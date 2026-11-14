"""First-run setup, login and logout.

Everything else under /api requires a session (see main.py). The UI is public static
files, so the data, not the pages, is what's protected.
"""

import re

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from athena import audit
from athena.auth import service
from athena.auth.deps import COOKIE_NAME, Authed, DbSession
from athena.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,64}$")


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool

    @classmethod
    def of(cls, user: User) -> "UserOut":
        assert user.id is not None
        return cls(id=user.id, username=user.username, is_admin=user.is_admin)


class AuthStatus(BaseModel):
    setup_required: bool
    """True until the first admin account exists. Only /api/auth/setup works then."""
    user: UserOut | None
    csrf_token: str | None
    """Send as the X-CSRF-Token header on every non-GET request."""


class Credentials(BaseModel):
    username: str
    password: str


class SetupRequest(BaseModel):
    username: str
    password: str = Field(min_length=service.MIN_PW_LENGTH, max_length=256)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_RE.match(value):
            raise ValueError("3 to 64 characters: letters, digits, dot, dash or underscore")
        return value


def _set_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(service.SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        path="/",
    )


def _signed_in(request: Request, response: Response, db: Session, user: User) -> AuthStatus:
    token, session = service.create_session(db, user)
    _set_cookie(request, response, token)
    return AuthStatus(setup_required=False, user=UserOut.of(user), csrf_token=session.csrf_token)


@router.get("/status", operation_id="getAuthStatus")
def auth_status(request: Request, db: DbSession) -> AuthStatus:
    """Public. Tells the UI whether to show setup, login, or the app."""
    if service.user_count(db) == 0:
        return AuthStatus(setup_required=True, user=None, csrf_token=None)
    token = request.cookies.get(COOKIE_NAME)
    found = service.session_for_token(db, token) if token else None
    if found is None:
        return AuthStatus(setup_required=False, user=None, csrf_token=None)
    session, user = found
    return AuthStatus(setup_required=False, user=UserOut.of(user), csrf_token=session.csrf_token)


@router.post("/setup", operation_id="setupAdmin", status_code=status.HTTP_201_CREATED)
def setup(body: SetupRequest, request: Request, response: Response, db: DbSession) -> AuthStatus:
    """Create the first admin account and sign in. Only works while no account exists."""
    if service.user_count(db) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Athena is already set up")
    user = service.create_user(db, body.username, body.password)
    return _signed_in(request, response, db, user)


@router.post("/login", operation_id="login")
def login(body: Credentials, request: Request, response: Response, db: DbSession) -> AuthStatus:
    throttle: service.LoginThrottle = request.app.state.login_throttle
    client = request.client.host if request.client else "unknown"
    if wait := throttle.retry_after(client):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many failed sign-ins. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )
    user = service.authenticate(db, body.username, body.password)
    if user is None:
        throttle.fail(client)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    throttle.reset(client)
    return _signed_in(request, response, db, user)


@router.post("/logout", operation_id="logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    _: Authed,
    db: DbSession,
) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        service.delete_session(db, token)
    response.delete_cookie(COOKIE_NAME, path="/")


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=service.MIN_PW_LENGTH, max_length=256)


@router.post("/password", operation_id="changePassword", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, request: Request, user: Authed, db: DbSession) -> None:
    """Change your password. Your other sessions are signed out; this one stays."""
    throttle: service.LoginThrottle = request.app.state.login_throttle
    client = request.client.host if request.client else "unknown"
    if wait := throttle.retry_after(client):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many wrong passwords. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )
    if not service.verify_password(user.user.password_hash, body.current_password):
        throttle.fail(client)
        # 400, not 401: the session is fine, and a 401 would make the UI sign out.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is wrong")
    if body.new_password == body.current_password:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "The new password must differ from the current one"
        )
    throttle.reset(client)
    service.set_password(db, user.user, body.new_password, keep_session=user.session.id)
    audit.record(db, user.user.username, "auth.password", user.user.username)
