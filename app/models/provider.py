"""
Provider ORM model.

Represents the ordering or treating provider submitting the PA request.
NPI (National Provider Identifier) is the unique identifier for all US
healthcare providers and is used as the primary lookup key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base.model import BaseModel
from app.models.enums import ProviderType

if TYPE_CHECKING:
    from app.models.pa_case import PACase


class Provider(BaseModel):
    """
    Healthcare provider (ordering physician or facility).

    NPI uniquely identifies a provider across all US healthcare systems.
    Both individual practitioners and organizations are supported.
    """

    __tablename__ = "providers"

    # ----------------------------------------------------------
    # Identity
    # ----------------------------------------------------------
    npi: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="10-digit National Provider Identifier"
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        SAEnum(ProviderType), nullable=False, default=ProviderType.INDIVIDUAL
    )
    tax_id: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="Federal Tax ID / EIN"
    )

    # ----------------------------------------------------------
    # Individual provider fields
    # ----------------------------------------------------------
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    credentials: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="e.g. MD, DO, NP, PA-C"
    )
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ----------------------------------------------------------
    # Organization fields
    # ----------------------------------------------------------
    organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ----------------------------------------------------------
    # Contact
    # ----------------------------------------------------------
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ----------------------------------------------------------
    # Address
    # ----------------------------------------------------------
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ----------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------
    pa_cases: Mapped[list["PACase"]] = relationship(
        "PACase",
        back_populates="provider",
        lazy="raise",
    )

    # ----------------------------------------------------------
    # Indexes & Constraints
    # ----------------------------------------------------------
    __table_args__ = (
        UniqueConstraint("npi", name="uq_providers_npi"),
        Index("ix_providers_npi", "npi"),
        Index("ix_providers_last_name", "last_name"),
        Index("ix_providers_organization", "organization_name"),
        Index("ix_providers_deleted_at", "deleted_at"),
    )

    @property
    def display_name(self) -> str:
        """Return the most appropriate display name for the provider."""
        if self.provider_type == ProviderType.ORGANIZATION and self.organization_name:
            return self.organization_name
        parts = [p for p in [self.first_name, self.last_name] if p]
        name = " ".join(parts)
        if self.credentials:
            name += f", {self.credentials}"
        return name or self.npi

    def __repr__(self) -> str:
        return f"<Provider id={self.id} npi={self.npi} name={self.display_name}>"
