"""
Simple pass-through rate limiter.

Redis-backed sliding-window was removed with the caching layer.
Rate limiting can be re-added via a reverse proxy (nginx / Traefik) or
re-enabled here once a Redis dependency is restored.
"""

from __future__ import annotations

from fastapi import Depends


def rate_limit(endpoint: str = "default") -> Depends:
    """No-op rate limit dependency — always allows the request through."""
    async def _noop() -> None:
        pass

    return Depends(_noop)
