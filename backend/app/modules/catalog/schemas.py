import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

TargetAudience = Literal["HOMBRE", "MUJER"]
ImageType = Literal["CATALOGO", "MINIATURA", "PROMOCIONAL"]
StockState = Literal["DISPONIBLE", "STOCK_BAJO", "AGOTADO"]
OfficialCategory = Literal["POLERA", "CAMISA", "POLO", "BLUSA"]


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BranchOption(BaseModel):
    id_sucursal: int
    nombre: str
    direccion: str


class CityOption(ORMResponse):
    id_ciudad: int
    nombre: str
    departamento: str
    pais: str


class BranchCreate(BaseModel):
    id_ciudad: int = Field(gt=0)
    nombre: str = Field(min_length=1, max_length=120)
    direccion: str = Field(min_length=1, max_length=255)
    telefono: str | None = Field(default=None, max_length=30)
    latitud: Decimal | None = Field(default=None, ge=-90, le=90)
    longitud: Decimal | None = Field(default=None, ge=-180, le=180)
    place_id: str | None = Field(default=None, max_length=255)
    hora_apertura: time | None = None
    hora_cierre: time | None = None
    activo: bool = True

    @field_validator("nombre", "direccion")
    @classmethod
    def clean_required_text(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("El valor no puede ser nulo")
        value = value.strip()
        if not value:
            raise ValueError("El valor no puede estar vacío")
        return value

    @field_validator("telefono", "place_id", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def valid_hours(self) -> "BranchCreate":
        if bool(self.hora_apertura) != bool(self.hora_cierre):
            raise ValueError("Debes completar ambas horas o dejar las dos vacías")
        if self.hora_apertura and self.hora_cierre and self.hora_cierre <= self.hora_apertura:
            raise ValueError("La hora de cierre debe ser posterior a la hora de apertura")
        return self


class BranchUpdate(BaseModel):
    id_ciudad: int | None = Field(default=None, gt=0)
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    direccion: str | None = Field(default=None, min_length=1, max_length=255)
    telefono: str | None = Field(default=None, max_length=30)
    latitud: Decimal | None = Field(default=None, ge=-90, le=90)
    longitud: Decimal | None = Field(default=None, ge=-180, le=180)
    place_id: str | None = Field(default=None, max_length=255)
    hora_apertura: time | None = None
    hora_cierre: time | None = None
    activo: bool | None = None

    _clean_required_text = field_validator("nombre", "direccion")(
        BranchCreate.clean_required_text.__func__
    )
    _blank_to_none = field_validator("telefono", "place_id", mode="before")(
        BranchCreate.blank_to_none.__func__
    )

    @field_validator("id_ciudad", "activo")
    @classmethod
    def required_when_present(cls, value: object) -> object:
        if value is None:
            raise ValueError("El valor no puede ser nulo")
        return value

    @model_validator(mode="after")
    def has_fields(self) -> "BranchUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class BranchResponse(ORMResponse):
    id_sucursal: int
    id_ciudad: int
    ciudad: str
    departamento: str
    pais: str
    nombre: str
    direccion: str
    telefono: str | None
    latitud: Decimal | None
    longitud: Decimal | None
    place_id: str | None
    hora_apertura: time | None
    hora_cierre: time | None
    activo: bool
    created_at: datetime
    updated_at: datetime


class VariantOption(BaseModel):
    id_variante: int
    id_producto: int
    producto: str
    sku: str
    talla: str
    color: str


class NamedCreate(BaseModel):
    nombre: str = Field(min_length=1)

    @field_validator("nombre")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value


class CategoryCreate(NamedCreate):
    nombre: OfficialCategory
    descripcion: str | None = Field(default=None, max_length=250)
    activo: bool = True

    @field_validator("nombre", mode="before")
    @classmethod
    def normalize_official_name(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class CategoryUpdate(BaseModel):
    nombre: OfficialCategory | None = None
    descripcion: str | None = Field(default=None, max_length=250)
    activo: bool | None = None

    _normalize_official_name = field_validator("nombre", mode="before")(
        CategoryCreate.normalize_official_name.__func__
    )

    @model_validator(mode="after")
    def has_fields(self) -> "CategoryUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class CategoryResponse(ORMResponse):
    id_categoria: int
    nombre: str
    descripcion: str | None
    activo: bool
    created_at: datetime
    updated_at: datetime


class BrandCreate(NamedCreate):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=250)
    pais_origen: str | None = Field(default=None, max_length=100)
    activo: bool = True


class BrandUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=250)
    pais_origen: str | None = Field(default=None, max_length=100)
    activo: bool | None = None

    @model_validator(mode="after")
    def has_fields(self) -> "BrandUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class BrandResponse(ORMResponse):
    id_marca: int
    nombre: str
    descripcion: str | None
    pais_origen: str | None
    activo: bool
    created_at: datetime
    updated_at: datetime


class SizeResponse(ORMResponse):
    id_talla: int
    codigo: Literal["XS", "S", "M", "L", "XL", "XXL"]
    orden: int
    activo: bool


class ColorCreate(NamedCreate):
    nombre: str = Field(min_length=1, max_length=60)
    codigo_hex: str | None = None
    activo: bool = True

    @field_validator("codigo_hex")
    @classmethod
    def valid_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise ValueError("codigo_hex must use #RRGGBB format")
        return value.upper()


class ColorUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    codigo_hex: str | None = None
    activo: bool | None = None

    _valid_hex = field_validator("codigo_hex")(ColorCreate.valid_hex.__func__)

    @model_validator(mode="after")
    def has_fields(self) -> "ColorUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class ColorResponse(ORMResponse):
    id_color: int
    nombre: str
    codigo_hex: str | None
    activo: bool


class SeasonCreate(NamedCreate):
    nombre: str = Field(min_length=1, max_length=100)
    anio: int | None = Field(default=None, ge=1900, le=9999)
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    activo: bool = True

    @model_validator(mode="after")
    def valid_dates(self) -> "SeasonCreate":
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin cannot be before fecha_inicio")
        return self


class SeasonUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    anio: int | None = Field(default=None, ge=1900, le=9999)
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    activo: bool | None = None

    @model_validator(mode="after")
    def valid_update(self) -> "SeasonUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin cannot be before fecha_inicio")
        return self


