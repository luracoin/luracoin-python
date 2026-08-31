import asyncio
import json
import os
from types import SimpleNamespace

import pytest
from aiohttp import CookieJar, web
from aiohttp.test_utils import TestClient, TestServer

from luracoin.config import Config
from luracoin.wallet_web import (
    MAX_WALLET_REQUEST_BODY,
    WALLET_SESSION_COOKIE,
    WalletWebServer,
)


TOKEN = "r" * 48
KNOWN_ADDRESS = "LM6jpRVE2TYoZKc1onms6d6N9rXh16r38N"


@pytest.fixture
def wallet_dist(tmp_path):
    root = tmp_path / "dist"
    assets = root / "assets"
    assets.mkdir(parents=True)
    (root / "index.html").write_text(
        "<!doctype html><div id='root'>wallet</div>", encoding="utf-8"
    )
    (assets / "app.js").write_text("window.wallet = true;", encoding="utf-8")
    return root


@pytest.fixture
async def rpc_upstream():
    requests = []
    state = {"mode": "normal"}

    async def handler(request):
        body = await request.read()
        requests.append(
            {
                "method": request.method,
                "path": request.path,
                "query": list(request.query.items()),
                "authorization": request.headers.get("Authorization"),
                "content_type": request.content_type,
                "body": body,
            }
        )
        mode = state["mode"]
        if mode == "slow":
            await asyncio.sleep(0.1)
        if mode == "large":
            return web.json_response({"value": "x" * 512})
        if mode == "text":
            return web.Response(text="not-json", content_type="text/plain")
        if mode == "redirect":
            raise web.HTTPFound("http://example.invalid/")
        if mode == "token":
            return web.json_response({"credential": TOKEN})
        if mode == "escaped_token":
            encoded_token = "".join("\\u0072" for _ in TOKEN)
            return web.Response(
                body=f'{{"credential":"{encoded_token}"}}'.encode(),
                content_type="application/json",
            )

        status = 202 if request.method == "POST" else 200
        response = web.json_response(
            {
                "method": request.method,
                "path": request.path,
                "query": list(request.query.items()),
                "body": json.loads(body) if body else None,
            },
            status=status,
        )
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Set-Cookie"] = "upstream=must-not-pass"
        response.headers["X-Upstream-Only"] = "secret"
        return response

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    server = TestServer(app)
    await server.start_server()
    try:
        yield SimpleNamespace(
            server=server,
            requests=requests,
            state=state,
        )
    finally:
        await server.close()


async def _start_wallet(wallet_dist, rpc_upstream, **kwargs):
    server = WalletWebServer(
        wallet_dir=str(wallet_dist),
        rpc_host="127.0.0.1",
        rpc_port=rpc_upstream.server.port,
        rpc_token=TOKEN,
        **kwargs,
    )
    client = TestClient(
        TestServer(server.create_app()), cookie_jar=CookieJar(unsafe=True)
    )
    await client.start_server()
    return server, client


@pytest.fixture
async def wallet_client(wallet_dist, rpc_upstream):
    server, client = await _start_wallet(wallet_dist, rpc_upstream)
    try:
        yield SimpleNamespace(
            server=server,
            client=client,
            upstream=rpc_upstream,
        )
    finally:
        await client.close()


def _origin(client):
    url = client.make_url("/")
    return f"{url.scheme}://{url.host}:{url.port}"


def _browser_headers(client, *, site="same-origin", origin=True):
    headers = {"Sec-Fetch-Site": site}
    if origin:
        headers["Origin"] = _origin(client)
    return headers


async def _bootstrap(client):
    response = await client.get("/", headers={"Sec-Fetch-Site": "none"})
    assert response.status == 200
    return response


