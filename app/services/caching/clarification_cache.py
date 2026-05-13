"""
Clarification state cache.

Stores the pending clarification context for a PA case while waiting for
a provider response. This lets the clarification service reconstruct
exactly what was asked — and check for duplicate questions — without
hitting the database on every poll.

Key: pa:v1:clarification:{case_id}:{attempt_number}
TTL: 2 hours — providers have a 2-hour response window (configurable)

Stored payload:
    {
        "case_id":           str,
        "attempt_number":    int,
        "status":            "PENDING" | "ANSWERED" | "EXPIRED",
        "missing_criteria":  list[str],
        "questions":         list[str],
        "answers":           list[str] | null,
        "response_deadline": ISO-8601 str,
        "created_at":        ISO-8601 str,
    }
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.caching.base import BaseCacheService
from app.services.caching.keys import TTL, clarification_key

logger = structlog.get_logger(__name__)


class ClarificationState:
    """Typed wrapper around the clarification cache payload."""

    __slots__ = (
        "case_id", "attempt_number", "status",
        "missing_criteria", "questions", "answers",
        "response_deadline", "created_at",
    )

    def __init__(
        self,
        case_id: str,
        attempt_number: int,
        status: str,
        missing_criteria: list[str],
        questions: list[str],
        answers: list[str] | None = None,
        response_deadline: str | None = None,
        created_at: str | None = None,
    ) -> None:
        self.case_id = case_id
        self.attempt_number = attempt_number
        self.status = status
        self.missing_criteria = missing_criteria
        self.questions = questions
        self.answers = answers
        self.response_deadline = response_deadline
        self.created_at = created_at or datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "attempt_number": self.attempt_number,
            "status": self.status,
            "missing_criteria": self.missing_criteria,
            "questions": self.questions,
            "answers": self.answers,
            "response_deadline": self.response_deadline,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClarificationState":
        return cls(
            case_id=data["case_id"],
            attempt_number=int(data["attempt_number"]),
            status=data["status"],
            missing_criteria=list(data.get("missing_criteria") or []),
            questions=list(data.get("questions") or []),
            answers=data.get("answers"),
            response_deadline=data.get("response_deadline"),
            created_at=data.get("created_at"),
        )

    @property
    def is_answered(self) -> bool:
        return self.status == "ANSWERED"

    @property
    def is_pending(self) -> bool:
        return self.status == "PENDING"

    @property
    def is_expired(self) -> bool:
        if not self.response_deadline:
            return False
        try:
            deadline = datetime.fromisoformat(self.response_deadline)
            return datetime.now(UTC) > deadline
        except ValueError:
            return False


class ClarificationCache(BaseCacheService):
    """Cache for pending clarification state per case."""

    domain = "clarification"
    default_ttl = TTL.CLARIFICATION

    async def get(
        self, case_id: str, attempt_number: int
    ) -> ClarificationState | None:
        """
        Return the cached clarification state, or None.

        Args:
            case_id:        PA case UUID
            attempt_number: Clarification loop iteration (1, 2, or 3)

        Returns:
            ClarificationState or None on miss / corrupt data.
        """
        key = clarification_key(case_id, attempt_number)
        data = await self._get(key)
        if data is None:
            return None
        try:
            return ClarificationState.from_dict(data)
        except (KeyError, TypeError, ValueError):
            await self._delete(key)
            return None

    async def set(
        self,
        state: ClarificationState,
        ttl: int | None = None,
    ) -> None:
        """
        Store clarification state.

        Args:
            state: The clarification context to cache.
            ttl:   Override default TTL. Set to (response_deadline - now)
                   for precise expiry alignment.
        """
        key = clarification_key(state.case_id, state.attempt_number)
        await self._set(key, state.to_dict(), ttl=ttl)
        logger.debug(
            "clarification.cached",
            case_id=state.case_id,
            attempt=state.attempt_number,
            status=state.status,
        )

    async def mark_answered(
        self,
        case_id: str,
        attempt_number: int,
        answers: list[str],
    ) -> bool:
        """
        Update a pending clarification to ANSWERED status.

        Returns False if the clarification was not in cache (DB is source of
        truth — the service layer handles this case from DB).
        """
        existing = await self.get(case_id, attempt_number)
        if existing is None:
            return False
        existing.status = "ANSWERED"
        existing.answers = answers
        await self.set(existing)
        logger.info(
            "clarification.answered",
            case_id=case_id,
            attempt=attempt_number,
        )
        return True

    async def invalidate(self, case_id: str, attempt_number: int) -> bool:
        """Delete cached state for a specific clarification attempt."""
        key = clarification_key(case_id, attempt_number)
        return await self._delete(key)

    async def invalidate_all_for_case(self, case_id: str) -> int:
        """
        Delete ALL clarification cache entries for a case.

        Called when a case is decided, cancelled, or archived.
        """
        total = 0
        for attempt in range(1, 4):  # max 3 attempts
            key = clarification_key(case_id, attempt)
            if await self._delete(key):
                total += 1
        logger.debug(
            "clarification.all_invalidated",
            case_id=case_id,
            deleted_count=total,
        )
        return total
