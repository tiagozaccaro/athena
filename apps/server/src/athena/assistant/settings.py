"""Assistant settings (Settings → AI). Host-wide, admins only; one JSON row in
`system_settings` under the key "ai". Invalid stored values fall back to defaults."""

import logging

from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session

from athena.db.models import SystemSetting

log = logging.getLogger(__name__)
KEY = "ai"


class ModelRef(BaseModel):
    provider_id: str = Field(min_length=1, max_length=32)
    model: str = Field(min_length=1, max_length=255)


class AiSettings(BaseModel):
    default_model: ModelRef | None = None
    """Used for new chats."""
    title_model: ModelRef | None = None
    """A small model for writing chat titles; the chat's own model when empty."""
    shell_enabled: bool = False
    """Lets the assistant ask to run shell commands (each still needs approval)."""
    spend_limit_usd: float | None = Field(default=None, gt=0, le=10_000)
    """Stops a chat once its cost reaches this, for models with known prices."""


def load(db: Session) -> AiSettings:
    row = db.get(SystemSetting, KEY)
    if row is None:
        return AiSettings()
    try:
        return AiSettings.model_validate_json(row.value)
    except ValidationError:
        log.warning("ignoring invalid AI settings")
        return AiSettings()


def save(db: Session, settings: AiSettings) -> None:
    row = db.get(SystemSetting, KEY) or SystemSetting(key=KEY, value="")
    row.value = settings.model_dump_json()
    db.add(row)
    db.commit()
