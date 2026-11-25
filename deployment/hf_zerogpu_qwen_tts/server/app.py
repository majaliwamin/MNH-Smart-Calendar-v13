from __future__ import annotations

import logging
import time

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .inference import InferenceError, service
from .schemas import HealthResponse, ModelInfo, ModelListResponse, SpeechRequest
from .security import require_bearer

logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(title="MNH Qwen3-TTS ZeroGPU Experimental Service", version="0.1.0")
origins = settings.cors_origin_list()
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.on_event("startup")
async def _startup() -> None:
    logger.info("Qwen3-TTS ZeroGPU service starting model=%s startup_load=%s", settings.model_id, settings.startup_load)
    # On ZeroGPU, avoid loading model weights at startup outside a GPU-decorated path.
    # The first synthesis call will load as needed inside @spaces.GPU.
    if settings.startup_load and not str(settings.device).startswith("auto"):
        try:
            service.load()
        except Exception:
            logger.exception("Startup model load failed; service will load on first request/GPU call")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    gpu = service.gpu_info()
    return HealthResponse(
        status="ok",
        model_id=service.model_id,
        gpu_available=bool(gpu.get("gpu_available")),
        gpu_name=gpu.get("gpu_name"),
        vram_gb=gpu.get("vram_gb"),
        model_loaded=service.loaded,
        ready=not service.load_error,
        detail=service.load_error or service.last_error or ("GPU allocated dynamically on synthesis" if not service.loaded else None),
    )


@app.get("/ready")
async def ready() -> dict:
    # ZeroGPU may not have GPU allocated until synthesis; report config readiness.
    if service.load_error:
        raise HTTPException(status_code=503, detail=service.load_error)
    return {"ready": True, "model_id": service.model_id, "model_loaded": service.loaded, "mode": "zerogpu-dynamic"}


@app.get("/v1/models", response_model=ModelListResponse, dependencies=[Depends(require_bearer)])
async def models() -> ModelListResponse:
    return ModelListResponse(data=[ModelInfo(id=service.model_id, capabilities={
        "speech": True,
        "voice_clone": bool(settings.allow_voice_clone),
        "formats": ["wav", "mp3", "pcm"],
        "streaming": False,
        "experimental": True,
        "zerogpu": True,
    })])


@app.post("/v1/audio/speech", dependencies=[Depends(require_bearer)])
async def speech(req: SpeechRequest) -> Response:
    if req.model and req.model != settings.model_id:
        raise HTTPException(status_code=400, detail=f"Model '{req.model}' is not loaded. Configured model is '{settings.model_id}'.")
    started = time.time()
    try:
        result = service.synthesize(
            text=req.input,
            voice=req.voice,
            language=req.language,
            instructions=req.instructions,
            response_format=req.response_format,
            ref_audio_base64=req.ref_audio_base64,
            ref_text=req.ref_text,
        )
    except InferenceError as exc:
        logger.warning("Synthesis error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected synthesis error")
        raise HTTPException(status_code=500, detail="Unexpected synthesis error") from exc

    elapsed_ms = int((time.time() - started) * 1000)
    headers = {
        "X-Qwen-TTS-Model": result.model_id,
        "X-Qwen-TTS-Voice": result.voice,
        "X-Qwen-TTS-Sample-Rate": str(result.sample_rate),
        "X-Qwen-TTS-Latency-Ms": str(elapsed_ms),
        "Cache-Control": "no-store",
    }
    return Response(content=result.audio, media_type=result.media_type, headers=headers)
