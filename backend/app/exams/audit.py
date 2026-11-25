"""EXAMS audit/event helpers.

Append-only exam audit events are stored in the shared docs table under a
namespaced collection so they are isolated from legacy examinations calendar data.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from app.database.connection import database

EXAMS_AUDIT_COLLECTION = "exams_audit_events"


def emit_event(
    *,
    actor: dict[str, Any],
    action: str,
    entity_type: str,
    entity_id: str = "",
    summary: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = int(time.time() * 1000)
    event = {
        "id": f"exaevt_{uuid.uuid4().hex[:20]}",
        "at": now,
        "action": str(action),
        "entity_type": str(entity_type),
        "entity_id": str(entity_id or ""),
        "summary": str(summary or "")[:500],
        "actor": {
            "id": str(actor.get("actor_id") or "public"),
            "label": str(actor.get("actor_label") or "public"),
            "mnh_role": str(actor.get("mnh_role") or "public"),
            "exam_role": str(actor.get("exam_role") or "guest"),
        },
        "details": details or {},
    }
    with database() as connection:
        connection.execute(
            "INSERT INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (
                EXAMS_AUDIT_COLLECTION,
                event["id"],
                __import__("json").dumps(event, ensure_ascii=False),
                now,
            ),
        )
    return event
