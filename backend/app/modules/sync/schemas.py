from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.commerce.schemas import ReservationCreate, SaleCreate


class SyncDeviceRegister(BaseModel):
    id_dispositivo: UUID
    nombre: str = Field(min_length=1, max_length=100)
    plataforma: Literal["PWA", "ANDROID", "IOS"]
    version_app: str | None = Field(default=None, max_length=40)
    id_sucursal: int | None = Field(default=None, gt=0)


class SyncDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_dispositivo: UUID
    nombre: str
    plataforma: str
    version_app: str | None
    id_sucursal: int | None
    estado: str
    ultima_sincronizacion: datetime | None


class SyncOperationRequest(BaseModel):
    id_operacion: UUID
    tipo: Literal["VENTA", "RESERVA"]
    fecha_cliente: datetime
    payload: dict[str, Any]


class SyncBatchRequest(BaseModel):
    id_lote: UUID
    id_dispositivo: UUID
    fecha_cliente: datetime
    operaciones: list[SyncOperationRequest] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def operation_ids_are_unique(self) -> "SyncBatchRequest":
        ids = [item.id_operacion for item in self.operaciones]
        if len(ids) != len(set(ids)):
            raise ValueError("Cada operación del lote debe tener un UUID distinto")
        return self


class SyncOperationResponse(BaseModel):
    id_operacion: UUID
    tipo: str
    estado: str
    resultado: dict[str, Any] | None = None
    codigo_error: str | None = None
    mensaje_error: str | None = None
    procesada_at: datetime | None = None


class SyncBatchResponse(BaseModel):
    id_lote: UUID
    id_dispositivo: UUID
    estado: str
    recibido_at: datetime
    procesado_at: datetime | None
    confirmado_at: datetime | None
    total_operaciones: int
    total_aplicadas: int
    total_conflictos: int
    total_rechazadas: int
    operaciones: list[SyncOperationResponse]


class SyncConfirmationRequest(BaseModel):
    id_dispositivo: UUID


class CatalogSnapshotItem(BaseModel):
    id_variante: int
    sku: str
    producto: str
    talla: str
    color: str
    precio: Decimal
    stock_fisico: int
    stock_reservado: int
    stock_disponible: int
    updated_at: datetime | None


class CatalogSnapshotResponse(BaseModel):
    id_sucursal: int
    generado_at: datetime
    version: str
    items: list[CatalogSnapshotItem]


def parse_offline_payload(operation: SyncOperationRequest) -> SaleCreate | ReservationCreate:
    if operation.tipo == "VENTA":
        sale = SaleCreate.model_validate(operation.payload)
        if not sale.registrar_efectivo or sale.metodo_pago != "EFECTIVO":
            raise ValueError("Las ventas offline solo admiten pago en efectivo")
        if sale.referencia_pago:
            raise ValueError("Una venta offline en efectivo no admite referencia de pasarela")
        return sale
    return ReservationCreate.model_validate(operation.payload)