class SeasonResponse(ORMResponse):
    id_temporada: int
    nombre: str
    anio: int | None
    fecha_inicio: date | None
    fecha_fin: date | None
    activo: bool
    created_at: datetime
    updated_at: datetime


class CollectionCreate(NamedCreate):
    id_temporada: int | None = Field(default=None, gt=0)
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=250)
    activo: bool = True


class CollectionUpdate(BaseModel):
    id_temporada: int | None = Field(default=None, gt=0)
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=250)
    activo: bool | None = None

    @model_validator(mode="after")
    def has_fields(self) -> "CollectionUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class CollectionResponse(ORMResponse):
    id_coleccion: int
    id_temporada: int | None
    nombre: str
    descripcion: str | None
    activo: bool
    created_at: datetime
    updated_at: datetime


class ProductCreate(BaseModel):
    id_categoria: int = Field(gt=0)
    id_marca: int = Field(gt=0)
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: str | None = None
    publico_objetivo: TargetAudience
    permite_vestidor: bool = True
    activo: bool = True


class ProductUpdate(BaseModel):
    id_categoria: int | None = Field(default=None, gt=0)
    id_marca: int | None = Field(default=None, gt=0)
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    descripcion: str | None = None
    publico_objetivo: TargetAudience | None = None
    permite_vestidor: bool | None = None
    activo: bool | None = None

    @model_validator(mode="after")
    def has_fields(self) -> "ProductUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class VariantCreate(BaseModel):
    id_talla: int = Field(gt=0)
    id_color: int = Field(gt=0)
    sku: str = Field(min_length=1, max_length=80)
    codigo_barras: str | None = Field(default=None, max_length=80)
    activo: bool = True

    @field_validator("codigo_barras", mode="before")
    @classmethod
    def empty_barcode_is_null(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class VariantBatchCreate(BaseModel):
    id_color: int = Field(gt=0)
    id_tallas: list[int] = Field(min_length=1, max_length=20)
    sku_base: str = Field(min_length=1, max_length=70)

    @field_validator("sku_base")
    @classmethod
    def normalize_sku_base(cls, value: str) -> str:
        value = value.strip().upper().rstrip("-")
        if not value:
            raise ValueError("SKU base is required")
        return value

    @field_validator("id_tallas")
    @classmethod
    def unique_sizes(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError("Size identifiers must be positive")
        if len(value) != len(set(value)):
            raise ValueError("Size identifiers must be unique")
        return value


class VariantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str | None = Field(default=None, min_length=1, max_length=80)
    codigo_barras: str | None = Field(default=None, max_length=80)
    activo: bool | None = None

    @field_validator("codigo_barras", mode="before")
    @classmethod
    def empty_barcode_is_null(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def has_fields(self) -> "VariantUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class VariantResponse(ORMResponse):
    id_variante: int
    id_producto: int
    id_talla: int
    talla: str
    id_color: int
    color: str
    codigo_hex: str | None
    sku: str
    codigo_barras: str | None
    activo: bool
    stock_disponible: int | None = None
    estado_stock: StockState | None = None


class MeasurementUpsert(BaseModel):
    ancho_hombros_cm: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    ancho_pecho_cm: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    largo_prenda_cm: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    largo_manga_cm: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)


class MeasurementResponse(ORMResponse):
    id_medida: int
    id_producto: int
    id_talla: int
    talla: str
    ancho_hombros_cm: Decimal | None
    ancho_pecho_cm: Decimal | None
    largo_prenda_cm: Decimal | None
    largo_manga_cm: Decimal | None


class SeasonRelationRequest(BaseModel):
    id_temporada: int = Field(gt=0)


class CollectionRelationRequest(BaseModel):
    id_coleccion: int = Field(gt=0)


class PriceCreate(BaseModel):
    precio: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class PriceResponse(ORMResponse):
    id_historial_precio: int
    id_producto: int
    precio: Decimal
    fecha_inicio: datetime
    fecha_fin: datetime | None
    creado_por: int | None


class ProductImageCreate(BaseModel):
    id_color: int | None = Field(default=None, gt=0)
    proveedor_storage: str = Field(default="CLOUDINARY", min_length=1, max_length=30)
    public_id: str = Field(min_length=1, max_length=255)
    secure_url: HttpUrl
    tipo: ImageType = "CATALOGO"
    orden: int = Field(default=1, gt=0)
    es_principal: bool = False
    formato: str | None = Field(default=None, max_length=20)
    ancho_px: int | None = Field(default=None, gt=0)
    alto_px: int | None = Field(default=None, gt=0)


class ProductImageUpdate(BaseModel):
    id_color: int | None = Field(default=None, gt=0)
    public_id: str | None = Field(default=None, min_length=1, max_length=255)
    secure_url: HttpUrl | None = None
    tipo: ImageType | None = None
    orden: int | None = Field(default=None, gt=0)
    es_principal: bool | None = None
    formato: str | None = Field(default=None, max_length=20)
    ancho_px: int | None = Field(default=None, gt=0)
    alto_px: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def has_fields(self) -> "ProductImageUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class ProductImageResponse(ORMResponse):
    id_imagen: int
    id_producto: int
    id_color: int | None = None
    proveedor_storage: str
    public_id: str
    secure_url: str
    tipo: ImageType
    orden: int
    es_principal: bool
    formato: str | None
    ancho_px: int | None
    alto_px: int | None
    created_at: datetime


class ProductResponse(ORMResponse):
    id_producto: int
    id_categoria: int
    categoria: str
    id_marca: int
    marca: str
    nombre: str
    descripcion: str | None
    publico_objetivo: TargetAudience
    permite_vestidor: bool
    activo: bool
    precio_actual: Decimal | None
    descuento_porcentaje: Decimal | None = None
    precio_promocional: Decimal | None = None
    id_promocion: int | None = None
    promocion_nombre: str | None = None
    imagen_principal: ProductImageResponse | None
    variantes: list[VariantResponse]
    tallas_disponibles: list[str]
    colores_disponibles: list[str]
    created_at: datetime
    updated_at: datetime


class ProductPage(BaseModel):
    items: list[ProductResponse]
    page: int
    page_size: int
    total: int
    pages: int
