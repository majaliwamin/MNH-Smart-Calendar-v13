"""HTTP boundary for the Class Rep Assistant."""
import logging
from fastapi import APIRouter, HTTPException
from app.class_rep.config import provider_config
from app.class_rep.schemas import ChatRequest, ChatResponse
from app.class_rep.assistant import reply
from app.class_rep.providers import ProviderError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/class-rep", tags=["Class Representative Assistant"])


@router.get("/status")
def status():
    cfg = provider_config()
    return {"ready": bool(cfg["api_key"] and cfg["model"]),
            "provider": cfg["provider"], "model": cfg["model"],
            "secret_configured": bool(cfg["api_key"])}


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    try:
        text, provider, model, updated = reply(payload.message.strip(), [item.model_dump() for item in payload.history])
        return ChatResponse(reply=text, provider=provider, model=model, context_updated_at=updated)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Class Rep Assistant request failed")
        raise HTTPException(status_code=503, detail="The Class Rep Assistant is temporarily unavailable. Please try again later.") from exc
