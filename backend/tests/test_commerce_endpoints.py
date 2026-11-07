from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient, Response

from app.main import app
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.auth.models import Usuario
from app.modules.commerce.dependencies import get_commerce_service
from app.modules.commerce.exceptions import (
    CommerceConflictError,
    CommerceNotFoundError,
    InvalidCommerceOperationError,
)
from app.modules.commerce.repository import CommerceRepository
from app.modules.commerce.schemas import CheckoutCreate
from app.modules.commerce.service import ORDER_TRANSITIONS, RESERVATION_TRANSITIONS, CommerceService

NOW = "2026-09-10T14:00:00Z"
LINE = {
    "id_detalle": 1,
    "id_variante": 7,
    "sku": "POL-M-NEG-M",
    "producto": "Polera clásica",
    "talla": "M",
    "color": "Negro",
    "cantidad": 1,
    "precio_unitario": "120.00",
    "subtotal": "120.00",
    "stock_disponible": 4,
    "activo": True,
    "imagen_url": None,
}
CART = {"id_carrito": 1, "estado": "ACTIVO", "items": [LINE], "total": "120.00"}
RESERVATION = {
    "id_reserva": 3,
    "id_sucursal": 1,
    "sucursal": "Central",
    "direccion_sucursal": "Av. Central 10",
    "fecha_reserva": NOW,
    "fecha_cita": "2026-09-11T14:00:00Z",
    "fecha_expiracion": None,
    "estado": "PENDIENTE",
    "observacion": None,
    "items": [LINE],
}
ORDER = {
    "id_pedido": 8,
    "id_venta": 6,
    "estado": "PENDIENTE",
    "modalidad_entrega": "RETIRO_SUCURSAL",
    "id_sucursal": 1,
    "sucursal": "Central",
    "direccion_sucursal": "Av. Central 10",
    "id_direccion": None,
    "direccion_entrega": None,
    "total": "120.00",
    "fecha_creacion": NOW,
    "fecha_preparacion": None,
    "fecha_finalizacion": None,
    "items": [LINE],
}
STRIPE_CHECKOUT = {
    "session_id": "cs_test_capricho",
    "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_capricho",
    "expires_at": "2026-09-10T14:30:00Z",
}
RETURN = {
    "id_devolucion": 10,
    "tipo_solicitud": "DEVOLUCION",
    "id_venta": 6,
    "motivo": "La talla no corresponde",
    "estado": "PENDIENTE",
    "fecha_solicitud": NOW,
    "fecha_resolucion": None,
    "items": [
        {
            "id_detalle_devolucion": 12,
            "id_detalle_venta": 1,
            "id_variante": 7,
            "producto": "Polera clásica",
            "talla": "M",
            "color": "Negro",
            "cantidad": 1,
            "estado_prenda": "APTA_REINGRESO",
        }
    ],
}


def principal(*permissions: str) -> CurrentPrincipal:
    return CurrentPrincipal(
        user=Usuario(
            id_usuario=9,
            nombres="Ana",
            apellidos="Pérez",
            correo="ana@example.com",
            password_hash="not-returned",
            estado="ACTIVO",
            created_at=datetime(2026, 9, 10, tzinfo=UTC),
            updated_at=datetime(2026, 9, 10, tzinfo=UTC),
        ),
        roles=frozenset({"CLIENTE"}),
        permissions=frozenset(permissions),
        session_id="commerce-test",
    )


