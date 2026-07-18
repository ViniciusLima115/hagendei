"""mfa tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_mfa_settings",
        sa.Column("admin_username", sa.String(120), primary_key=True),
        sa.Column("secret_encrypted", sa.Text(), nullable=True),
        sa.Column("pending_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("recovery_code_hashes", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "admin_mfa_challenges",
        sa.Column("challenge_hash", sa.String(64), primary_key=True),
        sa.Column("admin_username", sa.String(120), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_admin_mfa_challenges_expires_at", "admin_mfa_challenges", ["expires_at"])
    op.create_index("ix_admin_mfa_challenges_admin_username", "admin_mfa_challenges", ["admin_username"])


def downgrade() -> None:
    op.drop_table("admin_mfa_challenges")
    op.drop_table("admin_mfa_settings")
