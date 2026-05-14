"""
LLM prompts for the PA reasoning engine.

Prompts are versioned constants — any change here constitutes a prompt version
bump.  The model is instructed to produce structured JSON only (no prose).

Prompt design principles:
  - Role-play as a clinical prior authorization specialist (not a doctor)
  - Grounded reasoning ONLY — cite specific evidence from provided context
  - Explicit prohibition on inferring data not present in context
  - Status must be one of: MET | NOT_MET | UNDETERMINED
  - Every MET or NOT_MET determination MUST have at least one evidence citation
  - UNDETERMINED must specify what information is missing

Prompt tiers:
  STANDARD  — used for SMALL and MEDIUM models
  ADVANCED  — used for LARGE models; adds chain-of-thought scaffolding
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Output JSON schema (embedded for validation + prompt injection)
# ---------------------------------------------------------------------------

CRITERION_EVAL_SCHEMA: dict = {
    "type": "object",
    "required": ["criterion_evaluations", "overall_confidence", "overall_rationale"],
    "additionalProperties": False,
    "properties": {
        "criterion_evaluations": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["criterion_id", "status", "confidence", "rationale"],
                "additionalProperties": False,
                "properties": {
                    "criterion_id":           {"type": "string"},
                    "criterion_text":         {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["MET", "NOT_MET", "UNDETERMINED"]
                    },
                    "confidence":             {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "evidence_citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["document_id", "quote", "relevance_explanation"],
                            "properties": {
                                "document_id":            {"type": "string"},
                                "quote":                  {"type": "string"},
                                "relevance_explanation":  {"type": "string"},
                                "section":                {"type": ["string", "null"]},
                            }
                        }
                    },
                    "rationale":              {"type": "string", "minLength": 10},
                    "requires_clarification": {"type": "boolean"},
                    "clarification_question": {"type": ["string", "null"]},
                    "missing_information":    {"type": "array", "items": {"type": "string"}},
                }
            }
        },
        "overall_confidence":    {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "overall_rationale":     {"type": "string", "minLength": 10},
        "requires_human_review": {"type": "boolean"},
        "review_reason":         {"type": ["string", "null"]},
        "missing_evidence":      {"type": "array", "items": {"type": "string"}},
        "reasoning_quality":     {"type": "number", "minimum": 0.0, "maximum": 1.0},
    }
}


# ---------------------------------------------------------------------------
# Standard system prompt (SMALL + MEDIUM models)
# ---------------------------------------------------------------------------

STANDARD_SYSTEM_PROMPT = """
You are a clinical prior authorization (PA) review specialist at a health insurance company.

Your role:
  Evaluate whether a patient's clinical evidence meets each insurance policy criterion.
  You do NOT make coverage decisions — you evaluate criteria and document your reasoning.

GROUNDING RULES (strictly enforced):
  1. ONLY use information explicitly stated in the clinical evidence provided.
  2. Do NOT infer, assume, or extrapolate facts not present in the provided text.
  3. Do NOT fabricate quotes, dates, lab values, or clinical findings.
  4. If information is absent, status MUST be UNDETERMINED — never MET.
  5. Every evidence_citation.quote must be a verbatim excerpt from the provided documents.

STATUS DEFINITIONS:
  MET          — Clear, direct evidence in the clinical notes satisfies this criterion.
  NOT_MET      — Clinical notes explicitly contradict the criterion, or a required
                 condition is provably absent (e.g., medication duration < required).
  UNDETERMINED — Insufficient evidence to determine; specify what is missing.

CONFIDENCE:
  0.95–1.0 → Certain: criterion text and evidence are unambiguous.
  0.80–0.94 → High: evidence strongly suggests, minor ambiguity.
  0.60–0.79 → Moderate: evidence present but incomplete.
  0.40–0.59 → Low: evidence sparse; judgment call.
  < 0.40   → Very low: almost no evidence; prefer UNDETERMINED.

CITATION REQUIREMENTS:
  - status MET or NOT_MET → at least 1 evidence_citation with a verbatim quote.
  - status UNDETERMINED → evidence_citations may be empty; missing_information MUST explain gap.
  - Quotes must be ≤ 300 characters and appear verbatim in the source document text.

PROHIBITED:
  - Fabricating clinical data
  - Using general medical knowledge to fill evidence gaps
  - Recommending approval or denial without evidence
  - Discussing patient identifiers (name, SSN, DOB) in rationale

REQUIRED OUTPUT FORMAT:
  Return ONLY valid JSON matching the provided schema. No explanatory text outside JSON.
""".strip()


# ---------------------------------------------------------------------------
# Advanced system prompt (LARGE model — adds chain-of-thought)
# ---------------------------------------------------------------------------

ADVANCED_SYSTEM_PROMPT = """
You are a senior clinical prior authorization specialist with expertise in complex coverage disputes.

This case has been escalated to you because initial evaluation produced low confidence,
detected inconsistencies, or found insufficient evidence for one or more criteria.

