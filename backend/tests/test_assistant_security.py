from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile

from app.modules.assistant.catalog import ShoppingCatalog, requested_color, shopping_filters
from app.modules.assistant.providers import ProviderUnavailable, answer_with_provider
from app.modules.assistant.router import transcribe_customer_question
from app.modules.assistant.schemas import AssistantProduct, Conversation, Message
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
        (principal(roles=frozenset({"CLIENTE"}), permissions=frozenset()), "EMPRESA"),
        (principal(), "CLIENTE"),
        (principal(roles=frozenset({"SUPERADMIN"}), tenant=None), "EMPRESA"),
    ],
)
def test_mode_authorization_rejects_cross_role(user, mode):
    with pytest.raises(HTTPException) as exc:
        AssistantService(AsyncMock(), user).authorize(mode)
    assert exc.value.status_code == 403


def test_client_can_use_shopping_assistant():
    AssistantService(
        AsyncMock(), principal(roles=frozenset({"CLIENTE"}), permissions=frozenset())
    ).authorize("CLIENTE")


def test_basic_admin_can_chat_without_report_entitlement():
    AssistantService(
        AsyncMock(), principal(plan="BASICO", ai=False, permissions=frozenset())
    ).authorize("EMPRESA")


@pytest.mark.asyncio
async def test_basic_admin_report_question_does_not_query_business_data(monkeypatch):
    service = AssistantService(
        AsyncMock(), principal(plan="BASICO", ai=False, permissions=frozenset())
    )
    service.settings = SimpleNamespace(groq_api_key="test-key", groq_reports_model="test-model")
    conversation = Conversation(
        id_conversacion=uuid4(),
        modo="EMPRESA",
        proveedor="GROQ",
        modelo="test-model",
        estado="ACTIVA",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    service.get = AsyncMock(return_value=conversation)
    service.repo.messages = AsyncMock(return_value=[])
    service.repo.append_exchange = AsyncMock(
        return_value=(
            Message(
                id_mensaje=1, rol="USUARIO", contenido="ventas", created_at="2026-01-01T00:00:00Z"
            ),
            Message(id_mensaje=2, rol="ASISTENTE", contenido="", created_at="2026-01-01T00:00:00Z"),
        )
    )
    context = AsyncMock()
    provider = AsyncMock()
    monkeypatch.setattr(service, "_business_context", context)
    monkeypatch.setattr("app.modules.assistant.service.answer_with_provider", provider)

    await service.send(conversation.id_conversacion, "¿Cuánto vendimos este mes?")

    assert "plan Profesional" in service.repo.append_exchange.await_args.args[2]
    context.assert_not_awaited()
    provider.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('followup', [False, True])
async def test_professional_report_preserves_verified_boliviano_answer(monkeypatch, followup):
    service = AssistantService(AsyncMock(), principal())
    service.settings = SimpleNamespace(groq_api_key="test-key", groq_reports_model="test-model")
    conversation = Conversation(
        id_conversacion=uuid4(), modo="EMPRESA", proveedor="GROQ", modelo="test-model", estado="ACTIVA",
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    service.get = AsyncMock(return_value=conversation)
    service.repo.messages = AsyncMock(return_value=[])
    if followup:
        service.repo.messages.return_value = [
            Message(id_mensaje=1, rol="USUARIO", contenido="Producto más vendido de septiembre de 2026", created_at="2026-01-01T00:00:00Z"),
            Message(id_mensaje=2, rol="ASISTENTE", contenido="¿Quieres que revisemos también las ventas por sucursal?", created_at="2026-01-01T00:00:00Z"),
        ]
    service._business_context = AsyncMock(return_value='{"respuesta_verificada":"21 unidades e ingresos de **Bs 4.200,00**."}')
    service.repo.append_exchange = AsyncMock(return_value=(
        Message(id_mensaje=1, rol="USUARIO", contenido="ventas", created_at="2026-01-01T00:00:00Z"),
        Message(id_mensaje=2, rol="ASISTENTE", contenido="", created_at="2026-01-01T00:00:00Z"),
    ))
    provider = AsyncMock(return_value="4.200 euros")
    monkeypatch.setattr("app.modules.assistant.service.answer_with_provider", provider)
    await service.send(conversation.id_conversacion, "Sí" if followup else "¿Qué producto fue el más vendido?")
    if followup:
        assert 'septiembre de 2026' in service._business_context.await_args.args[0]
        assert 'ventas agrupadas por sucursal' in service._business_context.await_args.args[0]
    assert service.repo.append_exchange.await_args.args[2] == '21 unidades e ingresos de **Bs 4.200,00**.'
    assert service.repo.append_exchange.await_args.kwargs['report_restricted'] is True
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_basic_admin_cannot_read_saved_professional_report():
    service = AssistantService(
        AsyncMock(), principal(plan="BASICO", ai=False, permissions=frozenset())
    )
    conversation = Conversation(
        id_conversacion=uuid4(),
        modo="EMPRESA",
        proveedor="GROQ",
        modelo="test-model",
        estado="ACTIVA",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    service.get = AsyncMock(return_value=conversation)
    service.repo.messages = AsyncMock(
        return_value=[
            Message(
                id_mensaje=2,
                rol="ASISTENTE",
                contenido="Ingresos: Bs 500",
                requiere_reportes_ia=True,
                created_at="2026-01-01T00:00:00Z",
            )
        ]
    )

    messages = await service.messages(conversation.id_conversacion)

    assert "500" not in messages[0].contenido
    assert "plan Profesional" in messages[0].contenido


@pytest.mark.asyncio
async def test_customer_voice_transcribes_only_after_authorization():
    transcriber = SimpleNamespace(transcribe=AsyncMock(return_value="Busco una polera verde"))
    audio = UploadFile(
        file=BytesIO(b"audio-data"),
        filename="consulta.webm",
        headers={"content-type": "audio/webm"},
    )
    customer = AssistantService(
        AsyncMock(), principal(roles=frozenset({"CLIENTE"}), permissions=frozenset())
    )
    result = await transcribe_customer_question(customer, transcriber, audio)
    assert result.texto == "Busco una polera verde"
    transcriber.transcribe.assert_awaited_once_with("consulta.webm", "audio/webm", b"audio-data")

    admin = AssistantService(AsyncMock(), principal())
    with pytest.raises(HTTPException) as exc:
        await transcribe_customer_question(admin, transcriber, audio)
    assert exc.value.status_code == 403


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


@pytest.mark.asyncio
async def test_existing_conversation_uses_current_configured_model(monkeypatch):
    service = AssistantService(
        AsyncMock(), principal(roles=frozenset({"CLIENTE"}), permissions=frozenset())
    )
    service.settings = SimpleNamespace(
        gemini_api_key="test-key", gemini_chat_model="gemini-3.5-flash"
    )
    conversation = Conversation(
        id_conversacion=uuid4(),
        modo="CLIENTE",
        proveedor="GEMINI",
        modelo="gemini-2.5-flash",
        estado="ACTIVA",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    service.get = AsyncMock(return_value=conversation)
    service.repo.messages = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.modules.assistant.service.ShoppingCatalog.for_question",
        AsyncMock(return_value=[]),
    )
    messages = (
        Message(id_mensaje=1, rol="USUARIO", contenido="hola", created_at="2026-01-01T00:00:00Z"),
        Message(id_mensaje=2, rol="ASISTENTE", contenido="hola", created_at="2026-01-01T00:00:00Z"),
    )
    service.repo.append_exchange = AsyncMock(return_value=messages)
    provider = AsyncMock(return_value='{"mensaje":"¡Hola! ¿Qué prenda buscas?","producto_ids":[]}')
    monkeypatch.setattr("app.modules.assistant.service.answer_with_provider", provider)

    await service.send(conversation.id_conversacion, "hola")

    assert provider.await_args.kwargs["model"] == "gemini-3.5-flash"
    service.repo.append_exchange.assert_awaited_once_with(
        conversation.id_conversacion, "hola", "¡Hola! ¿Qué prenda buscas?", "gemini-3.5-flash", []
    )


def test_shopping_filters_extract_category_budget_and_size():
    assert shopping_filters(
        "Quería recomendación de polera rondando precio de 200 a máximo 300 Bs en talla M"
    ) == ("POLERA", 200, 300, "M")


def test_requested_color_recognizes_green_without_matching_other_words():
    assert requested_color("¿Cuál de estos tiene color verde?") == "verde"
    assert requested_color("¿Tienes algo café?") == "cafe"
    assert requested_color("¿Cuál es el precio?") is None


@pytest.mark.asyncio
async def test_color_followup_filters_only_previous_products():
    catalog = ShoppingCatalog(AsyncMock(), 7)
    blue = AssistantProduct(
        id_producto=1,
        nombre="Polo azul",
        categoria="POLO",
        marca="Marca",
        precio="200",
        imagen_url=None,
        tallas=["M"],
        colores=["Azul"],
        permite_vestidor=False,
    )
    green = blue.model_copy(
        update={"id_producto": 2, "nombre": "Polo verde", "colores": ["Verde oliva"]}
    )
    catalog.available = AsyncMock(return_value=[blue, green])

    result = await catalog.for_question(
        "¿Cuál de estos tiene color verde?",
        prioritize_ids=[1, 2],
        restrict_to_prior=True,
    )

    assert result == [green]
    catalog.available.assert_awaited_once_with(category=None, ids=[1, 2])


@pytest.mark.asyncio
async def test_color_followup_without_match_does_not_claim_green_product(monkeypatch):
    service = AssistantService(
        AsyncMock(), principal(roles=frozenset({"CLIENTE"}), permissions=frozenset())
    )
    service.settings = SimpleNamespace(
        gemini_api_key="test-key", gemini_chat_model="gemini-3.5-flash"
    )
    conversation = Conversation(
        id_conversacion=uuid4(),
        modo="CLIENTE",
        proveedor="GEMINI",
        modelo="gemini-3.5-flash",
        estado="ACTIVA",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    previous = Message(
        id_mensaje=2,
        rol="ASISTENTE",
        contenido="Mira estas opciones.",
        created_at="2026-01-01T00:00:00Z",
        producto_ids=[7],
    )
    service.get = AsyncMock(return_value=conversation)
    service.repo.messages = AsyncMock(return_value=[previous])
    service.repo.append_exchange = AsyncMock(
        return_value=(
            Message(
                id_mensaje=3, rol="USUARIO", contenido="verde", created_at="2026-01-01T00:00:00Z"
            ),
            Message(id_mensaje=4, rol="ASISTENTE", contenido="", created_at="2026-01-01T00:00:00Z"),
        )
    )
    catalog = AsyncMock(return_value=[])
    monkeypatch.setattr("app.modules.assistant.service.ShoppingCatalog.for_question", catalog)
    provider = AsyncMock()
    monkeypatch.setattr("app.modules.assistant.service.answer_with_provider", provider)

    result = await service.send(conversation.id_conversacion, "¿Cuál de estos tiene color verde?")

    assert result.asistente.productos == []
    assert "No encontré" in service.repo.append_exchange.await_args.args[2]
    catalog.assert_awaited_once_with(
        "¿Cuál de estos tiene color verde?",
        prioritize_ids=[7],
        limit=40,
        restrict_to_prior=True,
    )
    provider.assert_not_awaited()


@pytest.mark.parametrize(
    "question",
    ["¿Hay promociones el día de hoy?", "¿Existe descuento de alguna prenda?", "¿Tienen ofertas?"],
)
def test_promotion_questions_are_recognized(question):
    assert AssistantService._promotion_intent(question)


@pytest.mark.asyncio
async def test_promotion_question_uses_verified_discounted_products(monkeypatch):
    service = AssistantService(
        AsyncMock(), principal(roles=frozenset({"CLIENTE"}), permissions=frozenset())
    )
    service.settings = SimpleNamespace(
        gemini_api_key="test-key", gemini_chat_model="gemini-3.5-flash"
    )
    conversation = Conversation(
        id_conversacion=uuid4(),
        modo="CLIENTE",
        proveedor="GEMINI",
        modelo="gemini-3.5-flash",
        estado="ACTIVA",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    discounted = AssistantProduct(
        id_producto=7,
        nombre="Polera azul",
        categoria="POLERA",
        marca="Marca",
        precio="240.00",
        precio_original="300.00",
        descuento_porcentaje="20",
        promocion_nombre="Oferta de hoy",
        imagen_url=None,
        tallas=["M"],
        colores=["Azul"],
        permite_vestidor=False,
    )
    regular = discounted.model_copy(update={"id_producto": 8, "descuento_porcentaje": None})
    service.get = AsyncMock(return_value=conversation)
    service.repo.messages = AsyncMock(return_value=[])
    service.repo.append_exchange = AsyncMock(
        return_value=(
            Message(
                id_mensaje=1,
                rol="USUARIO",
                contenido="¿Hay promociones?",
                created_at="2026-01-01T00:00:00Z",
            ),
            Message(
                id_mensaje=2, rol="ASISTENTE", contenido="Sí", created_at="2026-01-01T00:00:00Z"
            ),
        )
    )
    monkeypatch.setattr(
        "app.modules.assistant.service.ShoppingCatalog.for_question",
        AsyncMock(return_value=[regular, discounted]),
    )
    provider = AsyncMock()
    monkeypatch.setattr("app.modules.assistant.service.answer_with_provider", provider)

    result = await service.send(conversation.id_conversacion, "¿Hay promociones hoy?")

    assert result.asistente.productos == [discounted]
    assert "descuento" in service.repo.append_exchange.await_args.args[2]
    service.repo.append_exchange.assert_awaited_once()
    assert service.repo.append_exchange.await_args.args[-1] == [7]
    provider.assert_not_awaited()


def test_shopping_answer_accepts_only_verified_products_and_strips_prices():
    product = AssistantProduct(
        id_producto=7,
        nombre="Polera azul",
        categoria="POLERA",
        marca="Marca",
        precio="250.00",
        imagen_url=None,
        tallas=["M"],
        colores=["Azul"],
        permite_vestidor=True,
    )
    message, selected = AssistantService._shopping_answer(
        '{"mensaje":"La Polera azul cuesta Bs 3", "producto_ids":[999,7]}',
        [product],
        "Busco una polera de 200 a 300 Bs",
    )
    assert selected == [product]
    assert "Bs 3" not in message
    assert "Polera azul" not in message


@pytest.mark.asyncio
async def test_history_reloads_current_verified_product_cards(monkeypatch):
    service = AssistantService(
        AsyncMock(), principal(roles=frozenset({"CLIENTE"}), permissions=frozenset())
    )
    conversation = Conversation(
        id_conversacion=uuid4(),
        modo="CLIENTE",
        proveedor="GEMINI",
        modelo="gemini-3.5-flash",
        estado="ACTIVA",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    product = AssistantProduct(
        id_producto=7,
        nombre="Polera azul",
        categoria="POLERA",
        marca="Marca",
        precio="250.00",
        imagen_url=None,
        tallas=["M"],
        colores=["Azul"],
        permite_vestidor=True,
    )
    message = Message(
        id_mensaje=2,
        rol="ASISTENTE",
        contenido="Mira estas opciones.",
        created_at="2026-01-01T00:00:00Z",
        producto_ids=[7],
    )
    service.get = AsyncMock(return_value=conversation)
    service.repo.messages = AsyncMock(return_value=[message])
    catalog = AsyncMock(return_value=[product])
    monkeypatch.setattr("app.modules.assistant.service.ShoppingCatalog.for_ids", catalog)

    result = await service.messages(conversation.id_conversacion)

    assert result[0].productos == [product]
    catalog.assert_awaited_once_with([7])
