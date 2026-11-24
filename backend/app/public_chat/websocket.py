"""Authenticated realtime transport for the native public chat.

Identity comes from cookies, not a query parameter. Every outgoing message
event is re-read and serialized for the viewer so private replies and private
media can never be broadcast to the public room.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from . import auth, service, settings, store


class ChatSocketManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._clients: dict[WebSocket, dict[str, Any]] = {}

    async def add(self, websocket: WebSocket, info: dict[str, Any]) -> None:
        async with self._lock:
            self._clients[websocket] = info

    async def remove(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.pop(websocket, None)

    async def _snapshot(self) -> list[tuple[WebSocket, dict[str, Any]]]:
        async with self._lock:
            return list(self._clients.items())

    @staticmethod
    def _viewer(info: dict[str, Any]) -> dict[str, Any]:
        """Re-read membership so a member who joins after connecting is live."""
        uid = str(info.get("user_id") or "")
        return store.get_participant({"id": uid}) or {"user_id": uid, "code": ""}

    @staticmethod
    def _serialize_for(event: dict[str, Any], viewer: dict[str, Any], info: dict[str, Any]) -> dict[str, Any] | None:
        event_type = str(event.get("type") or "")
        viewer_uid = str(viewer.get("user_id") or info.get("user_id") or "")
        # A suspended or not-yet-joined socket may stay connected for join_check,
        # but it must not receive message, moderation, or notification events.
        if not str(viewer.get("code") or "") and event_type not in {"hello", "presence", "pong", "error"}:
            return None
        blocked = service.blocked_codes({"id": viewer_uid})
        if event_type == "message.reaction":
            message_id = str(event.get("message_id") or "")
            raw = store._message_doc(message_id)
            if not raw or not store._message_visible(raw, viewer, blocked):
                return None
            return {**event, "reactions": store._reaction_summaries(viewer_uid).get(message_id, {})}
        if not event_type.startswith("message.") or not isinstance(event.get("message"), dict):
            return event
        raw = store._message_doc(str(event["message"].get("id") or ""))
        if not raw:
            return None
        if not store._message_visible(raw, viewer, blocked):
            return None
        reactions = store._reaction_summaries(viewer_uid)
        readers = store._read_counts()
        return {**event, "message": store._serialize_message(raw, viewer, reactions, readers)}

    async def _deliver(self, websocket: WebSocket, info: dict[str, Any], event: dict[str, Any]) -> bool:
        try:
            payload = self._serialize_for(event, self._viewer(info), info)
            if payload is None:
                return True
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception:
            return False

    async def broadcast(self, event: dict[str, Any]) -> None:
        stale = []
        for websocket, info in await self._snapshot():
            if not await self._deliver(websocket, info, event):
                stale.append(websocket)
        for websocket in stale:
            await self.remove(websocket)

    async def send_to_users(self, event: dict[str, Any], user_ids: set[str]) -> None:
        wanted = {str(uid) for uid in user_ids if uid}
        if not wanted:
            return
        stale = []
        for websocket, info in await self._snapshot():
            if str(info.get("user_id") or "") not in wanted:
                continue
            if not await self._deliver(websocket, info, event):
                stale.append(websocket)
        for websocket in stale:
            await self.remove(websocket)

    async def presence(self) -> dict[str, Any]:
        clients = await self._snapshot()
        return {"type": "presence", "online": len(clients)}

    async def typing(self, sender_info: dict[str, Any], code: str, is_typing: bool) -> None:
        code = str(code or "").strip().upper()
        event = {
            "type": "typing",
            "code": str(sender_info.get("participant", {}).get("code") or ""),
            "identity": str(sender_info.get("participant", {}).get("public_identity") or ""),
            "private": bool(code),
            "typing": bool(is_typing),
        }
        sender_uid = str(sender_info.get("user_id") or "")
        target = store.participant_by_code(code) if code else None
        target_uid = str((target or {}).get("user_id") or "")
        for websocket, info in await self._snapshot():
            uid = str(info.get("user_id") or "")
            if uid == sender_uid:
                continue
            if target_uid and uid != target_uid:
                continue
            if not str(self._viewer(info).get("code") or ""):
                continue
            try:
                await websocket.send_text(json.dumps(event, ensure_ascii=False))
            except Exception:
                await self.remove(websocket)


manager = ChatSocketManager()


async def broadcast(event: dict[str, Any]) -> None:
    await manager.broadcast(event)


def dispatch_to_users(event: dict[str, Any], user_ids: set[str]) -> None:
    """Sync callback for notifications.dispatch, scheduled on the running loop."""
    asyncio.create_task(manager.send_to_users(event, user_ids))


async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    info: dict[str, Any] | None = None
    try:
        try:
            user = auth.resolve_user(websocket)
        except Exception:
            await websocket.send_text(json.dumps({"type": "error", "error": "Authentication required."}))
            await websocket.close(code=4401)
            return
        participant = store.get_participant(user)
        info = {"user_id": str(user.get("id") or ""), "participant": participant or {}}
        await manager.add(websocket, info)
        await websocket.send_text(json.dumps({
            "type": "hello",
            "joined": bool(participant),
            "participant": service.participant_payload(participant),
            "retention_days": settings.RETENTION_DAYS,
            "online": (await manager.presence())["online"],
        }, ensure_ascii=False))
        await manager.broadcast(await manager.presence())
        while True:
            raw = await websocket.receive_text()
            if raw == "ping":
                await websocket.send_text('{"type":"pong"}')
                continue
            try:
                command = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(command, dict):
                continue
            command_type = str(command.get("type") or "")
            if command_type == "ping":
                await websocket.send_text('{"type":"pong"}')
            elif command_type == "typing":
                fresh = store.get_participant({"id": str(info.get("user_id") or "")})
                if fresh:
                    info["participant"] = fresh
                    await manager.typing(info, str(command.get("to_code") or ""), bool(command.get("typing")))
            elif command_type == "read":
                uid = str(info.get("user_id") or "")
                store.require_participant({"id": uid})
                service.mark_read({"id": uid}, int(command.get("at") or 0))
            elif command_type == "join_check":
                fresh = store.get_participant({"id": str(info.get("user_id") or "")})
                info["participant"] = fresh or {}
                await websocket.send_text(json.dumps({
                    "type": "hello",
                    "joined": bool(fresh),
                    "participant": service.participant_payload(fresh),
                    "retention_days": settings.RETENTION_DAYS,
                }, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        if info is not None:
            await manager.remove(websocket)
            await manager.broadcast(await manager.presence())
