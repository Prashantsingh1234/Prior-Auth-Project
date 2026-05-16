"""
Evaluation worker — processes EvaluationTask messages.

Runs one or more evaluators against a completed workflow run:
  - Faithfulness      — do AI answers faithfully reflect retrieved context?
  - Answer relevance  — is the output relevant to the input?
  - Policy compliance — does the recommendation align with the cited policy?
  - Custom evaluators registered in app/evaluation/

Results are written to the evaluation_results table and optionally sent
back to LangSmith for dataset-level tracking.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.queues.consumer import BaseConsumer
from app.queues.models import AnyTask, EvaluationTask
from app.queues.topology import QUEUE_SPECS

logger = structlog.get_logger(__name__)


class EvaluationWorker(BaseConsumer):

    queue_spec = QUEUE_SPECS["evaluation"]

    async def process(self, task: AnyTask) -> None:
        assert isinstance(task, EvaluationTask), f"Expected EvaluationTask, got {type(task)}"
        log = logger.bind(
            task_id=task.task_id,
            run_id=task.run_id,
            case_id=task.case_id,
            evaluators=task.evaluator_names,
        )
        log.info("evaluation_worker.started")

        results: dict[str, Any] = {}
        errors:  dict[str, str] = {}

        for evaluator_name in task.evaluator_names:
            t0 = time.perf_counter()
            try:
                score, feedback = await self._run_evaluator(evaluator_name, task)
                results[evaluator_name] = {
                    "score":    score,
                    "feedback": feedback,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                }
                log.debug(
                    "evaluation_worker.evaluator_ok",
                    evaluator=evaluator_name,
                    score=score,
                )
            except Exception as exc:
                errors[evaluator_name] = str(exc)
                log.warning(
                    "evaluation_worker.evaluator_failed",
                    evaluator=evaluator_name,
                    error=str(exc),
                )

        await self._persist_results(task, results, errors)

        if errors and len(errors) == len(task.evaluator_names):
            raise RuntimeError(
                f"All {len(errors)} evaluators failed for run {task.run_id!r}: {errors}"
            )

        log.info(
            "evaluation_worker.completed",
            success_count=len(results),
            error_count=len(errors),
        )

    # ------------------------------------------------------------------

    async def _run_evaluator(
        self, name: str, task: EvaluationTask
    ) -> tuple[float, str]:
        """
        Dispatch to the named evaluator.  Returns (score 0–1, feedback string).
        Falls back to a simple OpenAI-based evaluator if no registered evaluator found.
        """
        try:
            from app.evaluation import get_evaluator_registry
            registry = get_evaluator_registry()
            if registry and hasattr(registry, "get"):
                evaluator = registry.get(name)
                if evaluator:
                    result = await evaluator.evaluate(
                        inputs=task.inputs,
                        outputs=task.outputs,
                        reference=task.reference,
                    )
                    return result.score, result.feedback
        except (ImportError, AttributeError):
            pass

        # Built-in fallback evaluators
        return await self._builtin_evaluator(name, task)

    async def _builtin_evaluator(
        self, name: str, task: EvaluationTask
    ) -> tuple[float, str]:
        """Simple LLM-as-judge evaluator using OpenAI."""
        from app.core.config.settings import get_settings
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set — cannot run LLM evaluator")

        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=60,
        )

        system_prompt = _EVALUATOR_PROMPTS.get(name, _EVALUATOR_PROMPTS["default"])
        user_content  = (
            f"INPUTS:\n{task.inputs}\n\n"
            f"OUTPUTS:\n{task.outputs}\n\n"
            f"REFERENCE:\n{task.reference}"
        )

        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.0,
            max_tokens=256,
        )
        raw = resp.choices[0].message.content or ""

        # Parse "SCORE: 0.85\nFEEDBACK: ..." format
        score    = _parse_score(raw)
        feedback = raw.strip()
        return score, feedback

    async def _persist_results(
        self,
        task: EvaluationTask,
        results: dict[str, Any],
        errors: dict[str, str],
    ) -> None:
        try:
            from app.db.session.database import get_db_session
            import json
            async with get_db_session() as session:
                from sqlalchemy import text
                await session.execute(
                    text(
                        "INSERT INTO evaluation_results "
                        "(run_id, case_id, evaluator_results, evaluator_errors, task_id) "
                        "VALUES (:run_id, :case_id, :results, :errors, :tid) "
                        "ON DUPLICATE KEY UPDATE "
                        "  evaluator_results=:results, evaluator_errors=:errors"
                    ),
                    {
                        "run_id":  task.run_id,
                        "case_id": task.case_id or "",
                        "results": json.dumps(results),
                        "errors":  json.dumps(errors),
                        "tid":     task.task_id,
                    },
                )
                await session.commit()
        except Exception as exc:
            logger.warning(
                "evaluation_worker.persist_failed",
                run_id=task.run_id,
                error=str(exc),
            )


def _parse_score(text: str) -> float:
    import re
    m = re.search(r"SCORE:\s*([0-9.]+)", text, re.IGNORECASE)
    if m:
        try:
            return max(0.0, min(1.0, float(m.group(1))))
        except ValueError:
            pass
    return 0.5  # neutral default


_EVALUATOR_PROMPTS: dict[str, str] = {
    "faithfulness": (
        "You are an evaluator assessing faithfulness of an AI answer. "
        "Rate how well the output is grounded in the provided context (0=not grounded, 1=fully grounded). "
        "Reply with: SCORE: <float>\nFEEDBACK: <one sentence>"
    ),
    "answer_relevance": (
        "You are an evaluator assessing relevance of an AI answer to the input question. "
        "Rate how well the output addresses the input (0=irrelevant, 1=fully relevant). "
        "Reply with: SCORE: <float>\nFEEDBACK: <one sentence>"
    ),
    "policy_compliance": (
        "You are a healthcare prior authorization expert. "
        "Evaluate whether the AI recommendation correctly applies the cited policy. "
        "Rate compliance (0=non-compliant, 1=fully compliant). "
        "Reply with: SCORE: <float>\nFEEDBACK: <one sentence>"
    ),
    "default": (
        "You are a quality evaluator. Rate the AI output on a scale of 0–1. "
        "Reply with: SCORE: <float>\nFEEDBACK: <one sentence>"
    ),
}
