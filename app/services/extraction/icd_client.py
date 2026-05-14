"""
WHO ICD-11 API client with OAuth2 token management and Redis caching.

API reference: https://icd.who.int/icdapi
OAuth2 token endpoint: https://icdaccessmanagement.who.int/connect/token
Code lookup:   GET /icd/release/11/{release}/mms/codeinfo/{code}
Code search:   GET /icd/release/11/{release}/mms/search?q={query}

Token lifecycle:
  - Access tokens expire (typically 3600s)
  - Tokens are cached in Redis under pa:v1:icd:token
  - Refreshed automatically 60s before expiry
  - Falls back to in-memory cache when Redis is unavailable
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

_TOKEN_CACHE_KEY  = "pa:v1:icd:token"
_TOKEN_TTL_BUFFER = 60      # refresh this many seconds before actual expiry
_REQUEST_TIMEOUT  = 15      # seconds per API call
_ACCEPT_HEADER    = "application/json"
_API_VERSION_HEADER = "API-Version"


class ICDCodeInfo:
    """Lightweight container for ICD code lookup results."""

    __slots__ = ("code", "description", "is_valid", "parent_code", "raw")

    def __init__(
        self,
        code: str,
        description: str,
        is_valid: bool,
        parent_code: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        self.code        = code
        self.description = description
        self.is_valid    = is_valid
        self.parent_code = parent_code
        self.raw         = raw or {}


class ICDApiClient:
    """
    WHO ICD-11 REST API client.

    Usage:
        client = ICDApiClient.from_settings()
        info = await client.validate_code("E11.65")
        results = await client.search("diabetes mellitus", top_k=5)
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = "https://id.who.int/icd",
        token_url: str = "https://icdaccessmanagement.who.int/connect/token",
        api_version: str = "v2",
        release: str = "2024-01",
    ) -> None:
        self._client_id     = client_id
        self._client_secret = client_secret
        self._base_url      = base_url.rstrip("/")
        self._token_url     = token_url
        self._api_version   = api_version
        self._release       = release
        self._log           = structlog.get_logger(self.__class__.__name__)

        # In-memory token fallback (used when Redis unavailable)
        self._token_cache:    str | None = None
        self._token_expiry:   float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def validate_code(self, code: str) -> ICDCodeInfo | None:
        """
        Validate an ICD-11 code and return its description.

        Returns None if the code does not exist in ICD-11.
        """
        token = await self._get_token()
        url = (
            f"{self._base_url}/release/11/{self._release}/mms"
            f"/codeinfo/{code}"
        )
        try:
            data = await self._get(url, token)
            title = self._extract_title(data)
            return ICDCodeInfo(
                code=code,
                description=title,
                is_valid=True,
                raw=data,
            )
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return ICDCodeInfo(code=code, description="", is_valid=False)
            self._log.warning("icd_client.validate_error", code=code, status=err.response.status_code)
            return None
        except Exception as err:
            self._log.warning("icd_client.validate_failed", code=code, error=str(err))
            return None

    async def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[ICDCodeInfo]:
        """
        Search ICD-11 codes by free-text query.

        Returns up to top_k results ordered by relevance.
        """
        token = await self._get_token()
        url = f"{self._base_url}/release/11/{self._release}/mms/search"
        params = {"q": query, "useFlexisearch": "true", "flatResults": "true"}
        try:
            data = await self._get(url, token, params=params)
            results: list[ICDCodeInfo] = []
            for item in (data.get("destinationEntities") or [])[:top_k]:
                code = item.get("theCode", "")
                title = self._extract_title(item)
                if code:
                    results.append(
                        ICDCodeInfo(code=code, description=title, is_valid=True, raw=item)
                    )
            return results
        except Exception as err:
            self._log.warning("icd_client.search_failed", query=query, error=str(err))
            return []

    async def is_available(self) -> bool:
        """Return True if the API can be reached and credentials are valid."""
        try:
            await self._get_token()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    async def _get_token(self) -> str:
        """Return a valid access token, refreshing if necessary."""
        # Try Redis cache first
        cached = await self._redis_get_token()
        if cached:
            return cached

        # Fall back to in-memory cache
        if self._token_cache and time.monotonic() < self._token_expiry - _TOKEN_TTL_BUFFER:
            return self._token_cache

        # Fetch a new token
        return await self._fetch_token()

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _fetch_token(self) -> str:
        self._log.debug("icd_client.fetching_token")
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(
                self._token_url,
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     self._client_id,
                    "client_secret": self._client_secret,
                    "scope":         "icdapi_access",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            payload    = resp.json()
            token      = payload["access_token"]
            expires_in = int(payload.get("expires_in", 3600))

        # Cache in memory
        self._token_cache  = token
        self._token_expiry = time.monotonic() + expires_in

        # Cache in Redis (best-effort)
        await self._redis_set_token(token, expires_in)

        self._log.info("icd_client.token_refreshed", expires_in=expires_in)
        return token

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get(
        self,
        url: str,
        token: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.get(
                url,
                params=params,
                headers={
                    "Authorization":   f"Bearer {token}",
                    "Accept":          _ACCEPT_HEADER,
                    _API_VERSION_HEADER: self._api_version,
                    "Accept-Language": "en",
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Redis helpers (best-effort — never raises)
    # ------------------------------------------------------------------

    async def _redis_get_token(self) -> str | None:
        try:
            from app.services.caching.redis_client import cache_get
            raw = await cache_get(_TOKEN_CACHE_KEY)
            return raw if isinstance(raw, str) else None
        except Exception:
            return None

    async def _redis_set_token(self, token: str, expires_in: int) -> None:
        try:
            from app.services.caching.redis_client import cache_set
            await cache_set(_TOKEN_CACHE_KEY, token, ttl=expires_in - _TOKEN_TTL_BUFFER)
        except Exception:
            pass

    @staticmethod
    def _extract_title(data: dict[str, Any]) -> str:
        title = data.get("title", {})
        if isinstance(title, dict):
            return title.get("@value", "") or title.get("value", "")
        return str(title) if title else ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls) -> "ICDApiClient":
        from app.core.config.settings import get_settings

        s = get_settings()
        if not s.icd_api_client_id or not s.icd_api_client_secret:
            raise RuntimeError("ICD API credentials not configured")
        return cls(
            client_id=s.icd_api_client_id,
            client_secret=s.icd_api_client_secret.get_secret_value(),
            base_url=s.icd_api_base_url,
            token_url=s.icd_api_token_url,
            api_version=s.icd_api_version,
            release=s.icd_api_release,
        )
