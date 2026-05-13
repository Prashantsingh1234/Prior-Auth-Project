"""Clarification repository — loop state management."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.clarification import Clarification
from app.models.enums import ClarificationStatus


class ClarificationRepository(BaseRepository[Clarification]):
    """Repository for clarification request-response cycles."""

    model = Clarification

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_case_id(self, case_id: str) -> list[Clarification]:
        """Return all clarification records for a case, in attempt order."""
        stmt = (
            select(Clarification)
            .where(
                Clarification.case_id == case_id,
                Clarification.deleted_at.is_(None),
            )
            .order_by(Clarification.attempt_number.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending(self, case_id: str) -> Clarification | None:
        """Return the current pending clarification for a case, if any."""
        stmt = select(Clarification).where(
            Clarification.case_id == case_id,
            Clarification.status == ClarificationStatus.PENDING,
            Clarification.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_attempt_count(self, case_id: str) -> int:
        """Return how many clarification attempts have been made for this case."""
        from sqlalchemy import func
        stmt = select(func.count(Clarification.id)).where(
            Clarification.case_id == case_id,
            Clarification.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def mark_answered(
        self,
        clarification_id: str,
        answers: list[dict],
    ) -> Clarification:
        """Record provider answers and mark clarification as ANSWERED."""
        from datetime import UTC, datetime
        return await self.update(
            clarification_id,
            status=ClarificationStatus.ANSWERED,
            answers=answers,
            answered_at=datetime.now(UTC),
        )
