"""Per-user settings. Appearance is the first; AI and system settings come later."""

import json
import logging
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, ValidationError

from athena.auth.deps import Authed, DbSession

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
