"""Evaluation repository — criterion-level AI reasoning records."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.enums import CriterionStatus, EvaluationType
from app.models.evaluation import Evaluation


class EvaluationRepository(BaseRepository[Evaluation]):
    """Repository for Evaluation (criterion-level AI + human review) records."""

    model = Evaluation

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_case_id(
        self,
        case_id: str,
        evaluation_type: EvaluationType | None = None,
    ) -> list[Evaluation]:
        """Return all evaluations for a case, optionally filtered by type."""
        stmt = select(Evaluation).where(
            Evaluation.case_id == case_id,
            Evaluation.deleted_at.is_(None),
        )
        if evaluation_type:
            stmt = stmt.where(Evaluation.evaluation_type == evaluation_type)
        stmt = stmt.order_by(Evaluation.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_failed_criteria(self, case_id: str) -> list[Evaluation]:
        """Return AI evaluations that FAILED or had INSUFFICIENT_EVIDENCE."""
        stmt = select(Evaluation).where(
            Evaluation.case_id == case_id,
            Evaluation.evaluation_type == EvaluationType.AI_CRITERION,
            Evaluation.criterion_status.in_([
                CriterionStatus.FAIL,
                CriterionStatus.INSUFFICIENT_EVIDENCE,
            ]),
            Evaluation.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_create_criteria(
        self, case_id: str, criteria: list[dict]
    ) -> list[Evaluation]:
        """
        Bulk-insert criterion evaluations for a case.
        Used by the reasoning engine after processing all criteria.
        """
        items = [{"case_id": case_id, **c} for c in criteria]
        return await self.bulk_create(items)
