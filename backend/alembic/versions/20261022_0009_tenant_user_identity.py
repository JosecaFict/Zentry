"""Scope user email and CI uniqueness by tenant.

Revision ID: 20261022_0009
Revises: 20261022_0008
"""

from alembic import op

revision = "20261022_0009"
down_revision = "20261022_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE capricho.usuario DROP CONSTRAINT IF EXISTS usuario_correo_key")
    op.execute("ALTER TABLE capricho.usuario DROP CONSTRAINT IF EXISTS usuario_ci_key")
    op.execute("DROP INDEX IF EXISTS capricho.uq_usuario_correo_lower")
    op.execute("DROP INDEX IF EXISTS capricho.idx_usuario_correo_lower")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_usuario_tenant_correo
        ON capricho.usuario (id_tenant, lower(btrim(correo)))
        WHERE id_tenant IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_usuario_global_correo
        ON capricho.usuario (lower(btrim(correo)))
        WHERE id_tenant IS NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_usuario_tenant_ci
        ON capricho.usuario (id_tenant, btrim(ci))
        WHERE id_tenant IS NOT NULL AND ci IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_usuario_global_ci
        ON capricho.usuario (btrim(ci))
        WHERE id_tenant IS NULL AND ci IS NOT NULL
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Tenant-scoped identities can contain duplicate emails across companies; "
        "restore a backup instead"
    )
