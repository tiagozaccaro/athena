"""Settings: per-user appearance, and host-wide system settings (admins only)."""

import json
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError

from athena import audit, system_settings
from athena.api.terminal import close_all as close_terminals
from athena.auth.deps import Authed, DbSession
from athena.system_settings import SystemSettings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])

# Option ids come from the shadcn preset lists (generated into packages/ui themes.json).
# The server only checks their shape; the UI falls back to the default for an id it
# doesn't know, so a newer or older UI never breaks on stored settings.
OptionId = Annotated[str, Field(pattern=r"^[a-z0-9-]{1,32}$")]


class Appearance(BaseModel):
    mode: Literal["light", "dark", "system"] = "system"
    base_color: OptionId = "neutral"
    theme: OptionId = "neutral"
    """A colored theme, or the base color's own name for its matching accent."""
    chart_color: OptionId = "neutral"
    """"neutral" means the charts follow the theme."""
    font: OptionId = "inter"
    font_heading: OptionId = "inherit"
    """"inherit" means headings use the body font."""
    radius: OptionId = "default"


@router.get("/appearance", operation_id="getAppearance")
def get_appearance(user: Authed) -> Appearance:
    stored = user.user.appearance
    if not stored:
        return Appearance()
    try:
        return Appearance.model_validate_json(stored)
    except ValidationError:
        log.warning("ignoring invalid appearance settings for %s", user.user.username)
        return Appearance()


@router.put("/appearance", operation_id="setAppearance")
def set_appearance(body: Appearance, user: Authed, db: DbSession) -> Appearance:
    user.user.appearance = json.dumps(body.model_dump(), separators=(",", ":"))
    db.add(user.user)
    db.commit()
    return body


@router.get("/system", operation_id="getSystemSettings")
def get_system(db: DbSession) -> SystemSettings:
    return system_settings.load(db)


@router.put("/system", operation_id="setSystemSettings")
def set_system(
    body: SystemSettings, request: Request, user: Authed, db: DbSession
) -> SystemSettings:
    """Turning the terminal off also closes the terminals that are open."""
    if not user.user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can change system settings")
    before = system_settings.load(db)
    system_settings.save(db, body)
    if before.terminal_enabled != body.terminal_enabled:
        state = "on" if body.terminal_enabled else "off"
        audit.record(db, user.user.username, "settings.terminal", state)
        if not body.terminal_enabled:
            close_terminals(request.app)
    return body
