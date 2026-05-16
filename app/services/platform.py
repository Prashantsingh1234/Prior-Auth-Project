"""
app/services/platform.py — PAReviewPlatform integration facade.

Single entry point that coordinates all platform services for the complete
PA review workflow. Designed for use by API routes, queue workers, and the
demo script. All operations are async and fully observable.

Workflow:
  submit_case → [queue] → process_case:
    ingest_documents → extract_entities → retrieve_policies
    → ai_reasoning → store_evaluation → notify → [human_review]
    → record_decision → audit
"""
from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.core.config.settings import get_settings
from app.models.enums import (
    AuditAction,
    CaseStatus,
    DecisionOutcome,
    DecisionSource,
)

logger = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class WorkflowResult:
    """Returned by process_case() — the complete AI evaluation result."""
    case_id: str
    recommendation: str                   # APPROVE | DENY | PEND | ESCALATE
    confidence: float
    rationale: str
    criteria_results: list[dict[str, Any]]
    retrieved_chunks: int
    entities_extracted: int
    cost_usd: float
    latency_ms: float
    audit_trail: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PlatformHealth:
    """Aggregated health status from all subsystems."""
    healthy: bool
    components: dict[str, bool]
    latency_ms: dict[str, float]
    details: dict[str, Any] = field(default_factory=dict)


