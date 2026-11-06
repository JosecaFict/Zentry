"""Finalize legacy schema updates previously applied during startup.

Revision ID: 20261106_0017
Revises: 20261101_0016
"""

from alembic import op

revision = "20261106_0017"
down_revision = "20261101_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE capricho.usuario
        ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500);
        """
    )
    op.execute(
        """
        ALTER TABLE capricho.notificacion
        DROP CONSTRAINT IF EXISTS notificacion_estado_check;
        """
    )
    op.execute(
        """
        ALTER TABLE capricho.notificacion
        ADD CONSTRAINT notificacion_estado_check
        CHECK (
          estado IN (
            'PENDIENTE', 'ENVIANDO', 'ENVIADO', 'ENTREGADO',
            'ERROR', 'LEIDO', 'ACTIVO', 'FALLIDO'
          )
        );
        """
    )


def downgrade() -> None:
    # avatar_url may contain user data and the previous state constraint varied
    # between legacy installations, so a downgrade intentionally preserves both.
    pass
