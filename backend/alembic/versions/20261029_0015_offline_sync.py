"""Add the idempotent offline synchronization protocol.

Revision ID: 20261029_0015
Revises: 20261024_0014
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261029_0015"
down_revision = "20261024_0014"
branch_labels = None
depends_on = None

SCHEMA = "capricho"


def upgrade() -> None:
    op.create_table(
        "dispositivo_sync",
        sa.Column("id_dispositivo", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "id_tenant",
            sa.BigInteger(),
            sa.ForeignKey("capricho.tenant.id_tenant", ondelete="CASCADE"),
            nullable=False,
            server_default=sa.text("capricho.fn_tenant_actual()"),
        ),
        sa.Column(
            "id_usuario",
            sa.BigInteger(),
            sa.ForeignKey("capricho.usuario.id_usuario", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "id_sucursal",
            sa.BigInteger(),
            sa.ForeignKey("capricho.sucursal.id_sucursal", ondelete="SET NULL"),
        ),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("plataforma", sa.String(20), nullable=False),
        sa.Column("version_app", sa.String(40)),
        sa.Column("estado", sa.String(20), nullable=False, server_default="ACTIVO"),
        sa.Column("ultima_sincronizacion", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "plataforma IN ('PWA','ANDROID','IOS')", name="dispositivo_sync_plataforma_check"
        ),
        sa.CheckConstraint(
            "estado IN ('ACTIVO','REVOCADO')", name="dispositivo_sync_estado_check"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_dispositivo_sync_tenant_usuario",
        "dispositivo_sync",
        ["id_tenant", "id_usuario"],
        schema=SCHEMA,
    )

    op.create_table(
        "lote_sincronizacion",
        sa.Column("id_lote", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "id_tenant",
            sa.BigInteger(),
            sa.ForeignKey("capricho.tenant.id_tenant", ondelete="CASCADE"),
            nullable=False,
            server_default=sa.text("capricho.fn_tenant_actual()"),
        ),
        sa.Column(
            "id_dispositivo",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("capricho.dispositivo_sync.id_dispositivo", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "id_usuario",
            sa.BigInteger(),
            sa.ForeignKey("capricho.usuario.id_usuario", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("estado", sa.String(40), nullable=False, server_default="RECIBIDO"),
        sa.Column("fecha_cliente", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recibido_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("procesado_at", sa.DateTime(timezone=True)),
        sa.Column("confirmado_at", sa.DateTime(timezone=True)),
        sa.Column("total_operaciones", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_aplicadas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_conflictos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rechazadas", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "estado IN ('RECIBIDO','PROCESANDO','COMPLETADO',"
            "'COMPLETADO_CON_CONFLICTOS','CONFIRMADO')",
            name="lote_sincronizacion_estado_check",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_lote_sync_tenant_dispositivo",
        "lote_sincronizacion",
        ["id_tenant", "id_dispositivo", "recibido_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "operacion_sincronizacion",
        sa.Column("id_operacion", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "id_tenant",
            sa.BigInteger(),
            sa.ForeignKey("capricho.tenant.id_tenant", ondelete="CASCADE"),
            nullable=False,
            server_default=sa.text("capricho.fn_tenant_actual()"),
        ),
        sa.Column(
            "id_lote",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("capricho.lote_sincronizacion.id_lote", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "id_dispositivo",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("capricho.dispositivo_sync.id_dispositivo", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "id_usuario",
            sa.BigInteger(),
            sa.ForeignKey("capricho.usuario.id_usuario", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("estado", sa.String(30), nullable=False, server_default="PENDIENTE"),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("resultado", postgresql.JSONB()),
        sa.Column("codigo_error", sa.String(60)),
        sa.Column("mensaje_error", sa.Text()),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fecha_cliente", sa.DateTime(timezone=True), nullable=False),
        sa.Column("procesada_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("tipo IN ('VENTA','RESERVA')", name="operacion_sync_tipo_check"),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE','PROCESANDO','APLICADA','CONFLICTO','RECHAZADA')",
            name="operacion_sync_estado_check",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_operacion_sync_lote_estado",
        "operacion_sincronizacion",
        ["id_lote", "estado"],
        schema=SCHEMA,
    )

    op.create_table(
        "conflicto_sincronizacion",
        sa.Column("id_conflicto", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "id_tenant",
            sa.BigInteger(),
            sa.ForeignKey("capricho.tenant.id_tenant", ondelete="CASCADE"),
            nullable=False,
            server_default=sa.text("capricho.fn_tenant_actual()"),
        ),
        sa.Column(
            "id_operacion",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("capricho.operacion_sincronizacion.id_operacion", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("tipo", sa.String(60), nullable=False),
        sa.Column("detalle", postgresql.JSONB(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="PENDIENTE"),
        sa.Column(
            "resuelto_por",
            sa.BigInteger(),
            sa.ForeignKey("capricho.usuario.id_usuario", ondelete="SET NULL"),
        ),
        sa.Column("resolucion", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resuelto_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE','RESUELTO','DESCARTADO')",
            name="conflicto_sync_estado_check",
        ),
        schema=SCHEMA,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION capricho.fn_validar_tenant_sync()
        RETURNS TRIGGER LANGUAGE plpgsql SET search_path = capricho, pg_temp AS $$
        BEGIN
          IF TG_TABLE_NAME = 'dispositivo_sync' THEN
            IF NOT EXISTS (
              SELECT 1 FROM usuario u
              WHERE u.id_usuario = NEW.id_usuario AND u.id_tenant = NEW.id_tenant
            ) THEN
              RAISE EXCEPTION 'sync user tenant mismatch';
            END IF;
            IF NEW.id_sucursal IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM sucursal s
              WHERE s.id_sucursal = NEW.id_sucursal AND s.id_tenant = NEW.id_tenant
            ) THEN
              RAISE EXCEPTION 'sync branch tenant mismatch';
            END IF;
          ELSIF TG_TABLE_NAME = 'lote_sincronizacion' THEN
            IF NOT EXISTS (
              SELECT 1 FROM dispositivo_sync d
              WHERE d.id_dispositivo = NEW.id_dispositivo
                AND d.id_tenant = NEW.id_tenant
                AND d.id_usuario = NEW.id_usuario
            ) THEN
              RAISE EXCEPTION 'sync batch tenant mismatch';
            END IF;
          ELSIF TG_TABLE_NAME = 'operacion_sincronizacion' THEN
            IF NOT EXISTS (
              SELECT 1 FROM lote_sincronizacion l
              WHERE l.id_lote = NEW.id_lote
                AND l.id_tenant = NEW.id_tenant
                AND l.id_dispositivo = NEW.id_dispositivo
                AND l.id_usuario = NEW.id_usuario
            ) THEN
              RAISE EXCEPTION 'sync operation tenant mismatch';
            END IF;
          ELSIF TG_TABLE_NAME = 'conflicto_sincronizacion' THEN
            IF NOT EXISTS (
              SELECT 1 FROM operacion_sincronizacion o
              WHERE o.id_operacion = NEW.id_operacion
                AND o.id_tenant = NEW.id_tenant
            ) THEN
              RAISE EXCEPTION 'sync conflict tenant mismatch';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$;
        """
    )
    for table in (
        "dispositivo_sync",
        "lote_sincronizacion",
        "operacion_sincronizacion",
        "conflicto_sincronizacion",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_tenant BEFORE INSERT OR UPDATE ON capricho.{table} "
            "FOR EACH ROW EXECUTE FUNCTION capricho.fn_validar_tenant_sync()"
        )
    for table, key in (
        ("dispositivo_sync", "id_dispositivo"),
        ("lote_sincronizacion", "id_lote"),
        ("operacion_sincronizacion", "id_operacion"),
        ("conflicto_sincronizacion", "id_conflicto"),
    ):
        op.execute(
            f"CREATE TRIGGER trg_audit_{table} AFTER INSERT OR UPDATE OR DELETE "
            f"ON capricho.{table} FOR EACH ROW EXECUTE FUNCTION "
            f"capricho.fn_bitacora_generica('SINCRONIZACION','{key}')"
        )


def downgrade() -> None:
    for table in (
        "conflicto_sincronizacion",
        "operacion_sincronizacion",
        "lote_sincronizacion",
        "dispositivo_sync",
    ):
        op.drop_table(table, schema=SCHEMA)
    op.execute("DROP FUNCTION IF EXISTS capricho.fn_validar_tenant_sync()")