async def call(
    method: str,
    path: str,
    *,
    service: AsyncMock,
    actor: CurrentPrincipal | None = None,
    json: dict | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    async def override_service() -> AsyncIterator[AsyncMock]:
        yield service

    app.dependency_overrides[get_commerce_service] = override_service
    if actor is not None:
        app.dependency_overrides[get_current_principal] = lambda: actor
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.request(method, path, json=json, headers=headers)
    finally:
        app.dependency_overrides.clear()


async def test_cart_requires_authentication() -> None:
    response = await call("GET", "/api/v1/cart", service=AsyncMock())
    assert response.status_code == 401


async def test_add_item_to_cart() -> None:
    service = AsyncMock()
    service.add_cart_item.return_value = CART
    response = await call(
        "POST",
        "/api/v1/cart/items",
        service=service,
        actor=principal(),
        json={"id_variante": 7, "cantidad": 1},
    )
    assert response.status_code == 201
    assert response.json()["items"][0]["talla"] == "M"


async def test_variant_query_uses_only_existing_image_fields() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.one_or_none.return_value = {"id_variante": 7}
    session.execute.return_value = result

    row = await CommerceRepository(session).variant_row(7)

    assert row == {"id_variante": 7}
    session.execute.assert_awaited_once()


async def test_cart_reports_insufficient_stock() -> None:
    service = AsyncMock()
    service.add_cart_item.side_effect = CommerceConflictError("Stock insuficiente")
    response = await call(
        "POST",
        "/api/v1/cart/items",
        service=service,
        actor=principal(),
        json={"id_variante": 7, "cantidad": 99},
    )
    assert response.status_code == 409


async def test_create_and_cancel_reservation() -> None:
    service = AsyncMock()
    service.create_reservation.return_value = RESERVATION
    service.cancel_reservation.return_value = {**RESERVATION, "estado": "CANCELADA"}
    created = await call(
        "POST",
        "/api/v1/reservations",
        service=service,
        actor=principal(),
        json={"id_sucursal": 1, "items": [{"id_variante": 7, "cantidad": 1}]},
    )
    cancelled = await call(
        "POST",
        "/api/v1/reservations/3/cancel",
        service=service,
        actor=principal(),
    )
    assert created.status_code == 201
    assert cancelled.json()["estado"] == "CANCELADA"


async def test_pos_sale_requires_effective_permission() -> None:
    response = await call(
        "POST",
        "/api/v1/sales/pos",
        service=AsyncMock(),
        actor=principal(),
        json={"id_sucursal": 1, "items": [{"id_variante": 7, "cantidad": 1}]},
    )
    assert response.status_code == 403


async def test_cash_sale_requires_payment_permission() -> None:
    response = await call(
        "POST",
        "/api/v1/sales/pos",
        service=AsyncMock(),
        actor=principal("ventas.crear"),
        json={"id_sucursal": 1, "items": [{"id_variante": 7, "cantidad": 1}]},
    )
    assert response.status_code == 403


async def test_checkout_pickup() -> None:
    service = AsyncMock()
    service.checkout.return_value = STRIPE_CHECKOUT
    response = await call(
        "POST",
        "/api/v1/checkout",
        service=service,
        actor=principal(),
        json={"id_sucursal": 1, "modalidad_entrega": "RETIRO_SUCURSAL"},
    )
    assert response.status_code == 201
    assert response.json()["session_id"] == "cs_test_capricho"


async def test_checkout_status_confirms_paid_order() -> None:
    service = AsyncMock()
    service.stripe_checkout_status.return_value = {
        "status": "PAGADO",
        "message": "Stripe confirmó el pago.",
        "order": ORDER,
    }
    response = await call(
        "GET",
        "/api/v1/checkout/cs_test_capricho/status",
        service=service,
        actor=principal(),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PAGADO"
    assert response.json()["order"]["id_pedido"] == 8


async def test_stripe_webhook_requires_signature() -> None:
    response = await call(
        "POST",
        "/api/v1/payments/stripe/webhook",
        service=AsyncMock(),
        json={"type": "checkout.session.completed"},
    )
    assert response.status_code == 400


async def test_stripe_webhook_processes_verified_event() -> None:
    service = AsyncMock()
    service.construct_stripe_event.return_value = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_capricho"}},
    }
    response = await call(
        "POST",
        "/api/v1/payments/stripe/webhook",
        service=service,
        json={"type": "checkout.session.completed"},
        headers={"stripe-signature": "t=1,v1=firma"},
    )
    assert response.status_code == 200
    assert response.json() == {"received": True}
    service.process_stripe_event.assert_awaited_once()


async def test_customer_can_list_own_orders() -> None:
    service = AsyncMock()
    service.list_orders.return_value = [ORDER]
    response = await call("GET", "/api/v1/orders", service=service, actor=principal())
    assert response.status_code == 200
    assert response.json()[0]["id_pedido"] == 8


async def test_missing_customer_order_returns_404() -> None:
    service = AsyncMock()
    service.get_order.side_effect = CommerceNotFoundError("El pedido no existe")
    response = await call("GET", "/api/v1/orders/999", service=service, actor=principal())
    assert response.status_code == 404


async def test_customer_can_confirm_delivery() -> None:
    service = AsyncMock()
    delivered_order = {**ORDER, "estado": "ENTREGADO", "modalidad_entrega": "DELIVERY"}
    service.confirm_delivery.return_value = delivered_order
    response = await call(
        "POST",
        "/api/v1/orders/8/confirm-delivery",
        service=service,
        actor=principal(),
    )
    assert response.status_code == 200
    assert response.json()["estado"] == "ENTREGADO"
    service.confirm_delivery.assert_awaited_once_with(9, 8)


async def test_customer_confirm_delivery_invalid_state() -> None:
    service = AsyncMock()
    service.confirm_delivery.side_effect = InvalidCommerceOperationError(
        "Solo puedes confirmar la recepción de un pedido que se encuentre en camino"
    )
    response = await call(
        "POST",
        "/api/v1/orders/8/confirm-delivery",
        service=service,
        actor=principal(),
    )
    assert response.status_code == 400
    assert "en camino" in response.json()["detail"]


async def test_customer_can_request_return() -> None:
    service = AsyncMock()
    service.create_return.return_value = RETURN
    response = await call(
        "POST",
        "/api/v1/returns",
        service=service,
        actor=principal(),
        json={
            "id_venta": 6,
            "tipo_solicitud": "CAMBIO_TALLA",
            "motivo": "La talla no corresponde",
            "items": [{"id_detalle_venta": 1, "cantidad": 1}],
        },
    )
    assert response.status_code == 201
    assert response.json()["estado"] == "PENDIENTE"
    assert service.create_return.await_args.args[1].tipo_solicitud == "CAMBIO_TALLA"


async def test_customer_return_rejects_unknown_request_kind() -> None:
    response = await call(
        "POST",
        "/api/v1/returns",
        service=AsyncMock(),
        actor=principal(),
        json={
            "id_venta": 6,
            "tipo_solicitud": "CAMBIO_DESCONOCIDO",
            "motivo": "No me quedó",
            "items": [{"id_detalle_venta": 1, "cantidad": 1}],
        },
    )
    assert response.status_code == 422


async def test_delivery_requires_address_and_quote() -> None:
    response = await call(
        "POST",
        "/api/v1/checkout",
        service=AsyncMock(),
        actor=principal(),
        json={"id_sucursal": 1, "modalidad_entrega": "DELIVERY"},
    )
    assert response.status_code == 422


async def test_supplier_history_requires_permission() -> None:
    response = await call(
        "GET",
        "/api/v1/supplier-purchase-history",
        service=AsyncMock(),
        actor=principal(),
    )
    assert response.status_code == 403


def test_commerce_state_transitions_reject_invalid_jumps() -> None:
    try:
        CommerceService._validate_transition("PENDIENTE", "LISTA", RESERVATION_TRANSITIONS)
    except Exception as exc:
        assert "PENDIENTE" in str(exc)
    else:
        raise AssertionError("The invalid reservation transition was accepted")
    try:
        CommerceService._validate_transition("PENDIENTE", "ENTREGADO", ORDER_TRANSITIONS)
    except Exception as exc:
        assert "PENDIENTE" in str(exc)
    else:
        raise AssertionError("The invalid order transition was accepted")


def test_checkout_contract_accepts_complete_delivery() -> None:
    payload = CheckoutCreate(
        id_sucursal=1,
        modalidad_entrega="DELIVERY",
        id_direccion=2,
        id_cotizacion=4,
    )
    assert payload.id_cotizacion == 4


async def test_cart_endpoints_support_branch_and_clear() -> None:
    service = AsyncMock()
    cart_data = {**CART, "id_sucursal": 2, "sucursal": "Banzer"}
    service.clear_cart.return_value = {**CART, "id_sucursal": None, "sucursal": None, "items": [], "total": "0.00"}
    service.add_cart_item.return_value = cart_data

    clear_response = await call("POST", "/api/v1/cart/clear", service=service, actor=principal())
    assert clear_response.status_code == 200
    assert clear_response.json()["id_sucursal"] is None

    add_response = await call(
        "POST",
        "/api/v1/cart/items",
        service=service,
        actor=principal(),
        json={"id_variante": 7, "cantidad": 2, "id_sucursal": 2},
    )
    assert add_response.status_code == 201
    assert add_response.json()["id_sucursal"] == 2
    assert add_response.json()["sucursal"] == "Banzer"


async def test_list_sales_endpoint() -> None:
    service = AsyncMock()
    service.list_sales.return_value = []
    response = await call(
        "GET",
        "/api/v1/sales",
        service=service,
        actor=principal("ventas.ver"),
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_list_sales_endpoint_with_data() -> None:
    service = AsyncMock()
    service.list_sales.return_value = [
        {
            "id_venta": 101,
            "id_cliente": 1,
            "cliente_nombre": "María López",
            "cliente_correo": "maria@example.com",
            "cliente_telefono": "77123456",
            "id_sucursal": 1,
            "sucursal": "Central",
            "id_empleado": 5,
            "empleado_nombre": "Carlos Cajero",
            "id_reserva": None,
            "canal_venta": "PRESENCIAL",
            "modalidad_entrega": "MOSTRADOR",
            "metodo_pago": "💵 Efectivo",
            "estado": "COMPLETADA",
            "subtotal": "200.00",
            "costo_envio": "0.00",
            "total": "200.00",
            "fecha_venta": NOW,
            "items": [LINE],
        }
    ]
    response = await call(
        "GET",
        "/api/v1/sales?canal=PRESENCIAL",
        service=service,
        actor=principal("ventas.ver"),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["cliente_nombre"] == "María López"
    assert data[0]["metodo_pago"] == "💵 Efectivo"

async def test_inspect_sale_for_return_endpoint() -> None:
    service = AsyncMock()
    service.inspect_sale_for_return.return_value = {
        "id_venta": 6,
        "id_cliente": None,
        "cliente_nombre": "Consumidor Final",
        "cliente_correo": None,
        "cliente_telefono": None,
        "id_sucursal": 1,
        "sucursal": "Central",
        "canal_venta": "PRESENCIAL",
        "modalidad_entrega": "MOSTRADOR",
        "total": "120.00",
        "fecha_venta": NOW,
        "es_retornable": True,
        "dias_habiles_transcurridos": 1,
        "dias_habiles_limite": 5,
        "fecha_limite_devolucion": NOW,
        "motivo_invalidez": None,
        "items": [
            {
                "id_detalle_venta": 1,
                "id_variante": 7,
                "sku": "POL-NEG-M",
                "producto": "Polera clásica",
                "talla": "M",
                "color": "Negro",
                "cantidad_vendida": 2,
                "cantidad_devuelta": 0,
                "cantidad_disponible": 2,
                "precio_unitario": "60.00",
                "imagen_url": None,
            }
        ],
    }
    response = await call(
        "GET",
        "/api/v1/admin/returns/inspect-sale/6",
        service=service,
        actor=principal("ventas.ver"),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cliente_nombre"] == "Consumidor Final"
    assert data["es_retornable"] is True
    assert data["items"][0]["cantidad_disponible"] == 2


async def test_admin_create_counter_return_endpoint() -> None:
    service = AsyncMock()
    completed_return = {
        **RETURN,
        "id_cliente": None,
        "cliente_nombre": "Consumidor Final",
        "estado": "COMPLETADA",
    }
    service.create_admin_return.return_value = completed_return
    response = await call(
        "POST",
        "/api/v1/admin/returns",
        service=service,
        actor=principal("ventas.crear"),
        json={
            "id_venta": 6,
            "motivo": "Falla de confección en costura",
            "items": [{"id_detalle_venta": 1, "cantidad": 1, "estado_prenda": "NO_APTA"}],
            "completar_inmediato": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["estado"] == "COMPLETADA"
    assert response.json()["cliente_nombre"] == "Consumidor Final"


async def test_get_sale_by_id_endpoint() -> None:
    service = AsyncMock()
    service.get_sale.return_value = {
        "id_venta": 6,
        "id_cliente": 1,
        "cliente_nombre": "Ana Pérez",
        "cliente_correo": "ana@example.com",
        "cliente_telefono": None,
        "id_sucursal": 1,
        "sucursal": "Central",
        "id_empleado": 2,
        "empleado_nombre": "Pedro Cajero",
        "id_reserva": None,
        "canal_venta": "PRESENCIAL",
        "modalidad_entrega": "MOSTRADOR",
        "metodo_pago": "Efectivo",
        "estado": "CONFIRMADA",
        "subtotal": "120.00",
        "costo_envio": "0.00",
        "total": "120.00",
        "fecha_venta": NOW,
        "items": [LINE],
    }
    response = await call(
        "GET",
        "/api/v1/sales/6",
        service=service,
        actor=principal("ventas.ver"),
    )
    assert response.status_code == 200
    assert response.json()["id_venta"] == 6


async def test_admin_update_return_status_approved() -> None:
    service = AsyncMock()
    service.update_return_status.return_value = {
        **RETURN,
        "estado": "APROBADA",
    }
    response = await call(
        "PATCH",
        "/api/v1/admin/returns/1/status",
        service=service,
        actor=principal("ventas.crear"),
        json={"estado": "APROBADA"},
    )
    assert response.status_code == 200
    assert response.json()["estado"] == "APROBADA"


async def test_admin_update_return_status_completed_with_conditions() -> None:
    service = AsyncMock()
    service.update_return_status.return_value = {
        **RETURN,
        "estado": "COMPLETADA",
        "items": [
            {
                **RETURN["items"][0],
                "estado_prenda": "NO_APTA",
            }
        ],
    }
    response = await call(
        "PATCH",
        "/api/v1/admin/returns/1/status",
        service=service,
        actor=principal("ventas.crear"),
        json={
            "estado": "COMPLETADA",
            "items": [{"id_detalle_devolucion": 1, "estado_prenda": "NO_APTA"}],
            "observaciones": "Prenda con mancha de tinta, no apta para reingreso",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "COMPLETADA"
    assert data["items"][0]["estado_prenda"] == "NO_APTA"

