"""claim provenance: product, period, source url

Revision ID: 004
Revises: 003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("claims") as batch:
        batch.add_column(sa.Column("product_scope", sa.String(256), nullable=True))
        batch.add_column(sa.Column("period", sa.String(64), nullable=True))
        batch.add_column(sa.Column("source_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("claims") as batch:
        batch.drop_column("source_url")
        batch.drop_column("period")
        batch.drop_column("product_scope")
