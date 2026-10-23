"""Create SaaS tenants, plans and the initial Capricho Store subscription.

Revision ID: 20261021_0002
Revises: 20261021_0001
"""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0002"
down_revision = "20261021_0001"
branch_labels = None
depends_on = None

SCHEMA = "capricho"


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("id_tenant", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("estado", sa.String(20), server_default="ACTIVO", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("estado IN ('ACTIVO','SUSPENDIDO')", name="ck_tenant_estado"),
        schema=SCHEMA,
    )
    op.create_table(
        "plan",
        sa.Column("id_plan", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("codigo", sa.String(30), nullable=False, unique=True),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("max_sucursales_activas", sa.Integer(), nullable=False),
        sa.Column("permite_reportes_ia", sa.Boolean(), nullable=False),
        sa.Column("permite_offline", sa.Boolean(), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint("max_sucursales_activas > 0", name="ck_plan_max_sucursales_activas"),
        schema=SCHEMA,
    )
    op.create_table(
        "subscription",
        sa.Column("id_subscription", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("id_tenant", sa.BigInteger(), sa.ForeignKey("capricho.tenant.id_tenant", ondelete="RESTRICT"), nullable=False),
        sa.Column("id_plan", sa.BigInteger(), sa.ForeignKey("capricho.plan.id_plan", ondelete="RESTRICT"), nullable=False),
        sa.Column("estado", sa.String(20), server_default="ACTIVA", nullable=False),
        sa.Column("fecha_inicio", sa.Date(), server_default=sa.func.current_date(), nullable=False),
        sa.Column("fecha_fin", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("estado IN ('ACTIVA','VENCIDA','SUSPENDIDA')", name="ck_subscription_estado"),
        sa.CheckConstraint("fecha_fin IS NULL OR fecha_fin >= fecha_inicio", name="ck_subscription_fechas"),
        schema=SCHEMA,
    )
    op.create_index("ix_subscription_tenant", "subscription", ["id_tenant"], schema=SCHEMA)
    op.execute("CREATE UNIQUE INDEX uq_subscription_activa_tenant ON capricho.subscription (id_tenant) WHERE estado = 'ACTIVA'")

    connection = op.get_bind()
    connection.execute(sa.text("INSERT INTO capricho.plan (codigo, nombre, max_sucursales_activas, permite_reportes_ia, permite_offline) VALUES ('BASICO', 'Básico', 2, false, true), ('PROFESIONAL', 'Profesional', 10, true, true)"))
    tenant_id = connection.execute(sa.text("INSERT INTO capricho.tenant (nombre, slug) VALUES ('Capricho Store', 'capricho-store') RETURNING id_tenant")).scalar_one()
    # Existing data contains two active branches, so the initial plan fits.
    active_branches = connection.execute(sa.text("SELECT count(*) FROM capricho.sucursal WHERE activo")).scalar_one()
    if active_branches > 2:
        raise RuntimeError("Existing active branches exceed the Básico plan")
    connection.execute(sa.text("INSERT INTO capricho.subscription (id_tenant, id_plan) SELECT :tenant_id, id_plan FROM capricho.plan WHERE codigo = 'BASICO'"), {"tenant_id": tenant_id})

def downgrade() -> None:
    raise RuntimeError("Tenant foundation downgrade would erase ownership; restore a verified backup instead")
