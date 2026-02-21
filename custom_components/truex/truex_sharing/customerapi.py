"""OPENAPI CUBE REST client using standard HMAC-SHA256 auth.

Matches the Postman collection endpoints and signing method.
Two signing modes:
  - Token mode (no access_token): clientId + timestamp + signStr
  - Business mode (with access_token): clientId + accessToken + timestamp + signStr
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp

from .customerlogging import logger


# ── Token Info ───────────────────────────────────────────────


class TrueXTokenInfo:
    """Token information for OPENAPI CUBE."""

    def __init__(
        self,
        token_response: dict[str, Any] | None = None,
    ) -> None:
        """Initialize token info."""
        if token_response:
            self.access_token: str = token_response.get(
                "access_token", ""
            )
            self.refresh_token: str = token_response.get(
                "refresh_token", ""
            )
            self.uid: str = token_response.get("uid", "")
            # Calculate absolute expiry timestamp (ms)
            t = token_response.get("t", 0)
            expire_secs = token_response.get(
                "expire_time", 0
            )
            self.expire_time: int = expire_secs
            self.expire_at: int = t + expire_secs * 1000
        else:
            self.access_token = ""
            self.refresh_token = ""
            self.uid = ""
            self.expire_time = 0
            self.expire_at = 0

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (60s buffer)."""
        if not self.access_token:
            return True
        now_ms = int(time.time() * 1000)
        return self.expire_at - 60_000 <= now_ms

    def to_dict(self) -> dict[str, Any]:
        """Serialize token info for config entry storage."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "uid": self.uid,
            "expire_time": self.expire_time,
            "expire_at": self.expire_at,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any]
    ) -> TrueXTokenInfo:
        """Deserialize token info from stored dict."""
        info = cls()
        info.access_token = data.get(
            "access_token", ""
        )
        info.refresh_token = data.get(
            "refresh_token", ""
        )
        info.uid = data.get("uid", "")
        info.expire_time = data.get("expire_time", 0)
        info.expire_at = data.get("expire_at", 0)
        return info


class TrueXAPIError(Exception):
    """Exception raised for TrueX API errors."""


class SharingTokenListener:
    """Listener for token refresh events."""

    def update_token(
        self, token_info: dict[str, Any]
    ) -> None:
        """Called when token is refreshed."""


# ── HMAC-SHA256 Signing ─────────────────────────────────────


def _calc_sign(
    client_id: str,
    secret: str,
    timestamp: str,
    nonce: str,
    sign_str: str,
    access_token: str = "",
) -> str:
    """Calculate HMAC-SHA256 signature.

    Token mode:    str = clientId + timestamp + nonce + signStr
    Business mode: str = clientId + accessToken + timestamp + nonce + signStr
    """
    if access_token:
        raw = (
            client_id
            + access_token
            + timestamp
            + nonce
            + sign_str
        )
    else:
        raw = (
            client_id + timestamp + nonce + sign_str
        )

    h = hmac.new(
        secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    )
    return h.hexdigest().upper()


def _string_to_sign(
    method: str,
    path: str,
    query: dict[str, Any] | None = None,
    body: str = "",
) -> str:
    """Build the string-to-sign per Tuya OPENAPI spec.

    Format: METHOD\nSHA256(body)\nheaders_str\nurl
    """
    # SHA-256 of body content
    body_hash = hashlib.sha256(
        body.encode("utf-8")
    ).hexdigest()

    # Build sorted query string
    url = path
    if query:
        sorted_keys = sorted(query.keys())
        qs = "&".join(
            f"{k}={query[k]}" for k in sorted_keys
        )
        url = f"{path}?{qs}"

    # No custom signature headers
    headers_str = ""

    return f"{method}\n{body_hash}\n{headers_str}\n{url}"


# ── Main API Client ─────────────────────────────────────────


class CustomerApi:
    """OPENAPI CUBE REST API client.

    Uses standard HMAC-SHA256 signing as per the Postman
    collection, with `/v1.0/` endpoints.
    """

    def __init__(
        self,
        api_url: str,
        client_id: str,
        secret: str,
        schema: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self.api_url = api_url.rstrip("/")
        self.client_id = client_id
        self.secret = secret
        self.schema = schema
        self.token_info = TrueXTokenInfo()
        self.token_listener: (
            SharingTokenListener | None
        ) = None
        self._session = session
        self._owns_session = session is None
        self._refreshing_token = False

    async def _ensure_session(
        self,
    ) -> aiohttp.ClientSession:
        """Ensure an aiohttp session exists."""
        if (
            self._session is None
            or self._session.closed
        ):
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if (
            self._owns_session
            and self._session
            and not self._session.closed
        ):
            await self._session.close()

    # ── Token Management ────────────────────────────────

    async def get_access_token(self) -> dict[str, Any]:
        """Get initial access token (grant_type=1).

        Uses token-mode signing (no access_token in sign).
        """
        path = "/v1.0/token"
        query_params = {"grant_type": "1"}
        timestamp = str(int(time.time() * 1000))

        sign_str = _string_to_sign(
            "GET", path, query_params
        )
        sign = _calc_sign(
            self.client_id,
            self.secret,
            timestamp,
            "",
            sign_str,
        )

        headers = {
            "client_id": self.client_id,
            "sign": sign,
            "t": timestamp,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json",
        }

        session = await self._ensure_session()
        url = (
            f"{self.api_url}{path}"
            f"?{urlencode(query_params)}"
        )
        logger.debug("Getting access token from %s", url)

        async with session.get(
            url, headers=headers
        ) as resp:
            response = await resp.json()

        logger.debug("Token response: %s", response)

        if response.get("success"):
            result = response.get("result", {})
            token_data = {
                "t": response.get("t", 0),
                "expire_time": result.get(
                    "expire_time", 0
                ),
                "uid": result.get("uid", ""),
                "access_token": result.get(
                    "access_token", ""
                ),
                "refresh_token": result.get(
                    "refresh_token", ""
                ),
            }
            self.token_info = TrueXTokenInfo(token_data)
            if self.token_listener:
                self.token_listener.update_token(
                    self.token_info.to_dict()
                )
            return response

        raise TrueXAPIError(
            f"Failed to get access token: "
            f"{response.get('msg', 'Unknown error')} "
            f"(code: {response.get('code', 'N/A')})"
        )

    async def _refresh_access_token(self) -> None:
        """Refresh the access token."""
        if self._refreshing_token:
            return
        self._refreshing_token = True
        try:
            path = (
                "/v1.0/token/"
                + self.token_info.refresh_token
            )
            timestamp = str(int(time.time() * 1000))
            sign_str = _string_to_sign("GET", path)
            sign = _calc_sign(
                self.client_id,
                self.secret,
                timestamp,
                "",
                sign_str,
            )

            headers = {
                "client_id": self.client_id,
                "sign": sign,
                "t": timestamp,
                "sign_method": "HMAC-SHA256",
                "Content-Type": "application/json",
            }

            session = await self._ensure_session()
            url = f"{self.api_url}{path}"

            async with session.get(
                url, headers=headers
            ) as resp:
                response = await resp.json()

            if response.get("success"):
                result = response.get("result", {})
                token_data = {
                    "t": response.get("t", 0),
                    "expire_time": result.get(
                        "expire_time", 0
                    ),
                    "uid": result.get("uid", ""),
                    "access_token": result.get(
                        "access_token", ""
                    ),
                    "refresh_token": result.get(
                        "refresh_token", ""
                    ),
                }
                self.token_info = TrueXTokenInfo(
                    token_data
                )
                if self.token_listener:
                    self.token_listener.update_token(
                        self.token_info.to_dict()
                    )
            else:
                logger.warning(
                    "Token refresh failed: %s", response
                )
                await self.get_access_token()
        except Exception:
            logger.exception("Error refreshing token")
            await self.get_access_token()
        finally:
            self._refreshing_token = False

    async def _ensure_token(self) -> None:
        """Ensure we have a valid (non-expired) token."""
        if self.token_info.is_expired:
            if self.token_info.refresh_token:
                await self._refresh_access_token()
            else:
                await self.get_access_token()

    # ── Authenticated Request ───────────────────────────

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated business API request.

        Uses business-mode signing that includes
        access_token in the HMAC string.
        """
        await self._ensure_token()

        timestamp = str(int(time.time() * 1000))
        body_str = (
            json.dumps(body) if body else ""
        )
        sign_str = _string_to_sign(
            method, path, params, body_str
        )
        sign = _calc_sign(
            self.client_id,
            self.secret,
            timestamp,
            "",
            sign_str,
            access_token=(
                self.token_info.access_token
            ),
        )

        headers = {
            "client_id": self.client_id,
            "access_token": (
                self.token_info.access_token
            ),
            "sign": sign,
            "t": timestamp,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json",
        }

        session = await self._ensure_session()
        url = f"{self.api_url}{path}"
        if params:
            url += f"?{urlencode(params)}"

        logger.debug(
            "API %s %s body=%s", method, url, body_str
        )

        kwargs: dict[str, Any] = {"headers": headers}
        if body:
            kwargs["json"] = body

        async with session.request(
            method, url, **kwargs
        ) as resp:
            if not resp.ok:
                text = await resp.text()
                logger.error(
                    "HTTP error: %s %s",
                    resp.status,
                    text,
                )
                return {"success": False}
            response = await resp.json()

        logger.debug("API response: %s", response)

        if not response.get("success"):
            code = response.get("code", "N/A")
            msg = response.get("msg", "Unknown error")
            logger.error(
                "API error: %s (code: %s)", msg, code
            )
            raise TrueXAPIError(
                f"API error: {msg} (code: {code})"
            )

        return response

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """HTTP GET request."""
        return await self.request(
            "GET", path, params
        )

    async def post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """HTTP POST request."""
        return await self.request(
            "POST", path, params, body
        )

    async def put(
        self,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """HTTP PUT request."""
        return await self.request(
            "PUT", path, None, body
        )

    async def delete(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """HTTP DELETE request."""
        return await self.request(
            "DELETE", path, params
        )

    # ── High-Level API Methods (Postman endpoints) ──────

    async def get_user_by_username(
        self, username: str
    ) -> dict[str, Any]:
        """Get user info by username (SSO lookup).

        GET /v2.0/apps/{schema}/users?username=...
        """
        return await self.get(
            f"/v2.0/apps/{self.schema}/users",
            {"username": username},
        )

    async def get_user_homes(
        self, uid: str
    ) -> dict[str, Any]:
        """Get homes for a user.

        GET /v1.0/users/{uid}/homes
        """
        return await self.get(
            f"/v1.0/users/{uid}/homes"
        )

    async def get_user_devices(
        self, uid: str
    ) -> dict[str, Any]:
        """Get device list for a user.

        GET /v1.0/users/{uid}/devices
        """
        return await self.get(
            f"/v1.0/users/{uid}/devices"
        )

    async def get_device_info(
        self, device_id: str
    ) -> dict[str, Any]:
        """Get device information.

        GET /v1.0/devices/{device_id}
        """
        return await self.get(
            f"/v1.0/devices/{device_id}"
        )

    async def get_device_status(
        self, device_id: str
    ) -> dict[str, Any]:
        """Get latest device status.

        GET /v1.0/devices/{device_id}/status
        """
        return await self.get(
            f"/v1.0/devices/{device_id}/status"
        )

    async def get_device_specifications(
        self, device_id: str
    ) -> dict[str, Any]:
        """Get device specifications and properties.

        GET /v1.0/devices/{device_id}/specifications
        """
        return await self.get(
            f"/v1.0/devices/{device_id}/specifications"
        )

    async def send_device_commands(
        self,
        device_id: str,
        commands: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send commands to a device.

        POST /v1.0/devices/{device_id}/commands
        Body: {"commands": [{"code": "...", "value": ...}]}
        """
        return await self.post(
            f"/v1.0/devices/{device_id}/commands",
            None,
            {"commands": commands},
        )

    async def get_device_stream_allocate(
        self,
        uid: str,
        device_id: str,
        stream_type: str,
    ) -> dict[str, Any]:
        """Get live streaming address for a device.

        POST /v1.0/users/{uid}/devices/{device_id}/stream/actions/allocate
        Body: {"type": "RTSP" | "HLS" | "FLV" | "RTMP"}
        """
        return await self.post(
            f"/v1.0/users/{uid}/devices/{device_id}/stream/actions/allocate",
            None,
            {"type": stream_type},
        )

    async def get_device_functions(
        self, device_id: str
    ) -> dict[str, Any]:
        """Get device supported functions.

        GET /v1.0/devices/{device_id}/functions
        """
        return await self.get(
            f"/v1.0/devices/{device_id}/functions"
        )
