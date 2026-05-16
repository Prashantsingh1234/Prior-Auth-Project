"""
Task message contracts.

Every message published to a RabbitMQ queue is serialized from one of these
Pydantic models.  The base TaskMessage carries envelope metadata (task_id,
retry count, timestamps) that the consumer framework uses without needing to
know the payload type.

Hierarchy:
  TaskMessage          ← base envelope, all queues
  ├── IngestionTask    → pa.ingestion
  ├── OCRTask          → pa.ocr
  ├── EmbeddingTask    → pa.embedding
  ├── EvaluationTask   → pa.evaluation
  └── NotificationTask → pa.notifications
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TaskType(str, Enum):
    INGESTION    = "ingestion"
    OCR          = "ocr"
    EMBEDDING    = "embedding"
    EVALUATION   = "evaluation"
    NOTIFICATION = "notification"


class TaskPriority(int, Enum):
    LOW    = 1
    NORMAL = 5
    HIGH   = 9


class NotificationChannel(str, Enum):
    EMAIL    = "email"
    SMS      = "sms"
    IN_APP   = "in_app"
    WEBHOOK  = "webhook"


class NotificationEvent(str, Enum):
    CLARIFICATION_SENT     = "clarification_sent"
    CLARIFICATION_ANSWERED = "clarification_answered"
    CLARIFICATION_TIMEOUT  = "clarification_timeout"
    REVIEW_ASSIGNED        = "review_assigned"
    DECISION_READY         = "decision_ready"
    CASE_ESCALATED         = "case_escalated"


# ---------------------------------------------------------------------------
# Base envelope
# ---------------------------------------------------------------------------


class TaskMessage(BaseModel):
    """
    Common envelope carried by every task message.

    The framework reads task_id, retry_count, and enqueued_at; the worker
    reads the type-specific fields in the subclass.
    """

    task_id:     str      = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type:   TaskType
    case_id:     str | None = Field(default=None, description="PA case this task belongs to")
    priority:    TaskPriority = Field(default=TaskPriority.NORMAL)
    retry_count: int      = Field(default=0, ge=0)
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata:    dict[str, Any] = Field(default_factory=dict)

    def next_retry(self) -> "TaskMessage":
        """Return a copy of this message with retry_count incremented."""
        return self.model_copy(update={"retry_count": self.retry_count + 1})

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> "TaskMessage":
        return cls.model_validate_json(data)


# ---------------------------------------------------------------------------
# Ingestion task
# ---------------------------------------------------------------------------


class IngestionTask(TaskMessage):
    """
    Enqueue a document for full ingestion pipeline:
    download → OCR → normalize → embed → store.
    """

    task_type: TaskType = TaskType.INGESTION

    document_id:   str
    document_url:  str | None = None   # S3 / blob URL; None if already in DB
    document_type: str = "PA_REQUEST"  # PA_REQUEST | POLICY | CLINICAL_NOTE | FORMULARY
    owner_id:      str | None = None   # User who submitted
    force_reprocess: bool = False      # Re-ingest even if document_id already exists


# ---------------------------------------------------------------------------
# OCR task
# ---------------------------------------------------------------------------


class OCRTask(TaskMessage):
    """
    Run OCR on a stored document and write the extraction result to DB.

    Primary provider: Azure Document Intelligence.
    Fallback provider: PaddleOCR (triggered when confidence < threshold).
    """

    task_type: TaskType = TaskType.OCR

    document_id:      str
    storage_path:     str               # Path in secure storage
    document_type:    str = "PDF"
    preferred_provider: str = "azure"   # azure | paddleocr
    confidence_threshold: float = 0.80
    page_count:       int | None = None


# ---------------------------------------------------------------------------
# Embedding task
# ---------------------------------------------------------------------------


class EmbeddingTask(TaskMessage):
    """
    Generate and upsert embeddings for a text chunk into the vector store.
    """

    task_type: TaskType = TaskType.EMBEDDING

    document_id: str
    chunk_id:    str
    text:        str
    model:       str = "text-embedding-3-small"
    namespace:   str = "production"
    # Extra metadata to attach to the Pinecone vector
    vector_metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evaluation task
# ---------------------------------------------------------------------------


class EvaluationTask(TaskMessage):
    """
    Run one or more LangSmith / custom evaluators against a workflow run.
    """

    task_type: TaskType = TaskType.EVALUATION

    run_id:      str              # LangSmith / internal run identifier
    evaluator_names: list[str]   # e.g. ["faithfulness", "answer_relevance", "policy_compliance"]
    dataset_id:  str | None = None
    # Snapshot of the inputs/outputs to evaluate (avoids fetching from LangSmith)
    inputs:      dict[str, Any] = Field(default_factory=dict)
    outputs:     dict[str, Any] = Field(default_factory=dict)
    reference:   dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Notification task
# ---------------------------------------------------------------------------


class NotificationTask(TaskMessage):
    """
    Deliver a notification to a provider, reviewer, or admin.
    """

    task_type: TaskType = TaskType.NOTIFICATION

    recipient_id:    str
    recipient_email: str | None = None
    recipient_phone: str | None = None
    event:           NotificationEvent
    channels:        list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.IN_APP]
    )
    subject:         str | None = None
    body:            str        = ""
    template_id:     str | None = None
    template_vars:   dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Discriminated union — used by consumers for generic deserialization
# ---------------------------------------------------------------------------

AnyTask = IngestionTask | OCRTask | EmbeddingTask | EvaluationTask | NotificationTask


def deserialize_task(data: bytes) -> AnyTask:
    """
    Deserialize raw bytes into the correct task subclass.

    Reads task_type from the JSON without full validation, then delegates
    to the appropriate model.
    """
    import json
    raw = json.loads(data)
    task_type = TaskType(raw.get("task_type", ""))
    _MAP = {
        TaskType.INGESTION:    IngestionTask,
        TaskType.OCR:          OCRTask,
        TaskType.EMBEDDING:    EmbeddingTask,
        TaskType.EVALUATION:   EvaluationTask,
        TaskType.NOTIFICATION: NotificationTask,
    }
    cls = _MAP.get(task_type)
    if cls is None:
        raise ValueError(f"Unknown task_type: {task_type!r}")
    return cls.model_validate(raw)
