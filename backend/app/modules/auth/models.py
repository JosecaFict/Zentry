from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Rol(Base):
    __tablename__ = "rol"

    id_rol: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("capricho.tenant.id_tenant", ondelete="RESTRICT")
    )
    alcance: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'TENANT'")
    )
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Permiso(Base):
    __tablename__ = "permiso"

    id_permiso: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(250))
    modulo: Mapped[str] = mapped_column(String(60), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant", ondelete="RESTRICT"),
        server_default=text("capricho.fn_tenant_actual()"),
    )
    nombres: Mapped[str] = mapped_column(String(100), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(100), nullable=False)
    ci: Mapped[str | None] = mapped_column(String(30))
    correo: Mapped[str] = mapped_column(String(150), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVO'"))
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    id_usuario_rol: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.usuario.id_usuario", ondelete="CASCADE"),
        nullable=False,
    )
    id_rol: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.rol.id_rol", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RolPermiso(Base):
    __tablename__ = "rol_permiso"

    id_rol_permiso: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_rol: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.rol.id_rol", ondelete="CASCADE"),
        nullable=False,
    )
    id_permiso: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.permiso.id_permiso", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UsuarioPermiso(Base):
    __tablename__ = "usuario_permiso"

    id_usuario_permiso: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.usuario.id_usuario", ondelete="CASCADE"),
        nullable=False,
    )
    id_permiso: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.permiso.id_permiso", ondelete="CASCADE"),
        nullable=False,
    )
    otorgado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    id_asignado_por: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("capricho.usuario.id_usuario", ondelete="SET NULL"),
    )
    fecha_asignacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Ciudad(Base):
    __tablename__ = "ciudad"

    id_ciudad: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    departamento: Mapped[str] = mapped_column(String(100), nullable=False)
    pais: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'Bolivia'"))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Sucursal(Base):
    __tablename__ = "sucursal"

    id_sucursal: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_ciudad: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.ciudad.id_ciudad", ondelete="RESTRICT"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    direccion: Mapped[str] = mapped_column(String(255), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(30))
    latitud: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    place_id: Mapped[str | None] = mapped_column(String(255))
    hora_apertura: Mapped[time | None] = mapped_column(Time)
    hora_cierre: Mapped[time | None] = mapped_column(Time)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Cliente(Base):
    __tablename__ = "cliente"

    id_cliente: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.usuario.id_usuario", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVO'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Empleado(Base):
    __tablename__ = "empleado"

    id_empleado: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.usuario.id_usuario", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    id_sucursal: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("capricho.sucursal.id_sucursal", ondelete="RESTRICT"),
        nullable=False,
    )
    cargo_descriptivo: Mapped[str | None] = mapped_column(String(100))
    fecha_contratacion: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    estado_laboral: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ACTIVO'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Bitacora(Base):
    __tablename__ = "bitacora"

    id_bitacora: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_tenant: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("capricho.tenant.id_tenant", ondelete="RESTRICT"),
        server_default=text("capricho.fn_tenant_actual()"),
    )
    id_usuario: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("capricho.usuario.id_usuario", ondelete="SET NULL"),
    )
    id_sesion: Mapped[str | None] = mapped_column(String(120))
    accion: Mapped[str] = mapped_column(String(20), nullable=False)
    modulo: Mapped[str] = mapped_column(String(60), nullable=False)
    entidad: Mapped[str] = mapped_column(String(80), nullable=False)
    id_registro: Mapped[str | None] = mapped_column(String(120))
    datos_anteriores: Mapped[dict | None] = mapped_column(JSONB)
    datos_nuevos: Mapped[dict | None] = mapped_column(JSONB)
    direccion_ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    origen: Mapped[str | None] = mapped_column(String(10))
    request_id: Mapped[str | None] = mapped_column(String(120))
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
