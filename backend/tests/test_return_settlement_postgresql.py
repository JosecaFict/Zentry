"""Real FIFO/stock triggers, with every write rolled back after the test."""

import os
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.audit_context import AuditContext, apply_audit_context
from app.db.tenant_context import clear_tenant_context, database_scope, set_tenant_context
from app.modules.commerce.repository import CommerceRepository
from app.modules.commerce.schemas import AdminReturnCreate, ReturnSettlement, ReturnStatusUpdate, SaleCreate
from app.modules.commerce.service import CommerceService
from app.modules.platform import models as platform_models  # noqa: F401 - register tenant FK metadata

pytestmark = pytest.mark.skipif(os.getenv('RUN_POSTGRES_RETURN_TESTS') != '1', reason='Set RUN_POSTGRES_RETURN_TESTS=1 for a rollback-only local PostgreSQL test')


@pytest.mark.parametrize('kind', ['CAMBIO', 'REEMBOLSO'])
async def test_full_return_uses_real_stock_and_fifo_triggers(kind):
    url = os.getenv('RETURN_TEST_DATABASE_URL')
    if not url:
        pytest.fail('RETURN_TEST_DATABASE_URL is required')
    engine = create_async_engine(url, connect_args={'server_settings': {'search_path': 'capricho,public'}})
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(text("SELECT set_config('app.rls_scope', 'global', true)"))
                rows = (await connection.execute(text('''
                    SELECT DISTINCT i.id_tenant, i.id_sucursal, i.id_variante, e.id_usuario, v.id_producto, v.id_talla, v.id_color,
                        i.stock_fisico, i.stock_reservado
                    FROM capricho.inventario_sucursal i
                    JOIN capricho.empleado e ON e.id_sucursal=i.id_sucursal AND e.id_tenant=i.id_tenant
                    JOIN capricho.variante_producto v ON v.id_variante=i.id_variante
                    JOIN capricho.producto p ON p.id_producto=v.id_producto
                    WHERE e.estado_laboral='ACTIVO' AND p.activo AND v.activo
                    AND i.stock_fisico-i.stock_reservado>=2
                    AND EXISTS (SELECT 1 FROM capricho.historial_precio hp WHERE hp.id_producto=p.id_producto AND hp.fecha_fin IS NULL AND hp.precio>0)
                    AND EXISTS (SELECT 1 FROM capricho.lote_inventario l WHERE l.id_sucursal=i.id_sucursal AND l.id_variante=i.id_variante AND l.cantidad_disponible>=2 AND l.activo)
                    ORDER BY i.id_tenant, i.id_sucursal, i.id_variante LIMIT 200
                '''))).mappings().all()
                pair = next(((a, b) for a in rows for b in rows if a['id_sucursal'] == b['id_sucursal'] and a['id_tenant'] == b['id_tenant'] and a['id_variante'] != b['id_variante'] and (kind != 'CAMBIO' or (a['id_producto'] == b['id_producto'] and a['id_color'] == b['id_color'] and a['id_talla'] != b['id_talla']))), None)
                if pair is None:
                    pytest.skip('Seeded local database needs two stocked variants and an employee')
                original, replacement = pair
                set_tenant_context(original['id_tenant'])
                with database_scope('tenant'):
                    async with AsyncSession(bind=connection, join_transaction_mode='create_savepoint', expire_on_commit=False, autoflush=False) as session:
                        await apply_audit_context(session, AuditContext(tenant_id=original['id_tenant'], usuario_id=original['id_usuario'], request_id='test-return-rollback'))
                        repo = CommerceRepository(session)
                        service = CommerceService(session, repo)
                        service._notify = AsyncMock()
                        service._notify_branch_staff = AsyncMock()
                        sale = await service.create_pos_sale(original['id_usuario'], SaleCreate(
                            id_sucursal=original['id_sucursal'], items=[dict(id_variante=original['id_variante'], cantidad=1)],
                        ))
                        request = await service.create_admin_return(original['id_usuario'], AdminReturnCreate(
                            id_venta=sale.id_venta, motivo='Cambio de talla en prueba transaccional',
                            tipo_solicitud='CAMBIO_TALLA' if kind == 'CAMBIO' else 'REEMBOLSO',
                            items=[dict(id_detalle_venta=sale.items[0].id_detalle, cantidad=1,
                                        id_variante_solicitada=replacement['id_variante'] if kind == 'CAMBIO' else None)],
                        ))
                        assert request.items[0].estado_prenda == 'PENDIENTE_INSPECCION'
                        if kind == 'CAMBIO':
                            assert request.items[0].id_variante_solicitada == replacement['id_variante']
                            options = await service.admin_return_options(original['id_usuario'], request.id_devolucion)
                            candidates = options['items'][0]['opciones']
                            assert any(option['id_variante'] == replacement['id_variante'] for option in candidates)
                            assert all(option['id_producto'] == original['id_producto'] and option['color'] == request.items[0].color and option['talla'] != request.items[0].talla for option in candidates)
                        await service.update_return_status(original['id_usuario'], request.id_devolucion, ReturnStatusUpdate(estado='APROBADA'))
                        settlement = ReturnSettlement(tipo=kind, reemplazos=[dict(id_detalle_devolucion=request.items[0].id_detalle_devolucion, id_variante=replacement['id_variante'])] if kind == 'CAMBIO' else [])
                        quote = await service.quote_return(original['id_usuario'], request.id_devolucion, settlement)
                        settlement.monto_confirmado = Decimal(quote['monto'])
                        settlement.medio = 'EFECTIVO'
                        payload = ReturnStatusUpdate(
                            estado='COMPLETADA', resolucion=settlement,
                            checklist=dict(comprobante_verificado=True, sin_uso=True, sin_lavado=True, etiquetas_conservadas=True, sin_danos_cliente=True),
                            items=[dict(id_detalle_devolucion=request.items[0].id_detalle_devolucion, estado_prenda='APTA_REINGRESO')],
                        )
                        closed = await service.update_return_status(original['id_usuario'], request.id_devolucion, payload)
                        repeated = await service.update_return_status(original['id_usuario'], request.id_devolucion, payload)
                        assert repeated.cierre == closed.cierre
                        assert len(closed.cierre['notas_entrada']) == 1
                        assert len(closed.cierre['notas_salida']) == (1 if kind == 'CAMBIO' else 0)
                        await session.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))
                        actual = await repo.inventory_for_update(original['id_sucursal'], original['id_variante'])
                        await session.refresh(actual)
                        assert actual.stock_fisico == original['stock_fisico']
                        other = await repo.inventory_for_update(original['id_sucursal'], replacement['id_variante'])
                        await session.refresh(other)
                        assert other.stock_fisico == replacement['stock_fisico'] - (1 if kind == 'CAMBIO' else 0)
                        movements = await session.scalar(text('''
                            SELECT count(*) FROM capricho.movimiento_inventario
                            WHERE referencia_tipo='DEVOLUCION' AND referencia_id=:id
                        '''), {'id': request.id_devolucion})
                        assert movements == (2 if kind == 'CAMBIO' else 1)
                        pdf = await service.get_return_receipt(original['id_usuario'], request.id_devolucion, operational=True)
                        assert pdf.startswith(b'%PDF')
            finally:
                clear_tenant_context()
                await transaction.rollback()
    finally:
        await engine.dispose()
