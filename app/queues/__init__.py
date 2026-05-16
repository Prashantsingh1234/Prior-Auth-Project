"""
app.queues — Async task processing via RabbitMQ.

Public API
----------
Models:
  TaskMessage         Base envelope for all task types
  IngestionTask       Document ingestion pipeline trigger
  OCRTask             OCR extraction request
  EmbeddingTask       Vector embedding generation
  EvaluationTask      LLM evaluator run
  NotificationTask    Multi-channel notification delivery
  TaskType            Enum of task type identifiers
  TaskPriority        LOW / NORMAL / HIGH message priorities
  deserialize_task    Deserialize raw bytes into a typed task

Infrastructure:
  get_connection()    Shared RobustConnection to RabbitMQ
  close_connection()  Gracefully close connection (shutdown hook)
  is_connected()      Health-check: is the broker reachable?

Publishing:
  get_publisher()     Process-level TaskPublisher singleton
  TaskPublisher       Publish single / batch tasks with confirms

Topology:
  declare_topology()  Idempotently declare all exchanges + queues
  QUEUE_SPECS         Dict of QueueSpec descriptors

Metrics:
  QUEUE_METRICS       Prometheus metric wrapper

Workers:
  IngestionWorker     Consumes pa.ingestion
  OCRWorker           Consumes pa.ocr
  EmbeddingWorker     Consumes pa.embedding
  EvaluationWorker    Consumes pa.evaluation
  NotificationWorker  Consumes pa.notifications

Runner:
  start_workers()     Async: start all workers under supervision loop
"""

from app.queues.models import (
    AnyTask,
    EmbeddingTask,
    EvaluationTask,
    IngestionTask,
    NotificationTask,
    NotificationChannel,
    NotificationEvent,
    OCRTask,
    TaskMessage,
    TaskPriority,
    TaskType,
    deserialize_task,
)
from app.queues.connection import (
    close_connection,
    get_connection,
    is_connected,
)
from app.queues.publisher import get_publisher, TaskPublisher
from app.queues.topology import declare_topology, QUEUE_SPECS, QUEUE_SPECS as QUEUES
from app.queues.metrics import QUEUE_METRICS
from app.queues.workers import (
    EmbeddingWorker,
    EvaluationWorker,
    IngestionWorker,
    NotificationWorker,
    OCRWorker,
)
from app.queues.runner import start_workers

__all__ = [
    # Models
    "TaskMessage", "TaskType", "TaskPriority", "AnyTask", "deserialize_task",
    "IngestionTask", "OCRTask", "EmbeddingTask", "EvaluationTask", "NotificationTask",
    "NotificationChannel", "NotificationEvent",
    # Connection
    "get_connection", "close_connection", "is_connected",
    # Publishing
    "get_publisher", "TaskPublisher",
    # Topology
    "declare_topology", "QUEUE_SPECS", "QUEUES",
    # Metrics
    "QUEUE_METRICS",
    # Workers
    "IngestionWorker", "OCRWorker", "EmbeddingWorker", "EvaluationWorker", "NotificationWorker",
    # Runner
    "start_workers",
]
