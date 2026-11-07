from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.commerce.exceptions import CommerceConflictError, InvalidCommerceOperationError
from app.modules.commerce.models import Devolucion, DetalleVenta, Venta
from app.modules.commerce.return_policy import allocate_paid_amounts, returned_amount
from app.modules.commerce.return_receipt import return_receipt_pdf
from app.modules.commerce.schemas import ReturnSettlement, ReturnStatusUpdate
from app.modules.commerce.service import CommerceService
from app.modules.inventory.models import LoteInventario, MovimientoInventario, MovimientoLote


def fixture_service():
    repo, session = AsyncMock(), AsyncMock()
    sale = Venta(id_venta=1, id_sucursal=2, id_cliente=None, total=Decimal('240'),
                 costo_envio=Decimal(0), canal_venta='PRESENCIAL', modalidad_entrega='ENTREGA_DIRECTA',
                 estado='PAGADA', fecha_venta=datetime.now(UTC))
    returned = Devolucion(id_devolucion=3, id_venta=1, id_cliente=None, estado='APROBADA', motivo='Talla pequeña')
    original = DetalleVenta(id_detalle_venta=4, id_venta=1, id_variante=10, cantidad=2,
                           precio_unitario=Decimal('150'), subtotal=Decimal('300'), descuento=Decimal(0))
    detail = SimpleNamespace(id_detalle_devolucion=5, id_detalle_venta=4, cantidad=1, estado_prenda='PENDIENTE_INSPECCION')
    row = dict(id_producto=20, activo=True, precio=Decimal('150'), stock_disponible=5,
               producto='Polera', talla='M', color='Azul')
    replacement = {**row, 'talla': 'L'}
    rows = {10: row, 11: replacement}
    repo.variant_row.side_effect = lambda variant, branch: rows.get(variant)
    repo.sale_details.return_value = [original]
    repo.return_details.return_value = [detail]
    repo.completed_return_quantity.return_value = 0
    repo.confirmed_payment_total.return_value = Decimal('240')
    repo.get_active_discounts_for_products.return_value = {}
    repo.get.side_effect = lambda model, identifier: {Venta: sale, Devolucion: returned, DetalleVenta: original}.get(model)
    repo.locked.side_effect = repo.get.side_effect
    inventory = SimpleNamespace(id_inventario=7, id_sucursal=2, id_variante=10, stock_fisico=10, stock_reservado=0)
    repo.inventory_for_update.return_value = inventory
    lot = LoteInventario(id_lote=8, cantidad_disponible=0)
    repo.sale_lot_allocations.return_value = [(SimpleNamespace(cantidad=2, costo_unitario=Decimal('40')), lot)]
    repo.restored_sale_lots.return_value = {}
    additions = []

    async def add(obj):
        additions.append(obj)
        if isinstance(obj, MovimientoInventario):
            obj.id_movimiento = 100 + len(additions)
        return obj

    repo.add.side_effect = add
    service = CommerceService(session, repo)
    service._employee = AsyncMock(return_value=SimpleNamespace(id_empleado=9, id_sucursal=2))
    service._return_response = AsyncMock(return_value='response')
    return service, repo, session, sale, returned, detail, rows, additions, lot


def complete_payload(**overrides):
    value = dict(estado='COMPLETADA', items=[dict(id_detalle_devolucion=5, estado_prenda='APTA_REINGRESO')],
                 checklist=dict(comprobante_verificado=True, sin_uso=True, sin_lavado=True,
                                etiquetas_conservadas=True, sin_danos_cliente=True),
                 resolucion=dict(tipo='REEMBOLSO', monto_confirmado='120.00', medio='EFECTIVO'))
    value.update(overrides)
    return ReturnStatusUpdate(**value)


def test_partial_returns_preserve_exact_cents():
    assert [returned_amount(Decimal('1'), 3, 1, i) for i in range(3)] == [Decimal('.33'), Decimal('.34'), Decimal('.33')]
    allocated = allocate_paid_amounts([Decimal('1')] * 3, Decimal('1'))
    assert sum(allocated) == Decimal('1')


async def test_same_product_exchange_keeps_discounted_original_price():
    service, repo, _, sale, returned, *_ = fixture_service()
    quote = await service._return_quote(returned, sale, ReturnSettlement(tipo='CAMBIO', reemplazos=[dict(id_detalle_devolucion=5, id_variante=11)]))
    assert quote['importe_devuelto'] == '120.00'
    assert quote['importe_reemplazos'] == '120.00'
    assert quote['accion'] == 'SIN_DIFERENCIA'


@pytest.mark.parametrize(('price', 'expected', 'action'), [('180', '60.00', 'COBRAR'), ('80', '40.00', 'REEMBOLSAR')])
async def test_other_product_exchange_calculates_difference(price, expected, action):
    service, repo, _, sale, returned, _, rows, *_ = fixture_service()
    rows[11].update(id_producto=30, precio=Decimal(price))
    quote = await service._return_quote(returned, sale, ReturnSettlement(tipo='CAMBIO', reemplazos=[dict(id_detalle_devolucion=5, id_variante=11)]))
    assert quote['monto'] == expected
    assert quote['accion'] == action


