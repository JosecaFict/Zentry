from datetime import datetime
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


class Message(BaseModel):
    id_mensaje: int
    rol: Literal["USUARIO", "ASISTENTE"]
    contenido: str
    created_at: datetime


class MessageExchange(BaseModel):
    usuario: Message
    asistente: Message
