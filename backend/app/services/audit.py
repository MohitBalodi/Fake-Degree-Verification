from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> AuditLog:
    """Add an audit row to the current transaction (the caller commits).

    Keep `meta` free of personal data: identifiers and counts, not names/marks.
    """
    row = AuditLog(
        actor_id=actor_id, action=action, entity=entity, entity_id=entity_id, meta=meta or {}
    )
    db.add(row)
    return row
