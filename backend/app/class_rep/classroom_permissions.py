"""Server-derived classroom roles and whiteboard permissions for CRARA.

The embedded classroom receives only a presentation hint. Authorization for
host-only whiteboard actions is always re-derived from the signed-in CRARA
session; browser-supplied role fields are never trusted.
"""
from __future__ import annotations

import os
from typing import Any

_DEFAULT_HOST_EMAILS = {"majaliwamin@gmail.com"}


def _host_emails() -> set[str]:
    configured = os.getenv("MNH_CLASSROOM_HOST_EMAILS", "")
    values = {item.strip().lower() for item in configured.split(",") if item.strip()}
    return values | _DEFAULT_HOST_EMAILS


def classroom_role(user: dict[str, Any] | None) -> str:
    """Return 'host' for an authorised signed-in account, otherwise 'student'."""
    account = user or {}
    email = str(account.get("email") or "").strip().lower()
    user_id = str(account.get("id") or "").strip()
    if not email or user_id.startswith("guest_"):
        return "student"
    return "host" if email in _host_emails() else "student"


def classroom_permissions(user: dict[str, Any] | None, room: str = "") -> dict[str, Any]:
    """Return the starting permission set embedded in the signed handoff."""
    host = classroom_role(user) == "host"
    return {
        "canWrite": True,
        "canControl": host,
        "boardLocked": False,
        "boardOwner": "",
        "granted": [],
        "room": room[:160],
    }
