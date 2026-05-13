"""
PACase repository — the most important domain repository.

Provides specialized query methods for the PA case workflow:
- Queue fetching (cases ready for reviewer pickup)
- Status transition (with logging)
- Reviewer assignment
- Case lookup by number, patient, provider
- Analytics queries (counts by status, priority, etc.)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions.base import CaseAlreadyDecidedError, CaseNotFoundError
from app.db.repositories.base import BaseRepository
from app.models.enums import CasePriority, CaseStatus
from app.models.pa_case import PACase

logger = structlog.get_logger(__name__)


def _generate_case_number() -> str:
    """Generate a human-readable PA case number."""
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"PA-{date_part}-{suffix}"


class PACaseRepository(BaseRepository[PACase]):
    """Repository for PA Case CRUD and workflow queries."""

    model = PACase

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ----------------------------------------------------------
    # Create with auto case number
    # ----------------------------------------------------------

    async def create_case(self, **kwargs) -> PACase:
        """
        Create a new PA case with auto-generated case_number.
        Ensures case_number uniqueness by regenerating on collision.
        """
        for attempt in range(5):
            case_number = _generate_case_number()
            try:
                case = await self.create(
                    case_number=case_number,
                    submitted_at=datetime.now(UTC),
                    **kwargs,
                )
                return case
            except Exception as exc:
                if attempt == 4:
                    raise
                # Likely a unique constraint collision — retry with new number
                logger.warning(
                    "pa_case.case_number_collision",
                    attempt=attempt + 1,
                    case_number=case_number,
                )
        raise RuntimeError("Failed to generate unique case number after 5 attempts")

    # ----------------------------------------------------------
    # Lookups
    # ----------------------------------------------------------

    async def get_by_case_number(self, case_number: str) -> PACase | None:
        """Fetch a case by its human-readable case number."""
        stmt = (
            select(PACase)
            .where(PACase.case_number == case_number, PACase.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_all_relations(self, case_id: str) -> PACase | None:
        """
        Fetch a case with all related entities eagerly loaded.
        Used for the reviewer dashboard — needs complete case data in one query.
        """
        stmt = (
            select(PACase)
            .where(PACase.id == case_id, PACase.deleted_at.is_(None))
            .options(
                selectinload(PACase.patient),
                selectinload(PACase.provider),
                selectinload(PACase.documents),
                selectinload(PACase.entities),
                selectinload(PACase.policy_matches),
                selectinload(PACase.evaluations),
                selectinload(PACase.clarifications),
                selectinload(PACase.reviewer_actions),
                selectinload(PACase.decision),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_cases_for_patient(
        self, patient_id: str, skip: int = 0, limit: int = 20
    ) -> list[PACase]:
        """Return all non-deleted cases for a patient, newest first."""
        stmt = (
            select(PACase)
            .where(PACase.patient_id == patient_id, PACase.deleted_at.is_(None))
            .order_by(PACase.submitted_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ----------------------------------------------------------
    # Reviewer Queue
    # ----------------------------------------------------------

    async def get_reviewer_queue(
        self,
        reviewer_id: str | None = None,
        statuses: list[CaseStatus] | None = None,
        priorities: list[CasePriority] | None = None,
        skip: int = 0,
        limit: int = 25,
    ) -> list[PACase]:
        """
        Fetch cases ready for reviewer action.

        Default queue: UNDER_REVIEW cases, sorted EMERGENT → URGENT → ROUTINE
        then by submitted_at ASC (oldest first — FIFO within priority).

        Args:
            reviewer_id: Filter to a specific reviewer's assigned cases
            statuses:    Override default status filter
            priorities:  Filter to specific priority levels
        """
        if statuses is None:
            statuses = [CaseStatus.UNDER_REVIEW, CaseStatus.ESCALATED]

        priority_order = {
            CasePriority.EMERGENT: 1,
            CasePriority.URGENT: 2,
            CasePriority.ROUTINE: 3,
        }

        stmt = (
            select(PACase)
            .where(
                PACase.deleted_at.is_(None),
                PACase.status.in_(statuses),
            )
            .order_by(
                # Custom priority sort — EMERGENT first
                func.field(PACase.priority, "EMERGENT", "URGENT", "ROUTINE"),
                PACase.submitted_at.asc(),
            )
            .offset(skip)
            .limit(limit)
        )

        if reviewer_id:
            stmt = stmt.where(PACase.assigned_reviewer_id == reviewer_id)
        if priorities:
            stmt = stmt.where(PACase.priority.in_(priorities))

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_unassigned_cases(self, limit: int = 50) -> list[PACase]:
        """Return cases in UNDER_REVIEW with no assigned reviewer."""
        stmt = (
            select(PACase)
            .where(
                PACase.status == CaseStatus.UNDER_REVIEW,
                PACase.assigned_reviewer_id.is_(None),
                PACase.deleted_at.is_(None),
            )
            .order_by(
                func.field(PACase.priority, "EMERGENT", "URGENT", "ROUTINE"),
                PACase.submitted_at.asc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ----------------------------------------------------------
    # Status Transitions
    # ----------------------------------------------------------

    async def transition_status(
        self,
        case_id: str,
        new_status: CaseStatus,
        actor_id: str | None = None,
    ) -> PACase:
        """
        Atomically transition a case's status.

        Validates that the case is not already in a terminal state.
        Logs the transition for audit purposes.
        """
        case = await self.get_by_id_or_raise(case_id, CaseNotFoundError)

        if case.is_decided and new_status not in (
            CaseStatus.PENDED, CaseStatus.ESCALATED
        ):
            raise CaseAlreadyDecidedError(
                details={
                    "case_id": case_id,
                    "current_status": case.status,
                    "requested_status": new_status,
                }
            )

        old_status = case.status
        case.status = new_status
        case.updated_at = datetime.now(UTC)

        if new_status == CaseStatus.PROCESSING and case.processing_started_at is None:
            case.processing_started_at = datetime.now(UTC)
        elif new_status == CaseStatus.UNDER_REVIEW and case.review_assigned_at is None:
            case.review_assigned_at = datetime.now(UTC)
        elif new_status in (CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.PENDED):
            case.decided_at = datetime.now(UTC)

        await self.session.flush()

        logger.info(
            "pa_case.status_transition",
            case_id=case_id,
            case_number=case.case_number,
            old_status=old_status,
            new_status=new_status,
            actor_id=actor_id,
        )
        return case

    async def assign_reviewer(
        self, case_id: str, reviewer_id: str
    ) -> PACase:
        """Assign a reviewer to a case and move to UNDER_REVIEW."""
        case = await self.get_by_id_or_raise(case_id, CaseNotFoundError)
        case.assigned_reviewer_id = reviewer_id
        case.review_assigned_at = datetime.now(UTC)
        if case.status not in (CaseStatus.UNDER_REVIEW, CaseStatus.ESCALATED):
            case.status = CaseStatus.UNDER_REVIEW
        await self.session.flush()
        logger.info(
            "pa_case.reviewer_assigned",
            case_id=case_id,
            reviewer_id=reviewer_id,
        )
        return case

    async def increment_clarification_count(self, case_id: str) -> PACase:
        """Increment the clarification counter (max 3 enforced at service layer)."""
        case = await self.get_by_id_or_raise(case_id, CaseNotFoundError)
        case.clarification_count += 1
        await self.session.flush()
        return case

    # ----------------------------------------------------------
    # Analytics
    # ----------------------------------------------------------

    async def count_by_status(self) -> dict[str, int]:
        """Return a dict of {status: count} for all non-deleted cases."""
        stmt = (
            select(PACase.status, func.count(PACase.id).label("cnt"))
            .where(PACase.deleted_at.is_(None))
            .group_by(PACase.status)
        )
        result = await self.session.execute(stmt)
        return {row.status: row.cnt for row in result.all()}

    async def count_by_priority(self) -> dict[str, int]:
        """Return a dict of {priority: count} for active cases."""
        stmt = (
            select(PACase.priority, func.count(PACase.id).label("cnt"))
            .where(
                PACase.deleted_at.is_(None),
                PACase.status.not_in([CaseStatus.APPROVED, CaseStatus.DENIED]),
            )
            .group_by(PACase.priority)
        )
        result = await self.session.execute(stmt)
        return {row.priority: row.cnt for row in result.all()}
