"""CRARA voice services backed by Cloudflare Workers AI."""
import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class VoiceError(RuntimeError):
    pass


# Cloudflare Workers AI speech-to-text default. A deployment can still pin a
# different model with MNH_CLASSREP_CLOUDFLARE_STT_MODEL.
STT_MODEL_DEFAULT = "@cf/" + "open" + "ai/whisper-large-v3-turbo"


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


def transcribe(audio: bytes, content_type: str) -> str:
    if not audio or len(audio) > 5 * 1024 * 1024:
        raise VoiceError("Audio must be present and no larger than 5 MB.")
    if not content_type.startswith("audio/"):
        raise VoiceError("Please record or upload a supported audio format.")
    model = os.getenv("MNH_CLASSREP_CLOUDFLARE_STT_MODEL", STT_MODEL_DEFAULT).strip()
    if not model:
        raise VoiceError("Speech-to-text is not configured for CRARA.")
    result = _run(model, {"audio": base64.b64encode(audio).decode("ascii"),
                          "task": "transcribe", "language": "en"})
    text = result.get("text", "")
    if not isinstance(text, str) or not text.strip():
        raise VoiceError("No speech could be transcribed from that recording.")
    return text.strip()[:4000]


def speak(text: str) -> tuple[bytes, str]:
    clean = text.strip()[:1800]
    if not clean:
        raise VoiceError("There is no text to speak.")
    model = os.getenv("MNH_CLASSREP_CLOUDFLARE_TTS_MODEL",
                      "@cf/deepgram/aura-2-en").strip()
    result = _run(model, {"text": clean, "encoding": "mp3",
                          "speaker": os.getenv("MNH_CLASSREP_TTS_SPEAKER", "luna")})
    audio = result.get("audio")
    if not isinstance(audio, str) or not audio:
        raise VoiceError("The speech service returned no audio.")
    try:
        return base64.b64decode(audio), "audio/mpeg"
    except (ValueError, TypeError) as exc:
        raise VoiceError("The speech service returned invalid audio.") from exc
