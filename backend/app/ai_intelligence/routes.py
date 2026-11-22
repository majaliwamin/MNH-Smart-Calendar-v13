"""AI intelligence API: feedback, evaluation, performance, dataset and health."""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from hmac import compare_digest

from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.ai_intelligence import corrections, dataset, evaluation
from app.ai_intelligence.retrieval import retrieve_authoritative_context
from app.ai_intelligence.schemas import EvaluateRequest, FeedbackRequest
from app.class_rep import routes as class_rep_routes
from app.class_rep.config import provider_configs
from app.config import BUILD_ID
from app.services.authentication import role_for_password

logger = logging.getLogger(__name__)
router = APIRouter(tags=["AI Intelligence"])

_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[str, deque] = {}
_RATE_WINDOW_SECONDS = 60
_MANAGEMENT_ROLES = {"hod", "coordinator", "executive_dean"}
_ADMIN_HEADER = "x-mnh-ai-admin-token"
_ANALYTICS_HEADER = "x-cara-analytics-password"


def _rate(key: str, limit: int):
    now = time.monotonic()
    with _RATE_LOCK:
        bucket = _RATE_BUCKETS.setdefault(key, deque())
        while bucket and now - bucket[0] >= _RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, "Too many AI intelligence requests. Please wait a minute.")
        bucket.append(now)


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _require_management(request: Request, analytics_password: str | None, admin_token: str | None) -> str:
    expected = os.getenv("MNH_AI_ADMIN_TOKEN", "").strip()
    if expected and admin_token and compare_digest(str(admin_token), expected):
        return "admin"
    role = role_for_password(str(analytics_password or ""))
    if role not in _MANAGEMENT_ROLES:
        raise HTTPException(403, "AI evaluation and dataset access require an authorised management credential.")
    return role


@router.get("/api/ai/health")
@router.get("/ai/health")
def health():
    """Read-only status. Never returns credentials or raw connection errors."""
    payload = {"ok": True, "build": BUILD_ID, "model": "existing-crara-provider-chain"}
    try:
        ctx = retrieve_authoritative_context("health check", limit=5)
        payload["retrieval_ok"] = bool(ctx.ok)
        payload["provider_count"] = len(provider_configs())
        payload.update(corrections.stats())
        trends = evaluation.recent_trends(1)
        payload["last_evaluation_date"] = trends[0]["date"] if trends else None
        if not ctx.ok:
            payload["ok"] = False
    except Exception as exc:
        logger.warning("AI health check failed category=health_error detail=%s", type(exc).__name__)
        payload.update({"ok": False, "retrieval_ok": False, "error": "AI health checks could not complete."})
    return payload


@router.post("/api/ai/feedback")
@router.post("/ai/feedback")
def feedback(
    payload: FeedbackRequest,
    request: Request,
):
    user = class_rep_routes._user(request)
    _rate("ai-feedback:" + str(user.get("id", "unknown")) + ":" + _client(request), 20)
    try:
        result = corrections.submit_feedback(
            query=payload.query,
            original_response=payload.original_response,
            correction=payload.correction,
            user_id=str(user.get("id", "anonymous")),
            category=payload.category,
            date_or_entity=payload.date_or_entity,
            verified_facts=payload.verified_facts,
            conversation_id=payload.conversation_id,
            response_language=payload.response_language,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    logger.info(
        "AI feedback stored category=%s verification=%s learning=%s duplicate=%s",
        result.get("category"), result.get("verification_status"),
        result.get("learning_status"), result.get("duplicate"),
    )
    return result


@router.get("/api/ai/performance")
@router.get("/ai/performance")
def performance(
    request: Request,
    x_cara_analytics_password: str | None = Header(default=None),
    x_mnh_ai_admin_token: str | None = Header(default=None, alias=_ADMIN_HEADER),
):
    _require_management(request, x_cara_analytics_password, x_mnh_ai_admin_token)
    _rate("ai-performance:" + _client(request), 10)
    stats = corrections.stats()
    trends = evaluation.recent_trends(30)
    return {
        "ok": True,
        "corrections": stats,
        "trend_count": len(trends),
        "latest": trends[0] if trends else None,
        "trend": [
            {
                "date": item.get("date"),
                "total": item.get("total"),
                "passed": item.get("passed"),
                "pass_rate": item.get("pass_rate"),
                "average_attempts": item.get("average_attempts"),
                "failures": item.get("failures", {}),
            }
            for item in trends
        ],
    }


@router.post("/api/ai/evaluate")
@router.post("/ai/evaluate")
def evaluate(
    payload: EvaluateRequest,
    request: Request,
    x_cara_analytics_password: str | None = Header(default=None),
    x_mnh_ai_admin_token: str | None = Header(default=None, alias=_ADMIN_HEADER),
):
    _require_management(request, x_cara_analytics_password, x_mnh_ai_admin_token)
    _rate("ai-evaluate:" + _client(request), 3)
    if payload.force:
        trend = evaluation.run_evaluation()
    else:
        trend = evaluation.maybe_run_daily()
    logger.info(
        "AI evaluation requested category=evaluate forced=%s executed=%s",
        payload.force, bool(trend),
    )
    return {
        "ok": bool(trend),
        "message": "Evaluation completed." if trend else "Today's evaluation has already been recorded.",
        "trend": trend,
    }


@router.get("/api/ai/retrain-dataset")
@router.post("/api/ai/retrain-dataset")
@router.get("/ai/retrain-dataset")
@router.post("/ai/retrain-dataset")
def retrain_dataset(
    request: Request,
    x_cara_analytics_password: str | None = Header(default=None),
    x_mnh_ai_admin_token: str | None = Header(default=None, alias=_ADMIN_HEADER),
):
    _require_management(request, x_cara_analytics_password, x_mnh_ai_admin_token)
    _rate("ai-dataset:" + _client(request), 5)
    content = dataset.export_jsonl()
    logger.info("AI dataset export category=dataset records=%s", content.count("\n"))
    return Response(
        content=content,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="mnh-ai-verified-dataset.jsonl"'},
    )
