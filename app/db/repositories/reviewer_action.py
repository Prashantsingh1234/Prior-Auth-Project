"""Repository for ReviewerAction — the immutable reviewer audit trail."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.enums import ReviewerActionType
from app.models.reviewer_action import ReviewerAction


class ReviewerActionRepository(BaseRepository[ReviewerAction]):
    model = ReviewerAction

    async def list_for_case(self, case_id: str) -> list[ReviewerAction]:
        """Return all actions for a case, oldest first."""
        stmt = (
            select(ReviewerAction)
            .where(
                ReviewerAction.case_id == case_id,
                ReviewerAction.deleted_at.is_(None),
            )
            .order_by(ReviewerAction.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_reviewer(self, reviewer_id: str, limit: int = 100) -> list[ReviewerAction]:
        """Return recent actions by a specific reviewer."""
        stmt = (
            select(ReviewerAction)
            .where(
                ReviewerAction.reviewer_id == reviewer_id,
                ReviewerAction.deleted_at.is_(None),
            )
            .order_by(ReviewerAction.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
