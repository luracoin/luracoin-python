"""Local web wallet and narrow gateway to the authenticated node RPC."""

from __future__ import annotations

import asyncio
import binascii
import hmac
import json
import logging
import secrets
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlsplit

import aiohttp
from aiohttp import web

from luracoin.config import Config
from luracoin.wallet import is_valid_address

DEFAULT_WALLET_HOST = "127.0.0.1"
DEFAULT_WALLET_PORT = 8080
MAX_WALLET_REQUEST_BODY = 16 * 1024
MAX_WALLET_RPC_RESPONSE = 2_000_000
MAX_WALLET_STATIC_FILE = 16 * 1024 * 1024
WALLET_RPC_TIMEOUT = 5.0
WALLET_SESSION_COOKIE = "luracoin_wallet_session"

_ALLOWED_BROWSER_HOSTS = {"127.0.0.1", "localhost"}
_ALLOWED_BIND_HOSTS = {"127.0.0.1", "0.0.0.0"}
_ALLOWED_RPC_HOSTS = {"127.0.0.1", "::1", "localhost"}
_API_PREFIX = "/wallet-api"

log = logging.getLogger(__name__)


class WalletWebServer:
    """Serve a Vite build and a constrained, cookie-protected RPC gateway."""

    def __init__(
        self,
        *,
        wallet_dir: str,
        rpc_host: str,
        rpc_port: int,
        rpc_token: str,
        host: str = DEFAULT_WALLET_HOST,
        port: int = DEFAULT_WALLET_PORT,
        request_timeout: float = WALLET_RPC_TIMEOUT,
        max_response_size: int = MAX_WALLET_RPC_RESPONSE,
        max_static_file: int = MAX_WALLET_STATIC_FILE,
    ) -> None:
        if host not in _ALLOWED_BIND_HOSTS:
            raise ValueError(
                "Wallet web may only bind to 127.0.0.1 or 0.0.0.0"
            )
        if rpc_host not in _ALLOWED_RPC_HOSTS:
            raise ValueError("Wallet RPC target must be a loopback address")
        if not 1 <= int(port) <= 65_535:
            raise ValueError("Wallet port must be between 1 and 65535")
        if not 1 <= int(rpc_port) <= 65_535:
            raise ValueError("RPC port must be between 1 and 65535")
        if not isinstance(rpc_token, str) or len(rpc_token) < 32:
            raise ValueError("RPC token must contain at least 32 characters")
        if request_timeout <= 0:
            raise ValueError("Wallet RPC timeout must be positive")
        if max_response_size <= 0 or max_static_file <= 0:
            raise ValueError("Wallet response limits must be positive")

        try:
            root = Path(wallet_dir).expanduser().resolve(strict=True)
        except OSError as exc:
            raise ValueError("Wallet directory does not exist") from exc
        index = root / "index.html"
        if not root.is_dir() or not index.is_file():
            raise ValueError("Wallet directory must contain index.html")
        data_dir = Path(Config.DATA_DIR).expanduser().resolve()
        try:
            data_dir.relative_to(root)
        except ValueError:
            pass
        else:
            raise ValueError(
                "Wallet directory must not contain the node data directory"
            )

        self.wallet_dir = root
        self.host = host
        self.port = int(port)
        self.rpc_host = rpc_host
        self.rpc_port = int(rpc_port)
        self._rpc_token = rpc_token
        self._session_secret = secrets.token_urlsafe(48)
        self._request_timeout = float(request_timeout)
        self._max_response_size = int(max_response_size)
        self._max_static_file = int(max_static_file)
        self._runner = None
        self._site = None
        self._client = None

    @property
    def rpc_url(self) -> str:
        host = f"[{self.rpc_host}]" if ":" in self.rpc_host else self.rpc_host
        return f"http://{host}:{self.rpc_port}"

    @web.middleware
    async def _security(self, request: web.Request, handler):
        host, host_port = self._validate_host(request)
        self._validate_browser_context(request, host, host_port)
        if request.path.startswith(_API_PREFIX):
            supplied = request.cookies.get(WALLET_SESSION_COOKIE, "")
            if not hmac.compare_digest(supplied, self._session_secret):
                return self._json_error(401, "wallet_session_required")

        response = await handler(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'none'; object-src 'none'; "
            "frame-ancestors 'none'; connect-src 'self'; "
            "img-src 'self' data:; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; form-action 'self'",
        )
        if request.path.startswith(_API_PREFIX):
            response.headers["Cache-Control"] = "no-store"
        elif self._is_static_path(request.path) and response.status < 400:
            response.set_cookie(
                WALLET_SESSION_COOKIE,
                self._session_secret,
                httponly=True,
                samesite="Strict",
                path="/",
            )
        return response

    def create_app(self) -> web.Application:
        app = web.Application(
            middlewares=[self._security],
            client_max_size=MAX_WALLET_REQUEST_BODY,
        )
        app.on_startup.append(self._open_client)
        app.on_cleanup.append(self._close_client)
        app.router.add_get("/wallet-health", self._health)
        app.router.add_get(f"{_API_PREFIX}/status", self._status)
        app.router.add_get(
            f"{_API_PREFIX}/accounts/{{address}}", self._account
        )
        app.router.add_get(
            f"{_API_PREFIX}/accounts/{{address}}/transactions",
            self._account_transactions,
        )
        app.router.add_post(
            f"{_API_PREFIX}/transactions", self._submit_transaction
        )
        app.router.add_get("/{path:.*}", self._serve_spa)
        return app

    async def start(self) -> None:
        if self._runner is not None:
            return
        runner = web.AppRunner(self.create_app(), access_log=None)
        try:
            await runner.setup()
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
        except Exception:
            await runner.cleanup()
            raise
        self._runner = runner
        self._site = site

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
        self._runner = None
        self._site = None

    async def _open_client(self, _app: web.Application) -> None:
        if self._client is None:
            self._client = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._request_timeout),
                trust_env=False,
            )

    async def _close_client(self, _app: web.Application) -> None:
        if self._client is not None:
            await self._client.close()
        self._client = None

    async def _health(self, _request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "service": "wallet-web"})

    async def _status(self, request: web.Request) -> web.Response:
        self._reject_query(request)
        self._reject_body(request)
        return await self._proxy("GET", "/v1/status")

    async def _account(self, request: web.Request) -> web.Response:
        self._reject_query(request)
        self._reject_body(request)
        address = self._validated_address(request.match_info["address"])
        return await self._proxy(
            "GET", f"/v1/accounts/{quote(address, safe='')}"
        )

    async def _account_transactions(
        self, request: web.Request
    ) -> web.Response:
        self._reject_body(request)
        address = self._validated_address(request.match_info["address"])
        unknown = set(request.query) - {"limit", "cursor"}
        if unknown:
            return self._json_error(400, "invalid_query")

        params = {}
        if "limit" in request.query:
            values = request.query.getall("limit")
            if len(values) != 1:
                return self._json_error(400, "invalid_limit")
            try:
                limit = int(values[0])
            except ValueError:
                return self._json_error(400, "invalid_limit")
            if not 1 <= limit <= 200:
                return self._json_error(400, "invalid_limit")
            params["limit"] = str(limit)
        if "cursor" in request.query:
            values = request.query.getall("cursor")
            if len(values) != 1:
                return self._json_error(400, "invalid_cursor")
            cursor = values[0]
            if cursor != "latest":
                try:
                    raw_cursor = binascii.unhexlify(cursor)
                except (binascii.Error, ValueError):
                    return self._json_error(400, "invalid_cursor")
                if len(raw_cursor) != 6:
                    return self._json_error(400, "invalid_cursor")
            params["cursor"] = cursor
        return await self._proxy(
            "GET",
            f"/v1/accounts/{quote(address, safe='')}/transactions",
            params=params,
        )

    async def _submit_transaction(self, request: web.Request) -> web.Response:
        self._reject_query(request)
        if request.content_type != "application/json":
            return self._json_error(415, "json_required")
        try:
            raw_body = await request.read()
            body = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._json_error(400, "invalid_transaction_encoding")
        if not isinstance(body, dict) or set(body) != {"raw"}:
            return self._json_error(400, "invalid_transaction_encoding")
        raw = body["raw"]
        if (
            not isinstance(raw, str)
            or len(raw) != Config.TRANSACTION_LENGTH * 2
        ):
            return self._json_error(400, "invalid_transaction_length")
        try:
            decoded = bytes.fromhex(raw)
        except ValueError:
            return self._json_error(400, "invalid_transaction_encoding")
        if len(decoded) != Config.TRANSACTION_LENGTH:
            return self._json_error(400, "invalid_transaction_encoding")
        payload = json.dumps({"raw": raw}, separators=(",", ":")).encode()
        return await self._proxy(
            "POST",
            "/v1/transactions",
            body=payload,
        )

    async def _proxy(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        body: Optional[bytes] = None,
    ) -> web.Response:
        if self._client is None:
            return self._json_error(503, "wallet_gateway_unavailable")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._rpc_token}",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            async with self._client.request(
                method,
                f"{self.rpc_url}{path}",
                params=params,
                data=body,
                headers=headers,
                allow_redirects=False,
            ) as upstream:
                if 300 <= upstream.status < 400:
                    return self._json_error(502, "invalid_rpc_response")
                if upstream.content_type != "application/json":
                    return self._json_error(502, "invalid_rpc_response")
                if (
                    upstream.content_length is not None
                    and upstream.content_length > self._max_response_size
                ):
                    return self._json_error(502, "rpc_response_too_large")
                response_body = await upstream.content.read(
                    self._max_response_size + 1
                )
                if len(response_body) > self._max_response_size:
                    return self._json_error(502, "rpc_response_too_large")
                try:
                    decoded_response = json.loads(response_body)
                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                    RecursionError,
                ):
                    return self._json_error(502, "invalid_rpc_response")
                if self._contains_rpc_token(decoded_response):
                    log.error("RPC response contained its bearer credential")
                    return self._json_error(502, "invalid_rpc_response")
                return web.Response(
                    body=response_body,
                    status=upstream.status,
                    content_type="application/json",
                )
        except asyncio.TimeoutError:
            return self._json_error(504, "rpc_timeout")
        except aiohttp.ClientError:
            log.warning("Wallet gateway could not reach the local RPC")
            return self._json_error(502, "rpc_unavailable")

    async def _serve_spa(self, request: web.Request) -> web.StreamResponse:
        raw_path = request.match_info.get("path", "")
        if raw_path == "v1" or raw_path.startswith("v1/"):
            raise web.HTTPNotFound()
        if raw_path == "wallet-api" or raw_path.startswith("wallet-api/"):
            raise web.HTTPNotFound()
        if any(part.startswith(".") for part in Path(raw_path).parts):
            raise web.HTTPNotFound()

        try:
            candidate = (self.wallet_dir / raw_path).resolve()
            candidate.relative_to(self.wallet_dir)
        except (OSError, ValueError):
            raise web.HTTPNotFound()
        if candidate.name.casefold() == "rpc.token":
            raise web.HTTPNotFound()

        if candidate.is_file():
            return self._static_response(candidate)
        if not raw_path:
            return self._static_response(self.wallet_dir / "index.html")
        if Path(raw_path).suffix or "text/html" not in request.headers.get(
            "Accept", "text/html"
        ):
            raise web.HTTPNotFound()
        return self._static_response(self.wallet_dir / "index.html")

    def _static_response(self, path: Path) -> web.FileResponse:
        try:
            size = path.stat().st_size
        except OSError:
            raise web.HTTPNotFound()
        if size > self._max_static_file:
            raise web.HTTPRequestEntityTooLarge(
                max_size=self._max_static_file,
                actual_size=size,
            )
        response = web.FileResponse(path)
        if path.name == "index.html":
            response.headers["Cache-Control"] = "no-store"
        return response

    def _validate_host(self, request: web.Request) -> tuple:
        raw_host = request.headers.get("Host", "")
        try:
            parsed = urlsplit(f"//{raw_host}")
            port = parsed.port
        except ValueError:
            raise web.HTTPBadRequest(text="Invalid Host")
        hostname = (parsed.hostname or "").lower()
        if (
            not raw_host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or hostname not in _ALLOWED_BROWSER_HOSTS
        ):
            raise web.HTTPBadRequest(text="Invalid Host")
        return hostname, port

    def _validate_browser_context(
        self,
        request: web.Request,
        host: str,
        host_port: Optional[int],
    ) -> None:
        fetch_site = request.headers.get("Sec-Fetch-Site")
        if request.path.startswith(_API_PREFIX):
            if fetch_site != "same-origin":
                raise web.HTTPForbidden(text="Invalid browser context")
        elif fetch_site not in {None, "none", "same-origin"}:
            raise web.HTTPForbidden(text="Invalid browser context")

        origin = request.headers.get("Origin")
        if request.method == "POST" and not origin:
            raise web.HTTPForbidden(text="Origin required")
        if not origin:
            return
        try:
            parsed = urlsplit(origin)
            origin_port = parsed.port
        except ValueError:
            raise web.HTTPForbidden(text="Invalid Origin")
        origin_host = (parsed.hostname or "").lower()
        default_port = 443 if request.scheme == "https" else 80
        if (
            parsed.scheme != request.scheme
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or origin_host not in _ALLOWED_BROWSER_HOSTS
            or origin_host != host
            or (origin_port or default_port) != (host_port or default_port)
        ):
            raise web.HTTPForbidden(text="Invalid Origin")

    @staticmethod
    def _validated_address(address: str) -> str:
        if not is_valid_address(address):
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "invalid_address"}),
                content_type="application/json",
            )
        return address

    @staticmethod
    def _reject_query(request: web.Request) -> None:
        if request.query_string:
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "invalid_query"}),
                content_type="application/json",
            )

    @staticmethod
    def _reject_body(request: web.Request) -> None:
        if request.can_read_body:
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "request_body_not_allowed"}),
                content_type="application/json",
            )

    @staticmethod
    def _json_error(status: int, error: str) -> web.Response:
        return web.json_response({"error": error}, status=status)

    def _contains_rpc_token(self, payload) -> bool:
        pending = [payload]
        while pending:
            value = pending.pop()
            if isinstance(value, str):
                if self._rpc_token in value:
                    return True
            elif isinstance(value, dict):
                pending.extend(value.keys())
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
        return False

    @staticmethod
    def _is_static_path(path: str) -> bool:
        return not path.startswith(_API_PREFIX) and path != "/wallet-health"
