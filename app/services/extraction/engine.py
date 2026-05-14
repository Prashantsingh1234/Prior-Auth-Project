"""
Hybrid medical entity extraction engine.

Orchestrates the full extraction pipeline:
  1. Regex pass        — fast, deterministic, high precision
  2. LLM pass          — high recall, context-aware
  3. Merge             — combine both, resolve conflicts, dedup
  4. ICD validation    — WHO ICD-11 API per unique code
  5. CPT validation    — regex + category rules
  6. Confidence score  — multi-signal per entity
  7. Normalization     — standardize all values
  8. Grounding         — verify every entity appears in source text
  9. Result assembly   — ExtractionResult with quality metrics

Grounding (anti-hallucination):
  Any entity whose source_quote or code/value cannot be located in
  the original text has grounded=False and a confidence penalty applied.
"""

from __future__ import annotations

import time
from typing import TypeVar

import structlog

from app.services.extraction.confidence import ConfidenceScorer, ground_check
from app.services.extraction.icd_client import ICDApiClient
from app.services.extraction.llm_extractor import LLMExtractor
from app.services.extraction.models import (
    CodeSystem,
    ConfidenceSignals,
    ExtractionMethod,
    ExtractionRequest,
    ExtractionResult,
    HbA1cReading,
    GlucoseReading,
    InsulinRegimen,
    LabValue,
    Medication,
    PatientDemographics,
    ProviderDetails,
    SourceSpan,
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

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class ExtractionEngine:
    """
    Hybrid medical entity extraction engine.

    Usage:
        engine = ExtractionEngine.from_settings()
        result = await engine.extract(request)
    """

    def __init__(
        self,
        regex_parser:  RegexParser,
        llm_extractor: LLMExtractor,
        icd_validator: ICDValidator,
        cpt_validator: CPTValidator,
        scorer:        ConfidenceScorer,
    ) -> None:
        self._regex   = regex_parser
        self._llm     = llm_extractor
        self._icd_val = icd_validator
        self._cpt_val = cpt_validator
        self._scorer  = scorer
        self._log     = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Run the full hybrid extraction pipeline and return ExtractionResult."""
        start = time.monotonic()
        text  = request.text

        self._log.info(
            "engine.started",
            document_id=request.document_id,
            text_length=len(text),
        )

        # ----------------------------------------------------------
        # 1. Regex pass
        # ----------------------------------------------------------
        regex_out = self._regex.parse(text)

        # ----------------------------------------------------------
        # 2. LLM pass
        # ----------------------------------------------------------
        try:
            llm_out = await self._llm.extract(text, request.document_id)
            llm_tokens = llm_out.tokens_used
        except Exception as err:
            self._log.warning("engine.llm_failed", error=str(err))
            from app.services.extraction.llm_extractor import LLMExtractionOutput
            llm_out = LLMExtractionOutput(request.document_id)
            llm_tokens = 0

        # ----------------------------------------------------------
        # 3. Merge regex + LLM outputs
        # ----------------------------------------------------------
        icd_codes  = self._merge_codes(regex_out.icd_codes,  llm_out.icd_codes,  text, key=lambda c: normalize_icd_code(c.code))
        cpt_codes  = self._merge_codes(regex_out.cpt_codes,  llm_out.cpt_codes,  text, key=lambda c: normalize_cpt_code(c.code))
        medications = self._merge_list(
            regex_out.medications, llm_out.medications, text,
            key=lambda m: normalize_medication_name(m.name),
        )
        glucose   = self._merge_list(regex_out.glucose_readings, llm_out.glucose_readings, text, key=lambda g: str(g.value))
        hba1c     = self._merge_list(regex_out.hba1c_readings,   llm_out.hba1c_readings,   text, key=lambda h: str(h.value))
        insulin   = self._merge_list(regex_out.insulin_regimens, llm_out.insulin_regimens,  text, key=lambda i: i.insulin_name.lower())
        lab_vals  = self._merge_list(regex_out.lab_values,       llm_out.lab_values,        text, key=lambda l: l.test_name.lower())
        diagnoses = llm_out.diagnoses   # Only LLM produces structured diagnoses
        symptoms  = llm_out.symptoms
        complications = llm_out.complications
        treatment = llm_out.treatment_history

        # Merge patient / provider (LLM-primary, regex fills gaps)
        patient  = self._merge_patient(llm_out.patient,  regex_out, text)
        provider = self._merge_provider(llm_out.provider, regex_out, text)

        # ----------------------------------------------------------
        # 4. Validate ICD codes via WHO API
        # ----------------------------------------------------------
        validated_icd: list[ValidatedCode] = []
        if request.run_icd_validation:
            unique_icd = self._unique_codes(icd_codes, normalize_icd_code)
            validated_icd = await self._icd_val.validate_batch(
                [normalize_icd_code(c.code) for c in unique_icd],
                CodeSystem.ICD_10_CM,
            )
            for vc, orig in zip(validated_icd, unique_icd):
                vc.confidence = orig.confidence
                vc.source_span = orig.source_span
                self._scorer.score_from_validation(vc.confidence, vc.validation_status)
        else:
            validated_icd = icd_codes

        # ----------------------------------------------------------
        # 5. Validate CPT codes
        # ----------------------------------------------------------
        validated_cpt: list[ValidatedCode] = []
        if request.run_cpt_validation:
            unique_cpt = self._unique_codes(cpt_codes, normalize_cpt_code)
            validated_cpt = self._cpt_val.validate_batch(
                [normalize_cpt_code(c.code) for c in unique_cpt]
            )
            for vc, orig in zip(validated_cpt, unique_cpt):
                vc.confidence = orig.confidence
                vc.source_span = orig.source_span
                self._scorer.score_from_validation(vc.confidence, vc.validation_status)
        else:
            validated_cpt = cpt_codes

        # ----------------------------------------------------------
        # 6. Normalize all entities
        # ----------------------------------------------------------
        for med in medications:
            med.name = normalize_medication_name(med.name).title()
            med.frequency = normalize_frequency(med.frequency)
        for lv in lab_vals:
            lv.test_name = normalize_lab_test_name(lv.test_name)
            lv.unit = normalize_unit(lv.unit)
        for g in glucose:
            g.unit = normalize_unit(g.unit) or "mg/dL"
            g.date = normalize_date(g.date)
        for h in hba1c:
            h.date = normalize_date(h.date)

        # ----------------------------------------------------------
        # 7. Score all non-code entities
        # ----------------------------------------------------------
        all_scores: list[float] = []
        for entity_list in [medications, glucose, hba1c, insulin, lab_vals, symptoms, diagnoses]:
            for e in entity_list:
                if hasattr(e, "confidence"):
                    s = self._scorer.score(e.confidence, api_applicable=False)
                    all_scores.append(s)
        for code in validated_icd + validated_cpt:
            all_scores.append(code.confidence.final_score)

        overall_confidence = self._scorer.compute_overall(all_scores)

        # ----------------------------------------------------------
        # 8. Grounding pass — verify entities in source text
        # ----------------------------------------------------------
        grounding_passes = 0
        grounding_total  = 0
        for entity_list in [medications, glucose, hba1c, insulin, lab_vals, symptoms]:
            for e in entity_list:
                name = getattr(e, "name", None) or getattr(e, "test_name", None) or str(getattr(e, "value", ""))
                if name:
                    grounding_total += 1
                    if ground_check(name, text):
                        grounding_passes += 1
                    else:
                        if hasattr(e, "confidence"):
                            e.confidence.grounded = False

        grounding_rate = grounding_passes / grounding_total if grounding_total else 1.0

        # ----------------------------------------------------------
        # 9. Assemble result
        # ----------------------------------------------------------
        elapsed_ms = (time.monotonic() - start) * 1000

        method = ExtractionMethod.HYBRID if llm_tokens > 0 else ExtractionMethod.REGEX

        result = ExtractionResult(
            document_id=request.document_id,
            extraction_method=method,
            overall_confidence=overall_confidence,
            patient=patient,
            provider=provider,
            diagnoses=diagnoses,
            icd_codes=validated_icd,
            cpt_codes=validated_cpt,
            medications=medications,
            glucose_readings=glucose,
            hba1c_readings=hba1c,
            insulin_regimens=insulin,
            lab_values=lab_vals,
            symptoms=symptoms,
            treatment_history=treatment,
            complications=complications,
            icd_codes_validated=sum(1 for c in validated_icd if c.validation_status == ValidationStatus.VALID),
            cpt_codes_validated=sum(1 for c in validated_cpt if c.validation_status == ValidationStatus.VALID),
            grounding_pass_rate=round(grounding_rate, 3),
            processing_time_ms=elapsed_ms,
            llm_tokens_used=llm_tokens,
        )

        self._log.info(
            "engine.complete",
            document_id=request.document_id,
            method=method,
            total_entities=result.total_entities_extracted,
            icd_validated=result.icd_codes_validated,
            confidence=overall_confidence,
            elapsed_ms=round(elapsed_ms, 1),
        )

        self._emit_metrics(result)
        return result

    # ------------------------------------------------------------------
    # Merge helpers
    # ------------------------------------------------------------------

    def _merge_codes(
        self,
        regex_list: list[ValidatedCode],
        llm_list:   list[ValidatedCode],
        source_text: str,
        key,
    ) -> list[ValidatedCode]:
        merged: dict[str, ValidatedCode] = {}
        for code in regex_list:
            k = key(code)
            merged[k] = code
            code.confidence.regex_found = True
            code.confidence.grounded = ground_check(code.code, source_text)
        for code in llm_list:
            k = key(code)
            if k in merged:
                # Consensus: both found it
                merged[k].confidence.llm_found = True
                merged[k].confidence.consensus = True
            else:
                merged[k] = code
                code.confidence.llm_found = True
                code.confidence.grounded = ground_check(code.code, source_text)
        return list(merged.values())

    def _merge_list(
        self,
        regex_list: list[T],
        llm_list:   list[T],
        source_text: str,
        key,
    ) -> list[T]:
        merged: dict[str, T] = {}
        for item in regex_list:
            k = key(item)
            merged[k] = item
            if hasattr(item, "confidence"):
                item.confidence.regex_found = True
        for item in llm_list:
            k = key(item)
            if k in merged:
                if hasattr(merged[k], "confidence"):
                    merged[k].confidence.llm_found = True
                    merged[k].confidence.consensus = True
            else:
                merged[k] = item
                if hasattr(item, "confidence"):
                    item.confidence.llm_found = True
        return list(merged.values())

    def _merge_patient(self, llm_patient: PatientDemographics, regex_out, text: str) -> PatientDemographics:
        p = llm_patient
        if not p.patient_name and regex_out.patient_name:
            p = p.model_copy(update={"patient_name": regex_out.patient_name})
        if not p.date_of_birth and regex_out.patient_dob:
            p = p.model_copy(update={"date_of_birth": normalize_date(regex_out.patient_dob)})
        if not p.mrn and regex_out.patient_mrn:
            p = p.model_copy(update={"mrn": regex_out.patient_mrn})
        return p

    def _merge_provider(self, llm_provider: ProviderDetails, regex_out, text: str) -> ProviderDetails:
        pv = llm_provider
        if not pv.provider_name and regex_out.provider_name:
            pv = pv.model_copy(update={"provider_name": regex_out.provider_name})
        if not pv.npi and regex_out.provider_npi:
            pv = pv.model_copy(update={"npi": regex_out.provider_npi})
        return pv

    @staticmethod
    def _unique_codes(codes: list[ValidatedCode], normalize_fn) -> list[ValidatedCode]:
        seen: dict[str, ValidatedCode] = {}
        for code in codes:
            k = normalize_fn(code.code)
            if k not in seen:
                seen[k] = code
        return list(seen.values())

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @staticmethod
    def _emit_metrics(result: ExtractionResult) -> None:
        try:
            from app.monitoring.metrics import LLM_TOKENS_TOTAL, LLM_LATENCY_SECONDS
            LLM_TOKENS_TOTAL.labels(operation="extraction", token_type="total").inc(result.llm_tokens_used)
            LLM_LATENCY_SECONDS.labels(operation="extraction").observe(result.processing_time_ms / 1000)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls) -> "ExtractionEngine":
        icd_client = ICDApiClient.from_settings()
        return cls(
            regex_parser  = RegexParser(),
            llm_extractor = LLMExtractor.from_settings(),
            icd_validator = ICDValidator(icd_client),
            cpt_validator = CPTValidator(),
            scorer        = ConfidenceScorer(),
        )

    @classmethod
    def regex_only(cls) -> "ExtractionEngine":
        """Lightweight engine without LLM or API calls — for testing / offline use."""
        from unittest.mock import AsyncMock, MagicMock
        mock_llm = MagicMock()
        mock_llm.extract = AsyncMock(side_effect=RuntimeError("LLM disabled"))
        mock_icd = MagicMock()
        mock_icd.validate_batch = AsyncMock(return_value=[])
        return cls(
            regex_parser  = RegexParser(),
            llm_extractor = mock_llm,
            icd_validator = mock_icd,
            cpt_validator = CPTValidator(),
            scorer        = ConfidenceScorer(),
        )
