"""
LangSmith integration client.

Wraps the official `langsmith` SDK to provide:
  - Run tracing (log LLM inputs/outputs to LangSmith projects)
  - Dataset management (create/update benchmark datasets)
  - Feedback collection (attach human reviewer scores to runs)
  - Experiment tracking (group evaluation runs into named experiments)

Configuration (env vars):
  LANGSMITH_API_KEY   — required for all operations
  LANGSMITH_PROJECT   — default project name (default: "pa-review-eval")
  LANGSMITH_ENDPOINT  — override for self-hosted LangSmith (optional)

All methods are async and gracefully degrade (log + return None) when
the LANGSMITH_API_KEY is absent or the SDK is not installed.
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator

import structlog

from app.evaluation.models import BenchmarkCase, BenchmarkDataset, EvalDomain

logger = structlog.get_logger(__name__)

_DEFAULT_PROJECT = "pa-review-eval"


def _get_api_key() -> str | None:
    return os.getenv("LANGSMITH_API_KEY")


def _get_project() -> str:
    return os.getenv("LANGSMITH_PROJECT", _DEFAULT_PROJECT)


def _get_endpoint() -> str | None:
    return os.getenv("LANGSMITH_ENDPOINT")


class LangSmithClient:
    """
    Async-friendly LangSmith client.

    Methods silently no-op when LangSmith is not configured to prevent
    evaluation failures from cascading into pipeline failures.
    """

    def __init__(self, project: str | None = None) -> None:
        self._project = project or _get_project()
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        api_key = _get_api_key()
        if not api_key:
            logger.debug("langsmith.disabled", reason="LANGSMITH_API_KEY not set")
            return
        try:
            import langsmith
            kwargs: dict[str, Any] = {"api_key": api_key}
            endpoint = _get_endpoint()
            if endpoint:
                kwargs["api_url"] = endpoint
            self._client = langsmith.Client(**kwargs)
            self._available = True
            logger.info("langsmith.client_initialized", project=self._project)
        except ImportError:
            logger.warning("langsmith.not_installed", note="pip install langsmith")
        except Exception as exc:
            logger.error("langsmith.init_failed", error=str(exc))

    @property
    def is_available(self) -> bool:
        return self._available and self._client is not None

    # ------------------------------------------------------------------
    # Run tracing
    # ------------------------------------------------------------------

    def create_run(
        self,
        name: str,
        inputs: dict[str, Any],
        run_type: str = "chain",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Create a LangSmith run and return its run_id.
        Returns None when LangSmith is unavailable.
        """
        if not self.is_available:
            return None
        run_id = str(uuid.uuid4())
        try:
            self._client.create_run(
                id=run_id,
                name=name,
                inputs=inputs,
                run_type=run_type,
                project_name=self._project,
                tags=tags or [],
                extra={"metadata": metadata or {}},
            )
            return run_id
        except Exception as exc:
            logger.debug("langsmith.create_run_failed", error=str(exc))
            return None

    def update_run(
        self,
        run_id: str,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
        end_time: datetime | None = None,
    ) -> None:
        """Patch an existing run with outputs or error."""
        if not self.is_available or not run_id:
            return
        try:
            kwargs: dict[str, Any] = {}
            if outputs is not None:
                kwargs["outputs"] = outputs
            if error is not None:
                kwargs["error"] = error
            if end_time is not None:
                kwargs["end_time"] = end_time
            self._client.update_run(run_id, **kwargs)
        except Exception as exc:
            logger.debug("langsmith.update_run_failed", run_id=run_id, error=str(exc))

    @asynccontextmanager
    async def trace_run(
        self,
        name: str,
        inputs: dict[str, Any],
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str | None, None]:
        """
        Context manager that opens a run on entry and closes it on exit.

        Yields the run_id (or None if LangSmith is unavailable).
        Captures exceptions and logs them as run errors.

        Usage:
            async with langsmith_client.trace_run("llm_call", {"prompt": p}) as run_id:
                result = await model.invoke(p)
        """
        run_id = self.create_run(name, inputs, tags=tags, metadata=metadata)
        error: str | None = None
        try:
            yield run_id
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            self.update_run(run_id, error=error, end_time=datetime.utcnow())

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def log_feedback(
        self,
        run_id: str,
        key: str,
        score: float,
        value: str | None = None,
        comment: str | None = None,
        source_info: dict[str, Any] | None = None,
    ) -> None:
        """
        Attach a feedback score to a run.

        key:   metric name ("hallucination", "reviewer_agreement", etc.)
        score: numeric value (0.0–1.0)
        value: optional categorical label ("pass" / "fail")
        """
        if not self.is_available or not run_id:
            return
        try:
            self._client.create_feedback(
                run_id=run_id,
                key=key,
                score=score,
                value=value,
                comment=comment,
                source_info=source_info or {},
            )
        except Exception as exc:
            logger.debug("langsmith.feedback_failed", run_id=run_id, key=key, error=str(exc))

    def log_eval_metrics(self, run_id: str, metrics: dict[str, float]) -> None:
        """Batch-log all evaluation metrics as feedback entries."""
        for key, score in metrics.items():
            self.log_feedback(run_id=run_id, key=key, score=score)

    # ------------------------------------------------------------------
    # Dataset management
    # ------------------------------------------------------------------

    async def create_or_update_dataset(self, dataset: BenchmarkDataset) -> str | None:
        """
        Push a BenchmarkDataset to LangSmith.

        Creates a new dataset if it doesn't exist; appends new examples
        to the existing dataset if it does.  Returns the LangSmith dataset ID.
        """
        if not self.is_available:
            return None

        try:
            # Check if dataset already exists by name
            ls_dataset = None
            try:
                ls_dataset = self._client.read_dataset(dataset_name=dataset.name)
            except Exception:
                pass

            if ls_dataset is None:
                ls_dataset = self._client.create_dataset(
                    dataset_name=dataset.name,
                    description=dataset.description,
                )
                logger.info("langsmith.dataset_created", name=dataset.name)
            else:
                logger.debug("langsmith.dataset_exists", name=dataset.name)

            # Push examples
            inputs  = [{"input_text": c.input_text, "query": c.query} for c in dataset.cases]
            outputs = [
                {
                    "expected_output":  c.expected_output,
                    "expected_verdict": c.expected_verdict,
                    "expected_entities": c.expected_entities,
                }
                for c in dataset.cases
            ]
            self._client.create_examples(
                inputs=inputs,
                outputs=outputs,
                dataset_id=ls_dataset.id,
            )
            logger.info(
                "langsmith.examples_pushed",
                dataset=dataset.name,
                count=len(dataset.cases),
            )
            return str(ls_dataset.id)
        except Exception as exc:
            logger.error("langsmith.dataset_push_failed", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Experiments
    # ------------------------------------------------------------------

    def create_experiment_run(
        self,
        experiment_name: str,
        dataset_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Group evaluation results under a named experiment in LangSmith.
        Returns an experiment run_id for subsequent result attachments.
        """
        if not self.is_available:
            return None
        try:
            run_id = self.create_run(
                name=experiment_name,
                inputs={"dataset_id": dataset_id},
                run_type="evaluation",
                tags=["experiment"],
                metadata=metadata,
            )
            return run_id
        except Exception as exc:
            logger.debug("langsmith.experiment_failed", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> "LangSmithClient":
        """Return a client using environment variable configuration."""
        return cls()


# Singleton
_client_instance: LangSmithClient | None = None


def get_langsmith_client() -> LangSmithClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = LangSmithClient.default()
    return _client_instance