APPROACH:
  Step 1. Re-read all clinical evidence carefully.
  Step 2. For each criterion, identify the specific threshold or condition required.
  Step 3. Search the evidence for direct support, contradiction, or absence of each threshold.
  Step 4. Determine status based ONLY on found evidence (never inferred knowledge).
  Step 5. Write a rationale that a nurse reviewer can follow.

GROUNDING RULES (strictly enforced):
  1. ONLY use information explicitly stated in the clinical evidence provided.
  2. Do NOT infer, assume, or extrapolate facts not present in the provided text.
  3. Do NOT fabricate quotes, dates, lab values, or clinical findings.
  4. Every evidence_citation.quote must be a verbatim excerpt from the provided documents.
  5. Each criterion must be evaluated independently.

STATUS DEFINITIONS:
  MET          — Unambiguous, documented evidence satisfies the criterion.
  NOT_MET      — Evidence explicitly contradicts, or required condition is provably absent.
  UNDETERMINED — Insufficient or conflicting evidence; document what is missing.

CONFIDENCE CALIBRATION:
  After assigning status, explicitly ask yourself: "Could I be wrong?"
  If yes and confidence < 0.80, set requires_clarification=true and specify the question.

OUTPUT: Return ONLY valid JSON matching the schema. No preamble. No commentary.
""".strip()


# ---------------------------------------------------------------------------
# User prompt template
# ---------------------------------------------------------------------------

STANDARD_USER_TEMPLATE = """\
=== CLINICAL EVIDENCE ===
Case ID: {case_id}
Service Requested: {service_type}

{clinical_summary}

=== POLICY TO EVALUATE ===
Policy ID:      {policy_id}
Policy Version: {policy_version}
Payer:          {payer_name}

=== CRITERIA TO EVALUATE ===
{criteria_json}

=== REQUIRED OUTPUT SCHEMA ===
{schema_json}

Evaluate each criterion above against the clinical evidence.
Return valid JSON only.
"""


ADVANCED_USER_TEMPLATE = """\
=== ESCALATED CASE — REQUIRES CAREFUL ANALYSIS ===
Case ID:          {case_id}
Escalation Reason: {escalation_reason}
Prior Attempts:   {prior_attempts}

=== CLINICAL EVIDENCE ===
Service Requested: {service_type}

{clinical_summary}

=== ADDITIONAL CONTEXT ===
{additional_context}

=== POLICY TO EVALUATE ===
Policy ID:      {policy_id}
Policy Version: {policy_version}
Payer:          {payer_name}

=== CRITERIA TO EVALUATE ===
{criteria_json}

=== PREVIOUS GUARDRAIL VIOLATIONS (if any) ===
{violations_summary}

=== REQUIRED OUTPUT SCHEMA ===
{schema_json}

Evaluate each criterion with extra care given the escalation context.
Return valid JSON only.
"""


# ---------------------------------------------------------------------------
# Clarification question prompt
# ---------------------------------------------------------------------------

CLARIFICATION_PROMPT = """\
You are a PA reviewer drafting a clarification request to the requesting provider.

Context:
- Policy: {policy_id}
- Undetermined criteria: {undetermined_criteria}
- Missing information items: {missing_information}

Draft ONE clear, specific, clinical question that:
1. Asks for exactly the information needed to complete the evaluation
2. Is written for a clinical provider (not an administrator)
3. References the specific criterion or clinical threshold
4. Is ≤ 3 sentences

Return ONLY the question text. No JSON. No preamble.
"""


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

import json


def build_standard_user_prompt(
    *,
    case_id: str,
    service_type: str,
    clinical_summary: str,
    policy_id: str,
    policy_version: str,
    payer_name: str,
    criteria_list: list[dict],
    max_summary_chars: int = 6000,
    max_criteria: int = 15,
) -> str:
    return STANDARD_USER_TEMPLATE.format(
        case_id=case_id,
        service_type=service_type or "Not specified",
        clinical_summary=clinical_summary[:max_summary_chars],
        policy_id=policy_id,
        policy_version=policy_version,
        payer_name=payer_name or "Unknown",
        criteria_json=json.dumps(criteria_list[:max_criteria], indent=2),
        schema_json=json.dumps(CRITERION_EVAL_SCHEMA, indent=2),
    )


def build_advanced_user_prompt(
    *,
    case_id: str,
    service_type: str,
    clinical_summary: str,
    policy_id: str,
    policy_version: str,
    payer_name: str,
    criteria_list: list[dict],
    escalation_reason: str,
    prior_attempts: int,
    violations_summary: str = "",
    additional_context: str = "",
    max_summary_chars: int = 8000,
    max_criteria: int = 15,
) -> str:
    return ADVANCED_USER_TEMPLATE.format(
        case_id=case_id,
        service_type=service_type or "Not specified",
        clinical_summary=clinical_summary[:max_summary_chars],
        policy_id=policy_id,
        policy_version=policy_version,
        payer_name=payer_name or "Unknown",
        criteria_json=json.dumps(criteria_list[:max_criteria], indent=2),
        escalation_reason=escalation_reason,
        prior_attempts=prior_attempts,
        violations_summary=violations_summary or "None",
        additional_context=additional_context or "None",
        schema_json=json.dumps(CRITERION_EVAL_SCHEMA, indent=2),
    )
