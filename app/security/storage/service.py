"""Local filesystem storage backend used by the API.

The project originally referenced a SecureStorage abstraction; this implementation
keeps behavior simple and predictable for local/dev environments while preserving
the same interface for callers.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import anyio

from app.core.config.settings import get_settings


class SecureStorage:
    def __init__(self) -> None:
        self._root = Path(get_settings().storage_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        safe = path.lstrip("/\\")
        full = (self._root / safe).resolve()
        # Ensure we stay within storage root
        if self._root not in full.parents and full != self._root:
            raise ValueError("Invalid storage path")
        return full

    async def upload(
        self,
        *,
        data: bytes,
        path: str,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        async with await anyio.open_file(full, "wb") as f:
            await f.write(data)
        return str(full)

    async def download(self, *, path: str) -> bytes:
        full = Path(path)
        # If caller stored an absolute path previously, allow it as long as it's inside root.
        if not full.is_absolute():
            full = self._resolve(path)
        else:
            full = full.resolve()
            if self._root not in full.parents and full != self._root:
                raise ValueError("Invalid storage path")
        async with await anyio.open_file(full, "rb") as f:
            return await f.read()

    async def delete(self, *, path: str) -> None:
        full = Path(path)
        if not full.is_absolute():
            full = self._resolve(path)
        else:
            full = full.resolve()
        if full.exists():
            os.remove(full)
