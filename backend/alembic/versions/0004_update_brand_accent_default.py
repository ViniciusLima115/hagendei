"""update default brand accent

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "estabelecimentos",
        "accent_color",
        existing_type=sa.String(length=7),
        existing_nullable=False,
        server_default="#1e3a5f",
    )


def downgrade() -> None:
    op.alter_column(
        "estabelecimentos",
        "accent_color",
        existing_type=sa.String(length=7),
        existing_nullable=False,
        server_default="#d4930a",
    )
