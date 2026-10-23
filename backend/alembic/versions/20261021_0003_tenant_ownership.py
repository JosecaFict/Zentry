"""Assign tenant ownership to business root entities.

Revision ID: 20261021_0003
Revises: 20261021_0002
"""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0003"
down_revision = "20261021_0002"
branch_labels = None
depends_on = None

SCHEMA = "capricho"
REQUIRED_ROOTS = (
    "sucursal", "cliente", "empleado", "categoria", "marca", "talla",
    "color", "temporada", "coleccion", "producto", "proveedor",
    "promocion", "campania", "configuracion_recomendador",
)
OPTIONAL_ROOTS = ("usuario", "rol", "bitacora")


def upgrade() -> None:
    connection = op.get_bind()
    tenant_id = connection.execute(
        sa.text("SELECT id_tenant FROM capricho.tenant WHERE slug = 'capricho-store'")
    ).scalar_one()

    op.execute(
        """
        CREATE FUNCTION capricho.fn_tenant_actual() RETURNS BIGINT
        LANGUAGE plpgsql STABLE AS $$
        DECLARE
          configured TEXT;
          resolved BIGINT;
        BEGIN
          configured := NULLIF(current_setting('app.tenant_id', true), '');
          IF configured IS NOT NULL THEN
            RETURN configured::BIGINT;
          END IF;
          SELECT min(id_tenant) INTO resolved FROM capricho.tenant WHERE estado = 'ACTIVO';
          IF resolved IS NOT NULL AND (SELECT count(*) FROM capricho.tenant WHERE estado = 'ACTIVO') = 1 THEN
            RETURN resolved;
          END IF;
          RAISE EXCEPTION 'tenant context is required' USING ERRCODE = '42501';
        END;
        $$
        """
    )

    for table in (*REQUIRED_ROOTS, *OPTIONAL_ROOTS):
        op.add_column(
            table,
            sa.Column(
                "id_tenant",
                sa.BigInteger(),
                server_default=sa.text("capricho.fn_tenant_actual()"),
                nullable=True,
            ),
            schema=SCHEMA,
        )
        connection.execute(
            sa.text(f"UPDATE capricho.{table} SET id_tenant = :tenant_id"),
            {"tenant_id": tenant_id},
        )
        if table in REQUIRED_ROOTS:
            op.alter_column(table, "id_tenant", nullable=False, schema=SCHEMA)
        op.create_foreign_key(
            f"fk_{table}_tenant",
            table,
            "tenant",
            ["id_tenant"],
            ["id_tenant"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete="RESTRICT",
        )
        op.create_index(f"ix_{table}_tenant", table, ["id_tenant"], schema=SCHEMA)

    op.add_column(
        "rol",
        sa.Column("alcance", sa.String(10), server_default="TENANT", nullable=False),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_rol_alcance",
        "rol",
        "(alcance = 'TENANT' AND id_tenant IS NOT NULL) OR "
        "(alcance = 'GLOBAL' AND id_tenant IS NULL)",
        schema=SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError(
        "Tenant ownership downgrade would discard ownership; restore a verified backup instead"
    )
