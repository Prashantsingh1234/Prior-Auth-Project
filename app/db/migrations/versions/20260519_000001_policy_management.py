"""Policy management tables.

Revision ID: 20260519_000001
Revises: 20240101_000000
Create Date: 2026-05-19 00:00:01.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers
revision: str = "20260519_000001"
down_revision: str | None = "20240101_000000"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())

    if "policy_documents" not in existing:
        op.create_table(
            "policy_documents",
            sa.Column("id", mysql.CHAR(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),

            sa.Column("policy_key", sa.String(120), nullable=False),
            sa.Column("policy_name", sa.String(500), nullable=False),
            sa.Column("policy_version", sa.String(50), nullable=False, server_default="v1"),
            sa.Column("policy_type", sa.String(100), nullable=True),
            sa.Column("effective_date", sa.Date, nullable=True),

            sa.Column("original_filename", sa.String(500), nullable=False),
            sa.Column("storage_path", sa.String(1000), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=True),
            sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
            sa.Column("checksum_sha256", sa.String(64), nullable=True),

            sa.Column("extracted_text", mysql.LONGTEXT, nullable=True),
            sa.Column("extraction_warnings", sa.JSON, nullable=True),

            sa.Column(
                "processing_status",
                sa.Enum("UPLOADED", "EXTRACTED", "CHUNKED", "EMBEDDED", "STORED", "FAILED", name="policyprocessingstatus"),
                nullable=False,
                server_default="UPLOADED",
            ),
            sa.Column(
                "embedding_status",
                sa.Enum("NONE", "STORED", "DELETED", name="policyembeddingstatus"),
                nullable=False,
                server_default="NONE",
            ),
            sa.Column("pinecone_namespace", sa.String(100), nullable=False),
            sa.Column("total_chunks", sa.Integer, nullable=False, server_default="0"),
            sa.Column("last_processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text, nullable=True),

            sa.UniqueConstraint("policy_key", name="uq_policy_documents_policy_key"),
        )
        op.create_index("ix_policy_documents_policy_key", "policy_documents", ["policy_key"])
        op.create_index("ix_policy_documents_status", "policy_documents", ["processing_status"])
        op.create_index("ix_policy_documents_embedding", "policy_documents", ["embedding_status"])
        op.create_index("ix_policy_documents_checksum", "policy_documents", ["checksum_sha256"])
        op.create_index("ix_policy_documents_deleted_at", "policy_documents", ["deleted_at"])

    if "policy_chunks" not in existing:
        op.create_table(
            "policy_chunks",
            sa.Column("id", mysql.CHAR(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),

            sa.Column("policy_document_id", mysql.CHAR(36), nullable=False),
            sa.Column("chunk_index", sa.Integer, nullable=False),
            sa.Column("chunk_text", mysql.LONGTEXT, nullable=False),
            sa.Column("chunk_length", sa.Integer, nullable=False),
            sa.Column("chunk_overlap", sa.Integer, nullable=False, server_default="0"),
            sa.Column("cpt_codes", sa.JSON, nullable=True),
            sa.Column("icd_codes", sa.JSON, nullable=True),
            sa.Column("metadata", sa.JSON, nullable=True),
            sa.Column("pinecone_vector_id", sa.String(200), nullable=True),
            sa.Column("chunk_hash", sa.String(64), nullable=True),

            sa.ForeignKeyConstraint(
                ["policy_document_id"],
                ["policy_documents.id"],
                ondelete="CASCADE",
            ),
        )
        op.create_index("ix_policy_chunks_policy_id", "policy_chunks", ["policy_document_id"])
        op.create_index("ix_policy_chunks_policy_index", "policy_chunks", ["policy_document_id", "chunk_index"])
        op.create_index("ix_policy_chunks_vector_id", "policy_chunks", ["pinecone_vector_id"])
        op.create_index("ix_policy_chunks_hash", "policy_chunks", ["chunk_hash"])
        op.create_index("ix_policy_chunks_deleted_at", "policy_chunks", ["deleted_at"])


def downgrade() -> None:
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())

    if "policy_chunks" in existing:
        op.drop_index("ix_policy_chunks_deleted_at", table_name="policy_chunks")
        op.drop_index("ix_policy_chunks_hash", table_name="policy_chunks")
        op.drop_index("ix_policy_chunks_vector_id", table_name="policy_chunks")
        op.drop_index("ix_policy_chunks_policy_index", table_name="policy_chunks")
        op.drop_index("ix_policy_chunks_policy_id", table_name="policy_chunks")
        op.drop_table("policy_chunks")

    if "policy_documents" in existing:
        op.drop_index("ix_policy_documents_deleted_at", table_name="policy_documents")
        op.drop_index("ix_policy_documents_checksum", table_name="policy_documents")
        op.drop_index("ix_policy_documents_embedding", table_name="policy_documents")
        op.drop_index("ix_policy_documents_status", table_name="policy_documents")
        op.drop_index("ix_policy_documents_policy_key", table_name="policy_documents")
        op.drop_table("policy_documents")

    # Enums may be left behind in some MySQL configurations; keep downgrade safe.
