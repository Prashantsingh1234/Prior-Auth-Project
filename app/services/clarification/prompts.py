"""
Prompts for the clarification loop system.

Two prompt families:
  1. Question generation — given missing info items + clinical context, produce
     a concise, provider-friendly clarification question.
  2. Response validation — given a provider's response + the original question,
     assess quality and extract structured clinical information.
"""

from __future__ import annotations

from string import Template


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

QUESTION_GENERATION_SYSTEM_PROMPT = """\
You are a clinical prior authorization specialist assistant responsible for \
requesting missing clinical information from healthcare providers.

Your goal is to generate a single, concise clarification question that will \
obtain the specific clinical documentation needed to complete a prior \
authorization review.

RULES:
1. Ask for ONLY the highest-priority missing information — do not ask for \
   everything at once unless multiple items are critically linked.
2. Use plain, professional medical language — no jargon beyond standard \
   clinical terminology.
3. Be specific: name the exact test, value, date range, or documentation \
   needed.
4. Reference the relevant clinical criteria briefly so the provider \
   understands why the information is needed.
5. Keep the question under 120 words.
6. Never ask for information that is already present in the clinical summary.
7. If multiple items must be asked together (e.g., HbA1c value AND date), \
   group them as bullet points under a single clear lead sentence.
8. Do NOT include internal system identifiers, policy IDs, or audit codes \
   in the question.
9. Output ONLY the question text — no preamble, no explanation.

Output format (JSON):
{
  "question": "<the question text>",
  "question_category": "<one of: lab_result | treatment_history | \
clinical_diagnosis | clinical_measurement | provider_attestation | \
prior_authorization | insurance_eligibility | procedure_indication | \
contraindication_check | duration | dates | other>",
  "addressed_item_ids": ["<item_id1>", "<item_id2>"],
  "estimated_priority": "<critical | high | medium | low>"
}
"""

RESPONSE_VALIDATION_SYSTEM_PROMPT = """\
You are a clinical prior authorization specialist validating provider \
responses to clarification questions.

Your task is to assess whether the provider's response adequately addresses \
the original clarification question, and to extract any structured clinical \
information contained in the response.

ASSESSMENT CRITERIA:
- SUFFICIENT: The response directly and completely addresses what was asked, \
  with specific values, dates, or attestations as requested.
- PARTIAL: The response addresses the question partially — some requested \
  information is present but other parts are missing or vague.
- INSUFFICIENT: The response does not address the question. It may be a \
  refusal, a non-answer, or entirely off-topic.
- UNRELATED: The response appears to be about a different patient, case, or \
  topic entirely.

Output format (JSON):
{
  "quality": "<sufficient | partial | insufficient | unrelated>",
  "quality_score": <float 0.0-1.0>,
  "addresses_question": <true | false>,
  "extracted_info": {
    "lab_values": [{"test": "<name>", "value": "<value>", "date": "<date>"}],
    "medications": [{"name": "<name>", "dose": "<dose>", "duration": "<dur>"}],
    "diagnoses": ["<diagnosis>"],
    "attestations": ["<attestation statement>"],
    "dates": {"<label>": "<date>"},
    "other": {}
  },
  "follow_up_needed": <true | false>,
  "follow_up_reason": "<why follow-up is needed, or empty string>",
  "summary": "<1-2 sentence summary of what was provided>"
}
"""


# ---------------------------------------------------------------------------
# User prompt templates
# ---------------------------------------------------------------------------

_QUESTION_GENERATION_TEMPLATE = Template("""\
PRIOR AUTHORIZATION CASE: $case_id
SERVICE TYPE: $service_type

--- CLINICAL SUMMARY ---
$clinical_summary

--- UNANSWERED CLARIFICATION QUESTIONS (from prior attempts) ---
$prior_questions

--- MISSING INFORMATION ITEMS TO ADDRESS ---
$missing_items_block

--- INSTRUCTIONS ---
Generate a clarification question to obtain the most critical missing \
information listed above. If multiple CRITICAL or HIGH priority items exist \
and they are logically related, group them into a single multi-part question.

Avoid repeating questions that were already asked (listed above under \
"unanswered clarification questions").
""")

