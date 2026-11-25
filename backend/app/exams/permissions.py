"""Role and permission mapping for EXAMS.

Maps existing MNH auth identities/roles to EXAMS capabilities without creating
a parallel auth system. Core MNH editor checks are currently open/public in
some legacy paths; EXAMS endpoints enforce their own backend checks.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.services import authentication

# Existing MNH roles -> EXAMS roles/capabilities
ROLE_MAP = {
    "administrator": "exam_admin",
    "hod": "exam_officer",
    "coordinator": "exam_officer",
    "executive_dean": "exam_reviewer",
    "lecturer": "instructor",
}

# Capability grants. Keep conservative; expand by explicit design.
CAPABILITIES = {
    "exam_admin": {
        "exams.view", "exams.manage", "exams.question.manage", "exams.session.manage",
        "exams.invigilate", "exams.grade", "exams.analytics", "exams.audit.view",
    },
    "exam_officer": {
        "exams.view", "exams.manage", "exams.question.manage", "exams.session.manage",
        "exams.invigilate", "exams.analytics", "exams.audit.view",
    },
    "instructor": {
        "exams.view", "exams.manage", "exams.question.manage", "exams.grade",
        "exams.analytics",
    },
    "exam_reviewer": {"exams.view", "exams.analytics", "exams.audit.view"},
    "invigilator": {"exams.view", "exams.invigilate", "exams.audit.view"},
    "candidate": {"exams.view", "exams.take"},
    "guest": {"exams.view"},
}


def resolve_identity(mnh_session: str | None) -> dict[str, Any]:
    """Resolve EXAMS identity from existing MNH session cookie.

    Returns a normalized identity dict. No parallel auth is created.
    """
    session = authentication.get_session(mnh_session) if mnh_session else None
    if session:
        mnh_role = str(session.get("role") or "public").strip().lower()
        exam_role = ROLE_MAP.get(mnh_role, "guest")
        sid = str(session.get("sid") or "").strip()
        actor_id = f"mnh:{mnh_role}:{sid}" if sid else f"mnh:{mnh_role}"
        return {
            "authenticated": True,
            "mnh_role": mnh_role,
            "exam_role": exam_role,
            "actor_id": actor_id,
            "actor_label": mnh_role,
            "session_sid": sid,
        }
    return {
        "authenticated": False,
        "mnh_role": "public",
        "exam_role": "guest",
        "actor_id": "public",
        "actor_label": "public",
    }


def has_capability(identity: dict[str, Any], capability: str) -> bool:
    role = str(identity.get("exam_role") or "guest")
    return capability in CAPABILITIES.get(role, set())


def require_capability(mnh_session: str | None, capability: str) -> dict[str, Any]:
    identity = resolve_identity(mnh_session)
    if not has_capability(identity, capability):
        raise HTTPException(403, f"EXAMS permission required: {capability}")
    return identity
