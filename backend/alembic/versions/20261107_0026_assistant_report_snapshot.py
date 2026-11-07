"""Retain the exact report behind an assistant message for PDF/Excel exports."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "20261107_0026"
down_revision = "20261107_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("asistente_mensaje", sa.Column("reporte_snapshot", JSONB(), nullable=True), schema="capricho")


def downgrade() -> None:
    op.drop_column("asistente_mensaje", "reporte_snapshot", schema="capricho")
