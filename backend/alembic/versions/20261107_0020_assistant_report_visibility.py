"""Mark report-derived assistant messages for plan-aware access."""

from alembic import op

revision = "20261107_0020"
down_revision = "20261106_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE capricho.asistente_mensaje
        ADD COLUMN requiere_reportes_ia BOOLEAN NOT NULL DEFAULT FALSE;
    """)
    op.execute("""
        UPDATE capricho.asistente_mensaje m
           SET requiere_reportes_ia = TRUE
          FROM capricho.asistente_conversacion c
         WHERE m.id_conversacion = c.id_conversacion
           AND c.modo = 'EMPRESA' AND m.rol = 'ASISTENTE';
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE capricho.asistente_mensaje DROP COLUMN requiere_reportes_ia")