def test_wallet_server_rejects_unsafe_configuration(wallet_dist):
    common = {
        "wallet_dir": str(wallet_dist),
        "rpc_host": "127.0.0.1",
        "rpc_port": 18444,
        "rpc_token": TOKEN,
    }
    with pytest.raises(ValueError, match="only bind"):
        WalletWebServer(**common, host="192.0.2.10")
    with pytest.raises(ValueError, match="loopback"):
        WalletWebServer(**{**common, "rpc_host": "node.internal"})
    with pytest.raises(ValueError, match="at least 32"):
        WalletWebServer(**{**common, "rpc_token": "short"})
    with pytest.raises(ValueError, match="positive"):
        WalletWebServer(**common, request_timeout=0)
    with pytest.raises(ValueError, match="between 1 and 65535"):
        WalletWebServer(**common, port=0)


def test_wallet_server_requires_vite_index(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(ValueError, match="does not exist"):
        WalletWebServer(
            wallet_dir=str(missing),
            rpc_host="127.0.0.1",
            rpc_port=18444,
            rpc_token=TOKEN,
        )

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="contain index.html"):
        WalletWebServer(
            wallet_dir=str(empty),
            rpc_host="127.0.0.1",
            rpc_port=18444,
            rpc_token=TOKEN,
        )


def test_wallet_server_refuses_a_root_containing_node_data(tmp_path):
    root = tmp_path / "public"
    root.mkdir()
    (root / "index.html").write_text("wallet", encoding="utf-8")
    Config.DATA_DIR = str(root / "private-node-data")

    with pytest.raises(ValueError, match="must not contain"):
        WalletWebServer(
            wallet_dir=str(root),
            rpc_host="127.0.0.1",
            rpc_port=18444,
            rpc_token=TOKEN,
        )


@pytest.mark.asyncio
async def test_static_spa_sets_strict_httponly_cookie_and_security_headers(
    wallet_client,
):
    response = await _bootstrap(wallet_client.client)
    assert "wallet" in await response.text()
    cookie = response.headers["Set-Cookie"]
    assert f"{WALLET_SESSION_COOKIE}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie
    assert TOKEN not in cookie
    assert TOKEN not in await response.text()
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert (
        "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    )
    assert "Access-Control-Allow-Origin" not in response.headers

    asset = await wallet_client.client.get(
        "/assets/app.js", headers={"Sec-Fetch-Site": "same-origin"}
    )
    assert asset.status == 200
    assert await asset.text() == "window.wallet = true;"

    fallback = await wallet_client.client.get(
        "/send/confirm",
        headers={"Accept": "text/html", "Sec-Fetch-Site": "same-origin"},
    )
    assert fallback.status == 200
    assert "wallet" in await fallback.text()

    missing_asset = await wallet_client.client.get(
        "/assets/missing.js", headers={"Sec-Fetch-Site": "same-origin"}
    )
    assert missing_asset.status == 404


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="symlink semantics")
async def test_static_server_refuses_symlinks_outside_dist(
    wallet_dist, rpc_upstream
):
    secret = wallet_dist.parent / "rpc.token"
    secret.write_text(TOKEN, encoding="utf-8")
    (wallet_dist / "leak.txt").symlink_to(secret)
    _server, client = await _start_wallet(wallet_dist, rpc_upstream)
    try:
        response = await client.get(
            "/leak.txt", headers={"Sec-Fetch-Site": "none"}
        )
        assert response.status == 404
        assert TOKEN not in await response.text()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_static_server_never_serves_rpc_token_named_file(
    wallet_dist, rpc_upstream
):
    (wallet_dist / "rpc.token").write_text(TOKEN, encoding="utf-8")
    _server, client = await _start_wallet(wallet_dist, rpc_upstream)
    try:
        response = await client.get(
            "/rpc.token", headers={"Sec-Fetch-Site": "none"}
        )
        assert response.status == 404
        assert TOKEN not in await response.text()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cookie_rotates_with_each_server_process(
    wallet_dist, rpc_upstream
):
    _first_server, first = await _start_wallet(wallet_dist, rpc_upstream)
    _second_server, second = await _start_wallet(wallet_dist, rpc_upstream)
    try:
        first_cookie = (await _bootstrap(first)).headers["Set-Cookie"]
        second_cookie = (await _bootstrap(second)).headers["Set-Cookie"]
        assert first_cookie != second_cookie
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_host_fetch_metadata_origin_and_cookie_are_required(
    wallet_client,
):
    client = wallet_client.client
    evil_host = await client.get(
        "/", headers={"Host": "wallet.example", "Sec-Fetch-Site": "none"}
    )
    assert evil_host.status == 400
    assert "Set-Cookie" not in evil_host.headers

    cross_site = await client.get(
        "/", headers={"Sec-Fetch-Site": "cross-site"}
    )
    assert cross_site.status == 403
    assert "Set-Cookie" not in cross_site.headers

    missing_cookie = await client.get(
        "/wallet-api/status", headers=_browser_headers(client)
    )
    assert missing_cookie.status == 401

    await _bootstrap(client)
    missing_fetch_metadata = await client.get("/wallet-api/status")
    assert missing_fetch_metadata.status == 403

    wrong_origin = await client.get(
        "/wallet-api/status",
        headers={
            "Sec-Fetch-Site": "same-origin",
            "Origin": "http://localhost:1",
        },
    )
    assert wrong_origin.status == 403

    no_origin_post = await client.post(
        "/wallet-api/transactions",
        headers={
            "Sec-Fetch-Site": "same-origin",
            "Content-Type": "application/json",
        },
        json={"raw": "00" * 213},
    )
    assert no_origin_post.status == 403

    options = await client.options(
        "/wallet-api/status", headers=_browser_headers(client)
    )
    assert options.status == 405
    assert "Access-Control-Allow-Origin" not in options.headers


