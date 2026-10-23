"""Prevent cross-tenant references in tenant-owned aggregates.

Revision ID: 20261021_0005
Revises: 20261021_0004
"""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0005"
down_revision = "20261021_0004"
branch_labels = None
depends_on = None

SCHEMA = "capricho"

# table: primary key used by tenant-aware foreign keys
TENANT_PARENTS = {
    "usuario": "id_usuario",
    "sucursal": "id_sucursal",
    "cliente": "id_cliente",
    "empleado": "id_empleado",
    "categoria": "id_categoria",
    "marca": "id_marca",
    "temporada": "id_temporada",
    "producto": "id_producto",
    "proveedor": "id_proveedor",
    "carrito": "id_carrito",
    "reserva": "id_reserva",
    "venta": "id_venta",
    "orden_compra": "id_orden_compra",
    "recepcion_mercaderia": "id_recepcion",
    "inventario_sucursal": "id_inventario",
}

# child, child FK, parent, parent PK, original ON DELETE behavior
TENANT_REFERENCES = (
    ("cliente", "id_usuario", "usuario", "id_usuario", "RESTRICT"),
    ("empleado", "id_usuario", "usuario", "id_usuario", "RESTRICT"),
    ("empleado", "id_sucursal", "sucursal", "id_sucursal", "RESTRICT"),
    ("coleccion", "id_temporada", "temporada", "id_temporada", "SET NULL"),
    ("producto", "id_categoria", "categoria", "id_categoria", "RESTRICT"),
    ("producto", "id_marca", "marca", "id_marca", "RESTRICT"),
    ("carrito", "id_cliente", "cliente", "id_cliente", "CASCADE"),
    ("carrito", "id_sucursal", "sucursal", "id_sucursal", "SET NULL"),
    ("reserva", "id_cliente", "cliente", "id_cliente", "RESTRICT"),
    ("reserva", "id_sucursal", "sucursal", "id_sucursal", "RESTRICT"),
    ("venta", "id_cliente", "cliente", "id_cliente", "SET NULL"),
    ("venta", "id_sucursal", "sucursal", "id_sucursal", "RESTRICT"),
    ("venta", "id_empleado", "empleado", "id_empleado", "SET NULL"),
    ("venta", "id_reserva", "reserva", "id_reserva", "SET NULL"),
    ("orden_compra", "id_proveedor", "proveedor", "id_proveedor", "RESTRICT"),
    ("orden_compra", "id_sucursal", "sucursal", "id_sucursal", "RESTRICT"),
    ("orden_compra", "id_empleado", "empleado", "id_empleado", "SET NULL"),
    (
        "recepcion_mercaderia",
        "id_orden_compra",
        "orden_compra",
        "id_orden_compra",
        "SET NULL",
    ),
    (
        "recepcion_mercaderia",
        "id_sucursal",
        "sucursal",
        "id_sucursal",
        "RESTRICT",
    ),
    (
        "recepcion_mercaderia",
        "id_empleado",
        "empleado",
        "id_empleado",
        "SET NULL",
    ),
    ("lote_inventario", "id_sucursal", "sucursal", "id_sucursal", "RESTRICT"),
    (
        "inventario_sucursal",
        "id_sucursal",
        "sucursal",
        "id_sucursal",
        "RESTRICT",
    ),
    (
        "movimiento_inventario",
        "id_inventario",
        "inventario_sucursal",
        "id_inventario",
        "RESTRICT",
    ),
    (
        "movimiento_inventario",
        "id_empleado",
        "empleado",
        "id_empleado",
        "SET NULL",
    ),
    (
        "transferencia_inventario",
        "id_sucursal_origen",
        "sucursal",
        "id_sucursal",
        "RESTRICT",
    ),
    (
        "transferencia_inventario",
        "id_sucursal_destino",
        "sucursal",
        "id_sucursal",
        "RESTRICT",
    ),
    (
        "transferencia_inventario",
        "id_empleado",
        "empleado",
        "id_empleado",
        "SET NULL",
    ),
    ("pedido", "id_venta", "venta", "id_venta", "RESTRICT"),
    ("devolucion", "id_venta", "venta", "id_venta", "RESTRICT"),
    ("devolucion", "id_cliente", "cliente", "id_cliente", "SET NULL"),
    ("devolucion", "id_empleado", "empleado", "id_empleado", "SET NULL"),
)


def _fk_name(child: str, column: str) -> str:
    short_column = column.removeprefix("id_")
    return f"fk_{child}_{short_column}_tenant"


def upgrade() -> None:
    connection = op.get_bind()

    for child, child_column, parent, parent_column, _ in TENANT_REFERENCES:
        mismatches = connection.execute(
            sa.text(
                f"""
                SELECT count(*)
                FROM capricho.{child} child
                JOIN capricho.{parent} parent
                  ON parent.{parent_column} = child.{child_column}
                WHERE child.{child_column} IS NOT NULL
                  AND child.id_tenant IS DISTINCT FROM parent.id_tenant
                """
            )
        ).scalar_one()
        if mismatches:
            raise RuntimeError(
                f"Cross-tenant data found in {child}.{child_column}: {mismatches} rows"
            )

    for table, primary_key in TENANT_PARENTS.items():
        op.create_unique_constraint(
            f"uq_{table}_identity_tenant",
            table,
            [primary_key, "id_tenant"],
            schema=SCHEMA,
        )

    for child, child_column, parent, parent_column, ondelete in TENANT_REFERENCES:
        if ondelete == "SET NULL":
            # PostgreSQL supports selecting which columns are nulled. Keeping
            # id_tenant intact is required because tenant ownership is NOT NULL.
            op.execute(
                f"""
                ALTER TABLE capricho.{child}
                ADD CONSTRAINT {_fk_name(child, child_column)}
                FOREIGN KEY ({child_column}, id_tenant)
                REFERENCES capricho.{parent} ({parent_column}, id_tenant)
                ON DELETE SET NULL ({child_column})
                """
            )
        else:
            op.create_foreign_key(
                _fk_name(child, child_column),
                child,
                parent,
                [child_column, "id_tenant"],
                [parent_column, "id_tenant"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA,
                ondelete=ondelete,
            )


def downgrade() -> None:
    for child, child_column, _, _, _ in reversed(TENANT_REFERENCES):
        op.drop_constraint(
            _fk_name(child, child_column),
            child,
            schema=SCHEMA,
            type_="foreignkey",
        )

    for table, _ in reversed(tuple(TENANT_PARENTS.items())):
        op.drop_constraint(
            f"uq_{table}_identity_tenant",
            table,
            schema=SCHEMA,
            type_="unique",
        )
