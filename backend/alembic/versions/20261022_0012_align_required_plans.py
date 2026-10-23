"""Align subscription plans with the academic specification.

Revision ID: 20261022_0012
Revises: 20261022_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261022_0012"
down_revision: str | None = "20261022_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "capricho"


def upgrade() -> None:
    op.add_column(
        "plan",
        sa.Column(
            "permite_reportes_convencionales",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        schema=SCHEMA,
    )
    op.execute(
        """
        UPDATE capricho.plan
        SET codigo = 'BASICO',
            nombre = 'Básico',
            max_sucursales_activas = 2,
            permite_offline = TRUE,
            permite_reportes_convencionales = TRUE,
            permite_reportes_ia = FALSE
        WHERE codigo IN ('BASICO', 'GESTION')
        """
    )
    op.execute(
        """
        UPDATE capricho.plan
        SET codigo = 'PROFESIONAL',
            nombre = 'Profesional',
            max_sucursales_activas = 10,
            permite_offline = TRUE,
            permite_reportes_convencionales = TRUE,
            permite_reportes_ia = TRUE
        WHERE codigo IN ('PROFESIONAL', 'CRECIMIENTO')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE capricho.plan
        SET codigo = CASE codigo WHEN 'BASICO' THEN 'GESTION' ELSE 'CRECIMIENTO' END,
            nombre = CASE codigo WHEN 'BASICO' THEN 'Gestión' ELSE 'Crecimiento' END,
            max_sucursales_activas = CASE codigo WHEN 'BASICO' THEN 1 ELSE 5 END
        WHERE codigo IN ('BASICO', 'PROFESIONAL')
        """
    )
    op.drop_column("plan", "permite_reportes_convencionales", schema=SCHEMA)
