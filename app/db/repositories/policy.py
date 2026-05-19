"""Policy repositories (PolicyDocument + PolicyChunk)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.policy import PolicyChunk, PolicyDocument


class PolicyRepository(BaseRepository[PolicyDocument]):
    model = PolicyDocument

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_key(self, policy_key: str) -> PolicyDocument | None:
        stmt = select(PolicyDocument).where(
            PolicyDocument.policy_key == policy_key,
            PolicyDocument.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_policies(
        self,
        *,
        search: str | None = None,
        status: object | None = None,
        namespace: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PolicyDocument], int]:
        stmt = select(PolicyDocument).where(PolicyDocument.deleted_at.is_(None))

        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(
                (PolicyDocument.policy_name.ilike(like))
                | (PolicyDocument.policy_key.ilike(like))
                | (PolicyDocument.original_filename.ilike(like))
            )

        if status:
            stmt = stmt.where(PolicyDocument.processing_status == status)
        if namespace:
            stmt = stmt.where(PolicyDocument.pinecone_namespace == namespace)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(total_stmt)).scalar_one()

        stmt = stmt.order_by(PolicyDocument.created_at.desc()).offset(offset).limit(min(limit, 100))
        result = await self.session.execute(stmt)
        return (list(result.scalars().all()), int(total))


class PolicyChunkRepository(BaseRepository[PolicyChunk]):
    model = PolicyChunk

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_chunks(
        self,
        *,
        policy_document_id: str,
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[list[PolicyChunk], int]:
        base = (
            select(PolicyChunk)
            .where(
                PolicyChunk.policy_document_id == policy_document_id,
                PolicyChunk.deleted_at.is_(None),
            )
        )
        total_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            base.order_by(PolicyChunk.chunk_index.asc())
            .offset(offset)
            .limit(min(limit, 500))
        )
        result = await self.session.execute(stmt)
        return (list(result.scalars().all()), int(total))

    async def get_vector_ids(self, policy_document_id: str) -> list[str]:
        stmt = select(PolicyChunk.pinecone_vector_id).where(
            PolicyChunk.policy_document_id == policy_document_id,
            PolicyChunk.deleted_at.is_(None),
            PolicyChunk.pinecone_vector_id.is_not(None),
        )
        result = await self.session.execute(stmt)
        return [r[0] for r in result.all() if r[0]]

    async def hard_delete_for_policy(self, policy_document_id: str) -> int:
        chunks, _ = await self.list_chunks(policy_document_id=policy_document_id, offset=0, limit=500)
        deleted = 0
        for c in chunks:
            ok = await self.hard_delete(c.id)
            deleted += 1 if ok else 0
        return deleted
