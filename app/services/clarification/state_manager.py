"""
Clarification state manager.

Handles:
  - Validating provider responses via LLM
  - Building immutable state patches for workflow state updates
  - Applying ClarificationAttempt status transitions

All state mutations return dicts — callers merge them into PAWorkflowState.
The actual LangGraph state update is done in the node layer, not here.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.clarification.models import (
    ClarificationResponse,
    ResponseQualityLevel,
)
from app.services.clarification.prompts import (
    RESPONSE_VALIDATION_SYSTEM_PROMPT,
    build_response_validation_prompt,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Response validation LLM helpers
# ---------------------------------------------------------------------------

def _parse_validation_response(raw: str) -> dict[str, Any] | None:
    text = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
        if "quality" not in data:
            return None
        return data
    except (json.JSONDecodeError, ValueError):
        return None


_QUALITY_MAP = {
    "sufficient":   ResponseQualityLevel.SUFFICIENT,
    "partial":      ResponseQualityLevel.PARTIAL,
    "insufficient": ResponseQualityLevel.INSUFFICIENT,
    "unrelated":    ResponseQualityLevel.UNRELATED,
}


def _heuristic_quality(response_text: str, question: str) -> ResponseQualityLevel:
    """Simple rule-based quality check when LLM is unavailable."""
    if not response_text or len(response_text.strip()) < 10:
        return ResponseQualityLevel.INSUFFICIENT

    # Check token overlap between response and question as a proxy
    q_tokens = set(re.findall(r"\b\w+\b", question.lower()))
    r_tokens = set(re.findall(r"\b\w+\b", response_text.lower()))
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "for", "of",
                 "to", "in", "on", "with", "and", "or", "that", "this",
                 "please", "provide", "documentation"}
    q_tokens -= stopwords
    r_tokens -= stopwords

    if not q_tokens:
        return ResponseQualityLevel.PARTIAL

    overlap = len(q_tokens & r_tokens) / len(q_tokens)
    if overlap >= 0.50:
        return ResponseQualityLevel.SUFFICIENT
    if overlap >= 0.20:
        return ResponseQualityLevel.PARTIAL
    return ResponseQualityLevel.INSUFFICIENT


# ---------------------------------------------------------------------------
# State manager
# ---------------------------------------------------------------------------

class ClarificationStateManager:
    """
    Validates responses and builds workflow state patches.
    """

    def __init__(self, openai_client=None, model: str = "gpt-4o-mini") -> None:
        self._client = openai_client
        self._model = model
        self._log = structlog.get_logger(self.__class__.__name__)

    async def validate_response(
        self,
        *,
        case_id: str,
        attempt,               # ClarificationAttempt
        response_text: str,
        responded_by: str = "provider",
    ) -> ClarificationResponse:
        """
        Validate a provider response via LLM (or heuristic fallback).

        Returns a ClarificationResponse with quality assessment and
        extracted clinical information.
        """
        llm_result = await self._llm_validate(
            case_id=case_id,
            question=attempt.question,
            response_text=response_text,
        )

        if llm_result:
            quality_str = str(llm_result.get("quality", "")).lower()
            quality = _QUALITY_MAP.get(quality_str, ResponseQualityLevel.PARTIAL)
            quality_score = float(llm_result.get("quality_score", 0.5))
            quality_score = max(0.0, min(1.0, quality_score))
            addresses = bool(llm_result.get("addresses_question", quality != ResponseQualityLevel.INSUFFICIENT))
            extracted = llm_result.get("extracted_info", {})
            follow_up = bool(llm_result.get("follow_up_needed", False))
            follow_up_reason = str(llm_result.get("follow_up_reason", ""))
        else:
            quality = _heuristic_quality(response_text, attempt.question)
            quality_score = {
                ResponseQualityLevel.SUFFICIENT:   0.85,
                ResponseQualityLevel.PARTIAL:      0.50,
                ResponseQualityLevel.INSUFFICIENT: 0.15,
                ResponseQualityLevel.UNRELATED:    0.05,
            }[quality]
            addresses = quality in (ResponseQualityLevel.SUFFICIENT, ResponseQualityLevel.PARTIAL)
            extracted = {}
            follow_up = quality == ResponseQualityLevel.PARTIAL
            follow_up_reason = "Partial response — additional detail may be needed" if follow_up else ""

        self._log.info(
            "clarification.state_manager.response_validated",
            case_id=case_id,
            attempt_id=attempt.attempt_id,
            quality=quality.value,
            score=quality_score,
            llm_used=llm_result is not None,
        )

        return ClarificationResponse(
            attempt_id=attempt.attempt_id,
            response_text=response_text,
            responded_by=responded_by,
            response_quality=quality,
            quality_score=quality_score,
            extracted_info=extracted,
            addresses_question=addresses,
            follow_up_needed=follow_up,
            follow_up_reason=follow_up_reason,
        )

    async def _llm_validate(
        self,
        *,
        case_id: str,
        question: str,
        response_text: str,
    ) -> dict[str, Any] | None:
        if self._client is None:
            return None

        user_prompt = build_response_validation_prompt(
            case_id=case_id,
            original_question=question,
            provider_response=response_text,
        )

        t0 = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": RESPONSE_VALIDATION_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=512,
                temperature=0,
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            raw = response.choices[0].message.content or ""
            parsed = _parse_validation_response(raw)
            if parsed:
                self._log.debug(
                    "clarification.state_manager.llm_validation_success",
                    case_id=case_id,
                    latency_ms=round(latency_ms, 1),
                )
            return parsed
        except Exception as exc:
            self._log.error(
                "clarification.state_manager.llm_validation_error",
                case_id=case_id,
                error=str(exc),
            )
            return None

    # ------------------------------------------------------------------
    # State patch builders
    # ------------------------------------------------------------------

    @staticmethod
    def build_answered_patch(
        *,
        attempt,              # ClarificationAttempt
        response_text: str,
        responded_by: str,
        quality: ResponseQualityLevel,
    ) -> dict[str, Any]:
        """
        Build a state patch that marks a ClarificationAttempt as ANSWERED.

        The patch contains the updated attempt list with the matching attempt
        replaced by an answered copy.  LangGraph reducers handle the list merge.
        """
        from app.services.workflow.state.models import ClarificationStatus
        updated = attempt.model_copy(update={
            "status":       ClarificationStatus.ANSWERED,
            "response":     response_text,
            "responded_by": responded_by,
            "answered_at":  datetime.now(UTC),
        })
        return {"clarification_attempts": [updated]}

    @staticmethod
    def build_timeout_patch(*, attempt_id: str) -> dict[str, Any]:
        """
        Find and mark an attempt as TIMEOUT.

        Returns a minimal patch; the actual attempt lookup is done by the
        node which has access to the full state.
        """
        return {"_timeout_attempt_id": attempt_id}

    @staticmethod
    def build_skipped_patch(*, attempt_id: str) -> dict[str, Any]:
        return {"_skip_attempt_id": attempt_id}

    @classmethod
    def from_settings(cls) -> "ClarificationStateManager":
        try:
            from app.core.config.settings import get_settings
            from openai import AsyncOpenAI
            settings = get_settings()
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            model = getattr(settings, "clarification_validation_model", "gpt-4o-mini")
            return cls(openai_client=client, model=model)
        except Exception:
            logger.warning("clarification.state_manager.no_client")
            return cls(openai_client=None)
