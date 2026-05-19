"""initial schema: call_sessions and call_messages

Revision ID: 12f7e9ab8c9f
Revises:
Create Date: 2026-05-19 22:07:39.296719

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "12f7e9ab8c9f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema from scratch."""
    op.create_table(
        "call_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("caller_number", sa.String(length=32), nullable=False),
        sa.Column("livekit_room", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ringing"),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="greeting"),
        sa.Column("caller_name", sa.String(length=128), nullable=True),
        sa.Column("hubspot_contact_id", sa.String(length=64), nullable=True),
        sa.Column("hubspot_deal_id", sa.String(length=64), nullable=True),
        sa.Column("calcom_booking_uid", sa.String(length=128), nullable=True),
        sa.Column("lead_score", sa.String(length=16), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "call_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["call_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("call_messages")
    op.drop_table("call_sessions")
