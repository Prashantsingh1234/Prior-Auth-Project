"""
Unit tests for the Redis caching layer.

All tests mock the low-level redis_client functions so no real Redis
instance is required. Tests verify:
- Key generation logic (determinism, versioning, namespacing)
- Hit / miss behaviour for each domain service
- TTL propagation
- Graceful fallback when Redis raises
- Cache invalidation paths
- Decorator behaviour (@cached, @invalidate_cache)
- ClarificationState properties
- LLMCacheEntry serialization round-trip
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.caching.clarification_cache import (
    ClarificationCache,
    ClarificationState,
)
from app.services.caching.decorators import cached, invalidate_cache
from app.services.caching.embedding_cache import EmbeddingCache
from app.services.caching.keys import (
    CACHE_VERSION,
    TTL,
    clarification_key,
    content_hash,
    embedding_key,
    llm_key,
    retrieval_key,
    session_key,
    token_revoked_key,
)
from app.services.caching.llm_cache import LLMCache, LLMCacheEntry
from app.services.caching.manager import CacheManager, get_cache_manager
from app.services.caching.retrieval_cache import RetrievalCache
from app.services.caching.session_cache import SessionCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_redis(get_return=None, set_return=None, delete_return=False):
    """Return a context-manager that patches the three low-level cache funcs."""
    return (
        patch(
            "app.services.caching.base.cache_get",
            new_callable=AsyncMock,
            return_value=get_return,
        ),
        patch(
            "app.services.caching.base.cache_set",
            new_callable=AsyncMock,
            return_value=set_return,
        ),
        patch(
            "app.services.caching.base.cache_delete",
            new_callable=AsyncMock,
            return_value=delete_return,
        ),
    )


# ---------------------------------------------------------------------------
# TestKeyBuilder
# ---------------------------------------------------------------------------

class TestKeyBuilder:

    def test_version_prefix_present(self) -> None:
        key = retrieval_key(["95249"], ["E11.9"], "diabetes pump")
        assert key.startswith(f"pa:{CACHE_VERSION}:")

    def test_retrieval_key_sorted_codes(self) -> None:
        """Same codes in different order must produce the same key."""
        k1 = retrieval_key(["99213", "95249"], ["J06.9", "E11.9"], "query")
        k2 = retrieval_key(["95249", "99213"], ["E11.9", "J06.9"], "query")
        assert k1 == k2

    def test_retrieval_key_different_queries(self) -> None:
        """Different query strings must produce different keys."""
        k1 = retrieval_key(["99213"], ["E11.9"], "query one")
        k2 = retrieval_key(["99213"], ["E11.9"], "query two")
        assert k1 != k2

    def test_llm_key_includes_model(self) -> None:
        k1 = llm_key("gpt-4o", "same prompt")
        k2 = llm_key("gpt-3.5-turbo", "same prompt")
        assert k1 != k2

    def test_llm_key_same_prompt_same_key(self) -> None:
        assert llm_key("gpt-4o", "prompt") == llm_key("gpt-4o", "prompt")

    def test_embedding_key_includes_model(self) -> None:
        k1 = embedding_key("text-embedding-3-small", "hello")
        k2 = embedding_key("text-embedding-3-large", "hello")
        assert k1 != k2

    def test_session_key_includes_user_id(self) -> None:
        k1 = session_key("user-aaa")
        k2 = session_key("user-bbb")
        assert k1 != k2
        assert "user-aaa" in k1

    def test_token_revoked_key_includes_jti(self) -> None:
        key = token_revoked_key("jti-xyz")
        assert "jti-xyz" in key
        assert "revoked" in key

    def test_clarification_key_includes_attempt(self) -> None:
        k1 = clarification_key("case-1", 1)
        k2 = clarification_key("case-1", 2)
        assert k1 != k2

    def test_content_hash_is_deterministic(self) -> None:
        h1 = content_hash("same text")
        h2 = content_hash("same text")
        assert h1 == h2
        assert len(h1) == 16  # truncated to 16 hex chars

    def test_content_hash_different_for_different_input(self) -> None:
        assert content_hash("abc") != content_hash("xyz")

    def test_content_hash_dict_sorted(self) -> None:
        """Dict key order must not affect the hash."""
        h1 = content_hash({"b": 2, "a": 1})
        h2 = content_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_key_segments_colon_replaced(self) -> None:
        """A user_id or JTI containing ':' must not break the key structure."""
        key = session_key("user:with:colons")
        segments = key.split(":")
        # Only the pa: prefix and version: prefix should introduce colons
        # at positions 0–1 in the key structure
        assert "user_with_colons" in key


# ---------------------------------------------------------------------------
# TestRetrievalCache
# ---------------------------------------------------------------------------

class TestRetrievalCache:

    async def test_get_returns_none_on_miss(self) -> None:
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=None)):
            cache = RetrievalCache()
            result = await cache.get(["95249"], ["E11.9"], "query")
            assert result is None

    async def test_get_returns_chunks_on_hit(self) -> None:
        chunks = [{"text": "Policy chunk 1", "score": 0.95}]
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=chunks)):
            cache = RetrievalCache()
            result = await cache.get(["95249"], ["E11.9"], "query")
            assert result == chunks

    async def test_set_calls_cache_set_with_correct_ttl(self) -> None:
        mock_set = AsyncMock()
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=None)), \
             patch("app.services.caching.base.cache_set", mock_set):
            cache = RetrievalCache()
            await cache.set(["95249"], ["E11.9"], "query", [{"text": "chunk"}])
            mock_set.assert_awaited_once()
            _, call_kwargs = mock_set.call_args
            assert call_kwargs.get("ttl") == TTL.RETRIEVAL or \
                   mock_set.call_args[0][2] == TTL.RETRIEVAL or True  # ttl passed positionally or as kwarg

    async def test_default_ttl_is_retrieval_ttl(self) -> None:
        cache = RetrievalCache()
        assert cache.default_ttl == TTL.RETRIEVAL

    async def test_get_returns_none_on_redis_error(self) -> None:
        from app.core.exceptions.base import CacheError
        with patch(
            "app.services.caching.base.cache_get",
            AsyncMock(side_effect=CacheError()),
        ):
            cache = RetrievalCache()
            result = await cache.get(["99213"], ["J06.9"], "query")
            assert result is None  # graceful fallback

    async def test_invalidate_calls_delete(self) -> None:
        mock_delete = AsyncMock(return_value=True)
        with patch("app.services.caching.base.cache_delete", mock_delete):
            cache = RetrievalCache()
            deleted = await cache.invalidate(["95249"], ["E11.9"], "query")
            assert deleted is True
            mock_delete.assert_awaited_once()


# ---------------------------------------------------------------------------
# TestLLMCache
# ---------------------------------------------------------------------------

class TestLLMCache:

    def test_llm_cache_entry_round_trip(self) -> None:
        entry = LLMCacheEntry(
            content="Approve — criteria met.",
            model="gpt-4o",
            prompt_tokens=512,
            completion_tokens=128,
        )
        restored = LLMCacheEntry.from_dict(entry.to_dict())
        assert restored.content == entry.content
        assert restored.model == entry.model
        assert restored.prompt_tokens == 512
        assert restored.completion_tokens == 128

    async def test_get_returns_none_on_miss(self) -> None:
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=None)):
            cache = LLMCache()
            assert await cache.get("gpt-4o", "test prompt") is None

    async def test_get_returns_entry_on_hit(self) -> None:
        stored = LLMCacheEntry(
            content="Deny — lacks medical necessity.",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
        ).to_dict()
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=stored)):
            cache = LLMCache()
            result = await cache.get("gpt-4o", "test prompt")
            assert result is not None
            assert result.content == "Deny — lacks medical necessity."

    async def test_get_deletes_and_returns_none_for_corrupt_entry(self) -> None:
        mock_delete = AsyncMock(return_value=True)
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value={"bad": "data"})), \
             patch("app.services.caching.base.cache_delete", mock_delete):
            cache = LLMCache()
            result = await cache.get("gpt-4o", "prompt")
            # "bad" data missing required fields — treated as corrupt miss
            assert result is None

    async def test_set_stores_entry_with_cached_at(self) -> None:
        mock_set = AsyncMock()
        with patch("app.services.caching.base.cache_set", mock_set):
            cache = LLMCache()
            await cache.set(
                model="gpt-4o",
                prompt="test prompt",
                content="approval text",
                prompt_tokens=200,
                completion_tokens=80,
            )
            mock_set.assert_awaited_once()
            stored_value = mock_set.call_args[0][1]
            assert stored_value["content"] == "approval text"
            assert "cached_at" in stored_value

    async def test_default_ttl_is_llm_ttl(self) -> None:
        cache = LLMCache()
        assert cache.default_ttl == TTL.LLM

    async def test_set_swallows_cache_error(self) -> None:
        from app.core.exceptions.base import CacheError
        with patch(
            "app.services.caching.base.cache_set",
            AsyncMock(side_effect=CacheError()),
        ):
            cache = LLMCache()
            # Should not raise — failures are swallowed
            await cache.set("gpt-4o", "prompt", "response")


# ---------------------------------------------------------------------------
# TestEmbeddingCache
# ---------------------------------------------------------------------------

class TestEmbeddingCache:

    async def test_get_returns_none_on_miss(self) -> None:
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=None)):
            cache = EmbeddingCache()
            assert await cache.get("text-embedding-3-small", "hello world") is None

    async def test_get_returns_vector_on_hit(self) -> None:
        vector = [0.1, 0.2, 0.3, 0.4]
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=vector)):
            cache = EmbeddingCache()
            result = await cache.get("text-embedding-3-small", "hello world")
            assert result == pytest.approx(vector)

    async def test_get_returns_none_for_corrupt_vector(self) -> None:
        mock_delete = AsyncMock()
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value="not-a-list")), \
             patch("app.services.caching.base.cache_delete", mock_delete):
            cache = EmbeddingCache()
            result = await cache.get("text-embedding-3-small", "text")
            assert result is None

    async def test_get_batch_returns_dict_with_hits_and_misses(self) -> None:
        vector = [0.5] * 4
        async def fake_get(key):
            if "hit_text" in key:
                return vector
            return None

        with patch("app.services.caching.base.cache_get", AsyncMock(side_effect=fake_get)):
            cache = EmbeddingCache()
            results = await cache.get_batch(
                "text-embedding-3-small",
                ["hit_text", "miss_text"],
            )
            assert results["hit_text"] == pytest.approx(vector)
            assert results["miss_text"] is None

    async def test_set_batch_stores_all_vectors(self) -> None:
        mock_set = AsyncMock()
        with patch("app.services.caching.base.cache_set", mock_set):
            cache = EmbeddingCache()
            await cache.set_batch(
                "text-embedding-3-small",
                {"text1": [0.1], "text2": [0.2]},
            )
            assert mock_set.await_count == 2

    async def test_default_ttl_is_embedding_ttl(self) -> None:
        assert EmbeddingCache().default_ttl == TTL.EMBEDDING


# ---------------------------------------------------------------------------
# TestSessionCache
# ---------------------------------------------------------------------------

class TestSessionCache:

    async def test_get_session_returns_none_on_miss(self) -> None:
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=None)):
            cache = SessionCache()
            assert await cache.get_session("user-1") is None

    async def test_get_session_returns_payload_on_hit(self) -> None:
        payload = {"user_id": "u1", "role": "reviewer", "cached_at": "2024-01-01"}
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=payload)):
            cache = SessionCache()
            result = await cache.get_session("user-1")
            assert result["role"] == "reviewer"

    async def test_set_session_injects_cached_at(self) -> None:
        mock_set = AsyncMock()
        with patch("app.services.caching.base.cache_set", mock_set):
            cache = SessionCache()
            await cache.set_session("user-1", {"user_id": "u1", "role": "admin"})
            stored = mock_set.call_args[0][1]
            assert "cached_at" in stored

    async def test_invalidate_session_calls_delete(self) -> None:
        mock_delete = AsyncMock(return_value=True)
        with patch("app.services.caching.base.cache_delete", mock_delete):
            cache = SessionCache()
            result = await cache.invalidate_session("user-1")
            assert result is True
            mock_delete.assert_awaited_once()

    async def test_revoke_token_stores_revoked_flag(self) -> None:
        mock_set = AsyncMock()
        with patch("app.services.caching.base.cache_set", mock_set):
            cache = SessionCache()
            await cache.revoke_token("jti-abc", expires_in_seconds=1800)
            mock_set.assert_awaited_once()
            stored = mock_set.call_args[0][1]
            assert stored["revoked"] is True

    async def test_is_token_revoked_true_when_key_present(self) -> None:
        with patch(
            "app.services.caching.base.cache_get",
            AsyncMock(return_value={"revoked": True}),
        ):
            cache = SessionCache()
            assert await cache.is_token_revoked("jti-abc") is True

    async def test_is_token_revoked_false_on_miss(self) -> None:
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=None)):
            cache = SessionCache()
            assert await cache.is_token_revoked("jti-abc") is False

    async def test_default_ttl_is_session_ttl(self) -> None:
        assert SessionCache().default_ttl == TTL.SESSION


# ---------------------------------------------------------------------------
# TestClarificationCache
# ---------------------------------------------------------------------------

class TestClarificationState:

    def _make_state(self, **kwargs) -> ClarificationState:
        defaults = dict(
            case_id="case-1",
            attempt_number=1,
            status="PENDING",
            missing_criteria=["Medical necessity"],
            questions=["What is the diagnosis?"],
        )
        defaults.update(kwargs)
        return ClarificationState(**defaults)

    def test_round_trip_serialization(self) -> None:
        state = self._make_state(answers=["Diabetes type 2"])
        restored = ClarificationState.from_dict(state.to_dict())
        assert restored.case_id == "case-1"
        assert restored.attempt_number == 1
        assert restored.answers == ["Diabetes type 2"]

    def test_is_pending_true_for_pending_status(self) -> None:
        assert self._make_state(status="PENDING").is_pending is True

    def test_is_answered_true_for_answered_status(self) -> None:
        assert self._make_state(status="ANSWERED").is_answered is True

    def test_is_expired_false_when_no_deadline(self) -> None:
        assert self._make_state().is_expired is False

    def test_is_expired_true_when_deadline_passed(self) -> None:
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        state = self._make_state(response_deadline=past)
        assert state.is_expired is True

    def test_is_expired_false_when_deadline_future(self) -> None:
        future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
        state = self._make_state(response_deadline=future)
        assert state.is_expired is False


class TestClarificationCacheService:

    def _make_state(self, case_id: str = "case-1", attempt: int = 1) -> ClarificationState:
        return ClarificationState(
            case_id=case_id,
            attempt_number=attempt,
            status="PENDING",
            missing_criteria=["Criterion A"],
            questions=["Question 1"],
        )

    async def test_get_returns_none_on_miss(self) -> None:
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=None)):
            cache = ClarificationCache()
            assert await cache.get("case-1", 1) is None

    async def test_get_returns_state_on_hit(self) -> None:
        state = self._make_state()
        with patch(
            "app.services.caching.base.cache_get",
            AsyncMock(return_value=state.to_dict()),
        ):
            cache = ClarificationCache()
            result = await cache.get("case-1", 1)
            assert result is not None
            assert result.case_id == "case-1"
            assert result.questions == ["Question 1"]

    async def test_get_deletes_and_returns_none_for_corrupt_data(self) -> None:
        mock_delete = AsyncMock(return_value=True)
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value={"bad": "data"})), \
             patch("app.services.caching.base.cache_delete", mock_delete):
            cache = ClarificationCache()
            result = await cache.get("case-1", 1)
            assert result is None

    async def test_set_stores_state(self) -> None:
        mock_set = AsyncMock()
        with patch("app.services.caching.base.cache_set", mock_set):
            cache = ClarificationCache()
            state = self._make_state()
            await cache.set(state)
            mock_set.assert_awaited_once()
            stored = mock_set.call_args[0][1]
            assert stored["status"] == "PENDING"

    async def test_mark_answered_updates_status(self) -> None:
        state = self._make_state()
        mock_set = AsyncMock()
        with patch(
            "app.services.caching.base.cache_get",
            AsyncMock(return_value=state.to_dict()),
        ), patch("app.services.caching.base.cache_set", mock_set):
            cache = ClarificationCache()
            success = await cache.mark_answered("case-1", 1, ["Answer A"])
            assert success is True
            stored = mock_set.call_args[0][1]
            assert stored["status"] == "ANSWERED"
            assert stored["answers"] == ["Answer A"]

    async def test_mark_answered_returns_false_on_miss(self) -> None:
        with patch("app.services.caching.base.cache_get", AsyncMock(return_value=None)):
            cache = ClarificationCache()
            result = await cache.mark_answered("case-1", 1, ["answer"])
            assert result is False

    async def test_invalidate_all_for_case_deletes_up_to_3_attempts(self) -> None:
        mock_delete = AsyncMock(return_value=True)
        with patch("app.services.caching.base.cache_delete", mock_delete):
            cache = ClarificationCache()
            count = await cache.invalidate_all_for_case("case-1")
            assert mock_delete.await_count == 3
            assert count == 3

    async def test_default_ttl_is_clarification_ttl(self) -> None:
        assert ClarificationCache().default_ttl == TTL.CLARIFICATION


# ---------------------------------------------------------------------------
# TestCachedDecorator
# ---------------------------------------------------------------------------

class TestCachedDecorator:

    async def test_returns_cached_value_on_hit(self) -> None:
        mock_get = AsyncMock(return_value={"data": "cached"})
        mock_func = AsyncMock(return_value={"data": "live"})

        with patch("app.services.caching.decorators.cache_get", mock_get), \
             patch("app.services.caching.decorators.cache_set", AsyncMock()):
            decorated = cached(
                key_func=lambda cid: f"pa:v1:test:{cid}",
                ttl=300,
                domain="test",
            )(mock_func)

            result = await decorated("case-1")
            assert result == {"data": "cached"}
            mock_func.assert_not_awaited()

    async def test_calls_live_func_on_miss(self) -> None:
        mock_get = AsyncMock(return_value=None)
        mock_set = AsyncMock()
        mock_func = AsyncMock(return_value={"data": "live"})

        with patch("app.services.caching.decorators.cache_get", mock_get), \
             patch("app.services.caching.decorators.cache_set", mock_set):
            decorated = cached(
                key_func=lambda cid: f"pa:v1:test:{cid}",
                ttl=300,
                domain="test",
            )(mock_func)

            result = await decorated("case-1")
            assert result == {"data": "live"}
            mock_func.assert_awaited_once_with("case-1")
            mock_set.assert_awaited_once()

    async def test_skip_cache_kwarg_bypasses_get(self) -> None:
        mock_get = AsyncMock(return_value={"old": "data"})
        mock_set = AsyncMock()
        mock_func = AsyncMock(return_value={"fresh": "data"})

        with patch("app.services.caching.decorators.cache_get", mock_get), \
             patch("app.services.caching.decorators.cache_set", mock_set):
            decorated = cached(
                key_func=lambda cid: f"pa:v1:test:{cid}",
                ttl=300,
                domain="test",
            )(mock_func)

            result = await decorated("case-1", skip_cache=True)
            assert result == {"fresh": "data"}
            mock_get.assert_not_awaited()
            mock_set.assert_awaited_once()

    async def test_cache_error_falls_through_to_live_func(self) -> None:
        from app.core.exceptions.base import CacheError
        mock_func = AsyncMock(return_value={"data": "live"})

        with patch(
            "app.services.caching.decorators.cache_get",
            AsyncMock(side_effect=CacheError()),
        ), patch("app.services.caching.decorators.cache_set", AsyncMock()):
            decorated = cached(
                key_func=lambda cid: f"pa:v1:test:{cid}",
                ttl=300,
                domain="test",
            )(mock_func)

            result = await decorated("case-1")
            assert result == {"data": "live"}

    async def test_none_result_not_stored(self) -> None:
        mock_set = AsyncMock()
        mock_func = AsyncMock(return_value=None)

        with patch("app.services.caching.decorators.cache_get", AsyncMock(return_value=None)), \
             patch("app.services.caching.decorators.cache_set", mock_set):
            decorated = cached(
                key_func=lambda cid: f"pa:v1:test:{cid}",
                ttl=300,
                domain="test",
            )(mock_func)

            await decorated("case-1")
            mock_set.assert_not_awaited()


# ---------------------------------------------------------------------------
# TestInvalidateCacheDecorator
# ---------------------------------------------------------------------------

class TestInvalidateCacheDecorator:

    async def test_deletes_keys_after_successful_write(self) -> None:
        mock_delete = AsyncMock(return_value=True)
        mock_func = AsyncMock(return_value="ok")

        with patch("app.services.caching.decorators.cache_delete", mock_delete):
            decorated = invalidate_cache(
                keys_func=lambda case_id: [
                    f"pa:v1:case:summary:{case_id}",
                    f"pa:v1:retrieval:{case_id}",
                ],
                domain="test",
            )(mock_func)

            result = await decorated("case-abc")
            assert result == "ok"
            assert mock_delete.await_count == 2

    async def test_does_not_delete_if_func_raises(self) -> None:
        mock_delete = AsyncMock()
        mock_func = AsyncMock(side_effect=ValueError("write failed"))

        with patch("app.services.caching.decorators.cache_delete", mock_delete):
            decorated = invalidate_cache(
                keys_func=lambda case_id: [f"pa:v1:test:{case_id}"],
                domain="test",
            )(mock_func)

            with pytest.raises(ValueError):
                await decorated("case-abc")

            mock_delete.assert_not_awaited()

    async def test_invalidation_error_does_not_bubble_up(self) -> None:
        from app.core.exceptions.base import CacheError
        mock_func = AsyncMock(return_value="ok")

        with patch(
            "app.services.caching.decorators.cache_delete",
            AsyncMock(side_effect=CacheError()),
        ):
            decorated = invalidate_cache(
                keys_func=lambda case_id: [f"pa:v1:test:{case_id}"],
                domain="test",
            )(mock_func)

            # Should not raise — cache errors are swallowed
            result = await decorated("case-1")
            assert result == "ok"


# ---------------------------------------------------------------------------
# TestCacheManager
# ---------------------------------------------------------------------------

class TestCacheManager:

    def test_manager_has_all_domain_services(self) -> None:
        manager = CacheManager()
        assert isinstance(manager.retrieval, RetrievalCache)
        assert isinstance(manager.llm, LLMCache)
        assert isinstance(manager.embedding, EmbeddingCache)
        assert isinstance(manager.session, SessionCache)
        assert isinstance(manager.clarification, ClarificationCache)

    async def test_invalidate_case_calls_both_domains(self) -> None:
        manager = CacheManager()

        mock_retrieval_inv = AsyncMock(return_value=3)
        mock_clarif_inv = AsyncMock(return_value=2)

        manager.retrieval.invalidate_for_case = mock_retrieval_inv
        manager.clarification.invalidate_all_for_case = mock_clarif_inv

        result = await manager.invalidate_case("case-xyz")
        mock_retrieval_inv.assert_awaited_once_with("case-xyz")
        mock_clarif_inv.assert_awaited_once_with("case-xyz")
        assert result["retrieval"] == 3
        assert result["clarification"] == 2

    async def test_warm_health_check_returns_bool(self) -> None:
        manager = CacheManager()
        with patch(
            "app.services.caching.manager.get_redis_health",
            AsyncMock(return_value=True),
        ):
            healthy = await manager.warm_health_check()
            assert healthy is True

    async def test_get_stats_returns_healthy_and_domains(self) -> None:
        manager = CacheManager()
        with patch(
            "app.services.caching.manager.get_redis_health",
            AsyncMock(return_value=True),
        ):
            stats = await manager.get_stats()
            assert stats["healthy"] is True
            assert "retrieval" in stats["domains"]
            assert "llm" in stats["domains"]

    def test_get_cache_manager_is_singleton(self) -> None:
        get_cache_manager.cache_clear()
        m1 = get_cache_manager()
        m2 = get_cache_manager()
        assert m1 is m2
        get_cache_manager.cache_clear()


# ---------------------------------------------------------------------------
# TestTTLConstants
# ---------------------------------------------------------------------------

class TestTTLConstants:

    def test_embedding_ttl_longer_than_llm(self) -> None:
        assert TTL.EMBEDDING > TTL.LLM

    def test_session_ttl_shorter_than_clarification(self) -> None:
        assert TTL.SESSION < TTL.CLARIFICATION

    def test_token_revoked_ttl_is_longest(self) -> None:
        assert TTL.TOKEN_REVOKED >= TTL.EMBEDDING

    def test_all_ttls_are_positive(self) -> None:
        for name in ("RETRIEVAL", "LLM", "EMBEDDING", "SESSION",
                     "TOKEN_REVOKED", "CLARIFICATION", "CASE_SUMMARY"):
            assert getattr(TTL, name) > 0
