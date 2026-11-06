from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

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

router = APIRouter(prefix="/assistant", tags=["assistant"])


def service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> AssistantService:
    return AssistantService(session, principal)


Assistant = Annotated[AssistantService, Depends(service)]


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