@pytest.mark.asyncio
async def test_gateway_forwards_only_explicit_wallet_contract(wallet_client):
    client = wallet_client.client
    upstream = wallet_client.upstream
    await _bootstrap(client)
    headers = {
        **_browser_headers(client),
        "Authorization": "Bearer browser-controlled-value",
    }

    status = await client.get("/wallet-api/status", headers=headers)
    assert status.status == 200
    assert (await status.json())["path"] == "/v1/status"
    assert "Access-Control-Allow-Origin" not in status.headers
    assert "Set-Cookie" not in status.headers
    assert "X-Upstream-Only" not in status.headers

    account = await client.get(
        f"/wallet-api/accounts/{KNOWN_ADDRESS}", headers=headers
    )
    assert account.status == 200
    assert (await account.json())["path"] == f"/v1/accounts/{KNOWN_ADDRESS}"

    history = await client.get(
        f"/wallet-api/accounts/{KNOWN_ADDRESS}/transactions"
        "?limit=17&cursor=000000070000",
        headers=headers,
    )
    assert history.status == 200
    assert (await history.json())["query"] == [
        ["limit", "17"],
        ["cursor", "000000070000"],
    ]

    transaction = await client.post(
        "/wallet-api/transactions",
        headers={**headers, "Content-Type": "application/json"},
        json={"raw": "00" * 213},
    )
    assert transaction.status == 202
    assert (await transaction.json())["body"] == {"raw": "00" * 213}

    assert len(upstream.requests) == 4
    assert all(
        request["authorization"] == f"Bearer {TOKEN}"
        for request in upstream.requests
    )
    assert upstream.requests[-1]["content_type"] == "application/json"

    direct_rpc = await client.get(
        "/v1/status",
        headers={"Accept": "text/html", "Sec-Fetch-Site": "same-origin"},
    )
    assert direct_rpc.status == 404
    unknown_gateway = await client.get("/wallet-api/blocks/0", headers=headers)
    assert unknown_gateway.status == 404
    assert len(upstream.requests) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        f"/wallet-api/accounts/{KNOWN_ADDRESS}/transactions?unknown=1",
        f"/wallet-api/accounts/{KNOWN_ADDRESS}/transactions?limit=0",
        f"/wallet-api/accounts/{KNOWN_ADDRESS}/transactions?limit=1&limit=2",
        f"/wallet-api/accounts/{KNOWN_ADDRESS}/transactions?cursor=bad",
        "/wallet-api/status?extra=1",
        "/wallet-api/accounts/not-an-address",
    ],
)
async def test_gateway_rejects_noncanonical_reads_without_rpc(
    wallet_client, path
):
    await _bootstrap(wallet_client.client)
    response = await wallet_client.client.get(
        path, headers=_browser_headers(wallet_client.client)
    )
    assert response.status == 400
    assert wallet_client.upstream.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "content_type", "expected"),
    [
        (b"not-json", "application/json", 400),
        (
            json.dumps({"raw": "00", "extra": True}).encode(),
            "application/json",
            400,
        ),
        (json.dumps({"raw": "00"}).encode(), "application/json", 400),
        (json.dumps({"raw": "zz" * 213}).encode(), "application/json", 400),
        (json.dumps({"raw": "00" * 213}).encode(), "text/plain", 415),
    ],
)
async def test_gateway_rejects_noncanonical_posts_without_rpc(
    wallet_client, body, content_type, expected
):
    await _bootstrap(wallet_client.client)
    response = await wallet_client.client.post(
        "/wallet-api/transactions",
        data=body,
        headers={
            **_browser_headers(wallet_client.client),
            "Content-Type": content_type,
        },
    )
    assert response.status == expected
    assert wallet_client.upstream.requests == []


