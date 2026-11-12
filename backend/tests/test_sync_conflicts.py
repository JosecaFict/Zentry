"""Resolución de conflictos offline por encargados y administradores (fase 5)."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.auth.dependencies import CurrentPrincipal
from app.modules.commerce.exceptions import CommerceConflictError
from app.modules.sync.exceptions import (
    SyncConflictError,
    SyncForbiddenError,
    SyncNotFoundError,
)
from app.modules.sync.models import SyncConflict, SyncOperation
from app.modules.sync.schemas import SyncConflictResolveRequest
from app.modules.sync.service import SyncService

SELLER = 9
SUPERVISOR = 4


def principal(*, roles=frozenset({"ENCARGADO_SUCURSAL"}), branch=1, user=SUPERVISOR):
    return CurrentPrincipal(
        user=SimpleNamespace(id_usuario=user),
        roles=roles,
        permissions=frozenset(),
        session_id="test",
        id_sucursal=branch,
        id_tenant=3,
        tenant_slug="demo",
        permite_offline=True,
    )


def stored_operation(*, branch=1, state="CONFLICTO", code="STOCK_INSUFICIENTE"):
    return SyncOperation(
        id_operacion=uuid4(),
        id_tenant=3,
        id_lote=uuid4(),
        id_dispositivo=uuid4(),
        id_usuario=SELLER,
        tipo="VENTA",
        estado=state,
        codigo_error=code,
        mensaje_error="Stock insuficiente para completar la venta",
        payload={
            "id_sucursal": branch,
            "items": [{"id_variante": 2, "cantidad": 1}],
            "registrar_efectivo": True,
            "metodo_pago": "EFECTIVO",
            "precios_cobrados": {"2": 9990},
            "total_cobrado_centavos": 9990,
        },
        payload_hash="a" * 64,
        fecha_cliente=datetime.now(UTC),
    )


def conflict_for(operation, *, state="PENDIENTE"):
    return SyncConflict(
        id_conflicto=11,
        id_tenant=3,
        id_operacion=operation.id_operacion,
        tipo=operation.codigo_error,
        detalle={"mensaje": operation.mensaje_error, "tipo_operacion": "VENTA"},
        estado=state,
        created_at=datetime.now(UTC),
    )


def build(operation, conflict):
    session = AsyncMock()

    @asynccontextmanager
    async def nested():
        yield

    session.begin_nested = MagicMock(side_effect=nested)
    repository = AsyncMock()
    repository.conflict_by_id.return_value = conflict
    repository.operation.return_value = operation
    repository.variant_labels.return_value = {2: "Polo básico M Negro"}
    repository.user_names.return_value = {SELLER: "Ana Vendedora", SUPERVISOR: "Luis Encargado"}
    commerce = AsyncMock()
    commerce.create_pos_sale.return_value = SimpleNamespace(
        model_dump=lambda mode: {"id_venta": 77}
    )
    return SyncService(session, repository, commerce), repository, commerce, session


class TestSupervisorScope:
    def test_admin_ve_todas_las_sucursales(self):
        assert SyncService._supervisor_scope(principal(roles=frozenset({"ADMIN"}))) is None

    def test_encargado_ve_solo_su_sucursal(self):
        assert SyncService._supervisor_scope(principal(branch=5)) == 5

    def test_cajero_no_puede_revisar(self):
        with pytest.raises(SyncForbiddenError):
            SyncService._supervisor_scope(principal(roles=frozenset({"CAJERO"})))

    def test_encargado_sin_sucursal_no_puede_revisar(self):
        with pytest.raises(SyncForbiddenError):
            SyncService._supervisor_scope(principal(branch=None))


class TestResolve:
    @pytest.mark.asyncio
    async def test_reaplicar_registra_la_venta_a_nombre_del_vendedor(self):
        operation = stored_operation()
        conflict = conflict_for(operation)
        service, _, commerce, session = build(operation, conflict)

        result = await service.resolve_conflict(
            principal(), 11, SyncConflictResolveRequest(accion="REAPLICAR")
        )

        assert commerce.create_pos_sale.await_args.args[0] == SELLER
        assert commerce.create_pos_sale.await_args.kwargs["collected_prices"] == {2: 9990}
        assert operation.estado == "APLICADA"
        assert operation.resultado == {"id_venta": 77}
        assert operation.codigo_error is None
        assert conflict.estado == "RESUELTO"
        assert conflict.resuelto_por == SUPERVISOR
        assert result.accion == "REAPLICADA"
        assert result.items[0].descripcion == "Polo básico M Negro"
        session.commit.assert_awaited()
        # El vendedor recibe aviso de que su venta quedó registrada.
        recipients, kind = commerce.notify_users.await_args.args[:2]
        assert recipients == {SELLER}
        assert kind == "SYNC_CONFLICTO_RESUELTO"

    @pytest.mark.asyncio
    async def test_reaplicar_sin_stock_sigue_pendiente_y_explica_que_hacer(self):
        operation = stored_operation()
        conflict = conflict_for(operation)
        service, _, commerce, _ = build(operation, conflict)
        commerce.create_pos_sale.side_effect = CommerceConflictError(
            "Stock insuficiente para completar la venta"
        )

        with pytest.raises(SyncConflictError, match="ajusta primero el inventario"):
            await service.resolve_conflict(
                principal(), 11, SyncConflictResolveRequest(accion="REAPLICAR")
            )
        assert conflict.estado == "PENDIENTE"
        assert operation.estado == "CONFLICTO"

    @pytest.mark.asyncio
    async def test_datos_invalidos_no_se_reaplican(self):
        operation = stored_operation(state="RECHAZADA", code="DATOS_INVALIDOS")
        service, _, commerce, _ = build(operation, conflict_for(operation))

        with pytest.raises(SyncConflictError, match="anúlala"):
            await service.resolve_conflict(
                principal(), 11, SyncConflictResolveRequest(accion="REAPLICAR")
            )
        commerce.create_pos_sale.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_anular_guarda_la_nota_sin_registrar_la_venta(self):
        operation = stored_operation()
        conflict = conflict_for(operation)
        service, _, commerce, _ = build(operation, conflict)

        result = await service.resolve_conflict(
            principal(),
            11,
            SyncConflictResolveRequest(accion="ANULAR", nota="  Se devolvió el dinero  "),
        )

        commerce.create_pos_sale.assert_not_awaited()
        assert conflict.estado == "DESCARTADO"
        assert conflict.resolucion == "Se devolvió el dinero"
        assert result.accion == "ANULADA"
        assert result.resuelto_por == "Luis Encargado"
        assert operation.estado == "CONFLICTO"

    def test_anular_exige_una_nota(self):
        with pytest.raises(ValidationError, match="nota"):
            SyncConflictResolveRequest(accion="ANULAR")
        with pytest.raises(ValidationError):
            SyncConflictResolveRequest(accion="ANULAR", nota="   ")

    @pytest.mark.asyncio
    async def test_encargado_no_resuelve_otra_sucursal(self):
        operation = stored_operation(branch=2)
        service, _, commerce, _ = build(operation, conflict_for(operation))

        with pytest.raises(SyncForbiddenError):
            await service.resolve_conflict(
                principal(branch=1), 11, SyncConflictResolveRequest(accion="REAPLICAR")
            )
        commerce.create_pos_sale.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_se_resuelve_dos_veces(self):
        operation = stored_operation()
        service, _, _, _ = build(operation, conflict_for(operation, state="RESUELTO"))
        with pytest.raises(SyncConflictError, match="ya fue resuelto"):
            await service.resolve_conflict(
                principal(), 11, SyncConflictResolveRequest(accion="REAPLICAR")
            )

    @pytest.mark.asyncio
    async def test_conflicto_de_otra_empresa_no_existe(self):
        operation = stored_operation()
        conflict = conflict_for(operation)
        conflict.id_tenant = 99
        service, _, _, _ = build(operation, conflict)
        with pytest.raises(SyncNotFoundError):
            await service.resolve_conflict(
                principal(), 11, SyncConflictResolveRequest(accion="REAPLICAR")
            )

    @pytest.mark.asyncio
    async def test_si_el_supervisor_es_el_vendedor_no_se_autonotifica(self):
        operation = stored_operation()
        service, _, commerce, _ = build(operation, conflict_for(operation))
        await service.resolve_conflict(
            principal(user=SELLER),
            11,
            SyncConflictResolveRequest(accion="ANULAR", nota="Prueba"),
        )
        commerce.notify_users.assert_not_awaited()


class TestNotifications:
    @pytest.mark.asyncio
    async def test_avisa_a_supervisores_menos_al_vendedor(self):
        operation = stored_operation()
        conflict = conflict_for(operation)
        service, repository, commerce, _ = build(operation, conflict)
        repository.conflict_supervisors.return_value = {SUPERVISOR, SELLER, 1}

        await service._notify_supervisors([(conflict, operation)])

        repository.conflict_supervisors.assert_awaited_once_with(1)
        recipients, kind, title, body = commerce.notify_users.await_args.args
        assert recipients == {SUPERVISOR, 1}
        assert kind == "SYNC_CONFLICTO"
        assert "Venta offline no registrada" in title
        assert "Ana Vendedora" in body and "Polo básico M Negro" in body
        assert "No había stock" in body
        data = commerce.notify_users.await_args.kwargs["data"]
        assert data["route"] == "/admin/conflictos"

    @pytest.mark.asyncio
    async def test_un_fallo_al_avisar_no_rompe_la_sincronizacion(self):
        operation = stored_operation()
        conflict = conflict_for(operation)
        service, repository, _, session = build(operation, conflict)
        repository.conflict_supervisors.side_effect = RuntimeError("sin red")

        await service._notify_supervisors([(conflict, operation)])
        session.rollback.assert_awaited()


class TestReviewRecords:
    @pytest.mark.asyncio
    async def test_una_operacion_rechazada_tambien_queda_para_revision(self):
        operation = stored_operation(state="RECHAZADA", code="ERROR_INTERNO")
        service, repository, _, _ = build(operation, None)
        repository.conflict.return_value = None
        repository.add.side_effect = lambda entity: entity

        conflict = await service._register_review(operation)

        assert conflict.tipo == "ERROR_INTERNO"
        assert conflict.estado == "PENDIENTE"
        assert conflict.created_at is not None

    @pytest.mark.asyncio
    async def test_no_duplica_el_registro(self):
        operation = stored_operation()
        service, repository, _, _ = build(operation, None)
        repository.conflict.return_value = conflict_for(operation)
        assert await service._register_review(operation) is None
        repository.add.assert_not_awaited()


class TestDeviceStatus:
    @pytest.mark.asyncio
    async def test_el_vendedor_ve_como_se_resolvio(self):
        operation = stored_operation(state="APLICADA", code=None)
        conflict = conflict_for(operation, state="RESUELTO")
        conflict.detalle = {**conflict.detalle, "accion": "REAPLICADA"}
        service, repository, _, _ = build(operation, conflict)
        repository.operations_with_conflicts.return_value = [(operation, conflict)]

        [status] = await service.operation_status(
            principal(roles=frozenset({"CAJERO"}), user=SELLER), [operation.id_operacion]
        )

        repository.operations_with_conflicts.assert_awaited_once_with(
            [operation.id_operacion], SELLER
        )
        assert status.estado == "APLICADA"
        assert status.conflicto_estado == "RESUELTO"
        assert status.accion == "REAPLICADA"
