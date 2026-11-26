"""Role and permission mapping for EXAMS.

EXAMS reuses the existing MNH session (`mnh_session` cookie) and deliberately
maps MNH roles to EXAMS capabilities. It does not create a parallel password or
login system. Exam-scoped enrollment records can add candidate/invigilator/grader
capabilities to an authenticated MNH identity for a specific exam only.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.services import authentication

ROLE_MAP = {
    "administrator": "exam_admin",
    "hod": "exam_officer",
    "coordinator": "exam_officer",
    "executive_dean": "exam_reviewer",
    "lecturer": "instructor",
}

CAPABILITIES = {
    "exam_admin": {
        "exams.view", "exams.manage", "exams.question.manage", "exams.session.manage",
        "exams.invigilate", "exams.grade", "exams.analytics", "exams.audit.view",
        "exams.backup",
    },
    "exam_officer": {
        "exams.view", "exams.manage", "exams.question.manage", "exams.session.manage",
        "exams.invigilate", "exams.analytics", "exams.audit.view", "exams.backup",
    },
    "instructor": {
        "exams.view", "exams.manage", "exams.question.manage", "exams.grade",
        "exams.analytics",
    },
    "exam_reviewer": {"exams.view", "exams.analytics", "exams.audit.view"},
    "invigilator": {"exams.view", "exams.invigilate", "exams.audit.view"},
    "grader": {"exams.view", "exams.grade", "exams.analytics"},
    "candidate": {"exams.view", "exams.take"},
    "guest": {"exams.view"},
}

# Capabilities granted by an explicit exam enrollment, scoped to that exam only.
ENROLLMENT_ROLE_CAPABILITIES = {
    "candidate": {"exams.view", "exams.take"},
    "invigilator": {"exams.view", "exams.invigilate", "exams.audit.view"},
    "grader": {"exams.view", "exams.grade", "exams.analytics"},
}


def resolve_identity(mnh_session: str | None) -> dict[str, Any]:
    """Resolve an EXAMS identity from an existing MNH session cookie."""
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
            "actor_label": mnh_role.replace("_", " ").title(),
            "session_sid": sid,
            "identity_source": "mnh_session",
        }
    return {
        "authenticated": False,
        "mnh_role": "public",
        "exam_role": "guest",
        "actor_id": "public",
        "actor_label": "public",
        "identity_source": "mnh_session",
    }


def has_capability(identity: dict[str, Any], capability: str) -> bool:
    role = str(identity.get("exam_role") or "guest")
    return capability in CAPABILITIES.get(role, set())


def enrollment_allows(enrollment: dict[str, Any] | None, capability: str) -> bool:
    if not enrollment:
        return False
    role = str(enrollment.get("role") or "")
    return capability in ENROLLMENT_ROLE_CAPABILITIES.get(role, set())


def is_admin(identity: dict[str, Any]) -> bool:
    return str(identity.get("exam_role") or "") == "exam_admin"


def require_capability(mnh_session: str | None, capability: str) -> dict[str, Any]:
    identity = resolve_identity(mnh_session)
    if not has_capability(identity, capability):
        raise HTTPException(403, f"EXAMS permission required: {capability}")
    return identity


def require_exam_capability(
    identity: dict[str, Any], capability: str, enrollment: dict[str, Any] | None
) -> None:
    """Allow a global capability or an exam-scoped enrollment capability."""
    if has_capability(identity, capability) or enrollment_allows(enrollment, capability):
        return
    raise HTTPException(403, f"EXAMS permission required for this exam: {capability}")
