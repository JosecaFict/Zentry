from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.auth.models import Cliente, Usuario
from app.modules.commerce.exceptions import CommerceConflictError
from app.modules.commerce.models import (
    Carrito,
    DetalleCarrito,
    MetodoPago,
    Pago,
    Pedido,
    TransaccionPasarela,
    Venta,
)
from app.modules.commerce.schemas import CheckoutCreate
from app.modules.commerce.service import CommerceService


def checkout_records():
    transaction = TransaccionPasarela(
        id_transaccion=15,
        id_pago=12,
        proveedor="STRIPE",
        external_session_id="cs_test_capricho",
        estado="OPEN",
        monto=Decimal("240.00"),
        moneda="BOB",
        respuesta_resumen={"cart_id": 3, "order_id": 8},
    )
    payment = Pago(
        id_pago=12,
        id_venta=6,
        id_metodo_pago=2,
        monto=Decimal("240.00"),
        moneda="BOB",
        estado="PROCESANDO",
    )
    sale = Venta(
        id_venta=6,
        id_cliente=4,
        id_sucursal=1,
        canal_venta="WEB",
        modalidad_entrega="RETIRO_SUCURSAL",
        estado="PENDIENTE",
        subtotal=Decimal("240.00"),
        descuento_total=Decimal("0"),
        costo_envio=Decimal("0"),
        total=Decimal("240.00"),
    )
    order = Pedido(id_pedido=8, id_venta=6, estado="PENDIENTE")
    return transaction, payment, sale, order


async def test_checkout_creates_stripe_session_from_server_prices() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    gateway = AsyncMock()
    customer = Cliente(id_cliente=4, id_usuario=9, estado="ACTIVO")
    cart = Carrito(id_carrito=3, id_cliente=4, estado="ACTIVO")
    detail = DetalleCarrito(id_detalle_carrito=5, id_carrito=3, id_variante=7, cantidad=2)
    sale = checkout_records()[2]
    method = MetodoPago(id_metodo_pago=2, codigo="STRIPE", nombre="Stripe", tipo="PASARELA")
    repository.customer_by_user.return_value = customer
    repository.active_cart.return_value = cart
    repository.cart_details.return_value = [detail]
    repository.payment_method.return_value = method
    repository.get.return_value = Usuario(id_usuario=9, correo="ana@example.com")

    async def add(entity):
        if isinstance(entity, Pedido):
            entity.id_pedido = 8
        elif isinstance(entity, Pago):
            entity.id_pago = 12
        elif isinstance(entity, TransaccionPasarela):
            entity.id_transaccion = 15
        return entity

    repository.add.side_effect = add
    gateway.create_session.return_value = {
        "id": "cs_test_capricho",
        "url": "https://checkout.stripe.com/c/pay/cs_test_capricho",
        "status": "open",
    }
    service = CommerceService(session, repository, stripe_gateway=gateway)
    service._create_sale = AsyncMock(return_value=sale)
    service._sale_response = AsyncMock(
        return_value=SimpleNamespace(
            items=[
                SimpleNamespace(
                    producto="Polo Classic Fit",
                    color="Azul marino",
                    talla="S",
                    precio_unitario=Decimal("120.00"),
                    cantidad=2,
                )
            ]
        )
    )

    result = await service.checkout(
        9,
        CheckoutCreate(
            id_sucursal=1,
            modalidad_entrega="RETIRO_SUCURSAL",
            return_url="https://tienda.capricho.com",
        ),
    )

    assert result.session_id == "cs_test_capricho"
    assert cart.estado == "CONVERTIDO"
    params = gateway.create_session.await_args.kwargs
    assert params["customer_email"] == "ana@example.com"
    assert params["payment_intent_data"]["receipt_email"] == "ana@example.com"
    assert params["success_url"] == "https://tienda.capricho.com/checkout?session_id={CHECKOUT_SESSION_ID}"
    assert params["cancel_url"] == "https://tienda.capricho.com/checkout?pago_cancelado=1"
    assert params["line_items"][0]["price_data"]["unit_amount"] == 12000
    assert params["line_items"][0]["quantity"] == 2
    assert params["metadata"] == {"payment_id": "12", "sale_id": "6", "order_id": "8"}
    session.commit.assert_awaited_once()


