from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

Mode = Literal["EMPRESA", "CLIENTE"]


class ConversationCreate(BaseModel):
    modo: Mode


class Conversation(BaseModel):
    id_conversacion: UUID
    modo: Mode
    proveedor: Literal["GROQ", "GEMINI"]
    modelo: str
    estado: Literal["ACTIVA", "ARCHIVADA"]
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    contenido: str = Field(min_length=1, max_length=4000)


class AssistantProduct(BaseModel):
    id_producto: int
    nombre: str
    categoria: str
    marca: str
    precio: Decimal
    precio_original: Decimal | None = None
    descuento_porcentaje: Decimal | None = None
    promocion_nombre: str | None = None
    imagen_url: str | None
    tallas: list[str]
    colores: list[str]
    permite_vestidor: bool


class Message(BaseModel):
    id_mensaje: int
    rol: Literal["USUARIO", "ASISTENTE"]
    contenido: str
    created_at: datetime
    producto_ids: list[int] = Field(default_factory=list, exclude=True)
    requiere_reportes_ia: bool = Field(default=False, exclude=True)
    reporte_snapshot: dict | None = Field(default=None, exclude=True)
    productos: list[AssistantProduct] = Field(default_factory=list)

    @computed_field
    @property
    def reporte_exportable(self) -> bool:
        return self.rol == "ASISTENTE" and self.requiere_reportes_ia and self.reporte_snapshot is not None


class MessageExchange(BaseModel):
    usuario: Message
    asistente: Message
