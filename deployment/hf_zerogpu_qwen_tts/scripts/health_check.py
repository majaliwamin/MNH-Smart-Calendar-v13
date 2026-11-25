from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _request(url: str, *, method: str = "GET", headers: dict | None = None, data: bytes | None = None, timeout: int = 30):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, dict(resp.headers.items()), body
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return exc.code, dict(exc.headers.items()), body


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Qwen3-TTS HF ZeroGPU service")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", default=os.getenv("QWEN_TTS_API_KEY", ""))
    parser.add_argument("--speak", action="store_true", help="Run a tiny /v1/audio/speech smoke test")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    auth = {"Authorization": f"Bearer {args.api_key}"} if args.api_key else {}

    for path in ["/health", "/ready"]:
        status, _, body = _request(base + path, timeout=20)
        print(f"{path} -> {status}")
        print(body.decode("utf-8", errors="ignore")[:500])

    status, _, body = _request(base + "/v1/models", headers=auth, timeout=20)
    print(f"/v1/models -> {status}")
    print(body.decode("utf-8", errors="ignore")[:500])

    if args.speak:
        payload = json.dumps({
            "model": os.getenv("QWEN_TTS_MODEL_ID", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"),
            "input": "Hello from MNH Calendar experimental Qwen TTS health check.",
            "voice": os.getenv("QWEN_TTS_DEFAULT_VOICE", "Ryan"),
            "response_format": "wav",
        }).encode("utf-8")
        headers = {"Content-Type": "application/json", **auth}
        status, resp_headers, body = _request(base + "/v1/audio/speech", method="POST", headers=headers, data=payload, timeout=180)
        print(f"/v1/audio/speech -> {status}, bytes={len(body)}")
        for k in ["X-Qwen-TTS-Model", "X-Qwen-TTS-Latency-Ms", "Content-Type"]:
            if k in resp_headers:
                print(f"{k}: {resp_headers[k]}")
        if status >= 400:
            print(body.decode("utf-8", errors="ignore")[:500])
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
