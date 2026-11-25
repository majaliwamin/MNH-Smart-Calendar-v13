from __future__ import annotations

import base64
import io
import logging
import os
import tempfile
import wave
from dataclasses import dataclass
from typing import Any

from .config import settings

logger = logging.getLogger(__name__)

try:
    import spaces  # type: ignore

    HAS_SPACES_GPU = True
except Exception:  # pragma: no cover - optional on HF ZeroGPU
    spaces = None
    HAS_SPACES_GPU = False


class InferenceError(RuntimeError):
    pass


@dataclass
class SynthesisResult:
    audio: bytes
    media_type: str
    sample_rate: int
    model_id: str
    voice: str


class QwenTTSService:
    def __init__(self) -> None:
        self.model = None
        self.model_id = settings.model_id
        self.load_error: str | None = None
        self.last_error: str | None = None
        self._torch = None

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def gpu_info(self) -> dict[str, Any]:
        info = {"gpu_available": False, "gpu_name": None, "vram_gb": None}
        try:
            import torch

            self._torch = torch
            if torch.cuda.is_available():
                info["gpu_available"] = True
                info["gpu_name"] = torch.cuda.get_device_name(0)
                try:
                    props = torch.cuda.get_device_properties(0)
                    info["vram_gb"] = round(props.total_memory / (1024 ** 3), 2)
                except Exception:
                    pass
        except Exception as exc:
            info["detail"] = f"torch unavailable: {exc}"
        return info

    def _resolve_device_dtype(self):
        import torch

        device = settings.device
        if device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype_name = settings.dtype
        if dtype_name == "auto":
            dtype_name = "bfloat16" if str(device).startswith("cuda") else "float32"
        dtype = getattr(torch, dtype_name, torch.float32)
        return device, dtype

    def load(self) -> None:
        if self.loaded:
            return
        try:
            from qwen_tts import Qwen3TTSModel
        except Exception as exc:
            self.load_error = f"qwen-tts is not installed: {exc}"
            raise InferenceError(self.load_error) from exc

        device, dtype = self._resolve_device_dtype()
        kwargs: dict[str, Any] = {"device_map": device, "dtype": dtype}
        attn = settings.attn_impl
        if attn and attn != "auto":
            kwargs["attn_implementation"] = attn
        elif str(device).startswith("cuda"):
            kwargs["attn_implementation"] = "flash_attention_2"

        logger.info("Loading Qwen3-TTS model_id=%s device=%s dtype=%s kwargs=%s", self.model_id, device, dtype, kwargs)
        try:
            self.model = Qwen3TTSModel.from_pretrained(self.model_id, **kwargs)
        except Exception:
            kwargs.pop("attn_implementation", None)
            if dtype.__class__.__name__ != "float32":
                import torch

                kwargs["dtype"] = torch.float32
            self.model = Qwen3TTSModel.from_pretrained(self.model_id, **kwargs)
        self.load_error = None
        self.last_error = None
        logger.info("Qwen3-TTS model loaded: %s", self.model_id)

    def unload(self) -> None:
        self.model = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _wav_bytes(self, samples, sample_rate: int) -> bytes:
        import numpy as np

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

    def _encode(self, wav_bytes: bytes, response_format: str) -> tuple[bytes, str]:
        fmt = (response_format or "wav").lower().strip()
        if fmt == "wav":
            return wav_bytes, "audio/wav"
        if fmt == "pcm":
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                return wf.readframes(wf.getnframes()), "audio/L16;rate=24000;channels=1"
        if fmt == "mp3":
            try:
                import subprocess

                with tempfile.TemporaryDirectory(prefix="qwen-tts-") as td:
                    src = os.path.join(td, "in.wav")
                    dst = os.path.join(td, "out.mp3")
                    with open(src, "wb") as f:
                        f.write(wav_bytes)
                    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-ac", "1", "-ar", "24000", "-b:a", "48k", dst]
                    subprocess.run(cmd, check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    with open(dst, "rb") as f:
                        return f.read(), "audio/mpeg"
            except Exception as exc:
                raise InferenceError(f"MP3 encoding unavailable: {exc}") from exc
        raise InferenceError(f"Unsupported response_format '{response_format}'.")

    def _synthesize_impl(self, *, text: str, voice: str | None, language: str | None, instructions: str | None,
                         response_format: str, ref_audio_base64: str | None = None, ref_text: str | None = None) -> SynthesisResult:
        if not self.loaded:
            self.load()
        assert self.model is not None

        text = (text or "").strip()
        if not text:
            raise InferenceError("Text is required.")
        if len(text) > settings.max_text_length:
            raise InferenceError(f"Text exceeds max length ({settings.max_text_length}).")
        voice = (voice or settings.default_voice).strip() or settings.default_voice
        language = (language or settings.default_language).strip() or settings.default_language

        kwargs: dict[str, Any] = {
            "text": text,
            "language": language,
            "speaker": voice,
        }
        if instructions:
            kwargs["instruct"] = instructions[:500]
        if settings.max_new_tokens > 0:
            kwargs["max_new_tokens"] = settings.max_new_tokens

        if ref_audio_base64 and settings.allow_voice_clone:
            try:
                ref_bytes = base64.b64decode(ref_audio_base64)
                with tempfile.NamedTemporaryFile(prefix="qwen-ref-", suffix=".wav", delete=False) as tmp:
                    tmp.write(ref_bytes)
                    ref_path = tmp.name
                try:
                    clone_kwargs = {
                        "text": text,
                        "language": language,
                        "ref_audio": ref_path,
                    }
                    if ref_text:
                        clone_kwargs["ref_text"] = ref_text[:1000]
                    wavs, sr = self.model.generate_voice_clone(**clone_kwargs)
                finally:
                    try:
                        os.remove(ref_path)
                    except Exception:
                        pass
            except Exception as exc:
                self.last_error = str(exc)
                raise InferenceError(f"Voice clone synthesis failed: {exc}") from exc
        else:
            try:
                wavs, sr = self.model.generate_custom_voice(**kwargs)
            except TypeError:
                kwargs.pop("instruct", None)
                wavs, sr = self.model.generate_custom_voice(**kwargs)
            except Exception as exc:
                self.last_error = str(exc)
                raise InferenceError(f"Qwen3-TTS synthesis failed: {exc}") from exc

        if not wavs:
            raise InferenceError("Qwen3-TTS returned no audio.")
        wav_bytes = self._wav_bytes(wavs[0], int(sr))
        audio, media_type = self._encode(wav_bytes, response_format)
        self.last_error = None
        return SynthesisResult(audio=audio, media_type=media_type, sample_rate=int(sr), model_id=self.model_id, voice=voice)

    def synthesize(self, **kwargs) -> SynthesisResult:
        # On Hugging Face ZeroGPU, GPU time is allocated only inside a @spaces.GPU function.
        # Locally or on regular GPU hosts, run directly.
        if HAS_SPACES_GPU:
            duration = max(20, min(int(settings.zerogpu_duration), 300))

            @spaces.GPU(duration=duration)
            def _gpu_synthesize(**inner_kwargs):
                return self._synthesize_impl(**inner_kwargs)

            return _gpu_synthesize(**kwargs)
        return self._synthesize_impl(**kwargs)


service = QwenTTSService()
