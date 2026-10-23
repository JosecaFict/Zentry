from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator

from app.core.security import validate_password_strength


class PlatformOverview(BaseModel):
    tenants_total: int
    tenants_activos: int
    tenants_suspendidos: int
    sucursales_activas: int
    suscripciones_por_vencer: int
    suscripciones_en_gracia: int
    suscripciones_suspendidas: int


class TenantContextResponse(BaseModel):
    id_tenant: int
    nombre: str
    slug: str
    logo_url: str | None
    color_primario: str = "#064FE8"
    color_primario_oscuro: str = "#0039B8"
    estado: str
    subscription_estado: str | None = None
    fecha_fin: date | None = None
    fecha_fin_gracia: date | None = None
    dias_para_vencimiento: int | None = None


class TenantPublicResponse(BaseModel):
    nombre: str
    slug: str
    logo_url: str | None
    color_primario: str = "#064FE8"
    color_primario_oscuro: str = "#0039B8"


class TenantBrandUpdate(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    logo_url: str | None = Field(default=None, max_length=500)
    color_primario: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    color_primario_oscuro: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("nombre", "logo_url")
    @classmethod
    def strip_brand_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PlanResponse(BaseModel):
    id_plan: int
    codigo: str
    nombre: str
    max_sucursales_activas: int
    max_usuarios_internos: int
    max_productos_activos: int
    almacenamiento_mb: int
    precio_mensual: Decimal
    precio_anual: Decimal
    permite_reportes_convencionales: bool
    permite_reportes_ia: bool
    permite_offline: bool
    activo: bool


class TenantListItem(BaseModel):
    id_tenant: int
    nombre: str
    slug: str
    logo_url: str | None
    estado: str
    plan_codigo: str | None
    plan_nombre: str | None
    subscription_estado: str | None
    fecha_fin: date | None
    sucursales_activas: int
    created_at: datetime


class TenantDetail(TenantListItem):
    usuarios: int
    administradores: int
    razon_social: str | None = None
    nit: str | None = None
    correo_contacto: str | None = None
    telefono_contacto: str | None = None
    id_plan: int | None = None
    color_primario: str = "#064FE8"
    color_primario_oscuro: str = "#0039B8"
    modalidad: str | None = None
    precio_acordado: Decimal | None = None
    proxima_renovacion: date | None = None
    fecha_fin_gracia: date | None = None
    max_sucursales_activas: int | None = None
    max_usuarios_internos: int | None = None
    max_productos_activos: int | None = None
    almacenamiento_mb: int | None = None
    productos_activos: int = 0
    usuarios_internos: int = 0


class TenantAdminCreate(BaseModel):
    nombres: str = Field(min_length=1, max_length=100)
    apellidos: str = Field(min_length=1, max_length=100)
    correo: EmailStr
    telefono: str | None = Field(default=None, max_length=30)
    ci: str | None = Field(default=None, max_length=30)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: SecretStr) -> SecretStr:
        validate_password_strength(value.get_secret_value())
        return value


class TenantCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=100)
    razon_social: str | None = Field(default=None, max_length=180)
    nit: str | None = Field(default=None, max_length=40)
    correo_contacto: EmailStr | None = None
    telefono_contacto: str | None = Field(default=None, max_length=30)
    logo_url: str | None = Field(default=None, max_length=500)
    color_primario: str = Field(default="#064FE8", pattern=r"^#[0-9A-Fa-f]{6}$")
    color_primario_oscuro: str = Field(default="#0039B8", pattern=r"^#[0-9A-Fa-f]{6}$")
    id_plan: int = Field(gt=0)
    modalidad: Literal["MENSUAL", "ANUAL"] = "MENSUAL"
    fecha_fin: date | None = None
    administrador: TenantAdminCreate

    @field_validator("nombre", "razon_social", "nit", "telefono_contacto", "logo_url")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TenantUpdate(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    razon_social: str | None = Field(default=None, max_length=180)
    nit: str | None = Field(default=None, max_length=40)
    correo_contacto: EmailStr | None = None
    telefono_contacto: str | None = Field(default=None, max_length=30)
    logo_url: str | None = Field(default=None, max_length=500)
    color_primario: str = Field(default="#064FE8", pattern=r"^#[0-9A-Fa-f]{6}$")
    color_primario_oscuro: str = Field(default="#0039B8", pattern=r"^#[0-9A-Fa-f]{6}$")
    id_plan: int = Field(gt=0)
    modalidad: Literal["MENSUAL", "ANUAL"] = "MENSUAL"
    fecha_fin: date | None = None

    @field_validator("nombre", "razon_social", "nit", "telefono_contacto", "logo_url")
    @classmethod
    def strip_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TenantStatusUpdate(BaseModel):
    estado: Literal["ACTIVO", "SUSPENDIDO"]


class SubscriptionPaymentCreate(BaseModel):
    modalidad: Literal["MENSUAL", "ANUAL"]
    metodo_pago: Literal["TRANSFERENCIA", "QR", "EFECTIVO", "OTRO"]
    referencia: str | None = Field(default=None, max_length=120)
    fecha_pago: date = Field(default_factory=date.today)


class SubscriptionPaymentResponse(BaseModel):
    id_payment: int
    importe: Decimal
    moneda: str
    metodo_pago: str
    referencia: str | None
    fecha_pago: date
    estado: str
    created_at: datetime
