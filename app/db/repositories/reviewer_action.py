"""ReviewerAction repository — immutable reviewer timeline."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.enums import ReviewerActionType
from app.models.reviewer_action import ReviewerAction


class ReviewerActionRepository(BaseRepository[ReviewerAction]):
    """Append-only repository for reviewer action records."""

    model = ReviewerAction

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_case_timeline(self, case_id: str) -> list[ReviewerAction]:
        """Return full reviewer action history for a case (chronological)."""
        stmt = (
            select(ReviewerAction)
            .where(ReviewerAction.case_id == case_id)
            .order_by(ReviewerAction.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_reviewer_actions(
        self,
        reviewer_id: str,
        action_type: ReviewerActionType | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ReviewerAction]:
        """Return actions by a specific reviewer, optionally filtered by type."""
        stmt = (
            select(ReviewerAction)
            .where(ReviewerAction.reviewer_id == reviewer_id)
            .order_by(ReviewerAction.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if action_type:
            stmt = stmt.where(ReviewerAction.action_type == action_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_overrides(self, reviewer_id: str | None = None) -> int:
        """Count the number of AI override actions (for analytics)."""
        override_types = [
            ReviewerActionType.OVERRIDE_APPROVED,
            ReviewerActionType.OVERRIDE_DENIED,
        ]
        stmt = select(func.count(ReviewerAction.id)).where(
            ReviewerAction.action_type.in_(override_types)
        )
        if reviewer_id:
            stmt = stmt.where(ReviewerAction.reviewer_id == reviewer_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def log_action(
        self,
        case_id: str,
        reviewer_id: str,
        action_type: ReviewerActionType,
        **kwargs,
    ) -> ReviewerAction:
        """Append a new reviewer action to the timeline."""
        return await self.create(
            case_id=case_id,
            reviewer_id=reviewer_id,
            action_type=action_type,
            **kwargs,
        )
