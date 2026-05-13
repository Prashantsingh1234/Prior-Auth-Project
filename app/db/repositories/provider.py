"""Provider repository — NPI-based lookup and upsert."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.provider import Provider


class ProviderRepository(BaseRepository[Provider]):
    """CRUD and lookup operations for Provider records."""

    model = Provider

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_npi(self, npi: str) -> Provider | None:
        """Look up a provider by NPI (National Provider Identifier)."""
        stmt = select(Provider).where(
            Provider.npi == npi,
            Provider.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_by_npi(self, npi: str, **create_kwargs) -> tuple[Provider, bool]:
        """
        Fetch provider by NPI or create a new record.

        Returns:
            (provider, created) tuple
        """
        existing = await self.get_by_npi(npi)
        if existing:
            return existing, False
        provider = await self.create(npi=npi, **create_kwargs)
        return provider, True

    async def search_by_name(self, name: str) -> list[Provider]:
        """Search by organization or last name (case-insensitive)."""
        stmt = (
            select(Provider)
            .where(
                (
                    Provider.last_name.ilike(f"%{name}%")
                    | Provider.organization_name.ilike(f"%{name}%")
                ),
                Provider.deleted_at.is_(None),
            )
            .limit(50)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
