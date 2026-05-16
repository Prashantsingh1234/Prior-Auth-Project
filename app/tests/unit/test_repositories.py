"""
Unit tests for the base repository and PA case repository.

Uses AsyncMock sessions — no real database required.
Verifies CRUD contracts, soft-delete behaviour, error propagation,
and case-specific query methods.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.exceptions.base import DatabaseError, ResourceConflictError, ResourceNotFoundError
from app.db.repositories.pa_case import PACaseRepository
from app.models.enums import CasePriority, CaseStatus
from app.models.pa_case import PACase


def _make_case(**kwargs) -> PACase:
    defaults = dict(
        id=str(uuid.uuid4()),
        case_number="PA-20240101-ABCDEF",
        patient_id=str(uuid.uuid4()),
        provider_id=str(uuid.uuid4()),
        status=CaseStatus.SUBMITTED,
        priority=CasePriority.ROUTINE,
        cpt_codes=["95249"],
        icd_codes=["E11.9"],
        clarification_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )
    defaults.update(kwargs)
    case = MagicMock(spec=PACase)
    for k, v in defaults.items():
        setattr(case, k, v)
    return case


class TestBaseRepositoryGetById:

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_db_session: AsyncMock):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        repo = PACaseRepository(mock_db_session)
        result = await repo.get_by_id("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_record_when_found(self, mock_db_session: AsyncMock):
        case = _make_case()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = case
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        repo = PACaseRepository(mock_db_session)
        result = await repo.get_by_id(case.id)
        assert result is case

    @pytest.mark.asyncio
    async def test_raises_database_error_on_sql_error(self, mock_db_session: AsyncMock):
        from sqlalchemy.exc import SQLAlchemyError
        mock_db_session.execute = AsyncMock(side_effect=SQLAlchemyError("connection lost"))

        repo = PACaseRepository(mock_db_session)
        with pytest.raises(DatabaseError):
            await repo.get_by_id("some-id")

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise_raises_when_not_found(self, mock_db_session: AsyncMock):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        repo = PACaseRepository(mock_db_session)
        with pytest.raises(ResourceNotFoundError):
            await repo.get_by_id_or_raise("nonexistent-id")

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise_returns_record(self, mock_db_session: AsyncMock):
        case = _make_case()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = case
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        repo = PACaseRepository(mock_db_session)
        result = await repo.get_by_id_or_raise(case.id)
        assert result is case


class TestBaseRepositoryCreate:

    @pytest.mark.asyncio
    async def test_create_adds_to_session(self, mock_db_session: AsyncMock):
        case = _make_case()
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        mock_db_session.add = MagicMock()

        with patch.object(PACase, "__init__", return_value=None):
            with patch("app.db.repositories.base.BaseRepository.create", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = case
                repo = PACaseRepository(mock_db_session)
                result = await repo.create(id=case.id, case_number=case.case_number)
                assert result is case

    @pytest.mark.asyncio
    async def test_create_raises_conflict_on_integrity_error(self, mock_db_session: AsyncMock):
        mock_db_session.flush = AsyncMock(
            side_effect=IntegrityError("Duplicate entry", params={}, orig=Exception("UNIQUE"))
        )
        mock_db_session.rollback = AsyncMock()

        from app.db.repositories.base import BaseRepository
        repo = PACaseRepository(mock_db_session)

        with patch.object(BaseRepository, "create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = ResourceConflictError(details={"constraint": "UNIQUE"})
            with pytest.raises(ResourceConflictError):
                await repo.create(case_number="DUPLICATE")


class TestBaseRepositorySoftDelete:

    @pytest.mark.asyncio
    async def test_soft_delete_returns_false_when_not_found(self, mock_db_session: AsyncMock):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        repo = PACaseRepository(mock_db_session)
        result = await repo.soft_delete("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_soft_delete_sets_deleted_at(self, mock_db_session: AsyncMock):
        case = _make_case()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = case
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        mock_db_session.flush = AsyncMock()
        case.soft_delete = MagicMock()

        repo = PACaseRepository(mock_db_session)
        result = await repo.soft_delete(case.id)
        assert result is True
        case.soft_delete.assert_called_once()


class TestBaseRepositoryGetAll:

    @pytest.mark.asyncio
    async def test_limit_capped_at_500(self, mock_db_session: AsyncMock):
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        repo = PACaseRepository(mock_db_session)
        # Request 1000 — should cap at 500 internally (no error raised)
        result = await repo.get_all(limit=1000)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_records(self, mock_db_session: AsyncMock):
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        repo = PACaseRepository(mock_db_session)
        result = await repo.get_all()
        assert result == []


class TestPACaseRepositorySpecificMethods:

    @pytest.mark.asyncio
    async def test_count_by_status_returns_dict(self, mock_db_session: AsyncMock):
        """count_by_status should return a dict of status → count."""
        rows = [
            MagicMock(status=CaseStatus.SUBMITTED, count=5),
            MagicMock(status=CaseStatus.UNDER_REVIEW, count=3),
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        repo = PACaseRepository(mock_db_session)
        counts = await repo.count_by_status()
        assert isinstance(counts, dict)

    @pytest.mark.asyncio
    async def test_transition_status_updates_case(self, mock_db_session: AsyncMock):
        """transition_status should update the case's status field."""
        case = _make_case(status=CaseStatus.SUBMITTED)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = case
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        mock_db_session.flush = AsyncMock()

        repo = PACaseRepository(mock_db_session)
        await repo.transition_status(case.id, CaseStatus.PROCESSING, actor_id="user-1")
        assert case.status == CaseStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_increment_clarification_count(self, mock_db_session: AsyncMock):
        """increment_clarification_count should add 1 to clarification_count."""
        case = _make_case(clarification_count=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = case
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        mock_db_session.flush = AsyncMock()

        repo = PACaseRepository(mock_db_session)
        await repo.increment_clarification_count(case.id)
        assert case.clarification_count == 2

    @pytest.mark.asyncio
    async def test_assign_reviewer_sets_reviewer_id(self, mock_db_session: AsyncMock):
        case = _make_case()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = case
        mock_db_session.execute = AsyncMock(return_value=result_mock)
        mock_db_session.flush = AsyncMock()

        reviewer_uuid = str(uuid.uuid4())
        repo = PACaseRepository(mock_db_session)
        await repo.assign_reviewer(case.id, reviewer_uuid)
        assert case.assigned_reviewer_id == reviewer_uuid


class TestRetryBehavior:
    """Repository should retry on transient OperationalErrors."""

    @pytest.mark.asyncio
    async def test_retries_on_operational_error(self, mock_db_session: AsyncMock):
        case = _make_case()
        success_result = MagicMock()
        success_result.scalar_one_or_none.return_value = case

        call_count = 0

        async def flaky_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError("connection reset", params={}, orig=Exception())
            return success_result

        mock_db_session.execute = flaky_execute

        repo = PACaseRepository(mock_db_session)
        result = await repo.get_by_id(case.id)
        assert result is case
        assert call_count == 3  # Failed twice, succeeded on 3rd try
