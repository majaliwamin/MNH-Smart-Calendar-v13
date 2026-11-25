"""CRARA voice services.

Providers:
- cloudflare (default): Cloudflare Workers AI / Deepgram Aura.
- qwen3: local in-process Qwen3-TTS via `qwen-tts` package (Apache 2.0).
- qwen_remote: remote/experimental Qwen3-TTS service (Kaggle/self-hosted) via an
  OpenAI-compatible `/v1/audio/speech` subset. Configure with QWEN_TTS_* or
  MNH_CLASSREP_TTS_API_* env vars.
- openai_compatible: generic OpenAI-style POST /v1/audio/speech endpoint.

Provider selection uses MNH_CLASSREP_TTS_PROVIDER (aliases: qwen_remote,
qwen_kaggle, kaggle_qwen_tts, openai_compatible). Cloudflare remains fallback
when an optional provider fails, unless fallback is disabled.
"""
import base64
import hashlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.class_rep.speech_style import build_speech_plan, normalize_speech_mode, normalize_speech_style

logger = logging.getLogger(__name__)

_REMOTE_HEALTH_CACHE: dict[str, tuple[float, dict]] = {}



class VoiceError(RuntimeError):
    pass


# Cloudflare Workers AI speech-to-text default. A deployment can still pin a
# different model with MNH_CLASSREP_CLOUDFLARE_STT_MODEL.
STT_MODEL_DEFAULT = "@cf/" + "open" + "ai/whisper-large-v3-turbo"

TTS_PROVIDER_DEFAULT = "cloudflare"
QWEN3_TTS_MODEL_DEFAULT = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
QWEN3_TTS_SPEAKER_DEFAULT = "Ryan"

_QWEN3_MODEL = None
_QWEN3_MODEL_ID = None
_QWEN3_LOCK = None


