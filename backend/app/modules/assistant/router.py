from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.modules.assistant.schemas import (
    Conversation,
    ConversationCreate,
    Message,
    MessageCreate,
    MessageExchange,
)
from app.modules.assistant.service import AssistantService
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.reports.dependencies import get_speech_transcriber
from app.modules.reports.schemas import VoiceTranscriptionResponse
from app.modules.reports.speech import GroqSpeechTranscriber, SpeechTranscriptionError

router = APIRouter(prefix="/assistant", tags=["assistant"])


def service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> AssistantService:
    return AssistantService(session, principal)


Assistant = Annotated[AssistantService, Depends(service)]
SpeechTranscriber = Annotated[GroqSpeechTranscriber | None, Depends(get_speech_transcriber)]


@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_customer_question(
    assistant: Assistant,
    transcriber: SpeechTranscriber,
    audio: Annotated[UploadFile, File()],
):
    assistant.authorize("CLIENTE")
    if transcriber is None:
        raise HTTPException(503, "La consulta por voz no está configurada")
    content_type = (audio.content_type or "").lower().split(";", 1)[0]
    if content_type not in {
        "audio/flac",
        "audio/m4a",
        "audio/mp4",
        "audio/mpeg",
        "audio/mp3",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
        "audio/x-m4a",
        "audio/x-wav",
    }:
        raise HTTPException(415, "El formato de audio no es compatible")
    max_bytes = get_settings().voice_max_file_size_mb * 1024 * 1024
    content = await audio.read(max_bytes + 1)
    if not content:
        raise HTTPException(422, "La grabación está vacía")
    if len(content) > max_bytes:
        raise HTTPException(413, "La grabación supera el tamaño permitido")
    try:
        result = await transcriber.transcribe(
            audio.filename or "consulta.webm", content_type, content
        )
    except SpeechTranscriptionError as exc:
        raise HTTPException(503, "No pudimos transcribir la grabación en este momento") from exc
    return VoiceTranscriptionResponse(texto=result)


@router.post("/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate, assistant: Assistant):
    return await assistant.create(payload.modo)


@router.get("/conversations", response_model=list[Conversation])
async def list_conversations(assistant: Assistant):
    return await assistant.list()


@router.get("/conversations/{conversation_id}/messages", response_model=list[Message])
async def get_messages(conversation_id: UUID, assistant: Assistant):
    return await assistant.messages(conversation_id)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageExchange)
async def send_message(conversation_id: UUID, payload: MessageCreate, assistant: Assistant):
    return await assistant.send(conversation_id, payload.contenido)


@router.post("/conversations/{conversation_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_conversation(conversation_id: UUID, assistant: Assistant):
    await assistant.archive(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/conversations/{conversation_id}/messages/{message_id}/export/{file_format}")
async def export_message_report(
    conversation_id: UUID, message_id: int, file_format: Literal["pdf", "xlsx"], assistant: Assistant,
):
    content, media_type, filename = await assistant.export_report(conversation_id, message_id, file_format)
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    })
