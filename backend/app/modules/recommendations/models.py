from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConfiguracionRecomendador(Base):
    __tablename__ = "configuracion_recomendador"

    id_configuracion: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_tenant: Mapped[int] = mapped_column(BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False, server_default=text("capricho.fn_tenant_actual()"))
    peso_categoria: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("40")
    )
    peso_marca: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("20")
    )
    peso_color: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("15")
    )
    peso_talla: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("10")
    )
    peso_temporada: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("10")
    )
    peso_promocion: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("5")
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InteraccionProducto(Base):
    __tablename__ = "interaccion_producto"

    id_interaccion: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_cliente: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.cliente.id_cliente", ondelete="CASCADE"),
        nullable=False,
    )
    id_producto: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.producto.id_producto", ondelete="CASCADE"),
        nullable=False,
    )
    id_variante: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("capricho.variante_producto.id_variante", ondelete="SET NULL"),
        nullable=True,
    )
    tipo_interaccion: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Recomendacion(Base):
    __tablename__ = "recomendacion"

    id_recomendacion: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_cliente: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.cliente.id_cliente", ondelete="CASCADE"),
        nullable=False,
    )
    id_producto: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.producto.id_producto", ondelete="CASCADE"),
        nullable=False,
    )
    puntuacion: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False
    )
    motivo: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    fecha_generacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
