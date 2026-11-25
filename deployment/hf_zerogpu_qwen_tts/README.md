# Qwen3-TTS Hugging Face ZeroGPU Experimental Deployment

This directory contains an **isolated, experimental** Qwen3-TTS inference service for MNH Calendar-v13, packaged for a **Hugging Face Gradio Space with ZeroGPU**.

It exposes a small OpenAI-compatible speech API (`/v1/audio/speech`) that MNH can call through its existing `qwen_remote` / `openai_compatible` CRARA TTS adapter.

## Why this option

- **No credit card required** for the free hosting path (HF account in good standing: verified email, account older than 30 days; verify current HF terms).
- **Recurring daily quota**: ZeroGPU gives free accounts a daily GPU quota (documented by HF as 5 min/day for free accounts, resetting 24 hours after first GPU use; verify current HF docs).
- **MNH-compatible**: reuses the existing MNH remote TTS adapter; no MNH backend architecture change required.

## Important limitations

- **Experimental / not always-on production.** ZeroGPU is shared/dynamic; expect cold starts, queueing, quota exhaustion, and platform limits.
- **5 GPU-minutes/day means GPU processing time**, not 5 minutes of audio and not 5 minutes of Space uptime. GPU time is consumed only while the `@spaces.GPU` function runs.
- **5 slides is a reasonable test**, but actual capacity depends on text length, model, warm/cold state, and GPU size. `xlarge` consumes 2x quota.
- **MNH backend uses one configured token/quota budget.** If MNH backend calls the Space, the Space/account quota behind that deployment is shared by MNH requests. Cache/pre-generate audio where possible.
- **No secrets in code.** Set `QWEN_TTS_API_KEY` as a Hugging Face Space Secret.
- **Authentication required by default.** Requests without a valid bearer token are rejected.

## Contents

- `app.py` - Hugging Face Space entrypoint (Gradio UI + mounted FastAPI API).
- `server/` - FastAPI inference service and Qwen3-TTS wrapper.
- `scripts/health_check.py` - health/readiness/model/speech probe.
- `docs/deployment.md` - beginner HF ZeroGPU deployment guide.
- `docs/troubleshooting.md` - common failures.

## Local smoke test (API shape, no ZeroGPU required)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r deployment/hf_zerogpu_qwen_tts/server/requirements.txt
set QWEN_TTS_API_KEY=change-me
set QWEN_TTS_MODEL_ID=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
python deployment/hf_zerogpu_qwen_tts/app.py
```

Probe:

```bash
python deployment/hf_zerogpu_qwen_tts/scripts/health_check.py --base-url http://127.0.0.1:7860 --api-key change-me
```

Actual Qwen3-TTS inference requires model dependencies and a compatible GPU/runtime. On HF ZeroGPU, GPU is allocated dynamically when the `@spaces.GPU` function runs.
