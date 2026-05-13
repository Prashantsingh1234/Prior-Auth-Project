"""Patient repository — lookup by member ID and demographics."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.patient import Patient


class PatientRepository(BaseRepository[Patient]):
    """CRUD and lookup operations for Patient records."""

    model = Patient

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_member_id(
        self, member_id: str, plan_id: str | None = None
    ) -> Patient | None:
        """
        Look up a patient by insurance member ID.

        Args:
            member_id: Insurance plan member identifier
            plan_id:   Optionally scope to a specific insurance plan
        """
        stmt = select(Patient).where(
            Patient.member_id == member_id,
            Patient.deleted_at.is_(None),
        )
        if plan_id:
            stmt = stmt.where(Patient.insurance_plan_id == plan_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_by_name(
        self, last_name: str, first_name: str | None = None
    ) -> list[Patient]:
        """Case-insensitive name search — returns up to 50 matches."""
        stmt = select(Patient).where(
            Patient.last_name.ilike(f"%{last_name}%"),
            Patient.deleted_at.is_(None),
        )
        if first_name:
            stmt = stmt.where(Patient.first_name.ilike(f"%{first_name}%"))
        stmt = stmt.order_by(Patient.last_name, Patient.first_name).limit(50)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create(
        self, member_id: str, plan_id: str | None = None, **create_kwargs
    ) -> tuple[Patient, bool]:
        """
        Fetch existing patient by member_id + plan_id, or create new.

        Returns:
            (patient, created) — created=True if a new record was inserted
        """
        existing = await self.get_by_member_id(member_id, plan_id)
        if existing:
            return existing, False
        patient = await self.create(
            member_id=member_id,
            insurance_plan_id=plan_id,
            **create_kwargs,
        )
        return patient, True
