"""persist RAG citations for assistant messages

Revision ID: 0004_create_message_citations
Revises: 0003_knowledge_vector_tables
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_create_message_citations"
down_revision: str | None = "0003_knowledge_vector_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_citations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=16), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_message_citations_score"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["knowledge_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id", "chunk_id", name="uq_message_citations_message_chunk"
        ),
    )
    op.create_index(
        "ix_message_citations_message_ordinal",
        "message_citations",
        ["message_id", "ordinal"],
    )


def downgrade() -> None:
    op.drop_index("ix_message_citations_message_ordinal", table_name="message_citations")
    op.drop_table("message_citations")
