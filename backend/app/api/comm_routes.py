"""Communications Centre endpoints: contacts, drafts, templates, jobs, voice calls.

The shared communications workspace is open without password authentication.
Safeguards (consent, do-not-contact, calling hours and emergency stop) remain
enforced by the communications services.
"""
from fastapi import APIRouter, Body, Cookie, HTTPException

from app.services import ari_service, ai_assistant, ai_trigger, comm_contacts, comm_service, wa_bridge

router = APIRouter(prefix="/api/comm")
def _actor(mnh_session: str | None = None) -> str:
    return "public"


def _editor(mnh_session: str | None = None) -> str:
    return "public"


# ---- overview -----------------------------------------------------------------
@router.get("/status")
def comm_status(mnh_session: str | None = Cookie(None)):
    _actor(mnh_session)  # signed-in users only; viewing status leaks nothing sensitive
    info = comm_service.status()
    info["ai"] = ai_assistant.status()
    info["asterisk"] = ari_service.status()
    info["aiTrigger"] = ai_trigger.status()
    info["whatsapp"] = {**info["whatsapp"], "note": "Meta Cloud API retired — sending goes through the WhatsApp bridge (aiTrigger.bridge)"}
    return info


# ---- contacts -----------------------------------------------------------------
@router.get("/contacts")
def contacts(mnh_session: str | None = Cookie(None)):
    _actor(mnh_session)
    return {"contacts": comm_contacts.list_contacts(), "dnc": comm_contacts.dnc_list()}


