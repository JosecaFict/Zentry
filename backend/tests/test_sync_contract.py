from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.auth.dependencies import CurrentPrincipal
from app.modules.commerce.schemas import SaleCreate
from app.modules.sync.exceptions import SyncForbiddenError
from app.modules.sync.models import SyncOperation
from app.modules.sync.schemas import (
    OfflineReservationCreate,
    SyncBatchRequest,
    SyncOperationRequest,
    parse_offline_payload,
)
from app.modules.sync.service import SyncService


def operation(*, operation_id=None, method="EFECTIVO") -> SyncOperationRequest:
    return SyncOperationRequest(
        id_operacion=operation_id or uuid4(),
        tipo="VENTA",
        fecha_cliente=datetime.now(UTC),
        payload={
            "id_sucursal": 1,
            "items": [{"id_variante": 2, "cantidad": 1}],
            "registrar_efectivo": True,
            "metodo_pago": method,
        },
    )


def principal(*, permissions=frozenset({"ventas.crear", "pagos.registrar"})):
    return CurrentPrincipal(
        user=SimpleNamespace(id_usuario=9),
        roles=frozenset(),
        permissions=permissions,
        session_id="test",
        id_tenant=3,
        tenant_slug="demo",
        permite_offline=True,
    )


def test_batch_rejects_duplicate_operation_uuids() -> None:
    operation_id = uuid4()
    with pytest.raises(ValidationError):
        SyncBatchRequest(
            id_lote=uuid4(),
            id_dispositivo=uuid4(),
            fecha_cliente=datetime.now(UTC),
            operaciones=[
                operation(operation_id=operation_id),
                operation(operation_id=operation_id),
            ],
        )


def test_offline_sale_only_accepts_cash() -> None:
    with pytest.raises(ValueError, match="efectivo"):
        parse_offline_payload(operation(method="TARJETA"))


def test_payload_hash_is_stable_and_changes_with_payload() -> None:
    operation_id = uuid4()
    first = operation(operation_id=operation_id)
    same = SyncOperationRequest.model_validate(first.model_dump())
    changed = SyncOperationRequest.model_validate(first.model_dump())
    changed.payload["items"][0]["cantidad"] = 2

    assert SyncService._hash(first) == SyncService._hash(same)
    assert SyncService._hash(first) != SyncService._hash(changed)


def test_offline_sale_requires_sale_and_payment_permissions() -> None:
    sale = SaleCreate.model_validate(operation().payload)
    with pytest.raises(SyncForbiddenError):
        SyncService._authorize_operation(principal(permissions=frozenset()), sale)


def test_offline_reservation_requires_customer() -> None:
    request = SyncOperationRequest(
        id_operacion=uuid4(),
        tipo="RESERVA",
        fecha_cliente=datetime.now(UTC),
        payload={
            "id_sucursal": 1,
            "items": [{"id_variante": 2, "cantidad": 1}],
        },
    )
    with pytest.raises(ValidationError):
        parse_offline_payload(request)


def test_offline_reservation_requires_management_permission() -> None:
    reservation = OfflineReservationCreate(
        id_sucursal=1,
        id_cliente=7,
        items=[{"id_variante": 2, "cantidad": 1}],
    )
    with pytest.raises(SyncForbiddenError):
        SyncService._authorize_operation(principal(permissions=frozenset()), reservation)


@pytest.mark.asyncio
async def test_stock_conflict_is_persisted_without_exposing_internal_data() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    repository.conflict.return_value = None
    service = SyncService(session, repository, AsyncMock())
    item = SyncOperation(
        id_operacion=uuid4(),
        id_tenant=3,
        id_lote=uuid4(),
        id_dispositivo=uuid4(),
        id_usuario=9,
        tipo="VENTA",
        payload={},
        payload_hash="a" * 64,
        fecha_cliente=datetime.now(UTC),
    )

    await service._record_conflict(item, "Stock insuficiente para Polo azul")

    assert item.estado == "CONFLICTO"
    assert item.codigo_error == "STOCK_INSUFICIENTE"
    repository.add.assert_awaited_once()

