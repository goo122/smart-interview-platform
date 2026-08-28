"""create conversations and messages

Revision ID: 0002_chat_conversations_messages
Revises: 0001_create_users
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_chat_conversations_messages"
down_revision: str | None = "0001_create_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="ACTIVE"
        ),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversations_user_updated_at",
        "conversations",
        ["user_id", "updated_at"],
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="COMPLETED"
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "sequence", name="uq_messages_conversation_sequence"
        ),
    )
    op.create_index(
        "ix_messages_conversation_sequence",
        "messages",
        ["conversation_id", "sequence"],
    )
    op.create_index(
        "ix_messages_conversation_request_id",
        "messages",
        ["conversation_id", "request_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_request_id", table_name="messages")
    op.drop_index("ix_messages_conversation_sequence", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_user_updated_at", table_name="conversations")
    op.drop_table("conversations")