async def test_successful_stripe_session_marks_purchase_paid_once() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    transaction, payment, sale, order = checkout_records()
    customer = Cliente(id_cliente=4, id_usuario=9, estado="ACTIVO")
    cart = Carrito(id_carrito=3, id_cliente=4, id_sucursal=1, estado="CONVERTIDO")
    repository.gateway_transaction_by_session.return_value = transaction
    repository.payment.return_value = payment
    repository.order_by_sale.return_value = order

    def get_side_effect(model, _identity):
        if model is Venta:
            return sale
        if model is Carrito:
            return cart
        return customer

    repository.get.side_effect = get_side_effect
    service = CommerceService(session, repository, stripe_gateway=AsyncMock())
    service._notify = AsyncMock()
    stripe_session = {
        "id": "cs_test_capricho",
        "payment_status": "paid",
        "status": "complete",
        "amount_total": 24000,
        "currency": "bob",
        "payment_intent": {
            "id": "pi_capricho",
            "latest_charge": {
                "receipt_url": "https://pay.stripe.com/receipts/acct_123/ch_123/rcpt_123"
            },
        },
        "customer": "cus_capricho",
    }

    await service._complete_stripe_checkout(stripe_session)
    await service._complete_stripe_checkout(stripe_session)

    assert payment.estado == "PAGADO"
    assert sale.estado == "PAGADA"
    assert transaction.external_payment_id == "pi_capricho"
    assert transaction.respuesta_resumen["receipt_url"] == "https://pay.stripe.com/receipts/acct_123/ch_123/rcpt_123"
    assert cart.id_sucursal is None
    repository.clear_cart_items.assert_awaited_once_with(3)
    session.commit.assert_awaited_once()
    service._notify.assert_awaited_once()


async def test_stripe_amount_must_match_pending_payment() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    transaction, payment, sale, order = checkout_records()
    repository.gateway_transaction_by_session.return_value = transaction
    repository.payment.return_value = payment
    repository.order_by_sale.return_value = order
    repository.get.return_value = sale
    service = CommerceService(session, repository, stripe_gateway=AsyncMock())

    with pytest.raises(CommerceConflictError):
        await service._complete_stripe_checkout(
            {
                "id": "cs_test_capricho",
                "payment_status": "paid",
                "amount_total": 23999,
                "currency": "bob",
            }
        )

    assert payment.estado == "PROCESANDO"
    session.commit.assert_not_awaited()


async def test_expired_stripe_session_restores_stock_and_cart() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    transaction, payment, sale, order = checkout_records()
    repository.gateway_transaction_by_session.return_value = transaction
    repository.payment.return_value = payment
    repository.order_by_sale.return_value = order
    repository.get.return_value = sale
    service = CommerceService(session, repository, stripe_gateway=AsyncMock())
    service._restore_sale_stock = AsyncMock()
    service._restore_checkout_cart = AsyncMock()

    await service._cancel_stripe_checkout("cs_test_capricho")

    assert payment.estado == "CANCELADO"
    assert sale.estado == "ANULADA"
    assert order.estado == "CANCELADO"
    service._restore_sale_stock.assert_awaited_once()
    service._restore_checkout_cart.assert_awaited_once_with(transaction)
    session.commit.assert_awaited_once()


async def test_stripe_checkout_gateway_uses_to_dict(monkeypatch) -> None:
    import stripe

    from app.integrations.stripe_checkout import StripeCheckoutGateway

    class FakeSession:
        def __init__(self, data: dict):
            self._data = data

        def to_dict(self):
            return self._data

    fake_session = FakeSession({"id": "cs_test_123", "url": "https://stripe.com/test"})

    async def fake_create_async(**kwargs):
        return fake_session

    async def fake_retrieve_async(sid, **kwargs):
        return fake_session

    async def fake_expire_async(sid, **kwargs):
        return fake_session

    def fake_construct_event(payload, sig, secret):
        return fake_session

    monkeypatch.setattr(stripe.checkout.Session, "create_async", fake_create_async)
    monkeypatch.setattr(stripe.checkout.Session, "retrieve_async", fake_retrieve_async)
    monkeypatch.setattr(stripe.checkout.Session, "expire_async", fake_expire_async)
    monkeypatch.setattr(stripe.Webhook, "construct_event", fake_construct_event)

    gateway = StripeCheckoutGateway(secret_key="sk_test_123", webhook_secret="whsec_123")
    created = await gateway.create_session(customer="cus_123")
    assert created == {"id": "cs_test_123", "url": "https://stripe.com/test"}

    retrieved = await gateway.retrieve_session("cs_test_123")
    assert retrieved == {"id": "cs_test_123", "url": "https://stripe.com/test"}

    expired = await gateway.expire_session("cs_test_123")
    assert expired == {"id": "cs_test_123", "url": "https://stripe.com/test"}

    event = gateway.construct_event(b"{}", "sig")
    assert event == {"id": "cs_test_123", "url": "https://stripe.com/test"}


