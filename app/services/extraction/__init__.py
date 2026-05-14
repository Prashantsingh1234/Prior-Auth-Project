"""
Medical entity extraction engine package.

Primary entry point:
    from app.services.extraction import ExtractionEngine, ExtractionRequest

    engine = ExtractionEngine.from_settings()
    result = await engine.extract(ExtractionRequest(
        document_id="doc-001",
        text="Patient Jane Doe, HbA1c 8.5%, diagnosis E11.65...",
    ))
"""

from app.services.extraction.confidence import ConfidenceScorer, ground_check
from app.services.extraction.engine import ExtractionEngine
from app.services.extraction.icd_client import ICDApiClient, ICDCodeInfo
from app.services.extraction.llm_extractor import LLMExtractor
from app.services.extraction.models import (
    CodeSystem,
    ConfidenceSignals,
    Complication,
    Diagnosis,
    ExtractionMethod,
    ExtractionRequest,
    ExtractionResult,
    GlucoseContext,
    GlucoseReading,
    HbA1cReading,
    InsulinRegimen,
    InsulinType,
    LabValue,
    Medication,
    PatientDemographics,
    ProviderDetails,
    SourceSpan,
    Symptom,
    TreatmentHistory,
    ValidatedCode,
    ValidationStatus,
)
from app.services.extraction.normalizer import (
    normalize_cpt_code,
    normalize_date,
    normalize_frequency,
    normalize_icd_code,
    normalize_lab_test_name,
    normalize_medication_name,
    normalize_unit,
)
from app.services.extraction.regex_parser import RegexParser
from app.services.extraction.validators import CPTValidator, ICDValidator

__all__ = [
    # Engine
    "ExtractionEngine",
    # Services
    "RegexParser",
    "LLMExtractor",
    "ICDValidator",
    "CPTValidator",
    "ICDApiClient",
    "ICDCodeInfo",
    "ConfidenceScorer",
    "ground_check",
    # Models
    "ExtractionRequest",
    "ExtractionResult",
    "PatientDemographics",
    "ProviderDetails",
    "ValidatedCode",
    "Medication",
    "GlucoseReading",
    "HbA1cReading",
    "InsulinRegimen",
    "LabValue",
    "Diagnosis",
    "Symptom",
    "TreatmentHistory",
    "Complication",
    "ConfidenceSignals",
    "SourceSpan",
    "CodeSystem",
    "ValidationStatus",
    "ExtractionMethod",
    "GlucoseContext",
    "InsulinType",
    # Normalizers
    "normalize_icd_code",
    "normalize_cpt_code",
    "normalize_medication_name",
    "normalize_lab_test_name",
    "normalize_unit",
    "normalize_date",
    "normalize_frequency",
]
