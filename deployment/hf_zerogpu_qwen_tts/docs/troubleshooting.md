# Troubleshooting - HF ZeroGPU Qwen3-TTS

## 401 Missing/Invalid bearer token
- Ensure MNH sends `Authorization: Bearer <token>`.
- Ensure Space Secret `QWEN_TTS_API_KEY` matches MNH `QWEN_TTS_API_KEY` / `MNH_CLASSREP_TTS_API_KEY`.
- Do not put the token in frontend code.

## 503 Model not loaded / qwen-tts not installed
- Check Space logs. Confirm `torch` and `qwen-tts` installed in the Space runtime.
- First request on ZeroGPU may take longer due to model load + GPU allocation.
- Keep MNH fallback enabled.

## Quota exhausted / slow/queued
- HF ZeroGPU free quota is limited (documented as 5 GPU-min/day for free accounts; verify current docs). It is **GPU processing time**.
- `xlarge` consumes 2x quota.
- Use 5-slide tests, 0.6B model, and cache/pre-generate audio in MNH.
- CRARA should fall back to Cloudflare when configured.

## 400 Model not loaded/configured
- MNH `QWEN_TTS_MODEL` / request `model` must match the Space `QWEN_TTS_MODEL_ID`.
- The Space intentionally avoids hot model switching on limited GPU.

## Audio format issues
- Request `response_format=wav` or `mp3`. MP3 requires ffmpeg in runtime; if unavailable, use wav.
- MNH CRARA adapter can normalize audio to MP3 when ffmpeg is available on MNH backend.

## Voice clone not working
- Default model is CustomVoice. Voice cloning requires a clone-capable model and `QWEN_TTS_ALLOW_VOICE_CLONE=true`.
- Do not upload private audio without consent.

## MNH shows remote unavailable
- Check `/health` and `/ready` on the Space URL.
- Check `QWEN_TTS_BASE_URL` has no trailing typo and is reachable from MNH backend.
- Confirm Space is awake/build succeeded and not sleeping/errored.
- Keep `MNH_CLASSREP_TTS_FALLBACK=1` so CRARA remains usable.
