import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies import CurrentPrincipal
from app.modules.commerce.exceptions import (
    CommerceConflictError,
    CommerceForbiddenError,
    CommerceNotFoundError,
    InvalidCommerceOperationError,
)
from app.modules.commerce.schemas import ReservationCreate, SaleCreate
from app.modules.commerce.service import CommerceService
from app.modules.sync.exceptions import SyncConflictError, SyncForbiddenError, SyncNotFoundError
from app.modules.sync.models import SyncBatch, SyncConflict, SyncDevice, SyncOperation
from app.modules.sync.repository import SyncRepository
from app.modules.sync.schemas import (
    CatalogSnapshotItem,
    CatalogSnapshotResponse,
    SyncBatchRequest,
    SyncBatchResponse,
    SyncDeviceRegister,
    SyncDeviceResponse,
    SyncOperationRequest,
    SyncOperationResponse,
    parse_offline_payload,
)

logger = logging.getLogger("zentry.sync")


class SyncService:
    TERMINAL_BATCH_STATES = {
        "COMPLETADO",
        "COMPLETADO_CON_CONFLICTOS",
        "CONFIRMADO",
    }

    def __init__(
        self,
        session: AsyncSession,
        repository: SyncRepository,
        commerce: CommerceService,
    ) -> None:
        self.session = session
        self.repository = repository
        self.commerce = commerce

    @staticmethod
    def _require_offline(principal: CurrentPrincipal) -> int:
        if principal.id_tenant is None or not principal.permite_offline:
            raise SyncForbiddenError("El plan de la empresa no habilita operación offline")
        return principal.id_tenant

    @staticmethod
    def _hash(operation: SyncOperationRequest) -> str:
        value = {
            "tipo": operation.tipo,
            "fecha_cliente": operation.fecha_cliente.isoformat(),
            "payload": operation.payload,
        }
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
        return hashlib.sha256(encoded).hexdigest()

    async def register_device(
        self, principal: CurrentPrincipal, payload: SyncDeviceRegister
    ) -> SyncDeviceResponse:
        tenant_id = self._require_offline(principal)
        if payload.id_sucursal is not None:
            branch = await self.repository.branch(payload.id_sucursal)
            if branch is None or not branch.activo:
                raise SyncNotFoundError("La sucursal no está disponible")
            if principal.id_sucursal and principal.id_sucursal != payload.id_sucursal:
                raise SyncForbiddenError("El dispositivo no puede vincularse a otra sucursal")

        device = await self.repository.device(payload.id_dispositivo, lock=True)
        if device is not None:
            if device.id_tenant != tenant_id or device.id_usuario != principal.user.id_usuario:
                raise SyncConflictError("El UUID del dispositivo ya pertenece a otra cuenta")
            device.nombre = payload.nombre.strip()
            device.plataforma = payload.plataforma
            device.version_app = payload.version_app
            device.id_sucursal = payload.id_sucursal
            device.estado = "ACTIVO"
        else:
            device = SyncDevice(
                id_dispositivo=payload.id_dispositivo,
                id_tenant=tenant_id,
                id_usuario=principal.user.id_usuario,
                id_sucursal=payload.id_sucursal,
                nombre=payload.nombre.strip(),
                plataforma=payload.plataforma,
                version_app=payload.version_app,
            )
            await self.repository.add(device)
        await self.session.commit()
        return SyncDeviceResponse.model_validate(device)

    async def snapshot(
        self, principal: CurrentPrincipal, branch_id: int
    ) -> CatalogSnapshotResponse:
        self._require_offline(principal)
        branch = await self.repository.branch(branch_id)
        if branch is None or not branch.activo:
            raise SyncNotFoundError("La sucursal no está disponible")
        if principal.id_sucursal and principal.id_sucursal != branch_id:
            raise SyncForbiddenError("No tiene acceso al inventario de esa sucursal")
        rows = await self.repository.catalog_snapshot(branch_id)
        items = [CatalogSnapshotItem.model_validate(dict(row)) for row in rows]
        version_source = [item.model_dump(mode="json") for item in items]
        version = hashlib.sha256(
            json.dumps(version_source, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return CatalogSnapshotResponse(
            id_sucursal=branch_id,
            generado_at=datetime.now(UTC),
            version=version,
            items=items,
        )

    async def submit(
        self, principal: CurrentPrincipal, payload: SyncBatchRequest
    ) -> SyncBatchResponse:
        tenant_id = self._require_offline(principal)
        device = await self.repository.device(payload.id_dispositivo)
        if device is None:
            raise SyncNotFoundError("Registre el dispositivo antes de sincronizar")
        if device.id_tenant != tenant_id or device.id_usuario != principal.user.id_usuario:
            raise SyncForbiddenError("El dispositivo no pertenece a la sesión actual")
        if device.estado != "ACTIVO":
            raise SyncForbiddenError("El dispositivo fue revocado")

        batch = await self.repository.batch(payload.id_lote)
        if batch is not None:
            if (
                batch.id_dispositivo != payload.id_dispositivo
                or batch.id_usuario != principal.user.id_usuario
            ):
                raise SyncConflictError("El UUID del lote ya fue utilizado por otra sesión")
            await self._verify_retry_payload(payload)
            if batch.estado not in self.TERMINAL_BATCH_STATES:
                await self._process_batch(principal, batch)
            return await self._response(batch.id_lote)

        for item in payload.operaciones:
            existing = await self.repository.operation(item.id_operacion)
            if existing is not None:
                raise SyncConflictError(
                    "Una operación ya pertenece a otro lote; "
                    "reintente con el UUID del lote original"
                )

        try:
            batch = SyncBatch(
                id_lote=payload.id_lote,
                id_tenant=tenant_id,
                id_dispositivo=payload.id_dispositivo,
                id_usuario=principal.user.id_usuario,
                estado="RECIBIDO",
                fecha_cliente=payload.fecha_cliente,
                total_operaciones=len(payload.operaciones),
            )
            await self.repository.add(batch)
            for item in payload.operaciones:
                await self.repository.add(
                    SyncOperation(
                        id_operacion=item.id_operacion,
                        id_tenant=tenant_id,
                        id_lote=payload.id_lote,
                        id_dispositivo=payload.id_dispositivo,
                        id_usuario=principal.user.id_usuario,
                        tipo=item.tipo,
                        payload=item.payload,
                        payload_hash=self._hash(item),
                        fecha_cliente=item.fecha_cliente,
                    )
                )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            batch = await self.repository.batch(payload.id_lote)
            if batch is None:
                raise SyncConflictError(
                    "Un UUID del lote o de sus operaciones ya fue utilizado"
                ) from exc
            if (
                batch.id_dispositivo != payload.id_dispositivo
                or batch.id_usuario != principal.user.id_usuario
            ):
                raise SyncConflictError("El UUID del lote ya fue utilizado") from exc
            await self._verify_retry_payload(payload)
            if batch.estado in self.TERMINAL_BATCH_STATES:
                return await self._response(batch.id_lote)
        await self._process_batch(principal, batch)
        return await self._response(batch.id_lote)

    async def _verify_retry_payload(self, payload: SyncBatchRequest) -> None:
        stored = await self.repository.operations(payload.id_lote)
        incoming = {item.id_operacion: self._hash(item) for item in payload.operaciones}
        current = {item.id_operacion: item.payload_hash for item in stored}
        if incoming != current:
            raise SyncConflictError("El contenido del lote no coincide con su envío original")

    async def _process_batch(self, principal: CurrentPrincipal, batch: SyncBatch) -> None:
        batch.estado = "PROCESANDO"
        await self.session.commit()
        for current in await self.repository.operations(batch.id_lote):
            operation = await self.repository.operation(current.id_operacion, lock=True)
            if operation is None or operation.estado in {"APLICADA", "CONFLICTO", "RECHAZADA"}:
                continue
            operation.estado = "PROCESANDO"
            operation.intentos += 1
            try:
                request = SyncOperationRequest(
                    id_operacion=operation.id_operacion,
                    tipo=operation.tipo,
                    fecha_cliente=operation.fecha_cliente,
                    payload=operation.payload,
                )
                parsed = parse_offline_payload(request)
                self._authorize_operation(principal, parsed)
                async with self.session.begin_nested():
                    if isinstance(parsed, SaleCreate):
                        result = await self.commerce.create_pos_sale(
                            principal.user.id_usuario,
                            parsed,
                            all_branches="ventas.sucursales_todas" in principal.permissions
                            or "ADMIN" in principal.roles,
                            commit=False,
                        )
                    else:
                        result = await self.commerce.create_reservation(
                            principal.user.id_usuario, parsed, commit=False
                        )
                operation.estado = "APLICADA"
                operation.resultado = result.model_dump(mode="json")
                operation.codigo_error = None
                operation.mensaje_error = None
            except CommerceConflictError as exc:
                await self._record_conflict(operation, exc.detail)
            except (
                ValidationError,
                ValueError,
                CommerceNotFoundError,
                CommerceForbiddenError,
                InvalidCommerceOperationError,
                SyncForbiddenError,
            ) as exc:
                operation.estado = "RECHAZADA"
                operation.codigo_error = "DATOS_INVALIDOS"
                operation.mensaje_error = self._safe_message(exc)
            except Exception:
                logger.exception(
                    "Error inesperado procesando operación offline %s",
                    operation.id_operacion,
                )
                operation.estado = "RECHAZADA"
                operation.codigo_error = "ERROR_INTERNO"
                operation.mensaje_error = "No se pudo procesar la operación"
            operation.procesada_at = datetime.now(UTC)
            await self.session.commit()

        operations = await self.repository.operations(batch.id_lote)
        batch = await self.repository.batch(batch.id_lote, lock=True)
        if batch is None:
            raise SyncNotFoundError("El lote de sincronización ya no existe")
        batch.total_aplicadas = sum(op.estado == "APLICADA" for op in operations)
        batch.total_conflictos = sum(op.estado == "CONFLICTO" for op in operations)
        batch.total_rechazadas = sum(op.estado == "RECHAZADA" for op in operations)
        batch.procesado_at = datetime.now(UTC)
        batch.estado = (
            "COMPLETADO_CON_CONFLICTOS"
            if batch.total_conflictos or batch.total_rechazadas
            else "COMPLETADO"
        )
        device = await self.repository.device(batch.id_dispositivo, lock=True)
        if device:
            device.ultima_sincronizacion = batch.procesado_at
        await self.session.commit()

    @staticmethod
    def _authorize_operation(
        principal: CurrentPrincipal, payload: SaleCreate | ReservationCreate
    ) -> None:
        if isinstance(payload, SaleCreate):
            required = {"ventas.crear", "pagos.registrar"}
            if not required.issubset(principal.permissions) and "ADMIN" not in principal.roles:
                raise SyncForbiddenError("No tiene permisos para registrar ventas offline")

    async def _record_conflict(self, operation: SyncOperation, message: str) -> None:
        operation.estado = "CONFLICTO"
        operation.codigo_error = (
            "STOCK_INSUFICIENTE"
            if "stock" in message.lower() or "lote" in message.lower()
            else "CONFLICTO_COMERCIAL"
        )
        operation.mensaje_error = message
        if await self.repository.conflict(operation.id_operacion) is None:
            await self.repository.add(
                SyncConflict(
                    id_tenant=operation.id_tenant,
                    id_operacion=operation.id_operacion,
                    tipo=operation.codigo_error,
                    detalle={"mensaje": message, "tipo_operacion": operation.tipo},
                )
            )

    @staticmethod
    def _safe_message(exc: Exception) -> str:
        detail = getattr(exc, "detail", None)
        if detail:
            return str(detail)[:500]
        if isinstance(exc, ValidationError):
            return "Los datos de la operación no cumplen el contrato de sincronización"
        return str(exc)[:500]

    async def get_batch(
        self, principal: CurrentPrincipal, batch_id: UUID
    ) -> SyncBatchResponse:
        self._require_offline(principal)
        batch = await self.repository.batch(batch_id)
        if batch is None:
            raise SyncNotFoundError("No se encontró el lote")
        if batch.id_usuario != principal.user.id_usuario:
            raise SyncForbiddenError("El lote pertenece a otra sesión")
        return await self._response(batch_id)

    async def confirm(
        self, principal: CurrentPrincipal, batch_id: UUID, device_id: UUID
    ) -> SyncBatchResponse:
        self._require_offline(principal)
        batch = await self.repository.batch(batch_id, lock=True)
        if batch is None:
            raise SyncNotFoundError("No se encontró el lote")
        if batch.id_usuario != principal.user.id_usuario or batch.id_dispositivo != device_id:
            raise SyncForbiddenError("El lote no pertenece al dispositivo actual")
        if batch.estado not in self.TERMINAL_BATCH_STATES:
            raise SyncConflictError("El lote todavía no terminó de procesarse")
        batch.estado = "CONFIRMADO"
        batch.confirmado_at = batch.confirmado_at or datetime.now(UTC)
        await self.session.commit()
        return await self._response(batch_id)

    async def _response(self, batch_id: UUID) -> SyncBatchResponse:
        batch = await self.repository.batch(batch_id)
        if batch is None:
            raise SyncNotFoundError("No se encontró el lote")
        operations = await self.repository.operations(batch_id)
        return SyncBatchResponse(
            id_lote=batch.id_lote,
            id_dispositivo=batch.id_dispositivo,
            estado=batch.estado,
            recibido_at=batch.recibido_at,
            procesado_at=batch.procesado_at,
            confirmado_at=batch.confirmado_at,
            total_operaciones=batch.total_operaciones,
            total_aplicadas=batch.total_aplicadas,
            total_conflictos=batch.total_conflictos,
            total_rechazadas=batch.total_rechazadas,
            operaciones=[
                SyncOperationResponse(
                    id_operacion=op.id_operacion,
                    tipo=op.tipo,
                    estado=op.estado,
                    resultado=op.resultado,
                    codigo_error=op.codigo_error,
                    mensaje_error=op.mensaje_error,
                    procesada_at=op.procesada_at,
                )
                for op in operations
            ],
        )

