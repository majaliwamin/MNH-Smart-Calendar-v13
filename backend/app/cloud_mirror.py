"""Optional same-origin mirror of the deployed MNH Calendar API.

The Windows PWA is installed against ``http://127.0.0.1:8017``. When that local
server is started with ``MNH_CLOUD_MIRROR_URL``, its HTTP API and chat WebSocket
are forwarded to the deployed HTTPS service. The browser still talks only to
127.0.0.1, so the existing frontend, cookies and WebSockets keep working while
schedules, public chat and CRARA all use the authoritative cloud database.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, Response

HOP_BY_HOP = frozenset({
    "connection", "content-encoding", "content-length", "host", "keep-alive",
    "proxy-authenticate", "proxy-authorization", "te", "trailer",
    "transfer-encoding", "upgrade",
})
LOCAL_API_PASSTHROUGH = frozenset({"/api/build", "/api/health/ready"})
MIRROR_HEADER = "X-MNH-Cloud-Mirror"
TIMEOUT = httpx.Timeout(120.0, connect=10.0)


def validate_upstream(upstream: str):
    """Return parsed upstream URL, rejecting credentials and unexpected schemes."""
    parts = urlsplit(upstream.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("MNH_CLOUD_MIRROR_URL must be an absolute http(s) URL.")
    if parts.username or parts.password or "@" in parts.netloc:
        raise ValueError("MNH_CLOUD_MIRROR_URL must not contain credentials.")
    return parts


def upstream_http_url(upstream: str, request: Request) -> str:
    parts = validate_upstream(upstream)
    raw_path = request.scope.get("raw_path") or b""
    path = raw_path.decode("latin-1") if raw_path else request.url.path
    if not path.startswith("/"):
        path = "/" + path
    base = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, base + path, request.url.query, ""))


def upstream_websocket_url(upstream: str, websocket: WebSocket) -> str:
    parts = validate_upstream(upstream)
    raw_path = websocket.scope.get("raw_path") or b""
    path = raw_path.decode("latin-1") if raw_path else websocket.url.path
    if not path.startswith("/"):
        path = "/" + path
    scheme = "wss" if parts.scheme == "https" else "ws"
    base = parts.path.rstrip("/")
    return urlunsplit((scheme, parts.netloc, base + path, websocket.url.query, ""))


def _localise_set_cookie(value: str) -> str:
    """Make upstream host-only cookies usable by the loopback HTTP app.

    The upstream HTTPS service correctly emits Secure cookies and may set a
    production Domain. The browser talks to 127.0.0.1 over loopback HTTP, so
    keep the signed value but drop only those two attributes. HttpOnly and
    SameSite remain intact.
    """
    parts = [part.strip() for part in str(value or "").split(";") if part.strip()]
    if not parts:
        return ""
    kept = [parts[0]]
    for part in parts[1:]:
        lowered = part.lower()
        if lowered == "secure" or lowered.startswith("secure=") or lowered.startswith("domain="):
            continue
        kept.append(part)
    return "; ".join(kept)


async def proxy_http(request: Request, upstream: str) -> Response:
    try:
        target = upstream_http_url(upstream, request)
        headers = [
            (name, value)
            for name, value in request.headers.items()
            if name.lower() not in HOP_BY_HOP and name.lower() != "accept-encoding"
        ]
        body = await request.body()
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
            response = await client.request(request.method, target, headers=headers, content=body)
    except (httpx.HTTPError, ValueError) as error:
        return JSONResponse(
            status_code=503,
            content={"error": "The cloud data service is unavailable. Check the internet connection and try again."},
            headers={MIRROR_HEADER: "error", "X-MNH-Cloud-Mirror-Error": str(error)[:200]},
        )

    response_headers: dict[str, str] = {}
    set_cookies: list[str] = []
    for name, value in response.headers.multi_items():
        lowered = name.lower()
        if lowered in HOP_BY_HOP:
            continue
        if lowered == "set-cookie":
            local_cookie = _localise_set_cookie(value)
            if local_cookie:
                set_cookies.append(local_cookie)
        elif lowered not in response_headers:
            response_headers[lowered] = value
    response_headers[MIRROR_HEADER] = "upstream"

    proxied = Response(content=response.content, status_code=response.status_code,
                       headers=response_headers)
    for cookie in set_cookies:
        proxied.raw_headers.append((b"set-cookie", cookie.encode("latin-1")))
    return proxied


async def proxy_websocket(websocket: WebSocket, upstream: str) -> None:
    await websocket.accept()
    try:
        target = upstream_websocket_url(upstream, websocket)
    except ValueError:
        await websocket.close(code=1011)
        return

    headers = []
    cookie = websocket.headers.get("cookie")
    if cookie:
        headers.append(("Cookie", cookie))
    authorization = websocket.headers.get("authorization")
    if authorization:
        headers.append(("Authorization", authorization))

    connect_options = {"open_timeout": 10, "ping_interval": 20, "close_timeout": 5}
    try:
        import websockets

        try:
            connection = websockets.connect(target, additional_headers=headers, **connect_options)
        except TypeError:  # websockets < 14 used extra_headers
            connection = websockets.connect(target, extra_headers=headers, **connect_options)
        async with connection as remote:
            await _relay_websocket(websocket, remote)
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


async def _relay_websocket(websocket: WebSocket, remote) -> None:
    async def local_to_remote():
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("text") is not None:
                await remote.send(message["text"])
            elif message.get("bytes") is not None:
                await remote.send(message["bytes"])

    async def remote_to_local():
        async for message in remote:
            if isinstance(message, str):
                await websocket.send_text(message)
            else:
                await websocket.send_bytes(message)

    tasks = [asyncio.create_task(local_to_remote()), asyncio.create_task(remote_to_local())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()


def install_websocket_proxy(app: FastAPI, upstream: str) -> None:
    """Register the catch-all WebSocket proxy before the local API routers."""
    validate_upstream(upstream)

    @app.websocket("/api/{path:path}", name="cloud_mirror_websocket")
    async def cloud_mirror_websocket(websocket: WebSocket, path: str):
        await proxy_websocket(websocket, upstream)
