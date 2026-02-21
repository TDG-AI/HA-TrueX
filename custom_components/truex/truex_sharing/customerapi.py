"""OPENAPI CUBE REST client using grant_type=1 with HMAC-SHA256 signing.

Equivalent to tuya_sharing.customerapi.CustomerApi but for CUBE grant_type=1.
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


class SharingTokenListener:
    """Listener for token refresh events."""

    def update_token(self, token_info: dict[str, Any]) -> None:
        """Called when token is refreshed."""


class TrueXTokenInfo:
    """Token information for OPENAPI CUBE authentication."""

    def __init__(self, token_response: dict[str, Any] | None = None) -> None:
        """Initialize token info."""
        if token_response:
            result = token_response.get("result", token_response)
            self.access_token: str = result.get("access_token", "")
            self.refresh_token: str = result.get("refresh_token", "")
            self.expire_time: int = result.get("expire_time", 0)
            self.uid: str = result.get("uid", "")
            self.token_acquired_at: float = time.time()
        else:
            self.access_token = ""
            self.refresh_token = ""
            self.expire_time = 0
            self.uid = ""
            self.token_acquired_at = 0.0

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 60s buffer)."""
        if not self.access_token:
            return True
        return time.time() > (self.token_acquired_at + self.expire_time - 60)

    def to_dict(self) -> dict[str, Any]:
        """Serialize token info to dict for storage."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expire_time": self.expire_time,
            "uid": self.uid,
            "token_acquired_at": self.token_acquired_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrueXTokenInfo:
        """Deserialize token info from stored dict."""
        info = cls()
        info.access_token = data.get("access_token", "")
        info.refresh_token = data.get("refresh_token", "")
        info.expire_time = data.get("expire_time", 0)
        info.uid = data.get("uid", "")
        info.token_acquired_at = data.get("token_acquired_at", 0.0)
        return info


class TrueXAPIError(Exception):
    """Exception raised for TrueX API errors."""


class CustomerApi:
    """OPENAPI CUBE REST API client for Tuya grant_type=1.

    Equivalent to tuya_sharing.CustomerApi but uses HMAC-SHA256 signing
    instead of the encrypted AES-GCM protocol.
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
        self.token_listener: SharingTokenListener | None = None
        self._session = session
        self._owns_session = session is None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure an aiohttp session exists."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    # ── Signing ──────────────────────────────────────────────

    @staticmethod
    def _sha256(data: str) -> str:
        """SHA256 hash of a string."""
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def _calc_sign(
        self,
        method: str,
        path: str,
        query_params: dict[str, Any] | None = None,
        body: str = "",
        timestamp: str = "",
        nonce: str = "",
        use_token: bool = True,
    ) -> tuple[str, str]:
        """Calculate HMAC-SHA256 signature for an API request.

        Returns (sign, timestamp).
        """
        if not timestamp:
            timestamp = str(int(time.time() * 1000))

        # Content hash
        content_hash = self._sha256(body)

        # Sorted query string
        sorted_query = ""
        if query_params:
            sorted_keys = sorted(query_params.keys())
            sorted_query = "&".join(
                f"{k}={query_params[k]}" for k in sorted_keys
            )

        # URL with query
        url_with_query = path
        if sorted_query:
            url_with_query = f"{path}?{sorted_query}"

        # String to sign
        headers_str = ""  # No custom signed headers for now
        string_to_sign = f"{method}\n{content_hash}\n{headers_str}\n{url_with_query}"

        # Sign string: client_id + [access_token] + timestamp + nonce + stringToSign
        access_token = self.token_info.access_token if use_token else ""
        sign_str = f"{self.client_id}{access_token}{timestamp}{nonce}{string_to_sign}"

        # HMAC-SHA256
        sign = hmac.new(
            self.secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()

        return sign, timestamp

    def _build_headers(
        self,
        method: str,
        path: str,
        query_params: dict[str, Any] | None = None,
        body: str = "",
        use_token: bool = True,
    ) -> dict[str, str]:
        """Build request headers with signature."""
        nonce = ""
        sign, timestamp = self._calc_sign(
            method, path, query_params, body, nonce=nonce, use_token=use_token
        )

        headers = {
            "client_id": self.client_id,
            "sign": sign,
            "t": timestamp,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json",
        }
        if use_token and self.token_info.access_token:
            headers["access_token"] = self.token_info.access_token

        return headers

    # ── Token Management ─────────────────────────────────────

    async def get_access_token(self) -> dict[str, Any]:
        """Get access token using grant_type=1 (simple mode)."""
        path = "/v1.0/token"
        query_params = {"grant_type": "1"}
        headers = self._build_headers("GET", path, query_params, use_token=False)

        session = await self._ensure_session()
        url = f"{self.api_url}{path}?{urlencode(query_params)}"
        logger.debug("Getting access token from %s", url)

        async with session.get(url, headers=headers) as resp:
            response = await resp.json()

        logger.debug("Token response: %s", response)

        if response.get("success"):
            self.token_info = TrueXTokenInfo(response)
            if self.token_listener:
                self.token_listener.update_token(self.token_info.to_dict())
            return response
        raise TrueXAPIError(
            f"Failed to get access token: {response.get('msg', 'Unknown error')} "
            f"(code: {response.get('code', 'N/A')})"
        )

    async def refresh_access_token(self) -> dict[str, Any]:
        """Refresh access token."""
        if not self.token_info.refresh_token:
            return await self.get_access_token()

        path = f"/v1.0/token/{self.token_info.refresh_token}"
        headers = self._build_headers("GET", path, use_token=False)

        session = await self._ensure_session()
        url = f"{self.api_url}{path}"

        async with session.get(url, headers=headers) as resp:
            response = await resp.json()

        if response.get("success"):
            self.token_info = TrueXTokenInfo(response)
            if self.token_listener:
                self.token_listener.update_token(self.token_info.to_dict())
            return response

        # If refresh fails, try fresh token
        logger.warning("Token refresh failed, getting new token: %s", response)
        return await self.get_access_token()

    async def _ensure_token(self) -> None:
        """Ensure we have a valid (non-expired) token."""
        if self.token_info.is_expired:
            if self.token_info.refresh_token:
                await self.refresh_access_token()
            else:
                await self.get_access_token()

    # ── HTTP Methods ─────────────────────────────────────────

    async def request(
        self,
        method: str,
        path: str,
        query_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated API request."""
        await self._ensure_token()

        body_str = json.dumps(body) if body else ""
        headers = self._build_headers(method, path, query_params, body_str)

        session = await self._ensure_session()
        url = f"{self.api_url}{path}"
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        logger.debug("API %s %s", method, url)

        kwargs: dict[str, Any] = {"headers": headers}
        if body:
            kwargs["data"] = body_str

        async with session.request(method, url, **kwargs) as resp:
            response = await resp.json()

        if not response.get("success"):
            code = response.get("code", "N/A")
            msg = response.get("msg", "Unknown error")
            # If token is invalid, refresh and retry once
            if code in (1010, "1010"):
                logger.debug("Token invalid, refreshing and retrying...")
                await self.get_access_token()
                headers = self._build_headers(method, path, query_params, body_str)
                kwargs["headers"] = headers
                async with session.request(method, url, **kwargs) as resp:
                    response = await resp.json()
                if not response.get("success"):
                    raise TrueXAPIError(
                        f"API error after retry: {response.get('msg')} "
                        f"(code: {response.get('code')})"
                    )
            else:
                logger.warning("API error: %s (code: %s)", msg, code)

        return response

    async def get(
        self, path: str, query_params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """HTTP GET request."""
        return await self.request("GET", path, query_params)

    async def post(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """HTTP POST request."""
        return await self.request("POST", path, query_params, body)

    async def put(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """HTTP PUT request."""
        return await self.request("PUT", path, query_params, body)

    async def delete(
        self, path: str, query_params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """HTTP DELETE request."""
        return await self.request("DELETE", path, query_params)

    # ── High-Level API Methods ───────────────────────────────

    async def get_user_by_username(self, username: str) -> dict[str, Any]:
        """Get user info by username (SSO lookup)."""
        return await self.get(
            f"/v2.0/apps/{self.schema}/users",
            {"username": username},
        )

    async def get_user_homes(self, uid: str) -> dict[str, Any]:
        """Get homes for a user."""
        return await self.get(f"/v1.0/users/{uid}/homes")

    async def get_user_devices(self, uid: str) -> dict[str, Any]:
        """Get device list for a user."""
        return await self.get(
            f"/v1.0/users/{uid}/devices",
            {"page_size": "100"},
        )

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get latest status for a device."""
        return await self.get(f"/v1.0/devices/{device_id}/status")

    async def get_device_specifications(self, device_id: str) -> dict[str, Any]:
        """Get device specifications (functions and status range)."""
        return await self.get(f"/v1.0/devices/{device_id}/specifications")

    async def send_device_commands(
        self, device_id: str, commands: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Send commands to a device."""
        return await self.post(
            f"/v1.0/devices/{device_id}/commands",
            {"commands": commands},
        )

    async def get_device_info(self, device_id: str) -> dict[str, Any]:
        """Get device detail info."""
        return await self.get(f"/v1.0/devices/{device_id}")
