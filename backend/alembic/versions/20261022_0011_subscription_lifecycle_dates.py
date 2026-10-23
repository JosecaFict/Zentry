"""Normalize legacy subscription dates for automated lifecycle processing.

Revision ID: 20261022_0011
Revises: 20261022_0010
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261022_0011"
down_revision: str | None = "20261022_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "capricho"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE {SCHEMA}.subscription
        SET fecha_fin = COALESCE(proxima_renovacion - 1, fecha_inicio + 29)
        WHERE fecha_fin IS NULL
          AND proxima_renovacion IS NOT NULL
        """
    )
    op.execute(
        f"""
        UPDATE {SCHEMA}.subscription
        SET proxima_renovacion = fecha_fin + 1,
            fecha_fin_gracia = fecha_fin + 7,
            estado = CASE
                WHEN CURRENT_DATE > fecha_fin + 7 THEN 'SUSPENDIDA'
                WHEN CURRENT_DATE > fecha_fin THEN 'GRACIA'
                WHEN CURRENT_DATE >= fecha_fin - 6 THEN 'POR_VENCER'
                ELSE 'ACTIVA'
            END
        WHERE estado IN ('ACTIVA', 'POR_VENCER', 'GRACIA', 'SUSPENDIDA')
          AND fecha_fin IS NOT NULL
        """
    )


def downgrade() -> None:
    # The dates are valid commercial history and must not be erased on downgrade.
    pass
