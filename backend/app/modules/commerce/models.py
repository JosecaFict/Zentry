from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
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


class DireccionCliente(Base):
    __tablename__ = "direccion_cliente"

    id_direccion: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_cliente: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.cliente.id_cliente", ondelete="CASCADE"), nullable=False
    )
    id_ciudad: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.ciudad.id_ciudad", ondelete="RESTRICT"), nullable=False
    )
    alias: Mapped[str | None] = mapped_column(String(60))
    zona: Mapped[str | None] = mapped_column(String(120))
    direccion: Mapped[str] = mapped_column(String(255), nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(255))
    latitud: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    place_id: Mapped[str | None] = mapped_column(String(255))
    es_principal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Carrito(Base):
    __tablename__ = "carrito"

    id_carrito: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_cliente: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.cliente.id_cliente", ondelete="CASCADE"), nullable=False
    )
    id_sucursal: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="SET NULL"), nullable=True
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVO'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DetalleCarrito(Base):
    __tablename__ = "detalle_carrito"

    id_detalle_carrito: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_carrito: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.carrito.id_carrito", ondelete="CASCADE"), nullable=False
    )
    id_variante: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.variante_producto.id_variante", ondelete="RESTRICT"),
        nullable=False,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Reserva(Base):
    __tablename__ = "reserva"

    id_reserva: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_cliente: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.cliente.id_cliente", ondelete="RESTRICT"), nullable=False
    )
    id_sucursal: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="RESTRICT"), nullable=False
    )
    fecha_reserva: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_cita: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_expiracion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(
        String(25), nullable=False, server_default=text("'PENDIENTE'")
    )
    observacion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DetalleReserva(Base):
    __tablename__ = "detalle_reserva"

    id_detalle_reserva: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_reserva: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.reserva.id_reserva", ondelete="CASCADE"), nullable=False
    )
    id_variante: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.variante_producto.id_variante", ondelete="RESTRICT"),
        nullable=False,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)


class Venta(Base):
    __tablename__ = "venta"

    id_venta: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_cliente: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.cliente.id_cliente", ondelete="SET NULL")
    )
    id_sucursal: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="RESTRICT"), nullable=False
    )
    id_empleado: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.empleado.id_empleado", ondelete="SET NULL")
    )
    id_reserva: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.reserva.id_reserva", ondelete="SET NULL")
    )
    canal_venta: Mapped[str] = mapped_column(String(15), nullable=False)
    modalidad_entrega: Mapped[str] = mapped_column(String(20), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDIENTE'")
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    descuento_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    costo_envio: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    fecha_venta: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DetalleVenta(Base):
    __tablename__ = "detalle_venta"

    id_detalle_venta: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_venta: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.venta.id_venta", ondelete="CASCADE"), nullable=False
    )
    id_variante: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.variante_producto.id_variante", ondelete="RESTRICT"),
        nullable=False,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    descuento: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class MetodoPago(Base):
    __tablename__ = "metodo_pago"

    id_metodo_pago: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Pago(Base):
    __tablename__ = "pago"

    id_pago: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_venta: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.venta.id_venta", ondelete="RESTRICT"), nullable=False
    )
    id_metodo_pago: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.metodo_pago.id_metodo_pago", ondelete="RESTRICT"),
        nullable=False,
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'BOB'"))
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDIENTE'")
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_confirmacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TransaccionPasarela(Base):
    __tablename__ = "transaccion_pasarela"

    id_transaccion: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_pago: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.pago.id_pago", ondelete="CASCADE"), nullable=False
    )
    proveedor: Mapped[str] = mapped_column(String(30), nullable=False)
    external_payment_id: Mapped[str | None] = mapped_column(String(255))
    external_session_id: Mapped[str | None] = mapped_column(String(255))
    external_customer_id: Mapped[str | None] = mapped_column(String(255))
    estado: Mapped[str | None] = mapped_column(String(50))
    monto: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    moneda: Mapped[str | None] = mapped_column(String(3), server_default=text("'BOB'"))
    respuesta_resumen: Mapped[dict | None] = mapped_column(JSON)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_confirmacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TarifaEnvio(Base):
    __tablename__ = "tarifa_envio"

    id_tarifa: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    tarifa_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    distancia_base_km: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    costo_km_adicional: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class CotizacionEnvio(Base):
    __tablename__ = "cotizacion_envio"

    id_cotizacion: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_cliente: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.cliente.id_cliente", ondelete="RESTRICT"), nullable=False
    )
    id_sucursal: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="RESTRICT"), nullable=False
    )
    id_direccion: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.direccion_cliente.id_direccion", ondelete="RESTRICT"),
        nullable=False,
    )
    id_tarifa: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tarifa_envio.id_tarifa", ondelete="RESTRICT"),
        nullable=False,
    )
    distancia_km: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    duracion_estimada_min: Mapped[int | None] = mapped_column(Integer)
    costo_estimado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    proveedor_rutas: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'GOOGLE_MAPS'")
    )
    fecha_cotizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expira_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Pedido(Base):
    __tablename__ = "pedido"

    id_pedido: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_venta: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.venta.id_venta", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    id_direccion: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.direccion_cliente.id_direccion", ondelete="RESTRICT")
    )
    id_cotizacion: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.cotizacion_envio.id_cotizacion", ondelete="SET NULL")
    )
    estado: Mapped[str] = mapped_column(
        String(25), nullable=False, server_default=text("'PENDIENTE'")
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_preparacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_finalizacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Devolucion(Base):
    __tablename__ = "devolucion"

    id_devolucion: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    id_venta: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.venta.id_venta", ondelete="RESTRICT"), nullable=False
    )
    id_cliente: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.cliente.id_cliente", ondelete="SET NULL")
    )
    id_empleado: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.empleado.id_empleado", ondelete="SET NULL")
    )
    motivo: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDIENTE'")
    )
    fecha_solicitud: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_resolucion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DetalleDevolucion(Base):
    __tablename__ = "detalle_devolucion"

    id_detalle_devolucion: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_devolucion: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.devolucion.id_devolucion", ondelete="CASCADE"),
        nullable=False,
    )
    id_detalle_venta: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.detalle_venta.id_detalle_venta", ondelete="RESTRICT"),
        nullable=False,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    estado_prenda: Mapped[str] = mapped_column(
        String(25), nullable=False, server_default=text("'APTA_REINGRESO'")
    )


