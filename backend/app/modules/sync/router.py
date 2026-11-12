from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.sync.dependencies import get_sync_service
from app.modules.sync.exceptions import SyncError
from app.modules.sync.schemas import (
    CatalogSnapshotResponse,
    SyncBatchRequest,
    SyncBatchResponse,
    SyncConfirmationRequest,
    SyncConflictResolveRequest,
    SyncConflictResponse,
    SyncDeviceRegister,
    SyncDeviceResponse,
    SyncOperationStatusResponse,
)
from app.modules.sync.service import SyncService

router = APIRouter(prefix="/sync", tags=["sync"])


def _http_error(exc: SyncError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/devices", response_model=SyncDeviceResponse)
async def register_device(
    payload: SyncDeviceRegister,
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> SyncDeviceResponse:
    try:
        return await service.register_device(principal, payload)
    except SyncError as exc:
        raise _http_error(exc) from exc


@router.get("/catalog", response_model=CatalogSnapshotResponse)
async def catalog_snapshot(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[SyncService, Depends(get_sync_service)],
    id_sucursal: int = Query(gt=0),
) -> CatalogSnapshotResponse:
    try:
        return await service.snapshot(principal, id_sucursal)
    except SyncError as exc:
        raise _http_error(exc) from exc


@router.post("/batches", response_model=SyncBatchResponse)
async def submit_batch(
    payload: SyncBatchRequest,
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> SyncBatchResponse:
    try:
        return await service.submit(principal, payload)
    except SyncError as exc:
        raise _http_error(exc) from exc


@router.get("/batches/{batch_id}", response_model=SyncBatchResponse)
async def get_batch(
    batch_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> SyncBatchResponse:
    try:
        return await service.get_batch(principal, batch_id)
    except SyncError as exc:
        raise _http_error(exc) from exc


@router.get("/conflicts", response_model=list[SyncConflictResponse])
async def list_conflicts(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[SyncService, Depends(get_sync_service)],
    estado: Literal["PENDIENTE", "RESUELTO", "DESCARTADO", "TODOS"] = "PENDIENTE",
    id_sucursal: int | None = Query(default=None, gt=0),
) -> list[SyncConflictResponse]:
    """Operaciones offline no registradas, para encargados y administradores."""
    try:
        return await service.list_conflicts(
            principal,
            state=None if estado == "TODOS" else estado,
            branch_id=id_sucursal,
        )
    except SyncError as exc:
        raise _http_error(exc) from exc


@router.post("/conflicts/{conflict_id}/resolve", response_model=SyncConflictResponse)
async def resolve_conflict(
    conflict_id: int,
    payload: SyncConflictResolveRequest,
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> SyncConflictResponse:
    """REAPLICAR (registrarla ahora) o ANULAR (cerrarla con una nota)."""
    try:
        return await service.resolve_conflict(principal, conflict_id, payload)
    except SyncError as exc:
        raise _http_error(exc) from exc


@router.get("/operations/status", response_model=list[SyncOperationStatusResponse])
async def operation_status(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[SyncService, Depends(get_sync_service)],
    ids: Annotated[list[UUID], Query(min_length=1, max_length=100)],
) -> list[SyncOperationStatusResponse]:
    """Estado actual de operaciones propias (para que el dispositivo vea si un
    supervisor ya resolvió un conflicto)."""
    try:
        return await service.operation_status(principal, ids)
    except SyncError as exc:
        raise _http_error(exc) from exc


@router.post("/batches/{batch_id}/confirm", response_model=SyncBatchResponse)
async def confirm_batch(
    batch_id: UUID,
    payload: SyncConfirmationRequest,
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> SyncBatchResponse:
    try:
        return await service.confirm(principal, batch_id, payload.id_dispositivo)
    except SyncError as exc:
        raise _http_error(exc) from exc