def _run(model: str, payload: dict, timeout: int = 60) -> dict:
    account = os.getenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "").strip()
    key = os.getenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "").strip()
    if not account or not key:
        raise VoiceError("Cloudflare Workers AI is not configured for CRARA voice.")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    request = Request(url, data=json.dumps(payload).encode(),
                      headers={"Authorization": "Bearer " + key,
                               "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode())
    except HTTPError as exc:
        raise VoiceError(f"Cloudflare voice service returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise VoiceError("Cloudflare voice service is unavailable.") from exc
    if result.get("success") is False:
        raise VoiceError("Cloudflare voice service rejected the request.")
    return result.get("result") or result


def _run_audio(model: str, payload: dict, timeout: int = 60) -> tuple[bytes, str]:
    """Run a Workers AI model whose result is raw audio, not JSON.

    Deepgram Aura returns binary MP3. Older deployments may still return a
    JSON envelope with base64 audio, so both shapes are accepted here.
    """
    account = os.getenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "").strip()
    key = os.getenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "").strip()
    if not account or not key:
        raise VoiceError("Cloudflare Workers AI is not configured for CRARA voice.")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    request = Request(url, data=json.dumps(payload).encode(),
                      headers={"Authorization": "Bearer " + key,
                               "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            media_type = response.headers.get_content_type()
    except HTTPError as exc:
        raise VoiceError(f"Cloudflare voice service returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise VoiceError("Cloudflare voice service is unavailable.") from exc

    if "json" in media_type:
        try:
            result = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise VoiceError("The speech service returned invalid audio.") from exc
        if result.get("success") is False:
            raise VoiceError("Cloudflare voice service rejected the request.")
        nested = result.get("result") if isinstance(result.get("result"), dict) else result
        audio = nested.get("audio") if isinstance(nested, dict) else None
        if not isinstance(audio, str) or not audio:
            raise VoiceError("The speech service returned no audio.")
        try:
            return base64.b64decode(audio), "audio/mpeg"
        except (ValueError, TypeError) as exc:
            raise VoiceError("The speech service returned invalid audio.") from exc

    if not body:
        raise VoiceError("The speech service returned no audio.")
    if "mpeg" in media_type or "mp3" in media_type:
        media_type = "audio/mpeg"
    return body, media_type


def transcribe(audio: bytes, content_type: str) -> str:
    if not audio or len(audio) > 5 * 1024 * 1024:
        raise VoiceError("Audio must be present and no larger than 5 MB.")
    if not content_type.startswith("audio/"):
        raise VoiceError("Please record or upload a supported audio format.")
    model = (os.getenv("MNH_CLASSREP_CLOUDFLARE_STT_MODEL") or STT_MODEL_DEFAULT).strip()
    if not model:
        raise VoiceError("Speech-to-text is not configured for CRARA.")
    result = _run(model, {"audio": base64.b64encode(audio).decode("ascii"),
                          "task": "transcribe", "language": "en"})
    text = result.get("text", "")
    if not isinstance(text, str) or not text.strip():
        raise VoiceError("No speech could be transcribed from that recording.")
    return text.strip()[:4000]


def _cache_dir() -> Path:
    root = os.getenv("MNH_DATA_DIR", "").strip() or os.getenv("TMPDIR", "").strip() or tempfile.gettempdir()
    path = Path(root) / "crara_tts_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(str(part).encode("utf-8", errors="ignore"))
        h.update(b"\0")
    return h.hexdigest()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int((os.getenv(name) or str(default)).strip())
    except Exception:
        return default


def _tts_enabled() -> bool:
    if os.getenv("QWEN_TTS_ENABLED") is not None:
        return _env_bool("QWEN_TTS_ENABLED", False)
    provider = (os.getenv("MNH_CLASSREP_TTS_PROVIDER") or TTS_PROVIDER_DEFAULT).strip().lower()
    return provider not in {"", "off", "disabled", "none", "false", "0"}


def _tts_provider() -> str:
    raw = (os.getenv("MNH_CLASSREP_TTS_PROVIDER") or "").strip().lower()
    if not raw and _env_bool("QWEN_TTS_ENABLED", False):
        raw = "qwen_remote"
    provider = raw or TTS_PROVIDER_DEFAULT
    aliases = {
        "qwen": "qwen3",
        "qwen3_tts": "qwen3",
        "openai": "openai_compatible",
        "vllm": "openai_compatible",
        "qwen_remote": "qwen_remote",
        "qwen-kaggle": "qwen_remote",
        "qwen_kaggle": "qwen_remote",
        "kaggle_qwen_tts": "qwen_remote",
        "kaggle-qwen-tts": "qwen_remote",
        "kaggle": "qwen_remote",
    }
    return aliases.get(provider, provider)


def _tts_fallback_enabled() -> bool:
    if os.getenv("QWEN_TTS_FALLBACK_ENABLED") is not None:
        return _env_bool("QWEN_TTS_FALLBACK_ENABLED", True)
    return os.getenv("MNH_CLASSREP_TTS_FALLBACK", "1").strip().lower() not in {"0", "false", "no", "off"}


def _remote_tts_base_url() -> str:
    return (os.getenv("MNH_CLASSREP_TTS_API_BASE_URL") or os.getenv("QWEN_TTS_BASE_URL") or "").strip().rstrip("/")


def _remote_tts_api_key() -> str:
    return (os.getenv("MNH_CLASSREP_TTS_API_KEY") or os.getenv("QWEN_TTS_API_KEY") or "").strip()


def _remote_tts_model() -> str:
    return (os.getenv("MNH_CLASSREP_TTS_API_MODEL") or os.getenv("QWEN_TTS_MODEL") or os.getenv("MNH_CLASSREP_QWEN3_MODEL") or QWEN3_TTS_MODEL_DEFAULT).strip()


def _remote_tts_timeout() -> int:
    return max(5, min(_env_int("QWEN_TTS_TIMEOUT_SECONDS", _env_int("MNH_CLASSREP_TTS_TIMEOUT_SECONDS", 120)), 300))


def _remote_tts_connect_timeout() -> int:
    return max(2, min(_env_int("QWEN_TTS_CONNECT_TIMEOUT_SECONDS", _env_int("MNH_CLASSREP_TTS_CONNECT_TIMEOUT_SECONDS", 10)), 60))


def _remote_tts_max_text() -> int:
    return max(100, min(_env_int("QWEN_TTS_MAX_TEXT_LENGTH", _env_int("MNH_CLASSREP_TTS_MAX_TEXT_LENGTH", 1800)), 8000))


def _remote_tts_health_path() -> str:
    path = (os.getenv("QWEN_TTS_HEALTH_PATH") or "/health").strip() or "/health"
    return path if path.startswith("/") else "/" + path


def _is_remote_tts_provider(provider: str | None = None) -> bool:
    p = (provider or _tts_provider()).strip().lower()
    return p in {"qwen_remote", "openai_compatible", "openai-compatible"}


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except Exception:
        return default


def _wav_bytes(samples, sample_rate: int) -> bytes:
    """Encode mono float/int waveform samples as 16-bit PCM WAV bytes."""
    import numpy as np  # optional dependency, present with qwen-tts

    arr = np.asarray(samples)
    if arr.ndim > 1:
        arr = arr.reshape(-1)
    if arr.dtype != np.int16:
        arr = np.clip(arr.astype(np.float32), -1.0, 1.0)
        arr = (arr * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(arr.tobytes())
    return buf.getvalue()


_FFMPEG_PATH_CACHE: str | None = None
_FFMPEG_PATH_CHECKED = False


def _find_ffmpeg() -> str | None:
    global _FFMPEG_PATH_CACHE, _FFMPEG_PATH_CHECKED
    if _FFMPEG_PATH_CHECKED:
        return _FFMPEG_PATH_CACHE
    configured = os.getenv("MNH_CLASSREP_FFMPEG_PATH", "").strip()
    candidates = [configured] if configured else []
    candidates += [
        shutil.which("ffmpeg") or "",
        r"C:\Users\AMINILOGY\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe",
    ]
    # Common Penrose/ScholarMW sibling locations
    workspace = Path(__file__).resolve().parents[4]
    for rel in ("Penrose_ScholarMW/ffmpeg.exe", "ffmpeg/bin/ffmpeg.exe", "bin/ffmpeg.exe"):
        candidates.append(str(workspace / rel))
    try:
        candidates += [str(p) for p in workspace.glob("**/ffmpeg.exe")]
    except Exception:
        pass
    seen = set()
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        try:
            p = Path(c)
            if p.exists():
                _FFMPEG_PATH_CACHE = str(p)
                _FFMPEG_PATH_CHECKED = True
                return _FFMPEG_PATH_CACHE
        except Exception:
            continue
    _FFMPEG_PATH_CACHE = None
    _FFMPEG_PATH_CHECKED = True
    return None


def _to_mp3(audio: bytes, media_type: str) -> tuple[bytes, str]:
    if "mpeg" in (media_type or "") or "mp3" in (media_type or ""):
        return audio, "audio/mpeg"
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return audio, media_type or "application/octet-stream"
    suffix = ".wav" if "wav" in (media_type or "") else ".audio"
    try:
        with tempfile.TemporaryDirectory(prefix="crara-tts-enc-") as td:
            src = Path(td) / f"in{suffix}"
            dst = Path(td) / "out.mp3"
            src.write_bytes(audio)
            cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
                   "-ac", "1", "-ar", "24000", "-b:a", "48k", str(dst)]
            subprocess.run(cmd, check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if dst.exists() and dst.stat().st_size > 0:
                return dst.read_bytes(), "audio/mpeg"
    except Exception:
        logger.warning("CRARA TTS mp3 encoding failed; returning original audio", exc_info=True)
    return audio, media_type or "application/octet-stream"


def _stitch_segments_with_pauses(segments: list[tuple[bytes, int]], pauses_ms: list[int]) -> tuple[bytes, str] | None:
    """Stitch WAV segments with silence pauses using ffmpeg. Returns mp3 bytes."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg or not segments:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="crara-tts-stitch-") as td:
            inputs = []
            filter_parts = []
            concat_inputs = []
            for i, (wav_bytes, pause_ms) in enumerate(segments):
                seg_path = Path(td) / f"seg_{i}.wav"
                seg_path.write_bytes(wav_bytes)
                inputs += ["-i", str(seg_path)]
                filter_parts.append(f"[{i}:a]aformat=sample_rates=24000:channel_layouts=mono[s{i}]")
                concat_inputs.append(f"[s{i}]")
                if pause_ms > 0:
                    sil_idx = len(segments) + i
                    dur = max(0.05, min(pause_ms / 1000.0, 2.0))
                    # silence input will be added later; mark placeholder
                    concat_inputs.append(f"[sil{i}]")
                    filter_parts.append(f"aevalsrc=0:d={dur}:s=24000:c=mono[sil{i}]")
            # add silence sources as inputs? easier: use anullsrc via filter_complex only
            # rebuild with lavfi silence inputs
            inputs = []
            filter_parts = []
            concat_inputs = []
            audio_input_count = 0
            for i, (wav_bytes, pause_ms) in enumerate(segments):
                seg_path = Path(td) / f"seg_{i}.wav"
                seg_path.write_bytes(wav_bytes)
                inputs += ["-i", str(seg_path)]
                filter_parts.append(f"[{audio_input_count}:a]aformat=sample_rates=24000:channel_layouts=mono[a{i}]")
                concat_inputs.append(f"[a{i}]")
                audio_input_count += 1
                if pause_ms > 0:
                    dur = max(0.05, min(pause_ms / 1000.0, 2.0))
                    inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=24000:cl=mono"]
                    filter_parts.append(f"[{audio_input_count}:a]aformat=sample_rates=24000:channel_layouts=mono[p{i}]")
                    concat_inputs.append(f"[p{i}]")
                    audio_input_count += 1
            filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(concat_inputs)}:v=0:a=1[out]")
            out = Path(td) / "out.mp3"
            cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *inputs,
                   "-filter_complex", ";".join(filter_parts), "-map", "[out]",
                   "-ac", "1", "-ar", "24000", "-b:a", "48k", str(out)]
            subprocess.run(cmd, check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if out.exists() and out.stat().st_size > 0:
                return out.read_bytes(), "audio/mpeg"
    except Exception:
        logger.warning("CRARA ffmpeg stitch failed", exc_info=True)
    return None


def _render_speech_plan_audio(plan) -> tuple[bytes, str] | None:
    """Optional local command-based rendering.

    Command contract: may contain {text_file} and {out_file} placeholders.
    """
    cmd = os.getenv("MNH_CLASSREP_LOCAL_TTS_CMD", "").strip()
    if not cmd:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="crara-tts-") as td:
            text_file = Path(td) / "speech.txt"
            out_file = Path(td) / "speech.mp3"
            text_file.write_text(plan.text, encoding="utf-8")
            rendered_cmd = cmd.format(text_file=str(text_file), out_file=str(out_file))
            subprocess.run(rendered_cmd, shell=True, check=True, timeout=120,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if out_file.exists() and out_file.stat().st_size > 0:
                return out_file.read_bytes(), "audio/mpeg"
    except Exception:
        logger.warning("CRARA local TTS command failed", exc_info=True)
    return None


def _qwen3_language(language: str) -> str:
    return "Chinese" if str(language or "EN").upper() == "NY" else "English"


def _load_qwen3_model(model_id: str):
    global _QWEN3_MODEL, _QWEN3_MODEL_ID, _QWEN3_LOCK
    if _QWEN3_MODEL is not None and _QWEN3_MODEL_ID == model_id:
        return _QWEN3_MODEL
    try:
        import threading
    except Exception as exc:
        raise VoiceError("Qwen3-TTS threading support unavailable.") from exc
    if _QWEN3_LOCK is None:
        _QWEN3_LOCK = threading.Lock()
    with _QWEN3_LOCK:
        if _QWEN3_MODEL is not None and _QWEN3_MODEL_ID == model_id:
            return _QWEN3_MODEL
        try:
            import torch
            from qwen_tts import Qwen3TTSModel
        except Exception as exc:
            raise VoiceError("Qwen3-TTS is not installed. Install qwen-tts and torch, or set MNH_CLASSREP_TTS_PROVIDER=cloudflare.") from exc

        requested_device = (os.getenv("MNH_CLASSREP_QWEN3_DEVICE") or "auto").strip().lower()
        if requested_device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            device = requested_device
        dtype_name = (os.getenv("MNH_CLASSREP_QWEN3_DTYPE") or ("bfloat16" if device.startswith("cuda") else "float32")).strip().lower()
        dtype = getattr(torch, dtype_name, torch.float32)
        attn = (os.getenv("MNH_CLASSREP_QWEN3_ATTN_IMPL") or ("flash_attention_2" if device.startswith("cuda") else "sdpa")).strip()
        kwargs = {"device_map": device, "dtype": dtype}
        if attn and attn.lower() not in {"none", "default"}:
            kwargs["attn_implementation"] = attn
        try:
            model = Qwen3TTSModel.from_pretrained(model_id, **kwargs)
        except Exception:
            kwargs.pop("attn_implementation", None)
            if dtype != torch.float32:
                kwargs["dtype"] = torch.float32
            try:
                model = Qwen3TTSModel.from_pretrained(model_id, **kwargs)
            except Exception as exc:
                raise VoiceError(f"Failed to load Qwen3-TTS model '{model_id}'.") from exc
        _QWEN3_MODEL = model
        _QWEN3_MODEL_ID = model_id
        logger.info("CRARA Qwen3-TTS loaded model=%s device=%s dtype=%s", model_id, device, kwargs.get("dtype"))
        return model


def _speak_qwen3(plan, *, voice: str | None = None) -> tuple[bytes, str]:
    model_id = (os.getenv("MNH_CLASSREP_QWEN3_MODEL") or QWEN3_TTS_MODEL_DEFAULT).strip()
    speaker = (voice or os.getenv("MNH_CLASSREP_QWEN3_SPEAKER") or QWEN3_TTS_SPEAKER_DEFAULT).strip() or QWEN3_TTS_SPEAKER_DEFAULT
    model = _load_qwen3_model(model_id)
    language = _qwen3_language(plan.language)

    instruct = None
    if plan.style == "expressive" or plan.mode == "presentation":
        instruct = "Speak clearly and naturally with professional pacing." if plan.mode == "presentation" else "Speak naturally and warmly."
        if plan.language == "NY":
            instruct += " Use clear Chichewa pronunciation."

    gen_kwargs = {}
    for name, cast in (("max_new_tokens", int), ("temperature", float), ("top_p", float), ("top_k", int)):
        val = os.getenv(f"MNH_CLASSREP_QWEN3_{name.upper()}", "").strip()
        if val:
            try:
                gen_kwargs[name] = cast(val)
            except Exception:
                pass

    def _synth_one(text: str):
        kwargs = {"text": text[:1800], "language": language, "speaker": speaker}
        if instruct:
            kwargs["instruct"] = instruct
        kwargs.update(gen_kwargs)
        try:
            wavs, sr = model.generate_custom_voice(**kwargs)
        except TypeError:
            kwargs.pop("instruct", None)
            wavs, sr = model.generate_custom_voice(**kwargs)
        except Exception as exc:
            raise VoiceError(f"Qwen3-TTS synthesis failed: {exc}") from exc
        if not wavs:
            raise VoiceError("Qwen3-TTS returned no audio.")
        return _wav_bytes(wavs[0], int(sr)), int(sr)

    # For natural pacing, synthesize sentence chunks and stitch pauses with ffmpeg.
    chunks = [c.strip() for c in re.split(r"(?<=[.!?])\s+", plan.text.strip()) if c.strip()]
    use_stitch = bool(_find_ffmpeg()) and len(chunks) > 1 and plan.style != "clear"
    if use_stitch:
        segments = []
        for i, chunk in enumerate(chunks):
            wav_bytes, _sr = _synth_one(chunk)
            pause_ms = 0
            if i < len(chunks) - 1:
                pause_ms = 420 if plan.mode == "presentation" else 220
                if plan.style == "expressive":
                    pause_ms = 360 if plan.mode == "presentation" else 180
            segments.append((wav_bytes, pause_ms))
        stitched = _stitch_segments_with_pauses(segments, [])
        if stitched is not None:
            return stitched

    wav_bytes, _sr = _synth_one(plan.text[:1800])
    return _to_mp3(wav_bytes, "audio/wav")


def _remote_health_check(*, force: bool = False) -> dict:
    base = _remote_tts_base_url()
    if not base:
        return {"configured": False, "healthy": False, "ready": False, "detail": "Remote TTS base URL is not configured."}
    cache_key = base + "|" + _remote_tts_health_path() + "|" + (_remote_tts_api_key()[:6])
    now = time.time()
    if not force:
        cached = _REMOTE_HEALTH_CACHE.get(cache_key)
        if cached and now - cached[0] < 30:
            return dict(cached[1])

    url = base + _remote_tts_health_path()
    headers = {}
    api_key = _remote_tts_api_key()
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = Request(url, headers=headers, method="GET")
    result = {
        "configured": True,
        "healthy": False,
        "ready": False,
        "status_code": None,
        "url": url,
        "detail": None,
    }
    try:
        with urlopen(req, timeout=min(_remote_tts_connect_timeout(), 15)) as response:
            body = response.read().decode("utf-8", errors="ignore")
            result["status_code"] = getattr(response, "status", 200)
            result["healthy"] = 200 <= int(result["status_code"]) < 300
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            if isinstance(payload, dict):
                ready = payload.get("ready")
                status = str(payload.get("status") or "").lower()
                result["ready"] = bool(ready) if ready is not None else (result["healthy"] and status in {"ok", "ready", "healthy", ""})
                result["model"] = payload.get("model_id") or payload.get("model")
                result["detail"] = payload.get("detail")
            else:
                result["ready"] = result["healthy"]
    except HTTPError as exc:
        result["status_code"] = exc.code
        result["detail"] = f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        result["detail"] = str(exc)[:200]
    except Exception as exc:
        result["detail"] = str(exc)[:200]
    _REMOTE_HEALTH_CACHE[cache_key] = (now, dict(result))
    return result


def tts_status(*, probe_remote: bool = False) -> dict:
    provider = _tts_provider()
    enabled = _tts_enabled()
    fallback = _tts_fallback_enabled()
    remote_configured = bool(_remote_tts_base_url())
    cloudflare_configured = bool(os.getenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "").strip() and os.getenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "").strip())
    status = {
        "enabled": enabled,
        "provider": provider,
        "configured_provider": provider,
        "fallback_enabled": fallback,
        "fallback_provider": "cloudflare" if fallback else None,
        "remote_configured": remote_configured,
        "cloudflare_configured": cloudflare_configured,
        "experimental": provider == "qwen_remote",
        "max_text_length": _remote_tts_max_text() if _is_remote_tts_provider(provider) else 1800,
        "model": _remote_tts_model() if _is_remote_tts_provider(provider) else (os.getenv("MNH_CLASSREP_CLOUDFLARE_TTS_MODEL") or "@cf/deepgram/aura-2-en").strip(),
    }
    if provider == "qwen_remote":
        status["warnings"] = [
            "Experimental remote provider. Kaggle sessions are temporary and may stop without notice.",
            "Do not treat this as an always-on production TTS service.",
        ]
    if probe_remote and enabled and _is_remote_tts_provider(provider):
        status["remote_health"] = _remote_health_check(force=False)
    return status


def _speak_openai_compatible(plan, *, voice: str | None = None, provider: str | None = None) -> tuple[bytes, str, dict]:
    base = _remote_tts_base_url()
    if not base:
        raise VoiceError("Remote Qwen3-TTS is not configured. Set QWEN_TTS_BASE_URL or MNH_CLASSREP_TTS_API_BASE_URL.")
    if provider == "qwen_remote":
        health = _remote_health_check(force=False)
        if not health.get("healthy"):
            raise VoiceError("Remote Qwen3-TTS service is not healthy. Start the Kaggle/service session and confirm /health.")

    url = base if base.endswith("/v1/audio/speech") else base + "/v1/audio/speech"
    api_key = _remote_tts_api_key()
    model = _remote_tts_model()
    speaker = (voice or os.getenv("MNH_CLASSREP_TTS_SPEAKER") or os.getenv("QWEN_TTS_DEFAULT_VOICE") or QWEN3_TTS_SPEAKER_DEFAULT).strip() or QWEN3_TTS_SPEAKER_DEFAULT
    max_text = _remote_tts_max_text()
    payload = {
        "model": model,
        "input": plan.text[:max_text],
        "voice": speaker,
        "response_format": "wav",
        "language": _qwen3_language(plan.language),
        "speed": 0.95 if plan.mode == "presentation" else 1.0,
    }
    if plan.mode == "presentation":
        payload["instructions"] = "Speak clearly, professionally, and with natural presentation pacing."
    elif plan.style == "expressive":
        payload["instructions"] = "Speak naturally and warmly with conversational pacing."

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    timeout = _remote_tts_timeout()
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            media_type = response.headers.get_content_type() or "audio/wav"
            provider_header = response.headers.get("X-Qwen-TTS-Model") or model
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="ignore")[:200]
        except Exception:
            pass
        raise VoiceError(f"Remote Qwen3-TTS returned HTTP {exc.code}. {detail}".strip()) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise VoiceError(f"Remote Qwen3-TTS service unavailable: {exc}") from exc
    if not body:
        raise VoiceError("Remote Qwen3-TTS returned no audio.")
    audio, media_type = _to_mp3(body, media_type)
    meta = {"provider": provider or "openai_compatible", "model": provider_header, "remote": True}
    return audio, media_type, meta


def _speak_cloudflare(plan, *, voice: str | None = None) -> tuple[bytes, str, dict]:
    model = (os.getenv("MNH_CLASSREP_CLOUDFLARE_TTS_MODEL") or
             "@cf/deepgram/aura-2-en").strip()
    speaker = (voice or os.getenv("MNH_CLASSREP_TTS_SPEAKER", "luna")).strip() or "luna"
    payload = {"text": plan.text[:1800], "encoding": "mp3", "speaker": speaker}
    # Some providers accept style/prosody hints; harmlessly ignored by others.
    if plan.mode == "presentation":
        payload["speed"] = 0.95
    elif plan.style == "expressive":
        payload["speed"] = 1.02
    try:
        audio, media_type = _run_audio(model, payload)
    except VoiceError:
        # Fallback to plain text if provider rejects enriched payload.
        audio, media_type = _run_audio(model, {"text": plan.plain_fallback[:1800], "encoding": "mp3", "speaker": speaker})
    return audio, media_type, {"provider": "cloudflare", "model": model, "remote": False}


def speak(text: str, *, mode: str = "chat", style: str = "natural",
          language: str = "EN", voice: str | None = None) -> tuple[bytes, str, dict]:
    plan = build_speech_plan(text, mode=mode, style=style, language=language)
    if not plan.plain_fallback:
        raise VoiceError("There is no text to speak.")

    provider = _tts_provider()
    if not _tts_enabled():
        raise VoiceError("Text-to-speech is disabled by configuration.")

    cache_voice = (voice or os.getenv("MNH_CLASSREP_TTS_SPEAKER") or os.getenv("MNH_CLASSREP_QWEN3_SPEAKER") or os.getenv("QWEN_TTS_DEFAULT_VOICE") or "default").strip()
    cache_model = (_remote_tts_model() if _is_remote_tts_provider(provider) else (os.getenv("MNH_CLASSREP_QWEN3_MODEL") or os.getenv("MNH_CLASSREP_CLOUDFLARE_TTS_MODEL") or provider)).strip()
    key = _cache_key(provider, cache_model, cache_voice, plan.mode, plan.style, plan.language, plan.text)
    cache_file = _cache_dir() / f"{key}.mp3"
    if cache_file.exists() and cache_file.stat().st_size > 0:
        return cache_file.read_bytes(), "audio/mpeg", {"provider": provider, "model": cache_model, "cached": True, "remote": _is_remote_tts_provider(provider)}

    local = _render_speech_plan_audio(plan)
    if local is not None:
        audio, media_type = local
        try:
            cache_file.write_bytes(audio)
        except Exception:
            pass
        return audio, media_type, {"provider": "local_command", "model": "local_command", "cached": False, "remote": False}

    meta = {"provider": provider, "model": cache_model, "cached": False, "remote": _is_remote_tts_provider(provider)}
    try:
        if provider == "qwen3":
            audio, media_type = _speak_qwen3(plan, voice=voice)
            meta.update({"provider": "qwen3", "model": os.getenv("MNH_CLASSREP_QWEN3_MODEL") or QWEN3_TTS_MODEL_DEFAULT, "remote": False})
        elif _is_remote_tts_provider(provider):
            audio, media_type, remote_meta = _speak_openai_compatible(plan, voice=voice, provider=provider)
            meta.update(remote_meta)
        elif provider == "cloudflare":
            audio, media_type, cf_meta = _speak_cloudflare(plan, voice=voice)
            meta.update(cf_meta)
        else:
            raise VoiceError(f"Unsupported TTS provider '{provider}'.")
    except VoiceError as exc:
        if provider != "cloudflare" and _tts_fallback_enabled():
            logger.warning("CRARA TTS provider %s failed; falling back to Cloudflare: %s", provider, exc)
            audio, media_type, cf_meta = _speak_cloudflare(plan, voice=voice)
            meta.update(cf_meta)
            meta["fallback_from"] = provider
            meta["fallback_reason"] = str(exc)[:200]
        else:
            raise

    audio, media_type = _to_mp3(audio, media_type)
    try:
        cache_file.write_bytes(audio)
    except Exception:
        pass
    return audio, media_type, meta
