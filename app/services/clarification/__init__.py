"""
PA Clarification Loop package.

Production-grade clarification system for prior authorization review.

Quick start:
    from app.services.clarification import ClarificationEngine

    engine = ClarificationEngine.from_settings()

    # Generate a question from evaluation gaps
    request = await engine.prepare_question(
        state=state,
        case_id=case_id,
        service_type=service_type,
        clinical_summary=clinical_summary,
    )

    # Process a received response
    response, patch = await engine.process_response(
        state=state,
        case_id=case_id,
        attempt_id=attempt_id,
        response_text=response_text,
    )

    # Decide whether to escalate
    decision = await engine.decide_escalation(
        state=state,
        case_id=case_id,
        service_type=service_type,
        clinical_summary=clinical_summary,
    )
"""

from app.services.clarification.detector import MissingInfoDetector
from app.services.clarification.engine import ClarificationEngine, get_clarification_engine
from app.services.clarification.escalation import ClarificationEscalationEngine
from app.services.clarification.generator import ClarificationQuestionGenerator
from app.services.clarification.models import (
    ClarificationEscalationDecision,
    ClarificationRequest,
    ClarificationResponse,
    EscalationReason,
    MissingInfoAnalysis,
    MissingInfoCategory,
    MissingInfoItem,
    NotificationEvent,
    NotificationPayload,
    QuestionPriority,
    ResponseQualityLevel,
)
from app.services.clarification.notifier import ReviewerNotifier
from app.services.clarification.prompts import (
    QUESTION_GENERATION_SYSTEM_PROMPT,
    RESPONSE_VALIDATION_SYSTEM_PROMPT,
    build_escalation_summary_prompt,
    build_question_generation_prompt,
    build_response_validation_prompt,
)
from app.services.clarification.state_manager import ClarificationStateManager

__all__ = [
    # Primary engine
    "ClarificationEngine",
    "get_clarification_engine",
    # Sub-components
    "MissingInfoDetector",
    "ClarificationQuestionGenerator",
    "ClarificationStateManager",
    "ClarificationEscalationEngine",
    "ReviewerNotifier",
    # Models
    "MissingInfoCategory",
    "MissingInfoItem",
    "MissingInfoAnalysis",
    "QuestionPriority",
    "ResponseQualityLevel",
    "EscalationReason",
    "NotificationEvent",
    "NotificationPayload",
    "ClarificationRequest",
    "ClarificationResponse",
    "ClarificationEscalationDecision",
    # Prompts
    "QUESTION_GENERATION_SYSTEM_PROMPT",
    "RESPONSE_VALIDATION_SYSTEM_PROMPT",
    "build_question_generation_prompt",
    "build_response_validation_prompt",
    "build_escalation_summary_prompt",
]
