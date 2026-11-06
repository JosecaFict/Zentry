from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.assistant.providers import ProviderUnavailable, answer_with_provider
from app.modules.assistant.schemas import Conversation
from app.modules.assistant.service import AssistantService


def principal(
    *,
    roles=frozenset({"ADMIN"}),
    plan="PROFESIONAL",
    ai=True,
    tenant=7,
    permissions=frozenset({"ventas.ver", "inventario.ver"}),
):
    return SimpleNamespace(
        id_tenant=tenant,
        user=SimpleNamespace(id_usuario=91),
        roles=roles,
        plan_codigo=plan,
        permite_reportes_ia=ai,
        permissions=permissions,
    )


@pytest.mark.parametrize(
    "user,mode",
    [
        (principal(plan="BASICO", ai=False), "EMPRESA"),
        (principal(roles=frozenset({"CLIENTE"}), permissions=frozenset()), "EMPRESA"),
        (principal(), "CLIENTE"),
        (principal(roles=frozenset({"SUPERADMIN"}), tenant=None), "EMPRESA"),
    ],
)
def test_mode_authorization_rejects_cross_role_and_plan(user, mode):
    with pytest.raises(HTTPException) as exc:
        AssistantService(AsyncMock(), user).authorize(mode)
    assert exc.value.status_code == 403


def test_client_can_use_shopping_assistant():
    AssistantService(
        AsyncMock(), principal(roles=frozenset({"CLIENTE"}), permissions=frozenset())
    ).authorize("CLIENTE")


@pytest.mark.asyncio
async def test_conversation_from_other_owner_is_not_visible():
    service = AssistantService(AsyncMock(), principal())
    service.repo.get = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        await service.get(uuid4())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_archived_conversation_rejects_new_message():
    service = AssistantService(AsyncMock(), principal())
    conversation = Conversation(
        id_conversacion=uuid4(),
        modo="EMPRESA",
        proveedor="GROQ",
        modelo="test",
        estado="ARCHIVADA",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    service.get = AsyncMock(return_value=conversation)
    with pytest.raises(HTTPException) as exc:
        await service.send(conversation.id_conversacion, "ventas")
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_provider_error_does_not_expose_api_key(monkeypatch):
    class BrokenClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            raise ValueError("secret-key-from-provider")

    monkeypatch.setattr("app.modules.assistant.providers.httpx.AsyncClient", BrokenClient)
    with pytest.raises(ProviderUnavailable) as exc:
        await answer_with_provider(
            provider="GEMINI",
            model="gemini-2.5-flash",
            api_key="secret-key-from-provider",
            system="safe",
            history=[{"role": "user", "content": "hola"}],
        )
    assert "secret-key" not in str(exc.value)
