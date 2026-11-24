import asyncio

from starlette.requests import Request

from app import cloud_mirror


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


def _request(path: str = "/api/col/cells", query: bytes = b"") -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query,
        "headers": [(b"host", b"127.0.0.1:8017"), (b"cookie", b"cara_session=abc")],
        "client": ("127.0.0.1", 51000),
        "server": ("127.0.0.1", 8017),
    }, receive=_receive)


def test_upstream_url_keeps_path_and_query():
    request = _request(query=b"modules=STAT8100&week=0")
    url = cloud_mirror.upstream_http_url("https://mnh.example.onrender.com", request)
    assert url == "https://mnh.example.onrender.com/api/col/cells?modules=STAT8100&week=0"


def test_upstream_must_be_absolute_and_credential_free():
    for bad in ("", "mnh.example.onrender.com", "https://user:pass@mnh.example.onrender.com"):
        try:
            cloud_mirror.validate_upstream(bad)
        except ValueError:
            continue
        raise AssertionError("Accepted unsafe mirror URL: " + bad)


def test_upstream_cookie_is_made_usable_on_loopback():
    cookie = ("mnh_pc_guest=pc_guest_abc.def; Domain=mnh-smart-calendar-v13.onrender.com; "
              "Path=/; Secure; HttpOnly; SameSite=lax")
    local = cloud_mirror._localise_set_cookie(cookie)
    assert local.startswith("mnh_pc_guest=pc_guest_abc.def;")
    assert "HttpOnly" in local
    assert "SameSite=lax" in local
    assert "Path=/" in local
    assert "Secure" not in local
    assert "Domain=" not in local


def test_http_proxy_forwards_cookies_and_preserves_set_cookie(monkeypatch):
    captured = {}

    class FakeHeaders:
        def __init__(self, items):
            self._items = items

        def multi_items(self):
            return list(self._items)

    class FakeResponse:
        status_code = 200
        content = b'{"ok":true}'
        headers = FakeHeaders([
            ("content-type", "application/json"),
            ("content-encoding", "gzip"),
            ("content-length", "999"),
            ("set-cookie", "cara_session=xyz; Path=/; Secure; HttpOnly; SameSite=lax"),
        ])

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, method, url, headers=None, content=None):
            captured.update(method=method, url=url, headers=dict(headers or []), content=content)
            return FakeResponse()

    monkeypatch.setattr(cloud_mirror.httpx, "AsyncClient", FakeClient)

    response = asyncio.run(cloud_mirror.proxy_http(
        _request(), "https://mnh-smart-calendar-v13.onrender.com"))

    assert response.status_code == 200
    assert response.body == b'{"ok":true}'
    assert response.headers["x-mnh-cloud-mirror"] == "upstream"
    assert response.headers["content-type"] == "application/json"
    assert response.headers["set-cookie"] == "cara_session=xyz; Path=/; HttpOnly; SameSite=lax"
    assert "content-encoding" not in response.headers
    assert captured["url"] == "https://mnh-smart-calendar-v13.onrender.com/api/col/cells"
    assert captured["headers"]["cookie"] == "cara_session=abc"
