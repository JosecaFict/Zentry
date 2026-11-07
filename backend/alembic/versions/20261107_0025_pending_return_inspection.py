"""Allow a returned garment to wait for physical inspection."""

from alembic import op

revision = "20261107_0025"
down_revision = "20261107_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("detalle_devolucion_estado_prenda_check"), "detalle_devolucion", schema="capricho", type_="check")
    op.create_check_constraint(
        op.f("detalle_devolucion_estado_prenda_check"), "detalle_devolucion",
        "estado_prenda IN ('PENDIENTE_INSPECCION', 'APTA_REINGRESO', 'NO_APTA')", schema="capricho",
    )
    op.alter_column("detalle_devolucion", "estado_prenda", server_default="PENDIENTE_INSPECCION", schema="capricho")


def downgrade() -> None:
    # An uninspected garment must never become eligible stock during downgrade.
    op.execute("UPDATE capricho.detalle_devolucion SET estado_prenda='NO_APTA' WHERE estado_prenda='PENDIENTE_INSPECCION'")
    op.drop_constraint(op.f("detalle_devolucion_estado_prenda_check"), "detalle_devolucion", schema="capricho", type_="check")
    op.create_check_constraint(
        op.f("detalle_devolucion_estado_prenda_check"), "detalle_devolucion",
        "estado_prenda IN ('APTA_REINGRESO', 'NO_APTA')", schema="capricho",
    )
    op.alter_column("detalle_devolucion", "estado_prenda", server_default="APTA_REINGRESO", schema="capricho")
