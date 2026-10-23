"""Add commercial plans, billing periods and subscription payments.

Revision ID: 20261022_0010
Revises: 20261022_0009
"""

import sqlalchemy as sa

from alembic import op

revision = "20261022_0010"
down_revision = "20261022_0009"
branch_labels = None
depends_on = None

SCHEMA = "capricho"


def upgrade() -> None:
    op.add_column("plan", sa.Column("max_usuarios_internos", sa.Integer()), schema=SCHEMA)
    op.add_column("plan", sa.Column("max_productos_activos", sa.Integer()), schema=SCHEMA)
    op.add_column("plan", sa.Column("almacenamiento_mb", sa.Integer()), schema=SCHEMA)
    op.add_column("plan", sa.Column("precio_mensual", sa.Numeric(10, 2)), schema=SCHEMA)
    op.add_column("plan", sa.Column("precio_anual", sa.Numeric(10, 2)), schema=SCHEMA)
    op.execute(
        """
        UPDATE capricho.plan SET
          codigo = CASE WHEN codigo = 'BASICO' THEN 'GESTION' ELSE 'CRECIMIENTO' END,
          nombre = CASE WHEN codigo = 'BASICO' THEN 'Gestión' ELSE 'Crecimiento' END,
          max_sucursales_activas = CASE WHEN codigo = 'BASICO' THEN 1 ELSE 5 END,
          max_usuarios_internos = CASE WHEN codigo = 'BASICO' THEN 5 ELSE 25 END,
          max_productos_activos = CASE WHEN codigo = 'BASICO' THEN 3000 ELSE 20000 END,
          almacenamiento_mb = CASE WHEN codigo = 'BASICO' THEN 5120 ELSE 25600 END,
          precio_mensual = CASE WHEN codigo = 'BASICO' THEN 300 ELSE 700 END,
          precio_anual = CASE WHEN codigo = 'BASICO' THEN 3600 ELSE 8400 END
        """
    )
    for column in (
        "max_usuarios_internos",
        "max_productos_activos",
        "almacenamiento_mb",
        "precio_mensual",
        "precio_anual",
    ):
        op.alter_column("plan", column, nullable=False, schema=SCHEMA)

    op.add_column(
        "subscription",
        sa.Column("modalidad", sa.String(10), nullable=False, server_default="MENSUAL"),
        schema=SCHEMA,
    )
    op.add_column("subscription", sa.Column("precio_acordado", sa.Numeric(10, 2)), schema=SCHEMA)
    op.add_column("subscription", sa.Column("proxima_renovacion", sa.Date()), schema=SCHEMA)
    op.add_column("subscription", sa.Column("fecha_fin_gracia", sa.Date()), schema=SCHEMA)
    op.execute(
        """
        UPDATE capricho.subscription s SET
          precio_acordado = p.precio_mensual,
          proxima_renovacion = COALESCE(s.fecha_fin, s.fecha_inicio + 30),
          fecha_fin_gracia = COALESCE(s.fecha_fin, s.fecha_inicio + 30) + 7
        FROM capricho.plan p WHERE p.id_plan = s.id_plan
        """
    )
    op.alter_column("subscription", "precio_acordado", nullable=False, schema=SCHEMA)
    op.drop_constraint("ck_subscription_estado", "subscription", schema=SCHEMA, type_="check")
    op.create_check_constraint(
        "ck_subscription_estado",
        "subscription",
        "estado IN ('ACTIVA','POR_VENCER','GRACIA','SUSPENDIDA','VENCIDA','CANCELADA')",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_subscription_modalidad",
        "subscription",
        "modalidad IN ('MENSUAL','ANUAL')",
        schema=SCHEMA,
    )
    op.execute("DROP INDEX IF EXISTS capricho.uq_subscription_activa_tenant")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_subscription_vigente_tenant
        ON capricho.subscription (id_tenant)
        WHERE estado IN ('ACTIVA','POR_VENCER','GRACIA','SUSPENDIDA')
        """
    )
    op.create_table(
        "subscription_payment",
        sa.Column("id_payment", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "id_subscription",
            sa.BigInteger(),
            sa.ForeignKey("capricho.subscription.id_subscription", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("importe", sa.Numeric(10, 2), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False, server_default="BOB"),
        sa.Column("metodo_pago", sa.String(30), nullable=False),
        sa.Column("referencia", sa.String(120)),
        sa.Column("fecha_pago", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("estado", sa.String(20), nullable=False, server_default="CONFIRMADO"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("importe > 0", name="ck_subscription_payment_importe"),
        sa.CheckConstraint(
            "estado IN ('CONFIRMADO','ANULADO')", name="ck_subscription_payment_estado"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_subscription_payment_subscription",
        "subscription_payment",
        ["id_subscription"],
        schema=SCHEMA,
    )
    op.execute(
        """
        UPDATE capricho.subscription
        SET id_plan = (SELECT id_plan FROM capricho.plan WHERE codigo = 'CRECIMIENTO'),
            precio_acordado = 700
        WHERE id_tenant = (SELECT id_tenant FROM capricho.tenant WHERE slug = 'capricho-store')
        """
    )


def downgrade() -> None:
    raise RuntimeError("Billing history downgrade is not supported; restore a verified backup")
