"""Allow one active recommendation configuration per tenant."""

from alembic import op

revision = "20261107_0021"
down_revision = "20261107_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS capricho.uq_config_recomendador_activa")
    op.execute("""
        CREATE UNIQUE INDEX uq_config_recomendador_activa
        ON capricho.configuracion_recomendador (id_tenant)
        WHERE activo = TRUE
    """)


def downgrade() -> None:
    raise RuntimeError("El índice global no admite múltiples empresas; restaura un respaldo")
