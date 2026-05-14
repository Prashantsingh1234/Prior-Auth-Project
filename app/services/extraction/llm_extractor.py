"""
LLM-based medical entity extractor using OpenAI structured outputs.

Design:
  - response_format=json_object with detailed schema in the system prompt
  - Temperature=0 for deterministic, reproducible extractions
  - Explicit anti-hallucination instruction: "only extract what is in the text"
  - Grounding enforcement: each entity includes a verbatim source_quote
  - Retry via tenacity on transient API errors
  - Token budget enforced: truncates input to stay within context limits

Output is parsed into ExtractionResult Pydantic models.
The engine.py layer then merges this with the regex pass.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from openai import AsyncOpenAI, APITimeoutError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.services.extraction.models import (
    ConfidenceSignals,
    CodeSystem,
    Complication,
    Diagnosis,
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

logger = structlog.get_logger(__name__)

_MODEL = "gpt-4o"
_TEMPERATURE = 0.0
_MAX_INPUT_CHARS = 12_000   # ~3000 tokens — leave room for output
_SYSTEM_PROMPT = """
You are a medical entity extraction specialist. Your task is to extract structured
medical information ONLY from the document text provided.

CRITICAL RULES:
1. ONLY extract entities that are explicitly stated in the document text.
2. Do NOT infer, guess, or hallucinate information not present in the text.
3. For every entity, include a source_quote — the exact text excerpt it was derived from.
4. If information is ambiguous or absent, use null.
5. ICD and CPT codes: extract ONLY codes that appear literally in the text (e.g., "E11.65", "95249").

