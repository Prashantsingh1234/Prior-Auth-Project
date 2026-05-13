"""Initial schema — all 12 PA platform tables.

Revision ID: 20240101_000000
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers
revision: str = "20240101_000000"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create all 12 tables for the PA Review Platform."""

    # ----------------------------------------------------------
    # 1. patients
    # ----------------------------------------------------------
    op.create_table(
        "patients",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("member_id", sa.String(100), nullable=False),
        sa.Column("group_number", sa.String(100), nullable=True),
        sa.Column("insurance_plan_id", sa.String(100), nullable=True),
        sa.Column("insurance_plan_name", sa.String(255), nullable=True),
        sa.Column("insurance_plan_type", sa.String(50), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(50), nullable=True),
        sa.Column("zip_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(3), nullable=False, server_default="USA"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("member_id", "insurance_plan_id", name="uq_patients_member_plan"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_patients_member_id", "patients", ["member_id"])
    op.create_index("ix_patients_last_name", "patients", ["last_name"])
    op.create_index("ix_patients_dob", "patients", ["date_of_birth"])
    op.create_index("ix_patients_deleted_at", "patients", ["deleted_at"])

    # ----------------------------------------------------------
    # 2. providers
    # ----------------------------------------------------------
    op.create_table(
        "providers",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("npi", sa.String(10), nullable=False),
        sa.Column("provider_type", sa.Enum("INDIVIDUAL", "ORGANIZATION"), nullable=False, server_default="INDIVIDUAL"),
        sa.Column("tax_id", sa.String(20), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("credentials", sa.String(100), nullable=True),
        sa.Column("specialty", sa.String(255), nullable=True),
        sa.Column("organization_name", sa.String(255), nullable=True),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("fax", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(50), nullable=True),
        sa.Column("zip_code", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("npi", name="uq_providers_npi"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_providers_npi", "providers", ["npi"])
    op.create_index("ix_providers_last_name", "providers", ["last_name"])
    op.create_index("ix_providers_organization", "providers", ["organization_name"])
    op.create_index("ix_providers_deleted_at", "providers", ["deleted_at"])

    # ----------------------------------------------------------
    # 3. pa_cases
    # ----------------------------------------------------------
    op.create_table(
        "pa_cases",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("case_number", sa.String(30), nullable=False),
        sa.Column("patient_id", mysql.CHAR(36), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider_id", mysql.CHAR(36), sa.ForeignKey("providers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_reviewer_id", mysql.CHAR(36), nullable=True),
        sa.Column("status", sa.Enum(
            "SUBMITTED","PROCESSING","PENDING_CLARIFICATION","UNDER_REVIEW",
            "APPROVED","DENIED","PENDED","ESCALATED","CANCELLED"
        ), nullable=False, server_default="SUBMITTED"),
        sa.Column("priority", sa.Enum("ROUTINE","URGENT","EMERGENT"), nullable=False, server_default="ROUTINE"),
        sa.Column("service_type", sa.Enum(
            "IMAGING","LABORATORY","DURABLE_MEDICAL_EQUIPMENT","MEDICATION",
            "PROCEDURE","SPECIALTY_REFERRAL","HOME_HEALTH","INPATIENT_ADMISSION",
            "OUTPATIENT_SURGERY","BEHAVIORAL_HEALTH","OTHER"
        ), nullable=True),
        sa.Column("cpt_codes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("icd_codes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("requested_service_description", sa.Text, nullable=True),
        sa.Column("clinical_notes", sa.Text, nullable=True),
        sa.Column("ai_recommendation", sa.String(10), nullable=True),
        sa.Column("ai_confidence_score", sa.Float, nullable=True),
        sa.Column("ai_reasoning_summary", sa.Text, nullable=True),
        sa.Column("clarification_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_reference_id", sa.String(100), nullable=True),
        sa.Column("source_channel", sa.String(50), nullable=True),
        sa.Column("case_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("case_number", name="uq_pa_cases_case_number"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_pa_cases_status", "pa_cases", ["status"])
    op.create_index("ix_pa_cases_priority", "pa_cases", ["priority"])
    op.create_index("ix_pa_cases_patient_id", "pa_cases", ["patient_id"])
    op.create_index("ix_pa_cases_provider_id", "pa_cases", ["provider_id"])
    op.create_index("ix_pa_cases_reviewer_id", "pa_cases", ["assigned_reviewer_id"])
    op.create_index("ix_pa_cases_decided_at", "pa_cases", ["decided_at"])
    op.create_index("ix_pa_cases_submitted_at", "pa_cases", ["submitted_at"])
    op.create_index("ix_pa_cases_deleted_at", "pa_cases", ["deleted_at"])
    op.create_index("ix_pa_cases_status_priority", "pa_cases", ["status", "priority"])

    # ----------------------------------------------------------
    # 4. uploaded_documents
    # ----------------------------------------------------------
    op.create_table(
        "uploaded_documents",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("case_id", mysql.CHAR(36), sa.ForeignKey("pa_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.Enum(
            "PRESCRIPTION","LAB_REPORT","MEDICAL_NECESSITY","REFERRAL","EHR_EXPORT",
            "IMAGING_REPORT","CLINICAL_NOTES","PRIOR_AUTH_REQUEST_FORM","INSURANCE_CARD",
            "APPEAL","FAX","OTHER"
        ), nullable=False, server_default="OTHER"),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("stored_filename", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("ocr_provider", sa.Enum("AZURE","PADDLEOCR","NONE"), nullable=False, server_default="NONE"),
        sa.Column("ocr_status", sa.Enum("PENDING","PROCESSING","COMPLETED","FAILED","FALLBACK_USED"), nullable=False, server_default="PENDING"),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("extracted_text", mysql.LONGTEXT, nullable=True),
        sa.Column("ocr_raw_response", sa.JSON, nullable=True),
        sa.Column("processing_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("detected_tables", sa.JSON, nullable=True),
        sa.Column("detected_key_values", sa.JSON, nullable=True),
        sa.Column("detected_language", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_documents_case_id", "uploaded_documents", ["case_id"])
    op.create_index("ix_documents_ocr_status", "uploaded_documents", ["ocr_status"])
    op.create_index("ix_documents_checksum", "uploaded_documents", ["checksum_sha256"])
    op.create_index("ix_documents_deleted_at", "uploaded_documents", ["deleted_at"])
    op.create_index("ix_documents_case_type", "uploaded_documents", ["case_id", "document_type"])

    # ----------------------------------------------------------
    # 5. extracted_entities
    # ----------------------------------------------------------
    op.create_table(
        "extracted_entities",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("case_id", mysql.CHAR(36), sa.ForeignKey("pa_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", mysql.CHAR(36), sa.ForeignKey("uploaded_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entity_type", sa.Enum(
            "PATIENT_DEMOGRAPHICS","PROVIDER_INFO","DIAGNOSIS_CODE","PROCEDURE_CODE",
            "MEDICATION","LAB_VALUE","GLUCOSE_READING","INSULIN_FREQUENCY",
            "TREATMENT_HISTORY","COMPLICATION","SYMPTOM","DATE_OF_SERVICE",
            "INSURANCE_INFO","OTHER"
        ), nullable=False),
        sa.Column("entity_key", sa.String(200), nullable=False),
        sa.Column("entity_value", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("display_value", sa.String(500), nullable=True),
        sa.Column("extraction_method", sa.Enum("LLM","OCR","REGEX","MANUAL"), nullable=False, server_default="LLM"),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("source_text", sa.Text, nullable=True),
        sa.Column("source_page", sa.Integer, nullable=True),
        sa.Column("source_start_offset", sa.Integer, nullable=True),
        sa.Column("source_end_offset", sa.Integer, nullable=True),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("is_corrected", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("original_value", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_entities_case_id", "extracted_entities", ["case_id"])
    op.create_index("ix_entities_document_id", "extracted_entities", ["document_id"])
    op.create_index("ix_entities_type", "extracted_entities", ["entity_type"])
    op.create_index("ix_entities_key", "extracted_entities", ["entity_key"])
    op.create_index("ix_entities_case_type", "extracted_entities", ["case_id", "entity_type"])

    # ----------------------------------------------------------
    # 6. policy_matches
    # ----------------------------------------------------------
    op.create_table(
        "policy_matches",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("case_id", mysql.CHAR(36), sa.ForeignKey("pa_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_id", sa.String(100), nullable=True),
        sa.Column("policy_name", sa.String(500), nullable=False),
        sa.Column("policy_version", sa.String(20), nullable=False, server_default="v1"),
        sa.Column("pinecone_namespace", sa.String(100), nullable=False),
        sa.Column("matched_cpt_codes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("matched_icd_codes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("retrieval_score", sa.Float, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("retrieved_chunks", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("retrieval_metadata", sa.JSON, nullable=True),
        sa.Column("rerank_score", sa.Float, nullable=True),
        sa.Column("is_primary_policy", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_policy_matches_case_id", "policy_matches", ["case_id"])
    op.create_index("ix_policy_matches_policy_name", "policy_matches", ["policy_name"])
    op.create_index("ix_policy_matches_version", "policy_matches", ["policy_version"])
    op.create_index("ix_policy_matches_primary", "policy_matches", ["case_id", "is_primary_policy"])

    # ----------------------------------------------------------
    # 7. evaluations
    # ----------------------------------------------------------
    op.create_table(
        "evaluations",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("case_id", mysql.CHAR(36), sa.ForeignKey("pa_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evaluation_type", sa.Enum("AI_CRITERION","HUMAN_REVIEW"), nullable=False),
        sa.Column("criterion_name", sa.String(500), nullable=False),
        sa.Column("criterion_text", sa.Text, nullable=True),
        sa.Column("policy_name", sa.String(500), nullable=True),
        sa.Column("policy_version", sa.String(20), nullable=True),
        sa.Column("criterion_status", sa.Enum("PASS","FAIL","INSUFFICIENT_EVIDENCE","NOT_APPLICABLE"), nullable=False),
        sa.Column("evidence", sa.Text, nullable=True),
        sa.Column("evidence_sources", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("llm_model_used", sa.String(100), nullable=True),
        sa.Column("llm_prompt_tokens", sa.Integer, nullable=True),
        sa.Column("llm_completion_tokens", sa.Integer, nullable=True),
        sa.Column("llm_latency_ms", sa.Float, nullable=True),
        sa.Column("llm_raw_output", sa.Text, nullable=True),
        sa.Column("reviewer_override_status", sa.Enum("PASS","FAIL","INSUFFICIENT_EVIDENCE","NOT_APPLICABLE"), nullable=True),
        sa.Column("reviewer_override_note", sa.Text, nullable=True),
        sa.Column("reviewer_id", mysql.CHAR(36), nullable=True),
        sa.Column("evaluation_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_evaluations_case_id", "evaluations", ["case_id"])
    op.create_index("ix_evaluations_type", "evaluations", ["evaluation_type"])
    op.create_index("ix_evaluations_criterion", "evaluations", ["criterion_name"])
    op.create_index("ix_evaluations_status", "evaluations", ["criterion_status"])
    op.create_index("ix_evaluations_case_type", "evaluations", ["case_id", "evaluation_type"])

    # ----------------------------------------------------------
    # 8. clarifications
    # ----------------------------------------------------------
    op.create_table(
        "clarifications",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("case_id", mysql.CHAR(36), sa.ForeignKey("pa_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("status", sa.Enum("PENDING","ANSWERED","TIMEOUT","ESCALATED"), nullable=False, server_default="PENDING"),
        sa.Column("missing_criteria", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("questions", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("answers", sa.JSON, nullable=True),
        sa.Column("clarification_context", sa.JSON, nullable=True),
        sa.Column("resolution_summary", sa.Text, nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notification_sent", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("notification_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_notification_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_clarifications_case_id", "clarifications", ["case_id"])
    op.create_index("ix_clarifications_status", "clarifications", ["status"])
    op.create_index("ix_clarifications_deadline", "clarifications", ["response_deadline"])
    op.create_index("ix_clarifications_case_attempt", "clarifications", ["case_id", "attempt_number"])

    # ----------------------------------------------------------
    # 9. reviewer_actions
    # ----------------------------------------------------------
    op.create_table(
        "reviewer_actions",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("case_id", mysql.CHAR(36), sa.ForeignKey("pa_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", mysql.CHAR(36), nullable=False),
        sa.Column("reviewer_name", sa.String(255), nullable=True),
        sa.Column("reviewer_role", sa.String(50), nullable=True),
        sa.Column("action_type", sa.Enum(
            "ASSIGNED","VIEWED","APPROVED","DENIED","PENDED",
            "OVERRIDE_APPROVED","OVERRIDE_DENIED","REQUESTED_CLARIFICATION",
            "ESCALATED","ADDED_NOTE"
        ), nullable=False),
        sa.Column("previous_case_status", sa.String(50), nullable=True),
        sa.Column("new_case_status", sa.String(50), nullable=True),
        sa.Column("ai_recommendation", sa.Enum("APPROVE","DENY","PEND"), nullable=True),
        sa.Column("reviewer_decision", sa.Enum("APPROVE","DENY","PEND"), nullable=True),
        sa.Column("override_reason", sa.Text, nullable=True),
        sa.Column("override_reason_code", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("time_to_action_seconds", sa.Integer, nullable=True),
        sa.Column("ai_confidence_at_review", sa.Float, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("request_id", mysql.CHAR(36), nullable=True),
        sa.Column("action_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_reviewer_actions_case_id", "reviewer_actions", ["case_id"])
    op.create_index("ix_reviewer_actions_reviewer_id", "reviewer_actions", ["reviewer_id"])
    op.create_index("ix_reviewer_actions_action_type", "reviewer_actions", ["action_type"])
    op.create_index("ix_reviewer_actions_created_at", "reviewer_actions", ["created_at"])
    op.create_index("ix_reviewer_actions_reviewer_action", "reviewer_actions", ["reviewer_id", "action_type"])

    # ----------------------------------------------------------
    # 10. decisions
    # ----------------------------------------------------------
    op.create_table(
        "decisions",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("case_id", mysql.CHAR(36), sa.ForeignKey("pa_cases.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("final_decision", sa.Enum("APPROVE","DENY","PEND"), nullable=False),
        sa.Column("decision_source", sa.Enum("AI_RECOMMENDATION","REVIEWER_OVERRIDE"), nullable=False),
        sa.Column("ai_recommendation", sa.Enum("APPROVE","DENY","PEND"), nullable=True),
        sa.Column("ai_confidence_score", sa.Float, nullable=True),
        sa.Column("ai_reasoning_summary", sa.Text, nullable=True),
        sa.Column("reviewer_id", mysql.CHAR(36), nullable=True),
        sa.Column("reviewer_name", sa.String(255), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("denial_reason_code", sa.String(50), nullable=True),
        sa.Column("denial_reason_description", sa.Text, nullable=True),
        sa.Column("denial_letter_text", sa.Text, nullable=True),
        sa.Column("approval_conditions", sa.JSON, nullable=True),
        sa.Column("approved_service_description", sa.Text, nullable=True),
        sa.Column("approved_units", sa.String(100), nullable=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("expiration_date", sa.Date, nullable=True),
        sa.Column("appeal_deadline_days", sa.Integer, nullable=True, server_default="60"),
        sa.Column("turnaround_time_hours", sa.Float, nullable=True),
        sa.Column("is_expedited", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("regulatory_deadline_met", sa.Boolean, nullable=True),
        sa.Column("decision_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("case_id", name="uq_decisions_case_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_decisions_final_decision", "decisions", ["final_decision"])
    op.create_index("ix_decisions_source", "decisions", ["decision_source"])
    op.create_index("ix_decisions_decided_at", "decisions", ["decided_at"])
    op.create_index("ix_decisions_expiration", "decisions", ["expiration_date"])
    op.create_index("ix_decisions_reviewer_id", "decisions", ["reviewer_id"])

    # ----------------------------------------------------------
    # 11. audit_logs
    # ----------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("entity_type", sa.Enum(
            "PATIENT","PROVIDER","PA_CASE","DOCUMENT","EVALUATION",
            "CLARIFICATION","REVIEWER_ACTION","DECISION","POLICY_MATCH","USER","SYSTEM"
        ), nullable=False),
        sa.Column("entity_id", mysql.CHAR(36), nullable=True),
        sa.Column("action", sa.Enum(
            "CREATE","READ","UPDATE","DELETE","STATUS_CHANGE","LOGIN","LOGOUT",
            "EXPORT","AI_INFERENCE","OCR_PROCESSED","DECISION_MADE","OVERRIDE"
        ), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("actor_type", sa.Enum("USER","SYSTEM","AI"), nullable=False),
        sa.Column("actor_id", mysql.CHAR(36), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("previous_state", sa.JSON, nullable=True),
        sa.Column("new_state", sa.JSON, nullable=True),
        sa.Column("changed_fields", sa.JSON, nullable=True),
        sa.Column("request_id", mysql.CHAR(36), nullable=True),
        sa.Column("trace_id", mysql.CHAR(36), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("api_endpoint", sa.String(500), nullable=True),
        sa.Column("case_id", mysql.CHAR(36), nullable=True),
        sa.Column("audit_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_audit_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_action", "audit_logs", ["action"])
    op.create_index("ix_audit_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_case_id", "audit_logs", ["case_id"])
    op.create_index("ix_audit_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_entity_lookup", "audit_logs", ["entity_type", "entity_id", "created_at"])

    # ----------------------------------------------------------
    # 12. metrics
    # ----------------------------------------------------------
    op.create_table(
        "metrics",
        sa.Column("id", mysql.CHAR(36), primary_key=True),
        sa.Column("metric_name", sa.String(200), nullable=False),
        sa.Column("metric_type", sa.Enum("COUNTER","GAUGE","HISTOGRAM","SUMMARY"), nullable=False),
        sa.Column("labels", sa.JSON, nullable=True),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granularity", sa.String(20), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("metric_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_metrics_name", "metrics", ["metric_name"])
    op.create_index("ix_metrics_recorded_at", "metrics", ["recorded_at"])
    op.create_index("ix_metrics_granularity", "metrics", ["granularity"])
    op.create_index("ix_metrics_name_time", "metrics", ["metric_name", "recorded_at"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("metrics")
    op.drop_table("audit_logs")
    op.drop_table("decisions")
    op.drop_table("reviewer_actions")
    op.drop_table("clarifications")
    op.drop_table("evaluations")
    op.drop_table("policy_matches")
    op.drop_table("extracted_entities")
    op.drop_table("uploaded_documents")
    op.drop_table("pa_cases")
    op.drop_table("providers")
    op.drop_table("patients")
