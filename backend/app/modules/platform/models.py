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
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Tenant(Base):
    __tablename__ = "tenant"

    id_tenant: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    razon_social: Mapped[str | None] = mapped_column(String(180))
    nit: Mapped[str | None] = mapped_column(String(40))
    correo_contacto: Mapped[str | None] = mapped_column(String(150))
    telefono_contacto: Mapped[str | None] = mapped_column(String(30))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    color_primario: Mapped[str] = mapped_column(
        String(7), nullable=False, server_default=text("'#064FE8'")
    )
    color_primario_oscuro: Mapped[str] = mapped_column(
        String(7), nullable=False, server_default=text("'#0039B8'")
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVO'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Plan(Base):
    __tablename__ = "plan"

    id_plan: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    max_sucursales_activas: Mapped[int] = mapped_column(Integer, nullable=False)
    max_usuarios_internos: Mapped[int] = mapped_column(Integer, nullable=False)
    max_productos_activos: Mapped[int] = mapped_column(Integer, nullable=False)
    almacenamiento_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_mensual: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    precio_anual: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    permite_reportes_convencionales: Mapped[bool] = mapped_column(Boolean, nullable=False)
    permite_reportes_ia: Mapped[bool] = mapped_column(Boolean, nullable=False)
    permite_offline: Mapped[bool] = mapped_column(Boolean, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Subscription(Base):
    __tablename__ = "subscription"

    id_subscription: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_tenant: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.tenant.id_tenant"), nullable=False
    )
    id_plan: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("capricho.plan.id_plan"), nullable=False
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVA'"))
    modalidad: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'MENSUAL'")
    )
    precio_acordado: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    fecha_fin: Mapped[date | None] = mapped_column(Date)
    proxima_renovacion: Mapped[date | None] = mapped_column(Date)
    fecha_fin_gracia: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payment"

    id_payment: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_subscription: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.subscription.id_subscription", ondelete="RESTRICT"),
        nullable=False,
    )
    importe: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'BOB'"))
    metodo_pago: Mapped[str] = mapped_column(String(30), nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(120))
    fecha_pago: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'CONFIRMADO'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
