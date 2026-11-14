"""Host-wide settings that only admins change (docs/mvp-design.md §7).

Stored as one JSON row in `system_settings`. Unknown or invalid stored values fall back
to the defaults, so an older or newer server never fails on them.
"""

import logging

from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from athena.db.models import SystemSetting

log = logging.getLogger(__name__)
KEY = "system"


class SystemSettings(BaseModel):
    terminal_enabled: bool = True
    """The web terminal (host shell and container shells). Admins can turn it off."""


def load(db: Session) -> SystemSettings:
    row = db.get(SystemSetting, KEY)
    if row is None:
        return SystemSettings()
    try:
        return SystemSettings.model_validate_json(row.value)
    except ValidationError:
        log.warning("ignoring invalid system settings")
        return SystemSettings()


def save(db: Session, settings: SystemSettings) -> None:
    row = db.get(SystemSetting, KEY) or SystemSetting(key=KEY, value="")
    row.value = settings.model_dump_json()
    db.add(row)
    db.commit()
