# Hugging Face ZeroGPU Deployment Guide (Experimental Qwen3-TTS for MNH Calendar-v13)

This guide deploys the isolated experimental Qwen3-TTS API as a **Hugging Face Gradio Space with ZeroGPU**. It is for testing/small-scale use (e.g., 5 CRARA slides), not always-on production.

## 1. Prerequisites

- Hugging Face account in good standing.
- **Verified email** and account **older than 30 days** for the free ZeroGPU hosting path (verify current HF policy).
- No credit card is stated as required for the free ZeroGPU hosting path, but verify current HF terms before relying on it.
- A strong random `QWEN_TTS_API_KEY`.
- Access to MNH backend env vars.

## 2. Create a ZeroGPU Space

1. Create a new Space on Hugging Face.
2. Select **Gradio** SDK (ZeroGPU `@spaces.GPU` is documented for Gradio Spaces).
3. Choose a hardware setting compatible with ZeroGPU (follow current HF UI/docs; ZeroGPU hardware enables dynamic GPU allocation).
4. Keep the Space private if needed, but remember MNH backend must be able to reach it.

## 3. Copy files

Copy the contents of `deployment/hf_zerogpu_qwen_tts/` into the Space repo root:

- `app.py`
- `requirements.txt`
- `server/`
- `scripts/` (optional)
- `docs/` (optional)

The Space entrypoint is `app.py`. It serves:
- Gradio UI at `/gradio`
- FastAPI endpoints at `/health`, `/ready`, `/v1/models`, `/v1/audio/speech`

## 4. Configure Space Secrets / Variables

In Space Settings, add **Secrets** (not public variables):

- `QWEN_TTS_API_KEY` = strong random token (required)
- Optional:
  - `QWEN_TTS_MODEL_ID=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` (recommended for quota)
  - `QWEN_TTS_DEFAULT_VOICE=Ryan`
  - `QWEN_TTS_DEFAULT_LANGUAGE=English`
  - `QWEN_TTS_MAX_TEXT_LENGTH=1800`
  - `QWEN_TTS_ZEROGPU_DURATION=120` (seconds; keep conservative)
  - `QWEN_TTS_REQUIRE_AUTH=true`

Do **not** hardcode secrets in files.

## 5. Install/runtime notes

`requirements.txt` includes FastAPI/Gradio basics. For real inference, ensure the Space installs compatible:

- `torch` (CUDA build compatible with HF runtime)
- `qwen-tts`
- `accelerate`, `transformers`, `huggingface_hub` as needed

Model download/load can take time on first cold start. ZeroGPU allocates GPU only when the decorated synthesis function runs.

## 6. Verify the Space

After build/start:

```bash
curl https://<your-space>.hf.space/health
curl https://<your-space>.hf.space/ready
curl -H "Authorization: Bearer <QWEN_TTS_API_KEY>" https://<your-space>.hf.space/v1/models
```

Speech smoke test:

```bash
curl -X POST https://<your-space>.hf.space/v1/audio/speech \
  -H "Authorization: Bearer <QWEN_TTS_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice","input":"Hello from MNH CRARA.","voice":"Ryan","response_format":"wav"}' \
  --output test.wav
```

Or use:

```bash
python deployment/hf_zerogpu_qwen_tts/scripts/health_check.py --base-url https://<your-space>.hf.space --api-key <QWEN_TTS_API_KEY> --speak
```

## 7. Configure MNH Calendar-v13

Set MNH backend env vars (Render/local `.env`, never commit secrets):

```env
QWEN_TTS_ENABLED=true
QWEN_TTS_BASE_URL=https://<your-space>.hf.space
QWEN_TTS_API_KEY=<same-token>
QWEN_TTS_MODEL=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
QWEN_TTS_TIMEOUT_SECONDS=120
QWEN_TTS_CONNECT_TIMEOUT_SECONDS=10
QWEN_TTS_MAX_TEXT_LENGTH=1800
QWEN_TTS_FALLBACK_ENABLED=true

MNH_CLASSREP_TTS_PROVIDER=qwen_remote
MNH_CLASSREP_TTS_API_BASE_URL=https://<your-space>.hf.space
MNH_CLASSREP_TTS_API_KEY=<same-token>
MNH_CLASSREP_TTS_API_MODEL=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
MNH_CLASSREP_TTS_FALLBACK=1
```

Restart MNH backend. CRARA should report remote Qwen as configured/healthy when available and fallback when unavailable.

## 8. 5-slide test recommendation

- Test with **5 slides first**.
- Use **Qwen3-TTS 0.6B CustomVoice**.
- Pre-generate/cache slide audio where possible; repeated playback should hit MNH cache.
- Keep **Cloudflare fallback enabled**.
- Monitor quota: 5 GPU-min/day is GPU processing time, resets 24h after first GPU use.

## 9. Shutdown / safety

- Remove/revoke the Space secret if no longer used.
- Set `MNH_CLASSREP_TTS_PROVIDER=cloudflare` or disable Qwen remote in MNH.
- Do not treat this Space as permanent/always-on production hosting.
