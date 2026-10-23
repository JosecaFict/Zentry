"""Support tenant provisioning and tenant-scoped role names.

Revision ID: 20261021_0007
Revises: 20261021_0006
"""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0007"
down_revision = "20261021_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("razon_social", sa.String(180)), schema="capricho")
    op.add_column("tenant", sa.Column("nit", sa.String(40)), schema="capricho")
    op.add_column("tenant", sa.Column("correo_contacto", sa.String(150)), schema="capricho")
    op.add_column("tenant", sa.Column("telefono_contacto", sa.String(30)), schema="capricho")
    op.create_index(
        "uq_tenant_nit",
        "tenant",
        ["nit"],
        unique=True,
        schema="capricho",
        postgresql_where=sa.text("nit IS NOT NULL"),
    )

    op.execute("ALTER TABLE capricho.rol DROP CONSTRAINT IF EXISTS uq_rol_nombre")
    op.execute("ALTER TABLE capricho.rol DROP CONSTRAINT IF EXISTS rol_nombre_key")
    op.create_index(
        "uq_rol_global_nombre",
        "rol",
        ["nombre"],
        unique=True,
        schema="capricho",
        postgresql_where=sa.text("id_tenant IS NULL"),
    )
    op.create_index(
        "uq_rol_tenant_nombre",
        "rol",
        ["id_tenant", "nombre"],
        unique=True,
        schema="capricho",
        postgresql_where=sa.text("id_tenant IS NOT NULL"),
    )


def downgrade() -> None:
    raise RuntimeError(
        "Tenant provisioning downgrade can remove company identity data; restore a backup instead"
    )
