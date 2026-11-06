from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

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
    productos: list[AssistantProduct] = Field(default_factory=list)


class MessageExchange(BaseModel):
    usuario: Message
    asistente: Message
