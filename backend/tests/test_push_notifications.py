from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.auth.models import Usuario
from app.modules.commerce.dependencies import get_commerce_service
from app.modules.commerce.schemas import DeviceTokenResponse


def make_user(
    *,
    id_usuario: int = 1,
    nombres: str = "Carlos",
    apellidos: str = "Cliente",
    correo: str = "carlos@example.com",
) -> Usuario:
    return Usuario(
        id_usuario=id_usuario,
        nombres=nombres,
        apellidos=apellidos,
        correo=correo,
        estado="ACTIVO",
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_register_device_token_success() -> None:
    principal = CurrentPrincipal(
        user=make_user(id_usuario=10),
        roles=frozenset({"CLIENTE"}),
        permissions=frozenset(),
        session_id="session-push-1",
    )

    mock_service = AsyncMock()
    mock_service.register_device_token.return_value = DeviceTokenResponse(
        mensaje="Dispositivo registrado exitosamente para notificaciones push.",
        registrado=True,
    )

    async def override_service() -> AsyncIterator[AsyncMock]:
        yield mock_service

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_commerce_service] = override_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/notifications/devices",
                json={
                    "token": "fcm-test-token-1234567890",
                    "plataforma": "ios",
                    "dispositivo_info": "iPhone 15 Pro",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["registrado"] is True
    assert "Dispositivo registrado" in data["mensaje"]
    mock_service.register_device_token.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_device_token_unauthenticated_returns_401() -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notifications/devices",
            json={"token": "fcm-test-token-1234567890", "plataforma": "ios"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_device_token_short_token_returns_422() -> None:
    principal = CurrentPrincipal(
        user=make_user(id_usuario=10),
        roles=frozenset({"CLIENTE"}),
        permissions=frozenset(),
        session_id="session-push-2",
    )

    app.dependency_overrides[get_current_principal] = lambda: principal
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/notifications/devices",
                json={"token": "short", "plataforma": "ios"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_fcm_push_sender_dry_run() -> None:
    from app.modules.commerce.fcm_sender import FcmPushSender

    sender = FcmPushSender()
    # Empty tokens should return 0 immediately
    delivered = await sender.send_push_notification([], title="Test", body="Body")
    assert delivered == 0

    # With tokens and deep link data, returns 0 gracefully when credentials not present (dry-run)
    delivered = await sender.send_push_notification(
        ["token-1", "token-2"],
        title="Alerta de Stock Crítico",
        body="Vestido Floral alcanzó el stock mínimo",
        data={"type": "STOCK_CRITICO", "id": "42", "route": "/admin/inventario"},
    )
    assert delivered in (0, 2)


@pytest.mark.asyncio
async def test_notify_branch_staff_stock_alert() -> None:
    from app.modules.commerce.service import CommerceService

    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    mock_fcm = AsyncMock()
    mock_fcm.send_push_notification.return_value = 1

    from unittest.mock import MagicMock

    # Mock execute returning an active employee in branch 1
    mock_result = MagicMock()
    mock_result.all.return_value = [(20,)]  # id_usuario = 20
    mock_session.execute.return_value = mock_result

    # Mock user device tokens
    mock_repo.get_user_device_tokens.return_value = ["device-token-emp-1"]
    mock_repo.add.return_value = None

    service = CommerceService(mock_session, mock_repo, fcm_sender=mock_fcm)

    await service._notify_branch_staff(
        branch_id=1,
        title="Alerta de Stock Crítico",
        content="Blusa Seda roja alcanzó stock mínimo.",
        data={"type": "STOCK_CRITICO", "id": "99", "route": "/admin/inventario"},
    )

    # Repository must have added a notification for employee (user_id=20)
    mock_repo.add.assert_awaited()
    # FCM push sender must have been called with the device token and deep link
    mock_fcm.send_push_notification.assert_awaited_once()
    call_kwargs = mock_fcm.send_push_notification.await_args.kwargs
    assert call_kwargs["tokens"] == ["device-token-emp-1"]
    assert call_kwargs["title"] == "Alerta de Stock Crítico"
    assert call_kwargs["data"]["route"] == "/admin/inventario"


@pytest.mark.asyncio
async def test_notify_staff_and_admins_new_order() -> None:
    from unittest.mock import MagicMock

    from app.modules.commerce.service import CommerceService

    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    mock_fcm = AsyncMock()
    mock_fcm.send_push_notification.return_value = 1

    # Mock execute: 1st call for branch staff, 2nd call for global admins
    mock_res_branch = MagicMock()
    mock_res_branch.all.return_value = [(20,)]  # Branch staff user #20

    mock_res_admin = MagicMock()
    mock_res_admin.all.return_value = [(2,)]   # Admin user #2 (Jose Carlos)

    mock_session.execute.side_effect = [mock_res_branch, mock_res_admin]

    # Mock tokens
    mock_repo.get_user_device_tokens.side_effect = lambda uid: [f"token-user-{uid}"]
    mock_repo.add.return_value = None

    service = CommerceService(mock_session, mock_repo, fcm_sender=mock_fcm)

    await service._notify_staff_and_admins(
        branch_id=1,
        kind="NUEVO_PEDIDO",
        title="Nuevo Pedido #19 por preparar 🛍️",
        content="Flabia Domínguez realizó un pedido por Bs 200,00.",
        data={"type": "NUEVO_PEDIDO", "id": "19", "route": "/pedidos"},
    )

    # Repository should add 2 notifications (one for user 20, one for user 2)
    assert mock_repo.add.await_count == 2
    # FCM push sender called for both
    assert mock_fcm.send_push_notification.await_count == 2


@pytest.mark.asyncio
async def test_update_order_status_notifies_customer_lifecycle() -> None:
    from decimal import Decimal

    from app.modules.auth.models import Cliente, Empleado, Sucursal
    from app.modules.commerce.models import Pedido, Venta
    from app.modules.commerce.schemas import OrderResponse, OrderStatusUpdate
    from app.modules.commerce.service import CommerceService

    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    mock_fcm = AsyncMock()

    order = Pedido(
        id_pedido=19,
        id_venta=10,
        estado="PENDIENTE",
        fecha_creacion=datetime.now(UTC),
    )
    sale = Venta(
        id_venta=10,
        id_cliente=5,
        id_sucursal=1,
        total=Decimal("250.00"),
        modalidad_entrega="RETIRO_SUCURSAL",
    )
    customer = Cliente(id_cliente=5, id_usuario=42, estado="ACTIVO")
    branch = Sucursal(id_sucursal=1, nombre="Sucursal Central", direccion="Av. San Martín 456")
    employee = Empleado(id_empleado=3, id_usuario=2, id_sucursal=1, cargo_descriptivo="ENCARGADO", estado_laboral="ACTIVO")

    def get_side_effect(model, ident):
        if model is Pedido:
            return order
        if model is Venta:
            return sale
        if model is Cliente:
            return customer
        if model is Sucursal:
            return branch
        return None

    mock_repo.get.side_effect = get_side_effect
    mock_repo.employee_by_user.return_value = employee
    mock_repo.get_user_device_tokens.return_value = ["cust-fcm-token"]
    mock_repo.add.return_value = None

    service = CommerceService(mock_session, mock_repo, fcm_sender=mock_fcm)
    service._order_response = AsyncMock(return_value=OrderResponse(
        id_pedido=19,
        id_venta=10,
        estado="PREPARANDO",
        modalidad_entrega="RETIRO_SUCURSAL",
        id_sucursal=1,
        sucursal="Sucursal Central",
        direccion_sucursal="Av. San Martín 456",
        id_direccion=None,
        direccion_entrega=None,
        total=Decimal("250.00"),
        fecha_creacion=datetime.now(UTC),
        fecha_preparacion=None,
        fecha_finalizacion=None,
        items=[],
        receipt_url=None,
    ))

    # 1. Transition to PREPARANDO
    await service.update_order_status(
        user_id=2,
        order_id=19,
        payload=OrderStatusUpdate(estado="PREPARANDO"),
        all_branches=True,
    )

    assert mock_fcm.send_push_notification.await_count == 1
    call_kwargs = mock_fcm.send_push_notification.await_args.kwargs
    assert call_kwargs["tokens"] == ["cust-fcm-token"]
    assert "en preparación" in call_kwargs["title"]
    assert "Sucursal Central" in call_kwargs["body"]
    assert call_kwargs["data"]["route"] == "/pedidos/19"

    # 2. Transition to LISTO_PARA_RETIRO
    order.estado = "PREPARANDO"
    await service.update_order_status(
        user_id=2,
        order_id=19,
        payload=OrderStatusUpdate(estado="LISTO_PARA_RETIRO"),
        all_branches=True,
    )
    assert mock_fcm.send_push_notification.await_count == 2
    call_kwargs = mock_fcm.send_push_notification.await_args.kwargs
    assert "listo para retirar" in call_kwargs["title"]
    assert "Av. San Martín 456" in call_kwargs["body"]


@pytest.mark.asyncio
async def test_mark_notifications_as_read_persists_leido() -> None:
    from app.modules.commerce.models import Notificacion
    from app.modules.commerce.service import CommerceService

    mock_session = AsyncMock()
    mock_repo = AsyncMock()

    notif = Notificacion(
        id_notificacion=55,
        id_usuario=2,
        tipo="NUEVO_PEDIDO",
        canal="PUSH",
        proveedor="SISTEMA",
        contenido="Nuevo pedido por preparar",
        estado="ENVIADO",
    )

    from unittest.mock import MagicMock
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = notif
    mock_session.execute.return_value = mock_res

    service = CommerceService(mock_session, mock_repo)

    # 1. Mark single notification as read
    await service.mark_notification_as_read(user_id=2, notification_id=55, is_admin=True)
    assert notif.estado == "LEIDO"
    mock_session.commit.assert_awaited()

    # 2. Mark all as read
    await service.mark_all_notifications_as_read(user_id=2, is_admin=True)
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_notify_staff_and_admins_banzer_and_global_admin() -> None:
    from unittest.mock import MagicMock

    from app.modules.commerce.service import CommerceService

    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    mock_fcm = AsyncMock()
    mock_fcm.send_push_notification.return_value = 1

    # Branch 2 (Banzer) staff user #33 (Mario - Cajero Banzer)
    mock_res_branch = MagicMock()
    mock_res_branch.all.return_value = [(33,)]

    # Global Admin user #2 (Jose Carlos - Role ADMIN)
    mock_res_admin = MagicMock()
    mock_res_admin.all.return_value = [(2,)]

    mock_session.execute.side_effect = [mock_res_branch, mock_res_admin]
    mock_repo.get_user_device_tokens.side_effect = lambda uid: [f"token-user-{uid}"]
    mock_repo.add.return_value = None

    service = CommerceService(mock_session, mock_repo, fcm_sender=mock_fcm)

    await service._notify_staff_and_admins(
        branch_id=2,
        kind="NUEVO_PEDIDO",
        title="Nuevo Pedido #26 por preparar 🛍️",
        content="Julio Villa realizó un pedido por Bs 200,00 (Retiro en tienda - CAPRICHO STORE BANZER).",
        data={"type": "NUEVO_PEDIDO", "id": "26", "route": "/pedidos"},
    )

    # Both Mario (Cajero Banzer #33) and Admin (Jose Carlos #2) receive the notification
    assert mock_repo.add.await_count == 2
    assert mock_fcm.send_push_notification.await_count == 2





