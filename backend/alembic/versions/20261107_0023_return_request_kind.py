"""Record what the customer requests when returning a garment."""

import sqlalchemy as sa
from alembic import op

revision = "20261107_0023"
down_revision = "20261107_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devolucion",
        sa.Column(
            "tipo_solicitud",
            sa.String(length=20),
            nullable=False,
            server_default="DEVOLUCION",
        ),
        schema="capricho",
    )


def downgrade() -> None:
    op.drop_column("devolucion", "tipo_solicitud", schema="capricho")
