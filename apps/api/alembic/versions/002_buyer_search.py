from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buyer_searches",
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), primary_key=True),
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("buyers_json", sa.Text),
        sa.Column("sources_json", sa.Text),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message_fa", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("buyer_searches")