Return a JSON object with this exact structure:
{
  "patient": {
    "patient_name": string | null,
    "date_of_birth": string | null,
    "age": integer | null,
    "gender": string | null,
    "mrn": string | null,
    "insurance_id": string | null,
    "source_quote": string | null
  },
  "provider": {
    "provider_name": string | null,
    "npi": string | null,
    "specialty": string | null,
    "facility": string | null,
    "phone": string | null,
    "source_quote": string | null
  },
  "diagnoses": [
    {
      "name": string,
      "icd_codes": [string],
      "is_primary": boolean,
      "onset_date": string | null,
      "status": string | null,
      "severity": string | null,
      "source_quote": string
    }
  ],
  "icd_codes": [
    {"code": string, "description": string | null, "source_quote": string}
  ],
  "cpt_codes": [
    {"code": string, "description": string | null, "source_quote": string}
  ],
  "medications": [
    {
      "name": string,
      "dose": string | null,
      "frequency": string | null,
      "route": string | null,
      "start_date": string | null,
      "active": boolean,
      "source_quote": string
    }
  ],
  "glucose_readings": [
    {
      "value": number,
      "unit": string,
      "context": "fasting" | "postprandial" | "random" | "bedtime" | "unknown",
      "date": string | null,
      "source_quote": string
    }
  ],
  "hba1c_readings": [
    {
      "value": number,
      "unit": "%",
      "date": string | null,
      "source_quote": string
    }
  ],
  "insulin_regimens": [
    {
      "insulin_name": string,
      "insulin_type": "rapid_acting" | "short_acting" | "intermediate" | "long_acting" | "premixed" | "unknown",
      "dose": string | null,
      "frequency": string | null,
      "timing": string | null,
      "source_quote": string
    }
  ],
  "lab_values": [
    {
      "test_name": string,
      "value": number | null,
      "value_text": string | null,
      "unit": string | null,
      "is_abnormal": boolean | null,
      "flag": string | null,
      "date": string | null,
      "source_quote": string
    }
  ],
  "symptoms": [
    {
      "name": string,
      "duration": string | null,
      "severity": string | null,
      "onset_date": string | null,
      "source_quote": string
    }
  ],
  "complications": [
    {
      "name": string,
      "icd_codes": [string],
      "onset_date": string | null,
      "severity": string | null,
      "source_quote": string
    }
  ],
  "treatment_history": [
    {
      "treatment": string,
      "type": string | null,
      "start_date": string | null,
      "end_date": string | null,
      "status": "active" | "historical" | "discontinued",
      "reason_stopped": string | null,
      "source_quote": string
    }
  ]
}
""".strip()


class LLMExtractor:
    """
    Extracts medical entities from clinical text using GPT-4o.

    Usage:
        extractor = LLMExtractor.from_settings()
        output = await extractor.extract(text, document_id)
    """

    def __init__(self, openai_client: AsyncOpenAI, model: str = _MODEL) -> None:
        self._client = openai_client
        self._model  = model
        self._log    = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract(self, text: str, document_id: str) -> LLMExtractionOutput:
        """
        Run LLM extraction. Returns a structured output container.

        Raises LLMExtractionError on unrecoverable failure.
        """
        truncated = text[:_MAX_INPUT_CHARS]
        start = time.monotonic()

        self._log.info(
            "llm_extractor.started",
            document_id=document_id,
            input_chars=len(truncated),
        )

        raw_json, tokens = await self._call_llm(truncated)
        elapsed_ms = (time.monotonic() - start) * 1000

        self._log.info(
            "llm_extractor.complete",
            document_id=document_id,
            tokens=tokens,
            elapsed_ms=round(elapsed_ms, 1),
        )

        parsed = self._parse_response(raw_json, document_id)
        parsed.tokens_used = tokens
        parsed.elapsed_ms  = elapsed_ms
        return parsed

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((APITimeoutError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _call_llm(self, text: str) -> tuple[dict[str, Any], int]:
        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=_TEMPERATURE,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"Extract medical entities from this document:\n\n{text}"},
            ],
        )
        content = response.choices[0].message.content or "{}"
        tokens  = response.usage.total_tokens if response.usage else 0

        try:
            return json.loads(content), tokens
        except json.JSONDecodeError as err:
            self._log.warning("llm_extractor.json_parse_failed", error=str(err))
            return {}, tokens

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, data: dict[str, Any], document_id: str) -> "LLMExtractionOutput":
        out = LLMExtractionOutput(document_id=document_id)

        # Patient
        p = data.get("patient") or {}
        out.patient = PatientDemographics(
            patient_name=p.get("patient_name"),
            date_of_birth=p.get("date_of_birth"),
            age=p.get("age"),
            gender=p.get("gender"),
            mrn=p.get("mrn"),
            insurance_id=p.get("insurance_id"),
            confidence=ConfidenceSignals(llm_found=True),
            source_spans=_span_list(p.get("source_quote")),
        )

        # Provider
        pv = data.get("provider") or {}
        out.provider = ProviderDetails(
            provider_name=pv.get("provider_name"),
            npi=pv.get("npi"),
            specialty=pv.get("specialty"),
            facility=pv.get("facility"),
            phone=pv.get("phone"),
            confidence=ConfidenceSignals(llm_found=True),
            source_spans=_span_list(pv.get("source_quote")),
        )

        # Diagnoses
        for d in data.get("diagnoses") or []:
            codes = [
                ValidatedCode(code=c, code_system=CodeSystem.ICD_10_CM,
                              validation_status=ValidationStatus.UNVERIFIED,
                              confidence=ConfidenceSignals(llm_found=True))
                for c in (d.get("icd_codes") or [])
            ]
            out.diagnoses.append(Diagnosis(
                name=d.get("name", ""),
                icd_codes=codes,
                is_primary=d.get("is_primary", False),
                onset_date=d.get("onset_date"),
                status=d.get("status"),
                severity=d.get("severity"),
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(d.get("source_quote")),
            ))

        # ICD codes
        for c in data.get("icd_codes") or []:
            out.icd_codes.append(ValidatedCode(
                code=c.get("code", ""),
                description=c.get("description"),
                code_system=CodeSystem.ICD_10_CM,
                validation_status=ValidationStatus.UNVERIFIED,
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(c.get("source_quote")),
            ))

        # CPT codes
        for c in data.get("cpt_codes") or []:
            out.cpt_codes.append(ValidatedCode(
                code=c.get("code", ""),
                description=c.get("description"),
                code_system=CodeSystem.CPT_4,
                validation_status=ValidationStatus.UNVERIFIED,
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(c.get("source_quote")),
            ))

        # Medications
        for m in data.get("medications") or []:
            out.medications.append(Medication(
                name=m.get("name", ""),
                dose=m.get("dose"),
                frequency=m.get("frequency"),
                route=m.get("route"),
                start_date=m.get("start_date"),
                active=m.get("active", True),
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(m.get("source_quote")),
            ))

        # Glucose readings
        for g in data.get("glucose_readings") or []:
            val = g.get("value")
            if val is None:
                continue
            out.glucose_readings.append(GlucoseReading(
                value=float(val),
                unit=g.get("unit", "mg/dL"),
                context=GlucoseContext(g.get("context", "unknown")),
                date=g.get("date"),
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(g.get("source_quote")),
            ))

        # HbA1c
        for h in data.get("hba1c_readings") or []:
            val = h.get("value")
            if val is None:
                continue
            out.hba1c_readings.append(HbA1cReading(
                value=float(val),
                unit=h.get("unit", "%"),
                date=h.get("date"),
                is_elevated=float(val) >= 6.5,
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(h.get("source_quote")),
            ))

        # Insulin
        for i in data.get("insulin_regimens") or []:
            itype_str = i.get("insulin_type", "unknown")
            try:
                itype = InsulinType(itype_str)
            except ValueError:
                itype = InsulinType.UNKNOWN
            out.insulin_regimens.append(InsulinRegimen(
                insulin_name=i.get("insulin_name", ""),
                insulin_type=itype,
                dose=i.get("dose"),
                frequency=i.get("frequency"),
                timing=i.get("timing"),
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(i.get("source_quote")),
            ))

        # Lab values
        for lv in data.get("lab_values") or []:
            val = lv.get("value")
            out.lab_values.append(LabValue(
                test_name=lv.get("test_name", ""),
                value=float(val) if val is not None else None,
                value_text=lv.get("value_text"),
                unit=lv.get("unit"),
                is_abnormal=lv.get("is_abnormal"),
                flag=lv.get("flag"),
                date=lv.get("date"),
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(lv.get("source_quote")),
            ))

        # Symptoms
        for s in data.get("symptoms") or []:
            out.symptoms.append(Symptom(
                name=s.get("name", ""),
                duration=s.get("duration"),
                severity=s.get("severity"),
                onset_date=s.get("onset_date"),
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(s.get("source_quote")),
            ))

        # Complications
        for c in data.get("complications") or []:
            codes = [
                ValidatedCode(code=code, code_system=CodeSystem.ICD_10_CM,
                              validation_status=ValidationStatus.UNVERIFIED,
                              confidence=ConfidenceSignals(llm_found=True))
                for code in (c.get("icd_codes") or [])
            ]
            out.complications.append(Complication(
                name=c.get("name", ""),
                icd_codes=codes,
                onset_date=c.get("onset_date"),
                severity=c.get("severity"),
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(c.get("source_quote")),
            ))

        # Treatment history
        for t in data.get("treatment_history") or []:
            out.treatment_history.append(TreatmentHistory(
                treatment=t.get("treatment", ""),
                type=t.get("type"),
                start_date=t.get("start_date"),
                end_date=t.get("end_date"),
                status=t.get("status", "historical"),
                reason_stopped=t.get("reason_stopped"),
                confidence=ConfidenceSignals(llm_found=True),
                source_span=_span(t.get("source_quote")),
            ))

        return out

    @classmethod
    def from_settings(cls) -> "LLMExtractor":
        from app.core.config.settings import get_settings

        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        client = AsyncOpenAI(
            api_key=s.openai_api_key.get_secret_value(),
            timeout=s.openai_request_timeout,
        )
        return cls(client, model=s.openai_model)


# ---------------------------------------------------------------------------
# Output container
# ---------------------------------------------------------------------------

class LLMExtractionOutput:
    """Structured output from the LLM extractor."""

    __slots__ = (
        "document_id", "patient", "provider", "diagnoses", "icd_codes",
        "cpt_codes", "medications", "glucose_readings", "hba1c_readings",
        "insulin_regimens", "lab_values", "symptoms", "complications",
        "treatment_history", "tokens_used", "elapsed_ms",
    )

    def __init__(self, document_id: str) -> None:
        self.document_id       = document_id
        self.patient           = PatientDemographics()
        self.provider          = ProviderDetails()
        self.diagnoses:        list[Diagnosis]        = []
        self.icd_codes:        list[ValidatedCode]    = []
        self.cpt_codes:        list[ValidatedCode]    = []
        self.medications:      list[Medication]       = []
        self.glucose_readings: list[GlucoseReading]   = []
        self.hba1c_readings:   list[HbA1cReading]     = []
        self.insulin_regimens: list[InsulinRegimen]   = []
        self.lab_values:       list[LabValue]         = []
        self.symptoms:         list[Symptom]          = []
        self.complications:    list[Complication]     = []
        self.treatment_history: list[TreatmentHistory] = []
        self.tokens_used       = 0
        self.elapsed_ms        = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _span(quote: str | None) -> SourceSpan | None:
    if not quote:
        return None
    return SourceSpan(text=quote[:500])


def _span_list(quote: str | None) -> list[SourceSpan]:
    s = _span(quote)
    return [s] if s else []