@router.post("/contacts")
def add_contact(mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    try:
        return comm_contacts.upsert_contact(actor, data)
    except comm_contacts.ContactError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.put("/contacts/{contact_id}")
def update_contact(contact_id: str, mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    try:
        return comm_contacts.upsert_contact(actor, data, contact_id)
    except comm_contacts.ContactError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.delete("/contacts/{contact_id}")
def remove_contact(contact_id: str, mnh_session: str | None = Cookie(None)):
    actor = _editor(mnh_session)
    comm_contacts.delete_contact(actor, contact_id)
    return {"ok": True}


@router.post("/contacts/{contact_id}/consent")
def consent(contact_id: str, mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    try:
        contact = comm_contacts.set_consent(actor, contact_id, str(data.get("channel") or ""), bool(data.get("granted")))
    except comm_contacts.ContactError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"ok": True, "contact": contact}


# ---- do-not-contact ---------------------------------------------------------------
@router.post("/dnc")
def add_dnc(mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    try:
        return comm_contacts.dnc_add(actor, str(data.get("phone") or ""), str(data.get("reason") or ""))
    except comm_contacts.ContactError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.delete("/dnc/{item_id}")
def remove_dnc(item_id: str, mnh_session: str | None = Cookie(None)):
    actor = _editor(mnh_session)
    comm_contacts.dnc_remove(actor, item_id)
    return {"ok": True}


# ---- AI drafting (fills the composer; use /ai/trigger for AI-sent messages) -------
@router.post("/ai/draft")
def ai_draft(mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    comm_service._guard_preparation(actor)
    try:
        return {"draft": ai_assistant.draft(str(data.get("prompt") or ""))}
    except ai_assistant.AIError as error:
        raise HTTPException(status_code=503, detail=str(error))


# ---- AI-triggered sending (AI composes AND dispatches via the bridge) -------------
@router.post("/ai/trigger")
def ai_trigger_send(mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    try:
        return ai_trigger.trigger_now(
            actor,
            str(data.get("kind") or "announcement"),
            str(data.get("instructions") or ""),
            [str(c) for c in (data.get("contactIds") or [])] or None,
        )
    except ai_trigger.TriggerError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except wa_bridge.BridgeError as error:
        raise HTTPException(status_code=502, detail=str(error))


@router.get("/ai/trigger-log")
def ai_trigger_log(mnh_session: str | None = Cookie(None)):
    _actor(mnh_session)
    return {"log": ai_trigger.trigger_log()}


# ---- drafts & wa.me links ------------------------------------------------------------
@router.post("/drafts")
def create_draft(mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    try:
        return comm_service.create_draft(actor, list(data.get("contactIds") or []),
                                         str(data.get("body") or ""), title=str(data.get("title") or ""),
                                         aiAssisted=bool(data.get("aiAssisted")))
    except (comm_service.CommError, comm_contacts.ContactError) as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/drafts")
def drafts(mnh_session: str | None = Cookie(None)):
    _actor(mnh_session)
    return {"drafts": comm_service.draft_rows()}


@router.post("/drafts/{draft_id}/mark")
def mark_draft(draft_id: str, mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _actor(mnh_session)
    try:
        return comm_service.mark_draft(actor, draft_id, str(data.get("contactId") or ""), str(data.get("status") or ""))
    except comm_service.CommError as error:
        raise HTTPException(status_code=400, detail=str(error))


# ---- templates -----------------------------------------------------------------------
@router.get("/templates")
def templates(mnh_session: str | None = Cookie(None)):
    _actor(mnh_session)
    return {"templates": comm_service.list_templates()}


@router.post("/templates")
def add_template(mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    try:
        return comm_service.upsert_template(actor, data)
    except comm_service.CommError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.put("/templates/{template_id}")
def update_template(template_id: str, mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    try:
        return comm_service.upsert_template(actor, data, template_id)
    except comm_service.CommError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.delete("/templates/{template_id}")
def remove_template(template_id: str, mnh_session: str | None = Cookie(None)):
    actor = _editor(mnh_session)
    comm_service.delete_template(actor, template_id)
    return {"ok": True}


# ---- scheduled jobs (create drafts only, never send) -----------------------------------
@router.get("/jobs")
def jobs(mnh_session: str | None = Cookie(None)):
    _actor(mnh_session)
    return {"jobs": comm_service.job_rows()}


@router.post("/jobs")
def schedule_job(mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    try:
        return comm_service.schedule_job(actor, data)
    except comm_service.CommError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, mnh_session: str | None = Cookie(None)):
    actor = _editor(mnh_session)
    try:
        return comm_service.cancel_job(actor, job_id)
    except comm_service.CommError as error:
        raise HTTPException(status_code=400, detail=str(error))


# ---- voice calls (Asterisk ARI) ----------------------------------------------------------
@router.post("/voice/calls")
def start_call(mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    contact_id = str(data.get("contactId") or "")
    purpose = str(data.get("purpose") or "")
    contact = comm_contacts.get_contact(contact_id)
    if not contact:
        raise HTTPException(status_code=400, detail="Contact not found.")
    consent_ok, _ = comm_contacts.contact_allowed(contact, "voice")
    dnc_ok, _ = comm_contacts.contact_allowed(contact, "whatsapp")  # DNC applies to both channels
    window_ok, window_reason = comm_service.within_call_window()
    checks = {"consentOk": consent_ok, "dncOk": dnc_ok, "windowOk": window_ok}
    try:
        call = ari_service.request_call(actor, contact_id, purpose, checks=checks)
    except ari_service.ARIError as error:
        blocked = not (consent_ok and dnc_ok and window_ok)
        detail = str(error)
        if blocked:
            reason = "" if consent_ok else "no voice consent recorded"
            reason = reason or ("" if dnc_ok else "phone is on the do-not-contact list")
            reason = reason or window_reason
            raise HTTPException(status_code=403, detail=f"Call not permitted: {reason or detail}")
        raise HTTPException(status_code=502, detail=detail)
    return call


@router.get("/voice/calls")
def voice_calls(mnh_session: str | None = Cookie(None)):
    _actor(mnh_session)
    return {"calls": ari_service.call_rows()}


@router.post("/voice/calls/{call_id}/refresh")
def refresh_call(call_id: str, mnh_session: str | None = Cookie(None)):
    _actor(mnh_session)
    try:
        return ari_service.refresh_call(call_id)
    except ari_service.ARIError as error:
        raise HTTPException(status_code=502, detail=str(error))


@router.post("/voice/calls/{call_id}/hangup")
def hangup(call_id: str, mnh_session: str | None = Cookie(None)):
    actor = _editor(mnh_session)
    try:
        return ari_service.hangup(actor, call_id)
    except ari_service.ARIError as error:
        raise HTTPException(status_code=502, detail=str(error))


# ---- history, safeguards -----------------------------------------------------------------
@router.get("/history")
def history(mnh_session: str | None = Cookie(None), limit: int = 100):
    _actor(mnh_session)
    return {"history": comm_service.history(limit)}


@router.post("/emergency-stop")
def emergency_stop(mnh_session: str | None = Cookie(None), data: dict = Body(...)):
    actor = _editor(mnh_session)
    return comm_service.set_emergency_stop(actor, bool(data.get("enabled")))
