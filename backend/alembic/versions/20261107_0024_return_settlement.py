"""Keep the inspection, stock notes and settlement receipt with each return."""

import sqlalchemy as sa
from alembic import op

revision = "20261107_0024"
down_revision = "20261107_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devolucion", sa.Column("cierre", sa.JSON(), nullable=True), schema="capricho")


def downgrade() -> None:
    op.drop_column("devolucion", "cierre", schema="capricho")
