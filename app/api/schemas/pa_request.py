"""
Schemas for PA request submission and document upload.

POST /pa-requests — submit a new prior authorization request
POST /cases/{id}/documents — upload a supporting clinical document
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.api.schemas.common import BaseSchema
from app.models.enums import (
    CasePriority,
    DocumentType,
    ServiceType,
)


# ----------------------------------------------------------
# Patient Sub-Schema
# ----------------------------------------------------------

class PatientSubmitSchema(BaseSchema):
    """
    Patient identification for PA submission.

    Either an existing patient_id OR full demographics must be provided.
    If patient_id is given and the patient exists, records are linked.
    If demographics are given, a new patient record is created.
    """

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    # Existing patient reference
    patient_id: str | None = Field(
        default=None,
        description="UUID of an existing patient record",
    )

    # Demographics (required if patient_id not provided)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = Field(default=None)
    gender: str | None = Field(default=None, max_length=20)
    member_id: str | None = Field(
        default=None, max_length=50,
        description="Insurance member ID",
    )
    group_number: str | None = Field(default=None, max_length=50)
    insurance_plan_name: str | None = Field(default=None, max_length=200)
    insurance_plan_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_patient_identity(self) -> "PatientSubmitSchema":
        has_id   = self.patient_id is not None
        has_name = self.first_name is not None and self.last_name is not None
        if not has_id and not has_name:
            raise ValueError(
                "Either patient_id or patient demographics (first_name + last_name) must be provided"
            )
        return self


# ----------------------------------------------------------
# Provider Sub-Schema
# ----------------------------------------------------------

class ProviderSubmitSchema(BaseSchema):
    """Ordering provider for the PA request."""

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    npi: str = Field(description="10-digit National Provider Identifier")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    specialty: str | None = Field(default=None, max_length=200)
    organization_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    fax: str | None = Field(default=None, max_length=20)

    @field_validator("npi")
    @classmethod
    def validate_npi(cls, v: str) -> str:
        """NPI must be exactly 10 digits."""
        cleaned = re.sub(r"\D", "", v)
        if len(cleaned) != 10:
            raise ValueError("NPI must be exactly 10 digits")
        return cleaned


# ----------------------------------------------------------
# PA Request Submission
# ----------------------------------------------------------

class PARequestCreate(BaseSchema):
    """
    Body for POST /pa-requests.

    Clinical details + patient/provider identifiers.
    Documents are uploaded separately via POST /cases/{id}/documents.
    """

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    # Patient
    patient: PatientSubmitSchema

    # Ordering provider
    provider: ProviderSubmitSchema

    # Service classification
    service_type: ServiceType = Field(
        description="Category of the requested service",
    )
    cpt_codes: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="CPT procedure codes",
    )
    icd_codes: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="ICD-10 diagnosis codes",
    )
    requested_service_description: str | None = Field(
        default=None,
        max_length=5000,
        description="Free-text description of the requested service",
    )
    clinical_notes: str | None = Field(
        default=None,
        max_length=20_000,
        description="Additional clinical notes from the provider",
    )

    # Case management
    priority: CasePriority = Field(
        default=CasePriority.ROUTINE,
        description="Clinical urgency level",
    )
    external_reference_id: str | None = Field(
        default=None,
        max_length=100,
        description="Reference ID from the submitter's system (e.g., EHR encounter ID)",
    )
    source_channel: str | None = Field(
        default="api",
        max_length=50,
        description="Submission channel: api | portal | fax | hl7",
    )

    @field_validator("cpt_codes", mode="before")
    @classmethod
    def normalize_cpt_codes(cls, v: list[str]) -> list[str]:
        return [code.strip().upper() for code in v if code.strip()]

    @field_validator("icd_codes", mode="before")
    @classmethod
    def normalize_icd_codes(cls, v: list[str]) -> list[str]:
        return [code.strip().upper() for code in v if code.strip()]


# ----------------------------------------------------------
# Document Upload
# ----------------------------------------------------------

class DocumentUploadMetadata(BaseSchema):
    """
    Metadata provided alongside a document file upload (multipart/form-data).
    Sent as a JSON-encoded form field alongside the file binary.
    """

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    document_type: DocumentType = Field(
        description="Category of the clinical document",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
    )


# ----------------------------------------------------------
# Submission Response
# ----------------------------------------------------------

class PARequestSubmitResponse(BaseSchema):
    """Response body for a successfully submitted PA request."""

    case_id: str
    case_number: str
    status: str
    priority: str
    submitted_at: datetime | None
    message: str = "Prior authorization request submitted successfully. Processing will begin shortly."
    estimated_processing_minutes: int = Field(
        default=5,
        description="Estimated time for AI processing to complete",
    )


class DocumentUploadResponse(BaseSchema):
    """Response body for a successfully uploaded document."""

    document_id: str
    case_id: str
    document_type: str
    original_filename: str
    file_size_bytes: int
    content_type: str
    uploaded_at: datetime
    ocr_status: str
    message: str = "Document uploaded. OCR processing queued."
