"""Add tenant brand colors.

Revision ID: 20261022_0008
Revises: 20261021_0007
"""

import sqlalchemy as sa

from alembic import op

revision = "20261022_0008"
down_revision = "20261021_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("color_primario", sa.String(7), nullable=False, server_default="#064FE8"),
        schema="capricho",
    )
    op.add_column(
        "tenant",
        sa.Column("color_primario_oscuro", sa.String(7), nullable=False, server_default="#0039B8"),
        schema="capricho",
    )
    op.create_check_constraint(
        "tenant_color_primario_check",
        "tenant",
        "color_primario ~ '^#[0-9A-Fa-f]{6}$'",
        schema="capricho",
    )
    op.create_check_constraint(
        "tenant_color_primario_oscuro_check",
        "tenant",
        "color_primario_oscuro ~ '^#[0-9A-Fa-f]{6}$'",
        schema="capricho",
    )


def downgrade() -> None:
    op.drop_constraint(
        "tenant_color_primario_oscuro_check", "tenant", schema="capricho", type_="check"
    )
    op.drop_constraint("tenant_color_primario_check", "tenant", schema="capricho", type_="check")
    op.drop_column("tenant", "color_primario_oscuro", schema="capricho")
    op.drop_column("tenant", "color_primario", schema="capricho")
