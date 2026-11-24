"""Document shapes and collection names for the native public chat.

MNH Calendar-v13 uses a shared SQLite ``docs`` table instead of a migration
framework. These constants keep every chat collection in one place so chat data
can be tested, cleaned up, and excluded from unrelated exports safely.
"""
from __future__ import annotations

from .settings import RETENTION_SECONDS

COL_PARTICIPANTS = "public_chat_participants"
# Codes are reserved by primary key so simultaneous joins cannot claim the same
# MNH-XXXX identifier on SQLite or PostgreSQL.
COL_CODE_RESERVATIONS = "public_chat_code_reservations"
COL_MESSAGES = "public_chat_messages"
COL_ACCESS_REQUESTS = "public_chat_access_requests"
COL_REACTIONS = "public_chat_reactions"
COL_READ_STATE = "public_chat_read_state"
COL_PREFERENCES = "public_chat_preferences"
COL_BLOCKS = "public_chat_blocks"
COL_REPORTS = "public_chat_reports"
COL_MODERATION = "public_chat_moderation_actions"
COL_CLEANUP_LOG = "public_chat_cleanup_log"

CHAT_COLLECTIONS = frozenset({
    COL_PARTICIPANTS,
    COL_CODE_RESERVATIONS,
    COL_MESSAGES,
    COL_ACCESS_REQUESTS,
    COL_REACTIONS,
    COL_READ_STATE,
    COL_PREFERENCES,
    COL_BLOCKS,
    COL_REPORTS,
    COL_MODERATION,
    COL_CLEANUP_LOG,
})

PUBLIC_RETENTION_SECONDS = RETENTION_SECONDS

ROLE_MEMBER = "member"
ROLE_MODERATOR = "moderator"
ROLE_ADMIN = "administrator"

MEMBER_STATUS_ACTIVE = "active"
MEMBER_STATUS_PENDING = "pending"
MEMBER_STATUS_SUSPENDED = "suspended"
