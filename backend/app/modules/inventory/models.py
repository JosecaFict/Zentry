from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Proveedor(Base):
    __tablename__ = "proveedor"

    id_proveedor: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_ciudad: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.ciudad.id_ciudad", ondelete="SET NULL")
    )
    razon_social: Mapped[str] = mapped_column(String(150), nullable=False)
    nombre_comercial: Mapped[str | None] = mapped_column(String(150))
    nit: Mapped[str | None] = mapped_column(String(40), unique=True)
    telefono: Mapped[str | None] = mapped_column(String(30))
    correo: Mapped[str | None] = mapped_column(String(150))
    direccion: Mapped[str | None] = mapped_column(String(255))
    nombre_contacto: Mapped[str | None] = mapped_column(String(120))
    telefono_contacto: Mapped[str | None] = mapped_column(String(30))
    correo_contacto: Mapped[str | None] = mapped_column(String(150))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductoProveedor(Base):
    __tablename__ = "producto_proveedor"

    id_producto_proveedor: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_producto: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.producto.id_producto", ondelete="RESTRICT")
    )
    id_proveedor: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.proveedor.id_proveedor", ondelete="RESTRICT")
    )
    codigo_proveedor: Mapped[str | None] = mapped_column(String(100))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrdenCompra(Base):
    __tablename__ = "orden_compra"

    id_orden_compra: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_proveedor: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.proveedor.id_proveedor", ondelete="RESTRICT")
    )
    id_sucursal: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="RESTRICT")
    )
    id_empleado: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.empleado.id_empleado", ondelete="SET NULL")
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'SOLICITADA'")
    )
    fecha_orden: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_estimada: Mapped[date | None] = mapped_column(Date)
    observacion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DetalleOrdenCompra(Base):
    __tablename__ = "detalle_orden_compra"

    id_detalle_orden: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_orden_compra: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.orden_compra.id_orden_compra", ondelete="CASCADE")
    )
    id_variante: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.variante_producto.id_variante", ondelete="RESTRICT")
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_unitario_estimado: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class RecepcionMercaderia(Base):
    __tablename__ = "recepcion_mercaderia"

    id_recepcion: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_orden_compra: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.orden_compra.id_orden_compra", ondelete="SET NULL")
    )
    id_sucursal: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="RESTRICT")
    )
    id_empleado: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.empleado.id_empleado", ondelete="SET NULL")
    )
    fecha_recepcion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'CONFIRMADA'")
    )
    observacion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DetalleRecepcion(Base):
    __tablename__ = "detalle_recepcion"

    id_detalle_recepcion: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_recepcion: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.recepcion_mercaderia.id_recepcion", ondelete="CASCADE")
    )
    id_variante: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.variante_producto.id_variante", ondelete="RESTRICT")
    )
    cantidad_recibida: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class LoteInventario(Base):
    __tablename__ = "lote_inventario"

    id_lote: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_detalle_recepcion: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.detalle_recepcion.id_detalle_recepcion", ondelete="RESTRICT"),
    )
    id_sucursal: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="RESTRICT")
    )
    id_variante: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.variante_producto.id_variante", ondelete="RESTRICT")
    )
    numero_lote: Mapped[str | None] = mapped_column(String(100))
    cantidad_inicial: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad_disponible: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_ingreso: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class MovimientoInventario(Base):
    __tablename__ = "movimiento_inventario"

    id_movimiento: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_inventario: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.inventario_sucursal.id_inventario", ondelete="RESTRICT")
    )
    id_empleado: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.empleado.id_empleado", ondelete="SET NULL")
    )
    tipo_movimiento: Mapped[str] = mapped_column(String(30), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    referencia_tipo: Mapped[str | None] = mapped_column(String(40))
    referencia_id: Mapped[int | None] = mapped_column(BigInteger)
    motivo: Mapped[str | None] = mapped_column(String(255))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MovimientoLote(Base):
    __tablename__ = "movimiento_lote"

    id_movimiento_lote: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_movimiento: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.movimiento_inventario.id_movimiento", ondelete="CASCADE")
    )
    id_lote: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.lote_inventario.id_lote", ondelete="RESTRICT")
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class TransferenciaInventario(Base):
    __tablename__ = "transferencia_inventario"

    id_transferencia: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_sucursal_origen: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="RESTRICT")
    )
    id_sucursal_destino: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="RESTRICT")
    )
    id_empleado: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.empleado.id_empleado", ondelete="SET NULL")
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'SOLICITADA'")
    )
    fecha_solicitud: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_recepcion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DetalleTransferencia(Base):
    __tablename__ = "detalle_transferencia"

    id_detalle_transferencia: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_transferencia: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.transferencia_inventario.id_transferencia", ondelete="CASCADE"),
    )
    id_variante: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.variante_producto.id_variante", ondelete="RESTRICT")
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
