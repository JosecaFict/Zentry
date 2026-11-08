"""Add the Empresarial subscription plan."""

from alembic import op

revision = "20261108_0028"
down_revision = "20261107_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO capricho.plan (
            codigo, nombre, max_sucursales_activas, max_usuarios_internos,
            max_productos_activos, almacenamiento_mb, precio_mensual, precio_anual,
            permite_reportes_convencionales, permite_reportes_ia, permite_offline, activo
        ) VALUES ('EMPRESARIAL', 'Empresarial', 25, 100, 50000, 102400, 1200, 14400,
                  TRUE, TRUE, TRUE, TRUE)
    """)


def downgrade() -> None:
    op.execute("DELETE FROM capricho.plan WHERE codigo = 'EMPRESARIAL'")