class PAReviewPlatform:
    """
    Facade coordinating all PA platform services.

    Instantiate once at startup and share via FastAPI dependency injection
    or pass explicitly to workers. Thread-safe; all state is async-local.

    Usage:
        platform = PAReviewPlatform()
        await platform.startup()
        result = await platform.process_case(case_id="...", session=db_session)
        await platform.shutdown()
    """

    def __init__(self) -> None:
        self._started = False
        self._redis: Any = None
        self._log = structlog.get_logger(self.__class__.__name__)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def startup(self) -> None:
        """Initialize all platform services. Call once at application start."""
        if self._started:
            return
        self._log.info("platform.startup.begin")
        t0 = time.monotonic()

        # Import lazily to avoid circular imports and allow selective startup
        from app.db.session.database import get_session_factory
        from app.services.caching.redis_client import get_redis_client

        self._session_factory = get_session_factory()
        try:
            self._redis = await get_redis_client()
            self._log.info("platform.redis.connected")
        except Exception as exc:
            self._log.warning("platform.redis.unavailable", error=str(exc))
            self._redis = None

        self._started = True
        elapsed = (time.monotonic() - t0) * 1000
        self._log.info("platform.startup.complete", elapsed_ms=round(elapsed, 1))

    async def shutdown(self) -> None:
        """Graceful shutdown — drain connections, flush buffers."""
        self._log.info("platform.shutdown.begin")
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass
        self._started = False
        self._log.info("platform.shutdown.complete")

    @asynccontextmanager
    async def _db_session(self):
        """Yield a managed async DB session."""
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # ── Health ─────────────────────────────────────────────────────────────

    async def health_check(self) -> PlatformHealth:
        """
        Deep health check across all subsystems.
        Returns within 5 seconds regardless of component failures.
        """
        components: dict[str, bool] = {}
        latencies: dict[str, float] = {}

        async def _check(name: str, coro) -> None:
            t = time.monotonic()
            try:
                await asyncio.wait_for(coro, timeout=2.0)
                components[name] = True
            except Exception as exc:
                components[name] = False
                self._log.warning(f"health.{name}.failed", error=str(exc))
            finally:
                latencies[name] = round((time.monotonic() - t) * 1000, 1)

        await asyncio.gather(
            _check("database", self._ping_database()),
            _check("redis", self._ping_redis()),
            _check("rabbitmq", self._ping_rabbitmq()),
            _check("pinecone", self._ping_pinecone()),
            return_exceptions=True,
        )

        healthy = components.get("database", False) and components.get("redis", False)
        return PlatformHealth(
            healthy=healthy,
            components=components,
            latency_ms=latencies,
        )

    async def _ping_database(self) -> None:
        from sqlalchemy import text
        async with self._db_session() as session:
            await session.execute(text("SELECT 1"))

    async def _ping_redis(self) -> None:
        if self._redis:
            await self._redis.ping()
        else:
            raise RuntimeError("Redis not connected")

    async def _ping_rabbitmq(self) -> None:
        from app.queues.connection import get_connection
        conn = await get_connection()
        await conn.close()

    async def _ping_pinecone(self) -> None:
        if not settings.pinecone_api_key:
            raise RuntimeError("Pinecone not configured")
        from app.services.vector.pinecone_client import get_pinecone_client
        client = get_pinecone_client()
        client.describe_index(settings.pinecone_index_name)

    # ── Core Workflow ──────────────────────────────────────────────────────

    async def process_case(
        self,
        case_id: str,
        *,
        run_id: str | None = None,
    ) -> WorkflowResult:
        """
        Execute the complete AI reasoning workflow for a PA case.

        Stages:
          1. Load case + documents from DB
          2. Run OCR on unprocessed documents
          3. Extract clinical entities (LLM)
          4. Retrieve relevant policy chunks (hybrid vector+keyword)
          5. Run AI reasoning (multi-model with confidence routing)
          6. Store evaluation results
          7. Emit audit events
          8. Return structured WorkflowResult

        All stages are individually timed and traced. Any stage failure
        is caught, logged, and — where possible — recovered with fallbacks.
        """
        if not self._started:
            await self.startup()

        run_id = run_id or str(uuid.uuid4())
        log = self._log.bind(case_id=case_id, run_id=run_id)
        log.info("workflow.start")
        t_start = time.monotonic()
        audit_trail: list[str] = []
        warnings: list[str] = []

        try:
            async with self._db_session() as session:
                # ── Stage 1: Load case ─────────────────────────────────
                from app.db.repositories.pa_case import PACaseRepository
                repo = PACaseRepository(session)
                case = await repo.get_with_all_relations(case_id)
                if case is None:
                    raise ValueError(f"Case {case_id} not found")
                log.info("workflow.case_loaded", status=case.status)
                audit_trail.append(f"Case loaded: status={case.status}")

                # ── Stage 2: OCR ───────────────────────────────────────
                docs_processed = 0
                try:
                    from app.services.ocr.orchestrator import OCROrchestrator
                    ocr = OCROrchestrator()
                    for doc in case.documents:
                        if doc.ocr_status in ("PENDING", None):
                            await ocr.process_document(doc, session=session)
                            docs_processed += 1
                    audit_trail.append(f"OCR: {docs_processed} documents processed")
                    log.info("workflow.ocr_complete", docs_processed=docs_processed)
                except ImportError:
                    warnings.append("OCR service not available — using raw text")

                # ── Stage 3: Entity extraction ─────────────────────────
                entities_extracted = 0
                try:
                    from app.services.extraction.orchestrator import ExtractionOrchestrator
                    extractor = ExtractionOrchestrator()
                    extracted = await extractor.extract(case=case, session=session)
                    entities_extracted = len(extracted) if extracted else 0
                    audit_trail.append(f"Extraction: {entities_extracted} entities")
                    log.info("workflow.extraction_complete", entities=entities_extracted)
                except ImportError:
                    warnings.append("Extraction service not available")
                    extracted = []

                # ── Stage 4: Policy retrieval ──────────────────────────
                retrieved_chunks = 0
                policy_chunks: list[Any] = []
                try:
                    from app.services.retrieval.orchestrator import RetrievalOrchestrator
                    retrieval = RetrievalOrchestrator()
                    policy_chunks = await retrieval.retrieve(
                        case=case,
                        entities=extracted,
                        top_k=10,
                    )
                    retrieved_chunks = len(policy_chunks)
                    audit_trail.append(f"Retrieval: {retrieved_chunks} policy chunks")
                    log.info("workflow.retrieval_complete", chunks=retrieved_chunks)
                except ImportError:
                    warnings.append("Retrieval service not available — no policy context")

                # ── Stage 5: AI reasoning ──────────────────────────────
                from app.services.reasoning.orchestrator import ReasoningOrchestrator
                reasoner = ReasoningOrchestrator()
                context = {
                    "case_id": case_id,
                    "cpt_codes": [e for e in (case.entities or []) if "CPT" in str(getattr(e, "entity_type", ""))],
                    "icd_codes": [e for e in (case.entities or []) if "ICD" in str(getattr(e, "entity_type", ""))],
                    "clinical_notes": " ".join(
                        getattr(doc, "extracted_text", "") or ""
                        for doc in (case.documents or [])
                    ),
                    "extracted_entities": extracted,
                    "policy_criteria": policy_chunks,
                    "retrieved_chunks": policy_chunks,
                    "priority": case.priority,
                }
                reasoning_result = await reasoner.run(context=context)
                log.info(
                    "workflow.reasoning_complete",
                    recommendation=reasoning_result.recommendation,
                    confidence=reasoning_result.confidence,
                    cost_usd=reasoning_result.cost_usd,
                )
                audit_trail.append(
                    f"AI recommendation: {reasoning_result.recommendation} "
                    f"(confidence={reasoning_result.confidence:.2f})"
                )

                # ── Stage 6: Persist evaluation ────────────────────────
                try:
                    from app.db.repositories.evaluation import EvaluationRepository
                    eval_repo = EvaluationRepository(session)
                    await eval_repo.create_from_reasoning(
                        case_id=case_id,
                        recommendation=reasoning_result.recommendation,
                        confidence=reasoning_result.confidence,
                        rationale=reasoning_result.rationale,
                        criteria_results=getattr(reasoning_result, "criteria_results", []),
                        cost_usd=reasoning_result.cost_usd,
                    )
                    audit_trail.append("Evaluation persisted to database")
                except (ImportError, AttributeError) as exc:
                    warnings.append(f"Could not persist evaluation: {exc}")

                # ── Stage 7: Update case status ────────────────────────
                confidence = reasoning_result.confidence
                if confidence >= 0.90 and reasoning_result.recommendation in ("APPROVE", "DENY"):
                    new_status = CaseStatus.UNDER_REVIEW
                elif confidence < 0.65:
                    new_status = CaseStatus.PENDING_CLARIFICATION
                else:
                    new_status = CaseStatus.UNDER_REVIEW

                await repo.transition_status(case_id, new_status)
                audit_trail.append(f"Status → {new_status}")

                # ── Stage 8: Cache result ──────────────────────────────
                if self._redis:
                    try:
                        import orjson
                        cache_key = f"workflow:result:{case_id}"
                        await self._redis.setex(
                            cache_key,
                            300,  # 5-minute cache
                            orjson.dumps({
                                "recommendation": reasoning_result.recommendation,
                                "confidence": reasoning_result.confidence,
                                "run_id": run_id,
                            }),
                        )
                    except Exception:
                        pass

            latency_ms = round((time.monotonic() - t_start) * 1000, 1)
            log.info("workflow.complete", latency_ms=latency_ms, warnings=len(warnings))

            return WorkflowResult(
                case_id=case_id,
                recommendation=reasoning_result.recommendation,
                confidence=reasoning_result.confidence,
                rationale=reasoning_result.rationale,
                criteria_results=getattr(reasoning_result, "criteria_results", []),
                retrieved_chunks=retrieved_chunks,
                entities_extracted=entities_extracted,
                cost_usd=getattr(reasoning_result, "cost_usd", 0.0),
                latency_ms=latency_ms,
                audit_trail=audit_trail,
                warnings=warnings,
            )

        except Exception as exc:
            latency_ms = round((time.monotonic() - t_start) * 1000, 1)
            log.error("workflow.failed", error=str(exc), latency_ms=latency_ms)
            raise

    # ── Decision Recording ─────────────────────────────────────────────────

    async def record_decision(
        self,
        case_id: str,
        outcome: DecisionOutcome,
        rationale: str,
        reviewer_id: str | None = None,
        source: DecisionSource = DecisionSource.REVIEWER_OVERRIDE,
    ) -> None:
        """Persist a human reviewer decision and emit audit event."""
        log = self._log.bind(case_id=case_id, outcome=outcome, reviewer_id=reviewer_id)

        async with self._db_session() as session:
            from app.db.repositories.decision import DecisionRepository
            from app.db.repositories.reviewer_action import ReviewerActionRepository
            from app.db.repositories.pa_case import PACaseRepository

            decision_repo = DecisionRepository(session)
            action_repo = ReviewerActionRepository(session)
            case_repo = PACaseRepository(session)

            await decision_repo.create(
                case_id=case_id,
                outcome=outcome,
                rationale=rationale,
                source=source,
                reviewer_id=reviewer_id,
            )

            final_status = CaseStatus.APPROVED if outcome == DecisionOutcome.APPROVE else (
                CaseStatus.DENIED if outcome == DecisionOutcome.DENY else CaseStatus.PENDED
            )
            await case_repo.transition_status(case_id, final_status)

            if reviewer_id:
                action_type_map = {
                    DecisionOutcome.APPROVE: "APPROVED",
                    DecisionOutcome.DENY: "DENIED",
                    DecisionOutcome.PEND: "PENDED",
                }
                await action_repo.create(
                    case_id=case_id,
                    reviewer_id=reviewer_id,
                    action_type=action_type_map[outcome],
                    notes=rationale,
                )

        log.info("decision.recorded", status=final_status)

    # ── Cache Management ───────────────────────────────────────────────────

    async def invalidate_case_cache(self, case_id: str) -> int:
        """Invalidate all Redis cache entries for a given case."""
        if not self._redis:
            return 0
        pattern = f"*:{case_id}*"
        keys = await self._redis.keys(pattern)
        if keys:
            return await self._redis.delete(*keys)
        return 0

    async def get_cached_result(self, case_id: str) -> dict[str, Any] | None:
        """Return cached workflow result if available."""
        if not self._redis:
            return None
        import orjson
        raw = await self._redis.get(f"workflow:result:{case_id}")
        return orjson.loads(raw) if raw else None

    # ── Metrics ────────────────────────────────────────────────────────────

    async def get_platform_metrics(self) -> dict[str, Any]:
        """Aggregate real-time platform metrics from DB + Redis."""
        async with self._db_session() as session:
            from app.db.repositories.pa_case import PACaseRepository
            repo = PACaseRepository(session)
            status_counts = await repo.count_by_status()
            priority_counts = await repo.count_by_priority()

        redis_info: dict[str, Any] = {}
        if self._redis:
            try:
                info = await self._redis.info("stats")
                redis_info = {
                    "commands_per_sec": info.get("instantaneous_ops_per_sec", 0),
                    "hit_rate": _compute_hit_rate(info),
                    "memory_mb": round(
                        (await self._redis.info("memory")).get("used_memory", 0) / 1_048_576, 1
                    ),
                }
            except Exception:
                pass

        return {
            "cases": {s.value: c for s, c in status_counts.items()},
            "priority": {p.value: c for p, c in priority_counts.items()},
            "redis": redis_info,
        }


def _compute_hit_rate(info: dict) -> float:
    hits = info.get("keyspace_hits", 0)
    misses = info.get("keyspace_misses", 0)
    total = hits + misses
    return round(hits / total, 3) if total > 0 else 0.0


# ── Module-level singleton ─────────────────────────────────────────────────
_platform: PAReviewPlatform | None = None


def get_platform() -> PAReviewPlatform:
    """Return the module-level platform singleton (created on first call)."""
    global _platform
    if _platform is None:
        _platform = PAReviewPlatform()
    return _platform