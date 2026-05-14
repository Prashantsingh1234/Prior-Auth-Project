"""
Data models for the medical entity extraction engine.

These models are the structured output schema of the extraction pipeline.
Every extracted entity carries a confidence score and grounding evidence
(the source text span it was derived from).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExtractionMethod(str, Enum):
    REGEX       = "regex"
    LLM         = "llm"
    HYBRID      = "hybrid"      # Both regex and LLM agreed
    API_LOOKUP  = "api_lookup"  # Validated via external API


class CodeSystem(str, Enum):
    ICD_10_CM  = "ICD-10-CM"
    ICD_11     = "ICD-11"
    CPT_4      = "CPT-4"
    SNOMED     = "SNOMED-CT"
    RXNORM     = "RxNorm"
    LOINC      = "LOINC"


class ValidationStatus(str, Enum):
    VALID       = "VALID"
    INVALID     = "INVALID"
    UNVERIFIED  = "UNVERIFIED"   # Not checked against API
    NOT_FOUND   = "NOT_FOUND"    # API returned no match


class GlucoseContext(str, Enum):
    FASTING         = "fasting"
    POSTPRANDIAL    = "postprandial"
    RANDOM          = "random"
    BEDTIME         = "bedtime"
    UNKNOWN         = "unknown"


class InsulinType(str, Enum):
    RAPID_ACTING    = "rapid_acting"    # Lispro, Aspart, Glulisine
    SHORT_ACTING    = "short_acting"    # Regular
    INTERMEDIATE    = "intermediate"    # NPH
    LONG_ACTING     = "long_acting"     # Glargine, Detemir, Degludec
    PREMIXED        = "premixed"
    UNKNOWN         = "unknown"


# ---------------------------------------------------------------------------
# Confidence signal model
# ---------------------------------------------------------------------------

class ConfidenceSignals(BaseModel):
    """Breakdown of how confidence was calculated for an entity."""
    regex_found:     bool = False
    llm_found:       bool = False
    api_validated:   bool = False
    grounded:        bool = False    # Entity text found in source
    consensus:       bool = False    # Regex and LLM agree
    final_score:     float = Field(0.0, ge=0.0, le=1.0)

    @property
    def signal_count(self) -> int:
        return sum([
            self.regex_found, self.llm_found,
            self.api_validated, self.grounded, self.consensus,
        ])


# ---------------------------------------------------------------------------
# Individual entity models
# ---------------------------------------------------------------------------

class SourceSpan(BaseModel):
    """Reference back to the source text for grounding verification."""
    text: str
    start: int = -1
    end:   int = -1
    page:  int = 1


class PatientDemographics(BaseModel):
    patient_name:    str | None = None
    date_of_birth:   str | None = None    # ISO 8601 preferred
    age:             int | None = None
    gender:          str | None = None
    mrn:             str | None = None
    insurance_id:    str | None = None
    address:         str | None = None
    phone:           str | None = None
    confidence:      ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_spans:    list[SourceSpan] = Field(default_factory=list)


class ProviderDetails(BaseModel):
    provider_name:   str | None = None
    npi:             str | None = None
    specialty:       str | None = None
    facility:        str | None = None
    address:         str | None = None
    phone:           str | None = None
    fax:             str | None = None
    signature_date:  str | None = None
    confidence:      ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_spans:    list[SourceSpan] = Field(default_factory=list)


class ValidatedCode(BaseModel):
    """A medical code (ICD or CPT) with validation metadata."""
    code:             str
    description:      str | None = None
    code_system:      CodeSystem
    validation_status: ValidationStatus = ValidationStatus.UNVERIFIED
    is_primary:       bool = False
    api_description:  str | None = None   # Description returned by API
    confidence:       ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_span:      SourceSpan | None = None


class Medication(BaseModel):
    name:           str
    generic_name:   str | None = None
    dose:           str | None = None      # e.g. "10 mg"
    dose_numeric:   float | None = None
    dose_unit:      str | None = None
    frequency:      str | None = None      # e.g. "twice daily", "BID"
    route:          str | None = None      # oral, subcutaneous, etc.
    start_date:     str | None = None
    end_date:       str | None = None
    active:         bool = True
    rxnorm_code:    str | None = None
    confidence:     ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_span:    SourceSpan | None = None


class GlucoseReading(BaseModel):
    value:          float
    unit:           str = "mg/dL"
    context:        GlucoseContext = GlucoseContext.UNKNOWN
    date:           str | None = None
    time:           str | None = None
    is_abnormal:    bool | None = None     # None = unknown reference range
    reference_low:  float | None = None
    reference_high: float | None = None
    confidence:     ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_span:    SourceSpan | None = None


class HbA1cReading(BaseModel):
    value:       float             # percentage
    unit:        str = "%"
    date:        str | None = None
    is_elevated: bool | None = None   # > 6.5% = diagnostic for T2DM
    confidence:  ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_span: SourceSpan | None = None

    @property
    def is_diagnostic(self) -> bool:
        """HbA1c ≥ 6.5% is diagnostic for diabetes."""
        return self.value >= 6.5

    @property
    def is_controlled(self) -> bool:
        """ADA target for most adults: < 7.0%."""
        return self.value < 7.0


class InsulinRegimen(BaseModel):
    insulin_name:  str
    insulin_type:  InsulinType = InsulinType.UNKNOWN
    dose:          str | None = None
    dose_numeric:  float | None = None
    dose_unit:     str = "units"
    frequency:     str | None = None
    frequency_per_day: int | None = None
    route:         str = "subcutaneous"
    timing:        str | None = None   # "before meals", "bedtime"
    confidence:    ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_span:   SourceSpan | None = None


class LabValue(BaseModel):
    test_name:     str
    value:         float | None = None
    value_text:    str | None = None   # For non-numeric results
    unit:          str | None = None
    reference_low:  float | None = None
    reference_high: float | None = None
    is_abnormal:   bool | None = None
    flag:          str | None = None   # "H", "L", "HH", "LL"
    date:          str | None = None
    loinc_code:    str | None = None
    confidence:    ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_span:   SourceSpan | None = None


class Diagnosis(BaseModel):
    name:           str
    icd_codes:      list[ValidatedCode] = Field(default_factory=list)
    is_primary:     bool = False
    onset_date:     str | None = None
    status:         str | None = None   # "active", "resolved", "chronic"
    severity:       str | None = None
    confidence:     ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_span:    SourceSpan | None = None


class Symptom(BaseModel):
    name:         str
    duration:     str | None = None
    severity:     str | None = None   # mild / moderate / severe
    onset_date:   str | None = None
    frequency:    str | None = None   # "intermittent", "constant"
    confidence:   ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_span:  SourceSpan | None = None


class TreatmentHistory(BaseModel):
    treatment:    str
    type:         str | None = None   # "medication", "procedure", "lifestyle"
    start_date:   str | None = None
    end_date:     str | None = None
    status:       str = "historical"   # "active", "historical", "discontinued"
    reason_stopped: str | None = None
    cpt_codes:    list[ValidatedCode] = Field(default_factory=list)
    confidence:   ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_span:  SourceSpan | None = None


class Complication(BaseModel):
    name:         str
    icd_codes:    list[ValidatedCode] = Field(default_factory=list)
    onset_date:   str | None = None
    severity:     str | None = None
    related_to:   str | None = None   # "diabetes", "hypertension", etc.
    confidence:   ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    source_span:  SourceSpan | None = None


# ---------------------------------------------------------------------------
# Complete extraction result
# ---------------------------------------------------------------------------

class ExtractionResult(BaseModel):
    """Complete structured output of the medical entity extraction engine."""
    document_id:        str
    extraction_method:  ExtractionMethod
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0)

    # Entities
    patient:            PatientDemographics = Field(default_factory=PatientDemographics)
    provider:           ProviderDetails = Field(default_factory=ProviderDetails)
    diagnoses:          list[Diagnosis] = Field(default_factory=list)
    icd_codes:          list[ValidatedCode] = Field(default_factory=list)
    cpt_codes:          list[ValidatedCode] = Field(default_factory=list)
    medications:        list[Medication] = Field(default_factory=list)
    glucose_readings:   list[GlucoseReading] = Field(default_factory=list)
    hba1c_readings:     list[HbA1cReading] = Field(default_factory=list)
    insulin_regimens:   list[InsulinRegimen] = Field(default_factory=list)
    lab_values:         list[LabValue] = Field(default_factory=list)
    symptoms:           list[Symptom] = Field(default_factory=list)
    treatment_history:  list[TreatmentHistory] = Field(default_factory=list)
    complications:      list[Complication] = Field(default_factory=list)

    # Quality metadata
    total_entities_extracted: int = 0
    icd_codes_validated:      int = 0
    cpt_codes_validated:      int = 0
    grounding_pass_rate:      float = 0.0
    warnings:                 list[str] = Field(default_factory=list)
    processing_time_ms:       float = 0.0
    llm_tokens_used:          int = 0

    def model_post_init(self, __context: Any) -> None:
        self.total_entities_extracted = (
            len(self.diagnoses) + len(self.icd_codes) + len(self.cpt_codes)
            + len(self.medications) + len(self.glucose_readings)
            + len(self.hba1c_readings) + len(self.insulin_regimens)
            + len(self.lab_values) + len(self.symptoms)
            + len(self.treatment_history) + len(self.complications)
        )


class ExtractionRequest(BaseModel):
    """Input to the extraction engine."""
    document_id:    str
    text:           str              # Full document text
    document_type:  str = "general"  # hint for prompt selection
    case_id:        str | None = None
    run_icd_validation: bool = True
    run_cpt_validation: bool = True
    max_llm_tokens: int = 4000
