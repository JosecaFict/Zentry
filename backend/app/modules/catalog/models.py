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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Categoria(Base):
    __tablename__ = "categoria"
    __table_args__ = (UniqueConstraint("id_tenant", "nombre", name="uq_categoria_tenant_nombre"),)

    id_categoria: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(250))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Marca(Base):
    __tablename__ = "marca"
    __table_args__ = (UniqueConstraint("id_tenant", "nombre", name="uq_marca_tenant_nombre"),)

    id_marca: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(250))
    pais_origen: Mapped[str | None] = mapped_column(String(100))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Talla(Base):
    __tablename__ = "talla"
    __table_args__ = (
        UniqueConstraint("id_tenant", "codigo", name="uq_talla_tenant_codigo"),
        UniqueConstraint("id_tenant", "orden", name="uq_talla_tenant_orden"),
    )

    id_talla: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    codigo: Mapped[str] = mapped_column(String(10), nullable=False)
    orden: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Color(Base):
    __tablename__ = "color"
    __table_args__ = (UniqueConstraint("id_tenant", "nombre", name="uq_color_tenant_nombre"),)

    id_color: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    codigo_hex: Mapped[str | None] = mapped_column(String(7))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Temporada(Base):
    __tablename__ = "temporada"

    id_temporada: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    anio: Mapped[int | None] = mapped_column(SmallInteger)
    fecha_inicio: Mapped[date | None] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Coleccion(Base):
    __tablename__ = "coleccion"

    id_coleccion: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_temporada: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.temporada.id_temporada", ondelete="SET NULL")
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(250))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Producto(Base):
    __tablename__ = "producto"

    id_producto: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_categoria: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.categoria.id_categoria", ondelete="RESTRICT")
    )
    id_marca: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.marca.id_marca", ondelete="RESTRICT")
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    publico_objetivo: Mapped[str] = mapped_column(String(10), nullable=False)
    permite_vestidor: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductoTemporada(Base):
    __tablename__ = "producto_temporada"

    id_producto_temporada: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_producto: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.producto.id_producto", ondelete="CASCADE")
    )
    id_temporada: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.temporada.id_temporada", ondelete="CASCADE")
    )


class ProductoColeccion(Base):
    __tablename__ = "producto_coleccion"

    id_producto_coleccion: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_producto: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.producto.id_producto", ondelete="CASCADE")
    )
    id_coleccion: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.coleccion.id_coleccion", ondelete="CASCADE")
    )


class VarianteProducto(Base):
    __tablename__ = "variante_producto"

    id_variante: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_producto: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.producto.id_producto", ondelete="RESTRICT")
    )
    id_talla: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.talla.id_talla", ondelete="RESTRICT")
    )
    id_color: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.color.id_color", ondelete="RESTRICT")
    )
    sku: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    codigo_barras: Mapped[str | None] = mapped_column(String(80), unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MedidaTallaProducto(Base):
    __tablename__ = "medida_talla_producto"

    id_medida: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_producto: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.producto.id_producto", ondelete="CASCADE")
    )
    id_talla: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.talla.id_talla", ondelete="RESTRICT")
    )
    ancho_hombros_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ancho_pecho_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    largo_prenda_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    largo_manga_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))


class ImagenProducto(Base):
    __tablename__ = "imagen_producto"

    id_imagen: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_producto: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.producto.id_producto", ondelete="CASCADE")
    )
    id_color: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.color.id_color", ondelete="RESTRICT")
    )
    proveedor_storage: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'CLOUDINARY'")
    )
    public_id: Mapped[str] = mapped_column(String(255), nullable=False)
    secure_url: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'CATALOGO'"))
    orden: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    es_principal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    formato: Mapped[str | None] = mapped_column(String(20))
    ancho_px: Mapped[int | None] = mapped_column(Integer)
    alto_px: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HistorialPrecio(Base):
    __tablename__ = "historial_precio"

    id_historial_precio: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_producto: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.producto.id_producto", ondelete="RESTRICT")
    )
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.usuario.id_usuario", ondelete="SET NULL")
    )


class InventarioSucursal(Base):
    __tablename__ = "inventario_sucursal"

    id_inventario: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_sucursal: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.sucursal.id_sucursal", ondelete="RESTRICT")
    )
    id_variante: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.variante_producto.id_variante", ondelete="RESTRICT")
    )
    stock_fisico: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    stock_reservado: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    stock_minimo: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
