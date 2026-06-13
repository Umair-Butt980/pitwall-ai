from __future__ import annotations

from typing import Any

from database.connection import connections


class BaseHTTPService:
    """Shared plumbing for services that call a REST API.

    Subclasses set `base_url` and call `self._get(...)`. All requests reuse
    the one pooled httpx client created at startup (connections.http), so we
    never spin up a new connection pool per request — same idea as sharing a
    single axios instance.
    """

    base_url: str = ""

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET {base_url}{path} and return parsed JSON.

        Raises httpx.HTTPStatusError on a non-2xx response (so callers/routes
        surface a real error instead of silently caching junk).
        """
        url = f"{self.base_url}{path}"
        response = await connections.http.get(url, params=params)
        response.raise_for_status()
        return response.json()
