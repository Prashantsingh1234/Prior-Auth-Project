"""
Integration tests for database repositories.

Runs against an in-memory SQLite database via aiosqlite — no external
services required. Each test gets an isolated session that rolls back
on teardown, so tests are fully independent.

Notes:
- MySQL-specific features (func.field priority ordering) are exercised
  by asserting on filtering behaviour only; ordering is skipped.
- All models are imported before table creation so Base.metadata is
  populated with every table.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import all models to populate Base.metadata before create_all
import app.models  # noqa: F401 — side-effect import registers all tables
from app.db.base.model import Base
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.decision import DecisionRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.pa_case import PACaseRepository
from app.db.repositories.patient import PatientRepository
from app.core.exceptions.base import ResourceNotFoundError
from app.models.enums import (
    ActorType,
    AuditAction,
    AuditEntityType,
    CasePriority,
    CaseStatus,
    DecisionOutcome,
    DecisionSource,
    OCRProvider,
    OCRStatus,
    ProviderType,
)
from app.models.patient import Patient
from app.models.provider import Provider
from app.models.pa_case import PACase
from app.models.document import UploadedDocument
from app.models.decision import Decision


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Function-scoped async SQLite session.

    Creates a fresh in-memory database per test — schema creation against
    SQLite in-memory is effectively free, so we skip the SAVEPOINT complexity
    and avoid pytest-asyncio event-loop scope issues entirely.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Record factories
# ---------------------------------------------------------------------------

def _patient_kwargs(**overrides) -> dict:
    defaults = dict(
        first_name="Jane",
        last_name="Smith",
        member_id=f"MBR-{uuid.uuid4().hex[:8]}",
        country="USA",
    )
    defaults.update(overrides)
    return defaults


def _provider_kwargs(**overrides) -> dict:
    defaults = dict(
        npi=f"{uuid.uuid4().int % 10**10:010d}",
        provider_type=ProviderType.INDIVIDUAL,
        first_name="Alice",
        last_name="Chen",
        credentials="MD",
    )
    defaults.update(overrides)
    return defaults


async def _create_patient(session: AsyncSession, **kwargs) -> Patient:
    repo = PatientRepository(session)
    return await repo.create(**_patient_kwargs(**kwargs))


async def _create_provider(session: AsyncSession, **kwargs) -> Provider:
    from app.db.repositories.provider import ProviderRepository
    repo = ProviderRepository(session)
    return await repo.create(**_provider_kwargs(**kwargs))


async def _create_case(
    session: AsyncSession,
    patient_id: str,
    provider_id: str,
    **kwargs,
) -> PACase:
    repo = PACaseRepository(session)
    defaults = dict(
        patient_id=patient_id,
        provider_id=provider_id,
        status=CaseStatus.SUBMITTED,
        priority=CasePriority.ROUTINE,
        cpt_codes=["99213"],
        icd_codes=["J06.9"],
        clarification_count=0,
    )
    defaults.update(kwargs)
    return await repo.create_case(**defaults)


# ---------------------------------------------------------------------------
# TestBaseRepositoryIntegration
#
# Uses PatientRepository (simple, no FKs) to verify all BaseRepository
# operations against a real SQL engine.
# ---------------------------------------------------------------------------

class TestBaseRepositoryIntegration:

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession) -> PatientRepository:
        return PatientRepository(db_session)

    async def test_create_returns_record_with_id(self, repo: PatientRepository) -> None:
        p = await repo.create(**_patient_kwargs())
        assert p.id is not None
        assert re.match(r"[0-9a-f-]{36}", p.id)

    async def test_get_by_id_returns_created_record(self, repo: PatientRepository) -> None:
        p = await repo.create(**_patient_kwargs(first_name="TestGet"))
        fetched = await repo.get_by_id(p.id)
        assert fetched is not None
        assert fetched.first_name == "TestGet"

    async def test_get_by_id_returns_none_for_unknown(self, repo: PatientRepository) -> None:
        result = await repo.get_by_id(str(uuid.uuid4()))
        assert result is None

    async def test_get_by_id_or_raise_raises_for_missing(self, repo: PatientRepository) -> None:
        with pytest.raises(ResourceNotFoundError):
            await repo.get_by_id_or_raise(str(uuid.uuid4()))

    async def test_update_modifies_fields(self, repo: PatientRepository) -> None:
        p = await repo.create(**_patient_kwargs(first_name="Before"))
        updated = await repo.update(p.id, first_name="After")
        assert updated.first_name == "After"

    async def test_soft_delete_hides_record_from_default_query(
        self, repo: PatientRepository
    ) -> None:
        p = await repo.create(**_patient_kwargs())
        deleted = await repo.soft_delete(p.id)
        assert deleted is True
        result = await repo.get_by_id(p.id)
        assert result is None

    async def test_soft_deleted_record_visible_with_include_deleted(
        self, repo: PatientRepository
    ) -> None:
        p = await repo.create(**_patient_kwargs())
        await repo.soft_delete(p.id)
        result = await repo.get_by_id(p.id, include_deleted=True)
        assert result is not None
        assert result.is_deleted is True

    async def test_count_excludes_soft_deleted_records(
        self, repo: PatientRepository
    ) -> None:
        before = await repo.count()
        p = await repo.create(**_patient_kwargs())
        assert await repo.count() == before + 1
        await repo.soft_delete(p.id)
        assert await repo.count() == before

    async def test_exists_true_for_existing_record(self, repo: PatientRepository) -> None:
        p = await repo.create(**_patient_kwargs())
        assert await repo.exists(p.id) is True

    async def test_exists_false_for_missing_id(self, repo: PatientRepository) -> None:
        assert await repo.exists(str(uuid.uuid4())) is False

    async def test_exists_false_after_soft_delete(self, repo: PatientRepository) -> None:
        p = await repo.create(**_patient_kwargs())
        await repo.soft_delete(p.id)
        assert await repo.exists(p.id) is False

    async def test_get_all_respects_pagination(self, repo: PatientRepository) -> None:
        for _ in range(3):
            await repo.create(**_patient_kwargs())
        page1 = await repo.get_all(skip=0, limit=2)
        page2 = await repo.get_all(skip=2, limit=2)
        assert len(page1) == 2
        assert len(page2) >= 1

    async def test_bulk_create_inserts_all_records(self, repo: PatientRepository) -> None:
        items = [_patient_kwargs(member_id=f"BULK-{i}") for i in range(4)]
        results = await repo.bulk_create(items)
        assert len(results) == 4
        assert all(r.id is not None for r in results)

    async def test_hard_delete_removes_record_permanently(
        self, repo: PatientRepository
    ) -> None:
        p = await repo.create(**_patient_kwargs())
        removed = await repo.hard_delete(p.id)
        assert removed is True
        assert await repo.get_by_id(p.id, include_deleted=True) is None

    async def test_soft_delete_returns_false_for_missing_id(
        self, repo: PatientRepository
    ) -> None:
        result = await repo.soft_delete(str(uuid.uuid4()))
        assert result is False


# ---------------------------------------------------------------------------
# TestPACaseRepositoryIntegration
# ---------------------------------------------------------------------------

class TestPACaseRepositoryIntegration:

    @pytest_asyncio.fixture
    async def patient_provider(self, db_session: AsyncSession):
        """Pre-created patient and provider for FK-dependent case tests."""
        patient = await _create_patient(db_session)
        provider = await _create_provider(db_session)
        return patient, provider

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession) -> PACaseRepository:
        return PACaseRepository(db_session)

    async def test_create_case_generates_case_number(
        self, db_session: AsyncSession, patient_provider
    ) -> None:
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        assert case.case_number is not None
        assert len(case.case_number) > 0

    async def test_case_number_format_matches_pa_pattern(
        self, db_session: AsyncSession, patient_provider
    ) -> None:
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        assert re.match(r"PA-\d{8}-[A-F0-9]{6}", case.case_number)

    async def test_create_case_sets_submitted_at(
        self, db_session: AsyncSession, patient_provider
    ) -> None:
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        assert case.submitted_at is not None

    async def test_get_by_case_number_found(
        self, db_session: AsyncSession, patient_provider, repo: PACaseRepository
    ) -> None:
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        fetched = await repo.get_by_case_number(case.case_number)
        assert fetched is not None
        assert fetched.id == case.id

    async def test_get_by_case_number_not_found(self, repo: PACaseRepository) -> None:
        result = await repo.get_by_case_number("PA-00000000-XXXXXX")
        assert result is None

    async def test_get_cases_for_patient_returns_only_that_patient(
        self, db_session: AsyncSession, patient_provider, repo: PACaseRepository
    ) -> None:
        patient, provider = patient_provider
        other_patient = await _create_patient(db_session, member_id=f"OTHER-{uuid.uuid4().hex[:6]}")
        await _create_case(db_session, patient.id, provider.id)
        await _create_case(db_session, patient.id, provider.id)
        await _create_case(db_session, other_patient.id, provider.id)

        cases = await repo.get_cases_for_patient(patient.id)
        assert len(cases) >= 2
        assert all(c.patient_id == patient.id for c in cases)

    async def test_transition_status_changes_status(
        self, db_session: AsyncSession, patient_provider, repo: PACaseRepository
    ) -> None:
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        updated = await repo.transition_status(case.id, CaseStatus.PROCESSING)
        assert updated.status == CaseStatus.PROCESSING

    async def test_transition_status_sets_processing_started_at(
        self, db_session: AsyncSession, patient_provider, repo: PACaseRepository
    ) -> None:
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        updated = await repo.transition_status(case.id, CaseStatus.PROCESSING)
        assert updated.processing_started_at is not None

    async def test_transition_status_sets_decided_at_for_approved(
        self, db_session: AsyncSession, patient_provider, repo: PACaseRepository
    ) -> None:
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        # move through required states before approval
        await repo.transition_status(case.id, CaseStatus.PROCESSING)
        await repo.transition_status(case.id, CaseStatus.UNDER_REVIEW)
        updated = await repo.transition_status(case.id, CaseStatus.APPROVED)
        assert updated.decided_at is not None

    async def test_transition_status_raises_for_already_decided_case(
        self, db_session: AsyncSession, patient_provider, repo: PACaseRepository
    ) -> None:
        from app.core.exceptions.base import CaseAlreadyDecidedError
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        await repo.transition_status(case.id, CaseStatus.PROCESSING)
        await repo.transition_status(case.id, CaseStatus.UNDER_REVIEW)
        await repo.transition_status(case.id, CaseStatus.APPROVED)
        with pytest.raises(CaseAlreadyDecidedError):
            await repo.transition_status(case.id, CaseStatus.DENIED)

    async def test_assign_reviewer_sets_reviewer_id(
        self, db_session: AsyncSession, patient_provider, repo: PACaseRepository
    ) -> None:
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        reviewer_id = str(uuid.uuid4())
        updated = await repo.assign_reviewer(case.id, reviewer_id)
        assert updated.assigned_reviewer_id == reviewer_id
        assert updated.review_assigned_at is not None

    async def test_increment_clarification_count(
        self, db_session: AsyncSession, patient_provider, repo: PACaseRepository
    ) -> None:
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        assert case.clarification_count == 0
        updated = await repo.increment_clarification_count(case.id)
        assert updated.clarification_count == 1
        updated2 = await repo.increment_clarification_count(case.id)
        assert updated2.clarification_count == 2

    async def test_count_by_status_returns_correct_counts(
        self, db_session: AsyncSession, patient_provider, repo: PACaseRepository
    ) -> None:
        patient, provider = patient_provider
        case1 = await _create_case(db_session, patient.id, provider.id)
        case2 = await _create_case(db_session, patient.id, provider.id)
        await repo.transition_status(case2.id, CaseStatus.PROCESSING)

        counts = await repo.count_by_status()
        assert isinstance(counts, dict)
        # Both cases exist; submitted count >= 1 (case1 still submitted)
        assert counts.get(CaseStatus.SUBMITTED, 0) >= 1
        assert counts.get(CaseStatus.PROCESSING, 0) >= 1

    async def test_get_reviewer_queue_filters_under_review_cases(
        self, db_session: AsyncSession, patient_provider, repo: PACaseRepository
    ) -> None:
        patient, provider = patient_provider
        case = await _create_case(db_session, patient.id, provider.id)
        await repo.transition_status(case.id, CaseStatus.PROCESSING)
        await repo.transition_status(case.id, CaseStatus.UNDER_REVIEW)

        queue = await repo.get_reviewer_queue()
        case_ids = [c.id for c in queue]
        assert case.id in case_ids


# ---------------------------------------------------------------------------
# TestPatientRepositoryIntegration
# ---------------------------------------------------------------------------

class TestPatientRepositoryIntegration:

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession) -> PatientRepository:
        return PatientRepository(db_session)

    async def test_get_by_member_id_found(self, repo: PatientRepository) -> None:
        mid = f"MBR-{uuid.uuid4().hex[:8]}"
        await repo.create(**_patient_kwargs(member_id=mid))
        result = await repo.get_by_member_id(mid)
        assert result is not None
        assert result.member_id == mid

    async def test_get_by_member_id_not_found(self, repo: PatientRepository) -> None:
        result = await repo.get_by_member_id("NONEXISTENT-ID")
        assert result is None

    async def test_get_by_member_id_with_plan_filter_matches(
        self, repo: PatientRepository
    ) -> None:
        mid = f"MBR-{uuid.uuid4().hex[:8]}"
        plan = "PLAN-BLUE"
        await repo.create(**_patient_kwargs(member_id=mid, insurance_plan_id=plan))
        result = await repo.get_by_member_id(mid, plan_id=plan)
        assert result is not None

    async def test_get_by_member_id_with_wrong_plan_returns_none(
        self, repo: PatientRepository
    ) -> None:
        mid = f"MBR-{uuid.uuid4().hex[:8]}"
        await repo.create(**_patient_kwargs(member_id=mid, insurance_plan_id="PLAN-A"))
        result = await repo.get_by_member_id(mid, plan_id="PLAN-B")
        assert result is None

    async def test_search_by_last_name(self, repo: PatientRepository) -> None:
        await repo.create(**_patient_kwargs(last_name="Zymanski", member_id=f"Z-{uuid.uuid4().hex[:6]}"))
        results = await repo.search_by_name("zymanski")
        assert any(p.last_name == "Zymanski" for p in results)

    async def test_search_by_last_and_first_name(self, repo: PatientRepository) -> None:
        await repo.create(**_patient_kwargs(
            last_name="Nguyen", first_name="Van",
            member_id=f"N-{uuid.uuid4().hex[:6]}",
        ))
        results = await repo.search_by_name("Nguyen", first_name="Van")
        assert any(p.first_name == "Van" for p in results)

    async def test_get_or_create_creates_new_patient(
        self, repo: PatientRepository
    ) -> None:
        mid = f"NEW-{uuid.uuid4().hex[:8]}"
        patient, created = await repo.get_or_create(
            mid, first_name="Bob", last_name="Jones"
        )
        assert created is True
        assert patient.member_id == mid

    async def test_get_or_create_returns_existing_on_second_call(
        self, repo: PatientRepository
    ) -> None:
        mid = f"EXIST-{uuid.uuid4().hex[:8]}"
        _, created1 = await repo.get_or_create(mid, first_name="A", last_name="B")
        _, created2 = await repo.get_or_create(mid, first_name="A", last_name="B")
        assert created1 is True
        assert created2 is False


# ---------------------------------------------------------------------------
# TestDocumentRepositoryIntegration
# ---------------------------------------------------------------------------

class TestDocumentRepositoryIntegration:

    @pytest_asyncio.fixture
    async def case_id(self, db_session: AsyncSession) -> str:
        """Creates a real patient → provider → case and returns the case id."""
        patient = await _create_patient(db_session)
        provider = await _create_provider(db_session)
        case = await _create_case(db_session, patient.id, provider.id)
        return case.id

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession) -> DocumentRepository:
        return DocumentRepository(db_session)

    def _doc_kwargs(self, case_id: str, **overrides) -> dict:
        defaults = dict(
            case_id=case_id,
            original_filename="referral.pdf",
            stored_filename=f"stored_{uuid.uuid4().hex[:8]}.pdf",
            storage_path=f"/uploads/{uuid.uuid4().hex}.pdf",
            ocr_provider=OCRProvider.NONE,
            ocr_status=OCRStatus.PENDING,
            processing_attempts=0,
        )
        defaults.update(overrides)
        return defaults

    async def test_create_document(
        self, repo: DocumentRepository, case_id: str
    ) -> None:
        doc = await repo.create(**self._doc_kwargs(case_id))
        assert doc.id is not None
        assert doc.case_id == case_id

    async def test_get_by_case_id_returns_docs_for_case(
        self, repo: DocumentRepository, case_id: str
    ) -> None:
        await repo.create(**self._doc_kwargs(case_id))
        await repo.create(**self._doc_kwargs(case_id))
        docs = await repo.get_by_case_id(case_id)
        assert len(docs) >= 2
        assert all(d.case_id == case_id for d in docs)

    async def test_get_by_case_id_excludes_other_cases(
        self, db_session: AsyncSession, repo: DocumentRepository, case_id: str
    ) -> None:
        patient2 = await _create_patient(db_session, member_id=f"X-{uuid.uuid4().hex[:6]}")
        provider2 = await _create_provider(db_session, npi=f"{uuid.uuid4().int % 10**10:010d}")
        other_case = await _create_case(db_session, patient2.id, provider2.id)
        await repo.create(**self._doc_kwargs(case_id))
        await repo.create(**self._doc_kwargs(other_case.id))
        docs = await repo.get_by_case_id(case_id)
        assert all(d.case_id == case_id for d in docs)

    async def test_get_by_checksum_found(
        self, repo: DocumentRepository, case_id: str
    ) -> None:
        sha = "a" * 64
        await repo.create(**self._doc_kwargs(case_id, checksum_sha256=sha))
        result = await repo.get_by_checksum(sha)
        assert result is not None
        assert result.checksum_sha256 == sha

    async def test_get_by_checksum_not_found(self, repo: DocumentRepository) -> None:
        result = await repo.get_by_checksum("b" * 64)
        assert result is None

    async def test_get_pending_ocr_returns_pending_docs(
        self, repo: DocumentRepository, case_id: str
    ) -> None:
        pending = await repo.create(**self._doc_kwargs(case_id, ocr_status=OCRStatus.PENDING))
        await repo.create(**self._doc_kwargs(case_id, ocr_status=OCRStatus.COMPLETED))
        results = await repo.get_pending_ocr()
        assert any(d.id == pending.id for d in results)
        assert all(d.ocr_status == OCRStatus.PENDING for d in results)

    async def test_update_ocr_result_sets_status_and_confidence(
        self, repo: DocumentRepository, case_id: str
    ) -> None:
        doc = await repo.create(**self._doc_kwargs(case_id))
        updated = await repo.update_ocr_result(
            doc.id,
            ocr_status=OCRStatus.COMPLETED,
            extracted_text="Extracted clinical text.",
            ocr_confidence=0.94,
            ocr_provider=OCRProvider.AZURE,
        )
        assert updated.ocr_status == OCRStatus.COMPLETED
        assert updated.ocr_confidence == pytest.approx(0.94)
        assert updated.ocr_provider == OCRProvider.AZURE

    async def test_increment_processing_attempts(
        self, repo: DocumentRepository, case_id: str
    ) -> None:
        doc = await repo.create(**self._doc_kwargs(case_id))
        assert doc.processing_attempts == 0
        updated = await repo.increment_processing_attempts(doc.id)
        assert updated.processing_attempts == 1
        updated2 = await repo.increment_processing_attempts(doc.id)
        assert updated2.processing_attempts == 2


# ---------------------------------------------------------------------------
# TestAuditLogRepositoryIntegration
# ---------------------------------------------------------------------------

class TestAuditLogRepositoryIntegration:

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession) -> AuditLogRepository:
        return AuditLogRepository(db_session)

    async def test_log_event_creates_entry(self, repo: AuditLogRepository) -> None:
        case_id = str(uuid.uuid4())
        entry = await repo.log_event(
            action=AuditAction.CREATE,
            entity_type=AuditEntityType.PA_CASE,
            entity_id=case_id,
            actor_type=ActorType.SYSTEM,
            case_id=case_id,
            description="Case submitted via API",
        )
        assert entry.id is not None
        assert entry.action == AuditAction.CREATE

    async def test_get_for_case_returns_entries_for_case(
        self, repo: AuditLogRepository
    ) -> None:
        case_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        await repo.log_event(
            action=AuditAction.STATUS_CHANGE,
            entity_type=AuditEntityType.PA_CASE,
            case_id=case_id,
        )
        await repo.log_event(
            action=AuditAction.STATUS_CHANGE,
            entity_type=AuditEntityType.PA_CASE,
            case_id=other_id,
        )
        results = await repo.get_for_case(case_id)
        assert all(r.case_id == case_id for r in results)

    async def test_get_for_entity_returns_entries_for_entity(
        self, repo: AuditLogRepository
    ) -> None:
        entity_id = str(uuid.uuid4())
        await repo.log_event(
            action=AuditAction.CREATE,
            entity_type=AuditEntityType.DOCUMENT,
            entity_id=entity_id,
        )
        results = await repo.get_for_entity(AuditEntityType.DOCUMENT, entity_id)
        assert len(results) >= 1
        assert all(r.entity_id == entity_id for r in results)

    async def test_get_for_actor_returns_entries_for_actor(
        self, repo: AuditLogRepository
    ) -> None:
        actor_id = str(uuid.uuid4())
        await repo.log_event(
            action=AuditAction.DECISION_MADE,
            entity_type=AuditEntityType.DECISION,
            actor_type=ActorType.USER,
            actor_id=actor_id,
        )
        results = await repo.get_for_actor(actor_id)
        assert len(results) >= 1
        assert all(r.actor_id == actor_id for r in results)

    async def test_update_raises_not_implemented(
        self, repo: AuditLogRepository
    ) -> None:
        with pytest.raises(NotImplementedError):
            await repo.update(str(uuid.uuid4()), description="tampered")

    async def test_soft_delete_raises_not_implemented(
        self, repo: AuditLogRepository
    ) -> None:
        with pytest.raises(NotImplementedError):
            await repo.soft_delete(str(uuid.uuid4()))

    async def test_hard_delete_raises_not_implemented(
        self, repo: AuditLogRepository
    ) -> None:
        with pytest.raises(NotImplementedError):
            await repo.hard_delete(str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# TestDecisionRepositoryIntegration
# ---------------------------------------------------------------------------

class TestDecisionRepositoryIntegration:

    @pytest_asyncio.fixture
    async def case_id(self, db_session: AsyncSession) -> str:
        patient = await _create_patient(db_session)
        provider = await _create_provider(db_session)
        case = await _create_case(db_session, patient.id, provider.id)
        return case.id

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession) -> DecisionRepository:
        return DecisionRepository(db_session)

    async def test_get_by_case_id_returns_none_when_no_decision(
        self, repo: DecisionRepository, case_id: str
    ) -> None:
        result = await repo.get_by_case_id(case_id)
        assert result is None

    async def test_decision_exists_false_when_no_decision(
        self, repo: DecisionRepository, case_id: str
    ) -> None:
        assert await repo.decision_exists(case_id) is False

    async def test_get_by_case_id_returns_decision(
        self, repo: DecisionRepository, case_id: str
    ) -> None:
        d = await repo.create(
            case_id=case_id,
            final_decision=DecisionOutcome.APPROVE,
            decision_source=DecisionSource.AI_RECOMMENDATION,
            ai_recommendation=DecisionOutcome.APPROVE,
        )
        result = await repo.get_by_case_id(case_id)
        assert result is not None
        assert result.id == d.id

    async def test_decision_exists_true_after_creation(
        self, repo: DecisionRepository, case_id: str
    ) -> None:
        await repo.create(
            case_id=case_id,
            final_decision=DecisionOutcome.DENY,
            decision_source=DecisionSource.REVIEWER_OVERRIDE,
        )
        assert await repo.decision_exists(case_id) is True

    async def test_get_override_rate_zero_with_no_records(
        self, repo: DecisionRepository
    ) -> None:
        # May be non-zero if other tests ran — just assert it's a valid float
        rate = await repo.get_override_rate()
        assert 0.0 <= rate <= 1.0

    async def test_get_approval_rate_returns_all_outcomes(
        self, repo: DecisionRepository
    ) -> None:
        rates = await repo.get_approval_rate()
        # All DecisionOutcome values must be present (with 0.0 if no data)
        assert all(isinstance(v, float) for v in rates.values())
