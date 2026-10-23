"""Add direct tenant ownership to critical commercial aggregates.

Revision ID: 20261021_0004
Revises: 20261021_0003
"""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0004"
down_revision = "20261021_0003"
branch_labels = None
depends_on = None

SCHEMA = "capricho"
BACKFILL = {
    "carrito": "SELECT id_tenant FROM capricho.cliente p WHERE p.id_cliente = carrito.id_cliente",
    "reserva": "SELECT id_tenant FROM capricho.sucursal p WHERE p.id_sucursal = reserva.id_sucursal",
    "venta": "SELECT id_tenant FROM capricho.sucursal p WHERE p.id_sucursal = venta.id_sucursal",
    "orden_compra": "SELECT id_tenant FROM capricho.sucursal p WHERE p.id_sucursal = orden_compra.id_sucursal",
    "recepcion_mercaderia": "SELECT id_tenant FROM capricho.sucursal p WHERE p.id_sucursal = recepcion_mercaderia.id_sucursal",
    "lote_inventario": "SELECT id_tenant FROM capricho.sucursal p WHERE p.id_sucursal = lote_inventario.id_sucursal",
    "inventario_sucursal": "SELECT id_tenant FROM capricho.sucursal p WHERE p.id_sucursal = inventario_sucursal.id_sucursal",
    "movimiento_inventario": "SELECT id_tenant FROM capricho.inventario_sucursal p WHERE p.id_inventario = movimiento_inventario.id_inventario",
    "transferencia_inventario": "SELECT id_tenant FROM capricho.sucursal p WHERE p.id_sucursal = transferencia_inventario.id_sucursal_origen",
    "pedido": "SELECT id_tenant FROM capricho.venta p WHERE p.id_venta = pedido.id_venta",
    "devolucion": "SELECT id_tenant FROM capricho.venta p WHERE p.id_venta = devolucion.id_venta",
}


def upgrade() -> None:
    connection = op.get_bind()
    for table, parent_query in BACKFILL.items():
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
            sa.text(
                f"UPDATE capricho.{table} SET id_tenant = ({parent_query}) "
                "WHERE id_tenant IS NULL"
            )
        )
        missing = connection.execute(
            sa.text(f"SELECT count(*) FROM capricho.{table} WHERE id_tenant IS NULL")
        ).scalar_one()
        if missing:
            raise RuntimeError(f"Cannot infer tenant for {missing} rows in {table}")
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


def downgrade() -> None:
    raise RuntimeError(
        "Critical tenant ownership downgrade would discard ownership; restore a backup instead"
    )
