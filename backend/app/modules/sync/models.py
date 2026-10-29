from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncDevice(Base):
    __tablename__ = "dispositivo_sync"

    id_dispositivo: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant", ondelete="CASCADE"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_usuario: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.usuario.id_usuario", ondelete="CASCADE"), nullable=False
    )
    id_sucursal: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="SET NULL")
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    plataforma: Mapped[str] = mapped_column(String(20), nullable=False)
    version_app: Mapped[str | None] = mapped_column(String(40))
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ACTIVO'")
    )
    ultima_sincronizacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SyncBatch(Base):
    __tablename__ = "lote_sincronizacion"

    id_lote: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant", ondelete="CASCADE"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_dispositivo: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("capricho.dispositivo_sync.id_dispositivo", ondelete="RESTRICT"),
        nullable=False,
    )
    id_usuario: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.usuario.id_usuario", ondelete="RESTRICT"), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=text("'RECIBIDO'")
    )
    fecha_cliente: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recibido_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    procesado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_operaciones: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    total_aplicadas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_conflictos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_rechazadas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class SyncOperation(Base):
    __tablename__ = "operacion_sincronizacion"

    id_operacion: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant", ondelete="CASCADE"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_lote: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("capricho.lote_sincronizacion.id_lote", ondelete="CASCADE"),
        nullable=False,
    )
    id_dispositivo: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("capricho.dispositivo_sync.id_dispositivo", ondelete="RESTRICT"),
        nullable=False,
    )
    id_usuario: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.usuario.id_usuario", ondelete="RESTRICT"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'PENDIENTE'")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resultado: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    codigo_error: Mapped[str | None] = mapped_column(String(60))
    mensaje_error: Mapped[str | None] = mapped_column(Text)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    fecha_cliente: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    procesada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SyncConflict(Base):
    __tablename__ = "conflicto_sincronizacion"

    id_conflicto: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant", ondelete="CASCADE"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_operacion: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("capricho.operacion_sincronizacion.id_operacion", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    detalle: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDIENTE'")
    )
    resuelto_por: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.usuario.id_usuario", ondelete="SET NULL")
    )
    resolucion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resuelto_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

