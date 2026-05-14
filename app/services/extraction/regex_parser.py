"""
Regex-based medical entity parser.

Fast, deterministic extraction pass run before the LLM.
High precision for well-structured entities (lab values, ICD codes, HbA1c).
Lower recall for free-form text — LLM fills the gap.

All patterns return SourceSpan objects so the confidence scorer can
perform grounding checks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from app.services.extraction.models import (
    ConfidenceSignals,
    GlucoseContext,
    GlucoseReading,
    HbA1cReading,
    InsulinRegimen,
    InsulinType,
    LabValue,
    Medication,
    SourceSpan,
    ValidatedCode,
    CodeSystem,
    ValidationStatus,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# ICD-10-CM
_ICD10_RE = re.compile(
    r"\b([A-TV-Z]\d{2}(?:\.\d{1,4})?)\b", re.IGNORECASE
)

# CPT: 5-digit numeric, not part of longer numbers
_CPT_RE = re.compile(r"(?<!\d)(\d{5})(?!\d)")

# CPT with explicit label
_CPT_LABELED_RE = re.compile(
    r"(?:cpt|procedure\s+code)[:\s#]+(\d{5})", re.IGNORECASE
)

# HbA1c — handles: "HbA1c 8.5%", "A1C of 9.2", "hemoglobin A1c 7.8%"
_HBA1C_RE = re.compile(
    r"(?:hb\s*a1c|hemoglobin\s+a1c|a1c|glycated\s+hemoglobin)"
    r"[\s:=of]*"
    r"(\d{1,2}(?:\.\d{1,2})?)\s*%?",
    re.IGNORECASE,
)

# Fasting glucose
_GLUCOSE_FASTING_RE = re.compile(
    r"fasting\s+(?:blood\s+)?(?:glucose|sugar|bg)"
    r"[\s:=of]*(\d{2,3}(?:\.\d)?)\s*(?:mg/dl|mg/dL|mmol/L)?",
    re.IGNORECASE,
)

# Random / general glucose
_GLUCOSE_GENERAL_RE = re.compile(
    r"(?:blood\s+)?(?:glucose|sugar|bg)\s+"
    r"(?:level|reading|result|was)?[\s:=of]*"
    r"(\d{2,3}(?:\.\d)?)\s*(mg/dl|mg/dL|mmol/L)",
    re.IGNORECASE,
)

# Postprandial glucose
_GLUCOSE_PP_RE = re.compile(
    r"(?:post(?:prandial)?|2[-\s]?hour|2hr|pp)\s+"
    r"(?:blood\s+)?(?:glucose|sugar)"
    r"[\s:=of]*(\d{2,3}(?:\.\d)?)\s*(?:mg/dl|mg/dL|mmol/L)?",
    re.IGNORECASE,
)

# Insulin patterns: "insulin lispro 10 units TID", "Glargine 20 units at bedtime"
_INSULIN_RE = re.compile(
    r"(?P<name>insulin\s+\w+|\w+\s+insulin|glargine|detemir|lispro|aspart|glulisine|"
    r"nph|regular\s+insulin|degludec|basaglar|humalog|novolog|lantus|toujeo|levemir|tresiba)"
    r"[\s,]*(?P<dose>\d+(?:\.\d+)?)\s*(?:units?|u\b)"
    r"(?:\s+(?P<frequency>qd|bid|tid|qid|once daily|twice daily|"
    r"three times|four times|every \d+ hours?|bedtime|hs|ac|pc))?",
    re.IGNORECASE,
)

_INSULIN_TYPE_MAP: dict[str, InsulinType] = {
    "lispro": InsulinType.RAPID_ACTING, "aspart": InsulinType.RAPID_ACTING,
    "glulisine": InsulinType.RAPID_ACTING, "humalog": InsulinType.RAPID_ACTING,
    "novolog": InsulinType.RAPID_ACTING, "apidra": InsulinType.RAPID_ACTING,
    "regular": InsulinType.SHORT_ACTING,
    "nph": InsulinType.INTERMEDIATE,
    "glargine": InsulinType.LONG_ACTING, "detemir": InsulinType.LONG_ACTING,
    "degludec": InsulinType.LONG_ACTING, "lantus": InsulinType.LONG_ACTING,
    "basaglar": InsulinType.LONG_ACTING, "toujeo": InsulinType.LONG_ACTING,
    "levemir": InsulinType.LONG_ACTING, "tresiba": InsulinType.LONG_ACTING,
}

# Common medications with dosage: "metformin 1000 mg twice daily"
_MEDICATION_RE = re.compile(
    r"(?P<name>metformin|glipizide|glyburide|glimepiride|sitagliptin|"
    r"empagliflozin|dapagliflozin|canagliflozin|pioglitazone|"
    r"lisinopril|amlodipine|atorvastatin|simvastatin|losartan|"
    r"omeprazole|pantoprazole|levothyroxine|aspirin|"
    r"semaglutide|liraglutide|dulaglutide|ozempic|victoza|wegovy|trulicity)"
    r"[\s,]+(?P<dose>\d+(?:\.\d+)?\s*(?:mg|mcg|units?|ml))"
    r"(?:\s+(?P<frequency>qd|bid|tid|qid|once|twice|daily|weekly|"
    r"every day|every week|[1-4]x/(?:day|week)))?",
    re.IGNORECASE,
)

# Lab values: "Creatinine: 1.2 mg/dL", "HgB 11.5 g/dL (L)"
_LAB_VALUE_RE = re.compile(
    r"(?P<test>(?:creatinine|bun|gfr|egfr|alt|ast|alp|bilirubin|albumin|"
    r"sodium|potassium|chloride|bicarbonate|hemoglobin|hgb|hematocrit|hct|"
    r"wbc|rbc|platelets?|ldl|hdl|triglycerides?|cholesterol|"
    r"tsh|t4|t3|ferritin|b12|folate|vitamin\s+d|psa|crp|esr|"
    r"glucose|bmp|cmp|cbc))"
    r"[\s:=]+(?P<value>\d+\.?\d*)\s*"
    r"(?P<unit>g/dL|mg/dL|mmol/L|mEq/L|U/L|IU/L|ng/mL|pg/mL|%|K/uL|M/uL|"
    r"mIU/L|ug/dL|nmol/L|umol/L|cells/uL)?"
    r"(?:\s*\((?P<flag>[HL]{1,2})\))?",
    re.IGNORECASE,
)

# Patient demographics
_DOB_RE       = re.compile(r"(?:dob|date of birth|birth date)[:\s]+([^\n]{5,25})", re.I)
_MRN_RE       = re.compile(r"\b(?:mrn|patient\s+id|chart)[:\s#]+([A-Z0-9\-]{4,20})\b", re.I)
_PATIENT_RE   = re.compile(r"(?:patient|name)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", re.I)
_NPI_RE       = re.compile(r"\bNPI[:\s#]+(\d{10})\b", re.I)
_PROVIDER_RE  = re.compile(r"(?:ordering\s+provider|prescriber|physician|dr\.?)[:\s]+([^\n]{5,60})", re.I)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

@dataclass
class RegexExtractionOutput:
    icd_codes:       list[ValidatedCode]
    cpt_codes:       list[ValidatedCode]
    hba1c_readings:  list[HbA1cReading]
    glucose_readings: list[GlucoseReading]
    insulin_regimens: list[InsulinRegimen]
    medications:     list[Medication]
    lab_values:      list[LabValue]
    patient_name:    str | None
    patient_dob:     str | None
    patient_mrn:     str | None
    provider_name:   str | None
    provider_npi:    str | None


class RegexParser:
    """
    Fast pattern-based extractor for well-structured medical entities.

    Usage:
        parser = RegexParser()
        output = parser.parse(document_text)
    """

    def __init__(self) -> None:
        self._log = structlog.get_logger(self.__class__.__name__)

    def parse(self, text: str) -> RegexExtractionOutput:
        return RegexExtractionOutput(
            icd_codes=self._extract_icd(text),
            cpt_codes=self._extract_cpt(text),
            hba1c_readings=self._extract_hba1c(text),
            glucose_readings=self._extract_glucose(text),
            insulin_regimens=self._extract_insulin(text),
            medications=self._extract_medications(text),
            lab_values=self._extract_lab_values(text),
            patient_name=self._first_match(_PATIENT_RE, text, 1),
            patient_dob=self._first_match(_DOB_RE, text, 1),
            patient_mrn=self._first_match(_MRN_RE, text, 1),
            provider_name=self._first_match(_PROVIDER_RE, text, 1),
            provider_npi=self._first_match(_NPI_RE, text, 1),
        )

    # ------------------------------------------------------------------

    def _extract_icd(self, text: str) -> list[ValidatedCode]:
        seen: set[str] = set()
        codes: list[ValidatedCode] = []
        for m in _ICD10_RE.finditer(text):
            code = m.group(1).upper()
            if code in seen:
                continue
            seen.add(code)
            codes.append(
                ValidatedCode(
                    code=code,
                    code_system=CodeSystem.ICD_10_CM,
                    validation_status=ValidationStatus.UNVERIFIED,
                    confidence=ConfidenceSignals(regex_found=True, grounded=True),
                    source_span=SourceSpan(text=code, start=m.start(), end=m.end()),
                )
            )
        return codes

    def _extract_cpt(self, text: str) -> list[ValidatedCode]:
        seen: set[str] = set()
        codes: list[ValidatedCode] = []

        # Labeled CPT first (higher precision)
        for m in _CPT_LABELED_RE.finditer(text):
            code = m.group(1)
            if code not in seen:
                seen.add(code)
                codes.append(ValidatedCode(
                    code=code,
                    code_system=CodeSystem.CPT_4,
                    validation_status=ValidationStatus.UNVERIFIED,
                    confidence=ConfidenceSignals(regex_found=True, grounded=True),
                    source_span=SourceSpan(text=m.group(0), start=m.start(), end=m.end()),
                ))

        # General 5-digit numbers (lower precision, filter duplicates)
        for m in _CPT_RE.finditer(text):
            code = m.group(1)
            if code not in seen and int(code) >= 10_000:
                seen.add(code)
                codes.append(ValidatedCode(
                    code=code,
                    code_system=CodeSystem.CPT_4,
                    validation_status=ValidationStatus.UNVERIFIED,
                    confidence=ConfidenceSignals(regex_found=True),
                ))
        return codes

    def _extract_hba1c(self, text: str) -> list[HbA1cReading]:
        readings: list[HbA1cReading] = []
        seen: set[float] = set()
        for m in _HBA1C_RE.finditer(text):
            try:
                value = float(m.group(1))
            except ValueError:
                continue
            if value in seen or not (4.0 <= value <= 20.0):
                continue
            seen.add(value)
            readings.append(
                HbA1cReading(
                    value=value,
                    is_elevated=value >= 6.5,
                    confidence=ConfidenceSignals(regex_found=True, grounded=True),
                    source_span=SourceSpan(text=m.group(0), start=m.start(), end=m.end()),
                )
            )
        return readings

    def _extract_glucose(self, text: str) -> list[GlucoseReading]:
        readings: list[GlucoseReading] = []

        def _add(m: re.Match, context: GlucoseContext) -> None:
            try:
                value = float(m.group(1))
            except (ValueError, IndexError):
                return
            if not (20.0 <= value <= 800.0):
                return
            unit_raw = m.group(2) if m.lastindex and m.lastindex >= 2 else "mg/dL"
            readings.append(GlucoseReading(
                value=value,
                unit=unit_raw or "mg/dL",
                context=context,
                is_abnormal=value < 70 or value > 180,
                confidence=ConfidenceSignals(regex_found=True, grounded=True),
                source_span=SourceSpan(text=m.group(0), start=m.start(), end=m.end()),
            ))

        for m in _GLUCOSE_FASTING_RE.finditer(text):
            _add(m, GlucoseContext.FASTING)
        for m in _GLUCOSE_PP_RE.finditer(text):
            _add(m, GlucoseContext.POSTPRANDIAL)
        for m in _GLUCOSE_GENERAL_RE.finditer(text):
            _add(m, GlucoseContext.RANDOM)
        return readings

    def _extract_insulin(self, text: str) -> list[InsulinRegimen]:
        regimens: list[InsulinRegimen] = []
        seen: set[str] = set()
        for m in _INSULIN_RE.finditer(text):
            name = m.group("name").strip()
            if name.lower() in seen:
                continue
            seen.add(name.lower())

            dose_str  = m.group("dose") or ""
            dose_num  = float(re.sub(r"[^\d.]", "", dose_str)) if dose_str else None
            itype     = _resolve_insulin_type(name)

            regimens.append(InsulinRegimen(
                insulin_name=name,
                insulin_type=itype,
                dose=dose_str,
                dose_numeric=dose_num,
                frequency=m.group("frequency"),
                confidence=ConfidenceSignals(regex_found=True, grounded=True),
                source_span=SourceSpan(text=m.group(0), start=m.start(), end=m.end()),
            ))
        return regimens

    def _extract_medications(self, text: str) -> list[Medication]:
        meds: list[Medication] = []
        seen: set[str] = set()
        for m in _MEDICATION_RE.finditer(text):
            name = m.group("name").strip().lower()
            if name in seen:
                continue
            seen.add(name)
            dose_raw = m.group("dose") or ""
            dose_num = None
            dose_unit = None
            d = re.match(r"([\d.]+)\s*(\w+)", dose_raw)
            if d:
                try:
                    dose_num = float(d.group(1))
                    dose_unit = d.group(2)
                except ValueError:
                    pass
            meds.append(Medication(
                name=name.title(),
                dose=dose_raw,
                dose_numeric=dose_num,
                dose_unit=dose_unit,
                frequency=m.group("frequency"),
                confidence=ConfidenceSignals(regex_found=True, grounded=True),
                source_span=SourceSpan(text=m.group(0), start=m.start(), end=m.end()),
            ))
        return meds

    def _extract_lab_values(self, text: str) -> list[LabValue]:
        values: list[LabValue] = []
        seen: set[str] = set()
        for m in _LAB_VALUE_RE.finditer(text):
            test = m.group("test").strip().lower()
            if test in seen:
                continue
            seen.add(test)
            try:
                value = float(m.group("value"))
            except (ValueError, TypeError):
                continue
            flag = m.group("flag") if m.lastindex and m.lastindex >= 4 else None
            values.append(LabValue(
                test_name=test.title(),
                value=value,
                unit=m.group("unit"),
                flag=flag,
                is_abnormal=flag is not None,
                confidence=ConfidenceSignals(regex_found=True, grounded=True),
                source_span=SourceSpan(text=m.group(0), start=m.start(), end=m.end()),
            ))
        return values

    @staticmethod
    def _first_match(pattern: re.Pattern, text: str, group: int) -> str | None:
        m = pattern.search(text)
        return m.group(group).strip() if m else None


def _resolve_insulin_type(name: str) -> InsulinType:
    lower = name.lower()
    for keyword, itype in _INSULIN_TYPE_MAP.items():
        if keyword in lower:
            return itype
    return InsulinType.UNKNOWN
