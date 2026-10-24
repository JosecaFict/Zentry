"""Scope catalog identities to each tenant.

Revision ID: 20261024_0014
Revises: 20261024_0013
"""

from alembic import op

revision = "20261024_0014"
down_revision = "20261024_0013"
branch_labels = None
depends_on = None

SCHEMA = "capricho"


def upgrade() -> None:
    for constraint, table in (
        ("categoria_nombre_key", "categoria"),
        ("marca_nombre_key", "marca"),
        ("talla_codigo_key", "talla"),
        ("talla_orden_key", "talla"),
        ("color_nombre_key", "color"),
    ):
        op.execute(f"ALTER TABLE {SCHEMA}.{table} DROP CONSTRAINT IF EXISTS {constraint}")
    op.execute(
        "ALTER TABLE capricho.sucursal DROP CONSTRAINT IF EXISTS sucursal_id_ciudad_nombre_key"
    )

    op.execute("ALTER TABLE capricho.talla DROP CONSTRAINT IF EXISTS talla_codigo_check")
    op.create_check_constraint(
        "talla_codigo_check",
        "talla",
        "codigo IN ('XS','S','M','L','XL','XXL')",
        schema=SCHEMA,
    )
    op.create_unique_constraint(
        "uq_categoria_tenant_nombre", "categoria", ["id_tenant", "nombre"], schema=SCHEMA
    )
    op.create_unique_constraint(
        "uq_marca_tenant_nombre", "marca", ["id_tenant", "nombre"], schema=SCHEMA
    )
    op.create_unique_constraint(
        "uq_talla_tenant_codigo", "talla", ["id_tenant", "codigo"], schema=SCHEMA
    )
    op.create_unique_constraint(
        "uq_talla_tenant_orden", "talla", ["id_tenant", "orden"], schema=SCHEMA
    )
    op.create_unique_constraint(
        "uq_color_tenant_nombre", "color", ["id_tenant", "nombre"], schema=SCHEMA
    )
    op.create_unique_constraint(
        "uq_sucursal_tenant_ciudad_nombre",
        "sucursal",
        ["id_tenant", "id_ciudad", "nombre"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError("Catalog tenant identities cannot be safely reverted with multiple tenants")