async def test_stripe_checkout_status_completes_paid_and_returns_receipt_url() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    gateway = AsyncMock()
    transaction, payment, sale, order = checkout_records()
    customer = Cliente(id_cliente=4, id_usuario=9, estado="ACTIVO")
    cart = Carrito(id_carrito=3, id_cliente=4, id_sucursal=1, estado="CONVERTIDO")
    repository.gateway_transaction_by_session.return_value = transaction
    repository.payment.return_value = payment
    repository.order_by_sale.return_value = order

    def get_side_effect(model, _identity):
        if model is Venta:
            return sale
        if model is Carrito:
            return cart
        return customer

    repository.get.side_effect = get_side_effect
    gateway.retrieve_session.return_value = {
        "id": "cs_test_capricho",
        "payment_status": "paid",
        "status": "complete",
        "amount_total": 24000,
        "currency": "bob",
        "payment_intent": {
            "id": "pi_capricho",
            "latest_charge": {
                "receipt_url": "https://pay.stripe.com/receipts/acct_test/ch_test/rcpt_test"
            },
        },
    }
    from datetime import UTC, datetime

    from app.modules.commerce.schemas import OrderResponse

    mock_order = OrderResponse(
        id_pedido=8,
        id_venta=6,
        estado="PENDIENTE",
        modalidad_entrega="RETIRO_SUCURSAL",
        id_sucursal=1,
        sucursal="Central",
        direccion_sucursal="Av. Principal 123",
        id_direccion=None,
        direccion_entrega=None,
        total=Decimal("240.00"),
        fecha_creacion=datetime.now(UTC),
        fecha_preparacion=None,
        fecha_finalizacion=None,
        items=[],
        receipt_url="https://pay.stripe.com/receipts/acct_test/ch_test/rcpt_test",
    )
    service = CommerceService(session, repository, stripe_gateway=gateway)
    service._order_response = AsyncMock(return_value=mock_order)
    service._notify = AsyncMock()

    status_response = await service.stripe_checkout_status("cs_test_capricho", user_id=None)

    assert status_response.status == "PAGADO"
    assert status_response.receipt_url == "https://pay.stripe.com/receipts/acct_test/ch_test/rcpt_test"
    assert payment.estado == "PAGADO"
    assert sale.estado == "PAGADA"
    assert cart.id_sucursal is None


async def test_reconcile_pending_stripe_orders_completes_paid_sessions() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    gateway = AsyncMock()

    transaction, payment, sale, order = checkout_records()
    cart = Carrito(id_carrito=3, id_cliente=4, estado="CONVERTIDO", id_sucursal=1)

    async def get_side_effect(model, ident):
        if model is Pago and ident == 12:
            return payment
        if model is Venta and ident == 6:
            return sale
        if model is Pedido and ident == 8:
            return order
        if model is Carrito and ident == 3:
            return cart
        return None

    repository.get.side_effect = get_side_effect
    repository.pending_stripe_sessions.return_value = ["cs_test_capricho"]
    repository.gateway_transaction_by_session.return_value = transaction
    repository.payment.return_value = payment
    repository.order_by_sale.return_value = order

    gateway.retrieve_session.return_value = {
        "id": "cs_test_capricho",
        "payment_status": "paid",
        "status": "complete",
        "amount_total": 24000,
        "currency": "bob",
        "payment_intent": {
            "id": "pi_capricho",
            "latest_charge": {
                "receipt_url": "https://pay.stripe.com/receipts/acct_test/ch_test/rcpt_test"
            },
        },
    }

    service = CommerceService(session, repository, stripe_gateway=gateway)
    service._notify = AsyncMock()

    await service._reconcile_pending_stripe_orders(customer_id=None)

    assert payment.estado == "PAGADO"
    assert sale.estado == "PAGADA"
    assert transaction.estado == "PAGADO"