async def test_new_product_uses_active_promotion():
    service, repo, _, sale, returned, _, rows, *_ = fixture_service()
    rows[11].update(id_producto=30, precio=Decimal('200'))
    repo.get_active_discounts_for_products.return_value = {30: (Decimal('50'), 1, 'Oferta')}
    quote = await service._return_quote(returned, sale, ReturnSettlement(tipo='CAMBIO', reemplazos=[dict(id_detalle_devolucion=5, id_variante=11)]))
    assert quote['importe_reemplazos'] == '100.00'
    assert quote['diferencia'] == '-20.00'


async def test_replacement_without_stock_is_rejected_before_any_movement():
    service, repo, session, sale, returned, _, rows, additions, _ = fixture_service()
    rows[11]['stock_disponible'] = 0
    with pytest.raises(CommerceConflictError, match='Stock insuficiente'):
        await service.update_return_status(1, 3, complete_payload(resolucion=dict(tipo='CAMBIO', reemplazos=[dict(id_detalle_devolucion=5, id_variante=11)])))
    assert not additions
    session.rollback.assert_awaited_once()


async def test_refund_restores_lot_once_and_saves_receipt():
    service, repo, session, _, returned, _, _, additions, lot = fixture_service()
    await service.update_return_status(1, 3, complete_payload())
    assert returned.estado == 'COMPLETADA'
    assert lot.cantidad_disponible == 1
    assert len([item for item in additions if isinstance(item, MovimientoInventario)]) == 1
    assert len([item for item in additions if isinstance(item, MovimientoLote)]) == 1
    assert returned.cierre['monto'] == '120.00'
    assert returned.cierre['notas_salida'] == []
    session.commit.assert_awaited_once()
    await service.update_return_status(1, 3, complete_payload())
    assert len(additions) == 2
    session.commit.assert_awaited_once()


@pytest.mark.parametrize('override', [
    dict(checklist=None),
    dict(checklist=dict(comprobante_verificado=True, sin_uso=False, sin_lavado=True, etiquetas_conservadas=True, sin_danos_cliente=True)),
    dict(resolucion=dict(tipo='REEMBOLSO', monto_confirmado='119', medio='EFECTIVO')),
    dict(resolucion=dict(tipo='REEMBOLSO', monto_confirmado='120', medio='TRANSFERENCIA')),
])
async def test_incomplete_or_wrong_settlement_never_moves_stock(override):
    service, _, session, _, _, _, _, additions, _ = fixture_service()
    with pytest.raises((InvalidCommerceOperationError, CommerceConflictError)):
        await service.update_return_status(1, 3, complete_payload(**override))
    assert not additions
    session.rollback.assert_awaited_once()


async def test_online_return_window_starts_at_delivery_not_purchase():
    service, repo, _, sale, *_ = fixture_service()
    sale.canal_venta = 'WEB'
    sale.fecha_venta = datetime.now(UTC) - timedelta(days=30)
    delivered = datetime.now(UTC) - timedelta(days=1)
    repo.order_by_sale.return_value = SimpleNamespace(estado='ENTREGADO', fecha_finalizacion=delivered)
    assert await service._validate_return_window(sale) == delivered
    repo.order_by_sale.return_value = SimpleNamespace(estado='EN_CAMINO', fecha_finalizacion=None)
    with pytest.raises(CommerceConflictError, match='entrega'):
        await service._validate_return_window(sale)


async def test_expired_or_unpaid_purchase_cannot_be_returned():
    service, repo, _, sale, *_ = fixture_service()
    sale.fecha_venta = datetime.now(UTC) - timedelta(days=30)
    with pytest.raises(CommerceConflictError, match='plazo'):
        await service._validate_return_window(sale)
    sale.fecha_venta = datetime.now(UTC)
    repo.confirmed_payment_total.return_value = Decimal(0)
    with pytest.raises(CommerceConflictError, match='pago confirmado'):
        await service._validate_return_window(sale)


async def test_wrong_branch_cannot_quote_or_close():
    service, _, _, _, _, *_ = fixture_service()
    service._employee.return_value.id_sucursal = 99
    with pytest.raises(Exception, match='no existe'):
        await service.quote_return(1, 3, ReturnSettlement(tipo='REEMBOLSO'))
    with pytest.raises(Exception, match='no existe'):
        await service.update_return_status(1, 3, complete_payload())


async def test_receipt_pdf_has_real_settlement_data():
    service, _, _, _, returned, *_ = fixture_service()
    await service.update_return_status(1, 3, complete_payload())
    pdf = return_receipt_pdf(returned.cierre, 1, 'Sucursal <Centro>', 'Cliente & prueba')
    assert pdf.startswith(b'%PDF')
