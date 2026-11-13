"""Append-only audit log of privileged actions."""

import logging

from sqlmodel import Session

from athena.db.models import AuditEntry

log = logging.getLogger("athena.audit")


def record(
    db: Session, username: str, action: str, target: str | None = None, detail: str | None = None
) -> None:
    db.add(AuditEntry(username=username, action=action, target=target, detail=detail))
    db.commit()
    log.info("%s %s %s%s", username, action, target or "", f" ({detail})" if detail else "")
