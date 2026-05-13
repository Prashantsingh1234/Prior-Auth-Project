"""
Patient ORM model.

Stores de-identified patient demographic and insurance membership data.
PII fields (name, DOB, contact) are present but must be encrypted at rest
in production using column-level encryption or a secrets vault.

HIPAA note: This table contains PHI. Access must be logged via audit_logs.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base.model import BaseModel

if TYPE_CHECKING:
    from app.models.pa_case import PACase


class Patient(BaseModel):
    """
    Insurance plan member / patient record.

    One patient may have multiple PA cases over time.
    member_id is the insurance plan's unique identifier for this patient
    and is the primary lookup key when correlating with claims data.
    """

    __tablename__ = "patients"

    # ----------------------------------------------------------
    # Demographics
    # ----------------------------------------------------------
    first_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Patient first name"
    )
    last_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Patient last name"
    )
    date_of_birth: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="Date of birth"
    )
    gender: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="M | F | Other | Unknown"
    )

    # ----------------------------------------------------------
    # Insurance
    # ----------------------------------------------------------
    member_id: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Insurance plan member ID"
    )
    group_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Insurance group number"
    )
    insurance_plan_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    insurance_plan_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    insurance_plan_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="HMO | PPO | EPO | POS | HDHP"
    )

    # ----------------------------------------------------------
    # Contact
    # ----------------------------------------------------------
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USA", comment="ISO 3166-1 alpha-3"
    )

    # ----------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------
    pa_cases: Mapped[list["PACase"]] = relationship(
        "PACase",
        back_populates="patient",
        lazy="raise",  # Require explicit eager loading in async context
        cascade="all, delete-orphan",
    )

    # ----------------------------------------------------------
    # Indexes & Constraints
    # ----------------------------------------------------------
    __table_args__ = (
        Index("ix_patients_member_id", "member_id"),
        Index("ix_patients_last_name", "last_name"),
        Index("ix_patients_dob", "date_of_birth"),
        Index("ix_patients_deleted_at", "deleted_at"),
        # A member_id should be unique per plan
        UniqueConstraint(
            "member_id", "insurance_plan_id",
            name="uq_patients_member_plan",
        ),
    )

    def __repr__(self) -> str:
        return f"<Patient id={self.id} member_id={self.member_id} name={self.last_name}>"
