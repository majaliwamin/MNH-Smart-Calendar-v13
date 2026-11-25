from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
from pathlib import Path


def _pip_install(*args: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", *args])


def _ensure_runtime_deps() -> None:
    # HF Spaces Gradio 6.x image requires huggingface-hub>=1.16, while qwen-tts/transformers 4.x
    # metadata requires huggingface-hub<1.0. Install the Qwen stack at runtime with --no-deps to
    # avoid resolver conflicts; HF base image already provides torch/gradio/spaces/hub.
    if importlib.util.find_spec("qwen_tts") is None:
        if importlib.util.find_spec("transformers") is None:
            _pip_install("--no-deps", "transformers==4.57.3")
        _pip_install("--no-deps", "qwen-tts==0.1.1")


_ensure_runtime_deps()

import gradio as gr

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app import app as fastapi_app  # noqa: E402
from server.config import settings  # noqa: E402


def _ui_status() -> str:
    model = settings.model_id
    auth = "required" if settings.require_auth else "disabled (not recommended)"
    return (
        f"Model: {model}\n"
        f"Auth: Bearer token {auth}\n"
        "Endpoints: /health, /ready, /v1/models, /v1/audio/speech\n"
        "This Space is experimental and quota-limited. Do not use as always-on production hosting."
    )


with gr.Blocks(title="MNH Qwen3-TTS ZeroGPU", analytics_enabled=False) as demo:
    gr.Markdown(
        """
# MNH Qwen3-TTS Experimental Endpoint

This Hugging Face ZeroGPU Space exposes a small OpenAI-compatible speech API for MNH Calendar-v13.

- **Experimental:** not always-on production.
- **Quota:** ZeroGPU GPU time is limited and shared by quota rules; 5 GPU-min/day means GPU processing time.
- **Security:** set `QWEN_TTS_API_KEY` as a Space Secret and call with `Authorization: Bearer <token>`.

Use MNH `MNH_CLASSREP_TTS_PROVIDER=qwen_remote` and point `QWEN_TTS_BASE_URL` to this Space URL.
"""
    )
    gr.Textbox(label="Service status", value=_ui_status(), lines=6, interactive=False)
    gr.Markdown(
        """
**MNH config snippet**

    MNH_CLASSREP_TTS_PROVIDER=qwen_remote
    MNH_CLASSREP_TTS_API_BASE_URL=https://<your-space>.hf.space
    MNH_CLASSREP_TTS_API_KEY=<same-token-as-QWEN_TTS_API_KEY>
    MNH_CLASSREP_TTS_API_MODEL=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
    MNH_CLASSREP_TTS_FALLBACK=1
"""
    )


# Mount FastAPI API onto the Gradio Blocks. `asgi_app` serves both API routes and /gradio UI.
asgi_app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")
app = asgi_app  # alias for HF/uvicorn discovery

_launch_lock = threading.Lock()
_launch_started = False
_launch_done = threading.Event()


def _launch(*args, **kwargs):
    global _launch_started
    with _launch_lock:
        if _launch_started:
            should_run = False
        else:
            _launch_started = True
            should_run = True

    if not should_run:
        # Another launch already owns the server; keep process alive if HF expects non-blocking return.
        if kwargs.get("prevent_thread_lock"):
            return demo
        _launch_done.wait()
        return demo

    import uvicorn

    host = kwargs.get("server_name") or "0.0.0.0"
    port = int(kwargs.get("server_port") or os.getenv("PORT") or 7860)
    config = uvicorn.Config(asgi_app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    try:
        server.run()
    except BaseException as exc:
        err_no = getattr(exc, "errno", None)
        err_text = str(exc).lower()
        is_bind = err_no == 98 or "address already in use" in err_text
        is_exit = isinstance(exc, SystemExit)
        if is_bind or (is_exit and os.getenv("SPACE_ID")):
            # Port is owned by HF/another launcher, or uvicorn sys.exited on bind failure.
            # Keep process alive to prevent HF restart loop.
            print(f"[app.py] Server bind/start failed ({exc!r}); keeping process alive.", file=sys.stderr, flush=True)
            _launch_done.wait()
            return demo
        raise
    finally:
        # Reached only on normal server stop/crash we didn't intentionally keep alive.
        if not _launch_done.is_set():
            _launch_done.set()
    return demo


# HF Gradio SDK calls demo.launch(); serve the combined FastAPI+Gradio app instead.
demo.launch = _launch  # type: ignore[assignment]

if __name__ == "__main__":
    demo.launch()
