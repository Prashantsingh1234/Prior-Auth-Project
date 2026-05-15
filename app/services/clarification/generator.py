"""
LLM-powered clarification question generator.

Responsibilities:
  - Call an LLM with the question-generation prompt
  - Parse and validate the JSON response
  - Deduplicate against prior questions using token overlap
  - Fall back to template-based questions if the LLM fails
  - Return a ClarificationRequest ready for state storage
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.services.clarification.models import (
    ClarificationRequest,
    MissingInfoAnalysis,
    MissingInfoItem,
    QuestionPriority,
)
from app.services.clarification.prompts import (
    QUESTION_GENERATION_SYSTEM_PROMPT,
    build_question_generation_prompt,
)

logger = structlog.get_logger(__name__)

# Maximum items to include in a single question
_MAX_ITEMS_PER_QUESTION = 3

# Minimum token overlap fraction to consider a question a duplicate
_DUPLICATE_OVERLAP_THRESHOLD = 0.60

# Deadline for provider response
_DEFAULT_DEADLINE_HOURS = 48


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b\w+\b", text.lower()))


def _is_duplicate(new_question: str, prior_questions: list[str]) -> bool:
    """Return True if new_question is substantially similar to any prior question."""
    new_tokens = _tokenize(new_question)
    if not new_tokens:
        return False
    for prior in prior_questions:
        prior_tokens = _tokenize(prior)
        if not prior_tokens:
            continue
        overlap = len(new_tokens & prior_tokens) / len(new_tokens | prior_tokens)
        if overlap >= _DUPLICATE_OVERLAP_THRESHOLD:
            return True
    return False


# ---------------------------------------------------------------------------
# Template fallback
# ---------------------------------------------------------------------------

_CATEGORY_TEMPLATES: dict[str, str] = {
    "lab_result": (
        "To complete the prior authorization review, please provide the most recent "
        "lab test result(s) relevant to this request, including the test name, value, "
        "units, and collection date."
    ),
    "treatment_history": (
        "Please document the patient's prior treatment history relevant to this "
        "authorization, including medication names, doses, duration, and the reason "
        "for discontinuation if applicable."
    ),
    "clinical_diagnosis": (
        "Please confirm the patient's primary diagnosis with supporting clinical "
        "documentation, including ICD codes and the date of diagnosis."
    ),
    "clinical_measurement": (
        "Please provide the patient's current clinical measurements (e.g., BMI, "
        "blood pressure) with the date of measurement."
    ),
    "provider_attestation": (
        "Please provide a written attestation from the treating physician confirming "
        "medical necessity for the requested service."
    ),
    "prior_authorization": (
        "Please provide documentation of any prior authorization history for this "
        "or related services, including PA numbers and dates."
    ),
    "duration": (
        "Please document how long the patient has been on the current therapy, "
        "including the start date."
    ),
    "dates": (
        "Please provide the relevant clinical dates requested, including onset of "
        "condition and date of most recent clinical evaluation."
    ),
    "procedure_indication": (
        "Please provide the clinical indication and medical necessity justification "
        "for the requested procedure."
    ),
    "contraindication_check": (
        "Please document any contraindications, allergies, or adverse reactions "
        "that prevent use of alternative therapies."
    ),
    "other": (
        "To complete the prior authorization review, please provide the additional "
        "clinical documentation needed to evaluate the request."
    ),
}


def _build_template_question(items: list[MissingInfoItem]) -> str:
    if not items:
        return _CATEGORY_TEMPLATES["other"]

    top_item = items[0]
    category_key = top_item.category.value
    base = _CATEGORY_TEMPLATES.get(category_key, _CATEGORY_TEMPLATES["other"])

    # If multiple critical/high items exist, list them as bullets
    high_items = [i for i in items if i.priority in (QuestionPriority.CRITICAL, QuestionPriority.HIGH)]
    if len(high_items) > 1:
        bullets = "\n".join(f"• {i.description}" for i in high_items[:_MAX_ITEMS_PER_QUESTION])
        return (
            "To complete the prior authorization review, please provide the "
            f"following information:\n{bullets}"
        )

    if top_item.specific_value_needed:
        return f"Please provide: {top_item.specific_value_needed}"

    return base


# ---------------------------------------------------------------------------
# LLM response parser
# ---------------------------------------------------------------------------

def _parse_generation_response(raw: str) -> dict[str, Any] | None:
    """Extract JSON from the LLM response, tolerating markdown fences."""
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", raw).strip()
    # Find first JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
        if "question" not in data or not isinstance(data["question"], str):
            return None
        return data
    except (json.JSONDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class ClarificationQuestionGenerator:
    """
    Generates a single clarification question from a MissingInfoAnalysis.

    Uses an LLM for rich contextual questions; falls back to templates on
    LLM failure or when the LLM produces a duplicate question.
    """

    def __init__(self, openai_client=None, model: str = "gpt-4o-mini") -> None:
        self._client = openai_client
        self._model = model

    async def generate(
        self,
        *,
        analysis: MissingInfoAnalysis,
        case_id: str,
        service_type: str,
        clinical_summary: str,
        deadline_hours: int = _DEFAULT_DEADLINE_HOURS,
    ) -> ClarificationRequest:
        """
        Generate the best clarification question for the given analysis.

        Returns a ClarificationRequest with deadline set.
        Caller is responsible for persisting this as a ClarificationAttempt.
        """
        items = analysis.prioritized_items[:_MAX_ITEMS_PER_QUESTION]
        if not items:
            # All items already asked — return a catch-all
            return self._fallback_request(
                items=analysis.actionable_items or [],
                analysis=analysis,
                deadline_hours=deadline_hours,
                generated_by="template",
            )

        # Try LLM generation
        llm_result = await self._try_llm_generation(
            case_id=case_id,
            service_type=service_type,
            clinical_summary=clinical_summary,
            items=items,
            prior_questions=analysis.prior_questions,
        )

        if llm_result and not _is_duplicate(llm_result["question"], analysis.prior_questions):
            return ClarificationRequest(
                question=llm_result["question"],
                question_category=llm_result.get("question_category", items[0].category.value),
                addressed_items=items,
                missing_criteria=[cid for item in items for cid in item.affected_criteria],
                priority=items[0].priority,
                deadline=datetime.now(UTC) + timedelta(hours=deadline_hours),
                generated_by="llm",
                generation_model=self._model,
                tokens_used=llm_result.get("tokens_used", 0),
            )

        # LLM failed or produced a duplicate — use template
        logger.info(
            "clarification.generator.template_fallback",
            case_id=case_id,
            reason="llm_failed" if llm_result is None else "duplicate_detected",
        )
        return self._fallback_request(
            items=items,
            analysis=analysis,
            deadline_hours=deadline_hours,
            generated_by="template",
        )

    async def _try_llm_generation(
        self,
        *,
        case_id: str,
        service_type: str,
        clinical_summary: str,
        items: list[MissingInfoItem],
        prior_questions: list[str],
    ) -> dict[str, Any] | None:
        if self._client is None:
            return None

        user_prompt = build_question_generation_prompt(
            case_id=case_id,
            service_type=service_type,
            clinical_summary=clinical_summary,
            missing_items=items,
            prior_questions=prior_questions,
        )

        t0 = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": QUESTION_GENERATION_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=512,
                temperature=0,
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            raw = response.choices[0].message.content or ""
            parsed = _parse_generation_response(raw)
            if parsed:
                parsed["tokens_used"] = response.usage.total_tokens if response.usage else 0
                logger.debug(
                    "clarification.generator.llm_success",
                    case_id=case_id,
                    latency_ms=round(latency_ms, 1),
                    tokens=parsed["tokens_used"],
                )
                return parsed
            logger.warning(
                "clarification.generator.parse_failed",
                case_id=case_id,
                raw_snippet=raw[:200],
            )
            return None
        except Exception as exc:
            logger.error(
                "clarification.generator.llm_error",
                case_id=case_id,
                error=str(exc),
            )
            return None

    @staticmethod
    def _fallback_request(
        items: list[MissingInfoItem],
        analysis: MissingInfoAnalysis,
        deadline_hours: int,
        generated_by: str,
    ) -> ClarificationRequest:
        question = _build_template_question(items)
        category = items[0].category.value if items else "other"
        priority = items[0].priority if items else QuestionPriority.MEDIUM
        return ClarificationRequest(
            question=question,
            question_category=category,
            addressed_items=items,
            missing_criteria=[cid for item in items for cid in item.affected_criteria],
            priority=priority,
            deadline=datetime.now(UTC) + timedelta(hours=deadline_hours),
            generated_by=generated_by,
        )

    @classmethod
    def from_settings(cls) -> "ClarificationQuestionGenerator":
        """Build generator from application settings."""
        try:
            from app.core.config.settings import get_settings
            from openai import AsyncOpenAI
            settings = get_settings()
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            model = getattr(settings, "clarification_model", "gpt-4o-mini")
            return cls(openai_client=client, model=model)
        except Exception:
            logger.warning("clarification.generator.no_client")
            return cls(openai_client=None)
