"""Decision repository — final PA decision read/write."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.decision import Decision
from app.models.enums import DecisionOutcome, DecisionSource


class DecisionRepository(BaseRepository[Decision]):
    """Repository for final PA case decisions."""

    model = Decision

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_case_id(self, case_id: str) -> Decision | None:
        """Return the decision for a case (at most one per case)."""
        stmt = select(Decision).where(Decision.case_id == case_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def decision_exists(self, case_id: str) -> bool:
        """Return True if a decision already exists for this case."""
        return await self.get_by_case_id(case_id) is not None

    async def get_approval_rate(
        self, reviewer_id: str | None = None
    ) -> dict[str, float]:
        """
        Compute approval/denial/pend rates.

        Returns:
            {"APPROVE": 0.72, "DENY": 0.20, "PEND": 0.08}
        """
        stmt = select(
            Decision.final_decision,
            func.count(Decision.id).label("cnt"),
        ).group_by(Decision.final_decision)

        if reviewer_id:
            stmt = stmt.where(Decision.reviewer_id == reviewer_id)

        result = await self.session.execute(stmt)
        rows = result.all()

        total = sum(r.cnt for r in rows)
        if total == 0:
            return {d.value: 0.0 for d in DecisionOutcome}

        return {row.final_decision: round(row.cnt / total, 4) for row in rows}

    async def get_override_rate(self) -> float:
        """
        Compute the rate of reviewer overrides across all decisions.
        Returns proportion of decisions where source == REVIEWER_OVERRIDE.
        """
        total_stmt = select(func.count(Decision.id))
        override_stmt = select(func.count(Decision.id)).where(
            Decision.decision_source == DecisionSource.REVIEWER_OVERRIDE
        )
        total_result = await self.session.execute(total_stmt)
        override_result = await self.session.execute(override_stmt)

        total = total_result.scalar_one()
        overrides = override_result.scalar_one()

        return round(overrides / total, 4) if total > 0 else 0.0