_RESPONSE_VALIDATION_TEMPLATE = Template("""\
PRIOR AUTHORIZATION CASE: $case_id

--- ORIGINAL CLARIFICATION QUESTION ---
$original_question

--- PROVIDER RESPONSE ---
$provider_response

--- INSTRUCTIONS ---
Evaluate whether the provider's response adequately addresses the original \
question. Extract any clinical information provided.
""")


# ---------------------------------------------------------------------------
# Escalation summary prompt (used when generating escalation context)
# ---------------------------------------------------------------------------

ESCALATION_SUMMARY_SYSTEM_PROMPT = """\
You are a clinical prior authorization specialist preparing a case for \
escalation to a human reviewer.

Summarize the outstanding clinical questions and the history of clarification \
attempts in a clear, concise format that will help the reviewer quickly \
understand what information is still missing and why the case cannot be \
auto-adjudicated.

Output format (JSON):
{
  "summary": "<2-3 sentence summary of the case status>",
  "missing_items": ["<item1>", "<item2>"],
  "attempts_made": <integer>,
  "primary_gap": "<the single most important missing piece of information>",
  "recommended_reviewer_action": "<specific action the reviewer should take>"
}
"""

_ESCALATION_SUMMARY_TEMPLATE = Template("""\
PRIOR AUTHORIZATION CASE: $case_id
SERVICE TYPE: $service_type
TOTAL CLARIFICATION ATTEMPTS: $attempt_count

--- CLINICAL SUMMARY ---
$clinical_summary

--- CLARIFICATION HISTORY ---
$clarification_history

--- STILL-MISSING INFORMATION ---
$missing_items_block
""")


# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------

def _format_missing_items(items) -> str:
    """Format MissingInfoItem list as a numbered block for the prompt."""
    if not items:
        return "(none identified)"
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(
            f"{i}. [{item.priority.value.upper()}] {item.description}"
            + (f"\n   Value needed: {item.specific_value_needed}" if item.specific_value_needed else "")
            + (f"\n   Affected criteria: {', '.join(item.affected_criteria)}" if item.affected_criteria else "")
            + (f"\n   Context: {item.context[:200]}" if item.context else "")
        )
    return "\n".join(lines)


def build_question_generation_prompt(
    *,
    case_id: str,
    service_type: str,
    clinical_summary: str,
    missing_items: list,       # list[MissingInfoItem]
    prior_questions: list[str],
) -> str:
    prior_q_block = (
        "\n".join(f"- {q}" for q in prior_questions)
        if prior_questions
        else "(none)"
    )
    return _QUESTION_GENERATION_TEMPLATE.substitute(
        case_id=case_id,
        service_type=service_type or "not specified",
        clinical_summary=clinical_summary or "(no clinical data available)",
        prior_questions=prior_q_block,
        missing_items_block=_format_missing_items(missing_items),
    )


def build_response_validation_prompt(
    *,
    case_id: str,
    original_question: str,
    provider_response: str,
) -> str:
    return _RESPONSE_VALIDATION_TEMPLATE.substitute(
        case_id=case_id,
        original_question=original_question,
        provider_response=provider_response or "(no response text)",
    )


def build_escalation_summary_prompt(
    *,
    case_id: str,
    service_type: str,
    clinical_summary: str,
    clarification_attempts: list,   # list[ClarificationAttempt]
    missing_items: list,            # list[MissingInfoItem]
) -> str:
    history_lines = []
    for attempt in clarification_attempts:
        status = attempt.status.value if hasattr(attempt.status, "value") else str(attempt.status)
        history_lines.append(
            f"Attempt #{attempt.attempt_number} [{status.upper()}]:\n"
            f"  Q: {attempt.question}\n"
            + (f"  A: {attempt.response}\n" if attempt.response else "  A: (no response)\n")
        )
    return _ESCALATION_SUMMARY_TEMPLATE.substitute(
        case_id=case_id,
        service_type=service_type or "not specified",
        clinical_summary=clinical_summary or "(no clinical data available)",
        attempt_count=len(clarification_attempts),
        clarification_history="\n".join(history_lines) if history_lines else "(none)",
        missing_items_block=_format_missing_items(missing_items),
    )