class Notificacion(Base):
    __tablename__ = "notificacion"

    id_notificacion: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_usuario: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.usuario.id_usuario", ondelete="SET NULL")
    )
    id_campania: Mapped[int | None] = mapped_column(BigInteger)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    canal: Mapped[str] = mapped_column(String(10), nullable=False)
    proveedor: Mapped[str] = mapped_column(String(30), nullable=False)
    destinatario: Mapped[str | None] = mapped_column(String(255))
    titulo: Mapped[str | None] = mapped_column(String(180))
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDIENTE'")
    )
    external_message_id: Mapped[str | None] = mapped_column(String(255))
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_envio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_mensaje: Mapped[str | None] = mapped_column(Text)


class Campania(Base):
    __tablename__ = "campania"

    id_campania: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(250))
    asunto_email: Mapped[str | None] = mapped_column(String(180))
    segmento_objetivo: Mapped[str | None] = mapped_column(String(150))
    fecha_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'BORRADOR'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Promocion(Base):
    __tablename__ = "promocion"

    id_promocion: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(250))
    porcentaje_descuento: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    fecha_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fecha_fin: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PromocionProducto(Base):
    __tablename__ = "promocion_producto"

    id_promocion_producto: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_promocion: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.promocion.id_promocion", ondelete="CASCADE"),
        nullable=False,
    )
    id_producto: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.producto.id_producto", ondelete="CASCADE"),
        nullable=False,
    )


class PromocionCategoria(Base):
    __tablename__ = "promocion_categoria"

    id_promocion_categoria: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_promocion: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.promocion.id_promocion", ondelete="CASCADE"),
        nullable=False,
    )
    id_categoria: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.categoria.id_categoria", ondelete="CASCADE"),
        nullable=False,
    )


class PromocionTemporada(Base):
    __tablename__ = "promocion_temporada"

    id_promocion_temporada: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_promocion: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.promocion.id_promocion", ondelete="CASCADE"),
        nullable=False,
    )
    id_temporada: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.temporada.id_temporada", ondelete="CASCADE"),
        nullable=False,
    )