@pytest.mark.asyncio
async def test_gateway_limits_request_and_static_file_sizes(
    wallet_dist, rpc_upstream
):
    _server, client = await _start_wallet(wallet_dist, rpc_upstream)
    try:
        await _bootstrap(client)
        response = await client.post(
            "/wallet-api/transactions",
            data=b"x" * (MAX_WALLET_REQUEST_BODY + 1),
            headers={
                **_browser_headers(client),
                "Content-Type": "application/json",
            },
        )
        assert response.status == 413
        assert rpc_upstream.requests == []
    finally:
        await client.close()

    _server, small_static_client = await _start_wallet(
        wallet_dist, rpc_upstream, max_static_file=4
    )
    try:
        response = await small_static_client.get(
            "/", headers={"Sec-Fetch-Site": "none"}
        )
        assert response.status == 413
    finally:
        await small_static_client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_error"),
    [
        ("large", "rpc_response_too_large"),
        ("text", "invalid_rpc_response"),
        ("redirect", "invalid_rpc_response"),
        ("token", "invalid_rpc_response"),
        ("escaped_token", "invalid_rpc_response"),
        ("slow", "rpc_timeout"),
    ],
)
async def test_gateway_rejects_unsafe_or_unbounded_rpc_responses(
    wallet_dist, rpc_upstream, mode, expected_error
):
    rpc_upstream.state["mode"] = mode
    options = {"max_response_size": 64 if mode == "large" else 1024}
    if mode == "slow":
        options["request_timeout"] = 0.01
    _server, client = await _start_wallet(wallet_dist, rpc_upstream, **options)
    try:
        await _bootstrap(client)
        response = await client.get(
            "/wallet-api/status", headers=_browser_headers(client)
        )
        assert response.status in {502, 504}
        payload = await response.json()
        assert payload["error"] == expected_error
        assert TOKEN not in await response.text()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_wallet_health_is_host_guarded_but_needs_no_cookie(
    wallet_client,
):
    response = await wallet_client.client.get(
        "/wallet-health", headers={"Sec-Fetch-Site": "none"}
    )
    assert response.status == 200
    assert await response.json() == {"ok": True, "service": "wallet-web"}
    assert "Set-Cookie" not in response.headers

    rejected = await wallet_client.client.get(
        "/wallet-health",
        headers={"Host": "example.invalid", "Sec-Fetch-Site": "none"},
    )
    assert rejected.status == 400
