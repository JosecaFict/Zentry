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
from app.modules.commerce.schemas import SaleCreate
from app.modules.commerce.service import CommerceService
from app.modules.sync.exceptions import SyncConflictError, SyncForbiddenError, SyncNotFoundError
from app.modules.sync.models import SyncBatch, SyncConflict, SyncDevice, SyncOperation
from app.modules.sync.repository import SyncRepository
from app.modules.sync.schemas import (
    CatalogSnapshotItem,
    CatalogSnapshotResponse,
    OfflineReservationCreate,
    SyncBatchRequest,
    SyncBatchResponse,
    SyncConflictItem,
    SyncConflictResolveRequest,
    SyncConflictResponse,
    SyncDeviceRegister,
    SyncDeviceResponse,
    SyncOperationRequest,
    SyncOperationResponse,
    SyncOperationStatusResponse,
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

    @staticmethod
    def _parse_stored(operation: SyncOperation) -> SaleCreate | OfflineReservationCreate:
        return parse_offline_payload(
            SyncOperationRequest(
                id_operacion=operation.id_operacion,
                tipo=operation.tipo,
                fecha_cliente=operation.fecha_cliente,
                payload=operation.payload,
            )
        )

    async def _apply(
        self,
        user_id: int,
        parsed: SaleCreate | OfflineReservationCreate,
        *,
        all_branches: bool,
    ):
        """Registra la venta o reserva en una transacción anidada."""
        async with self.session.begin_nested():
            if isinstance(parsed, SaleCreate):
                return await self.commerce.create_pos_sale(
                    user_id,
                    parsed,
                    all_branches=all_branches,
                    commit=False,
                    collected_prices=parsed.precios_cobrados,
                )
            return await self.commerce.create_reservation(
                user_id,
                parsed,
                customer_id=parsed.id_cliente,
                all_branches=all_branches,
                commit=False,
            )

    async def _process_batch(self, principal: CurrentPrincipal, batch: SyncBatch) -> None:
        batch.estado = "PROCESANDO"
        await self.session.commit()
        new_conflicts: list[tuple[SyncConflict, SyncOperation]] = []
        for current in await self.repository.operations(batch.id_lote):
            operation = await self.repository.operation(current.id_operacion, lock=True)
            if operation is None or operation.estado in {"APLICADA", "CONFLICTO", "RECHAZADA"}:
                continue
            operation.estado = "PROCESANDO"
            operation.intentos += 1
            try:
                parsed = self._parse_stored(operation)
                self._authorize_operation(principal, parsed)
                result = await self._apply(
                    principal.user.id_usuario,
                    parsed,
                    all_branches="ventas.sucursales_todas" in principal.permissions
                    or "ADMIN" in principal.roles,
                )
                operation.estado = "APLICADA"
                operation.resultado = result.model_dump(mode="json")
                operation.codigo_error = None
                operation.mensaje_error = None
            except CommerceConflictError as exc:
                if conflict := await self._record_conflict(operation, exc.detail):
                    new_conflicts.append((conflict, operation))
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
            if operation.estado == "RECHAZADA":
                # También queda para revisión del supervisor: la venta pudo
                # ocurrir en la tienda aunque el servidor no la aceptara.
                if conflict := await self._register_review(operation):
                    new_conflicts.append((conflict, operation))
            operation.procesada_at = datetime.now(UTC)
            await self.session.commit()

        await self._notify_supervisors(new_conflicts)

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
        principal: CurrentPrincipal, payload: SaleCreate | OfflineReservationCreate
    ) -> None:
        if isinstance(payload, SaleCreate):
            required = {"ventas.crear", "pagos.registrar"}
            if not required.issubset(principal.permissions) and "ADMIN" not in principal.roles:
                raise SyncForbiddenError("No tiene permisos para registrar ventas offline")
        elif "reservas.gestionar" not in principal.permissions and "ADMIN" not in principal.roles:
            raise SyncForbiddenError("No tiene permisos para registrar reservas offline")

    async def _record_conflict(
        self, operation: SyncOperation, message: str
    ) -> SyncConflict | None:
        operation.estado = "CONFLICTO"
        operation.codigo_error = (
            "STOCK_INSUFICIENTE"
            if "stock" in message.lower() or "lote" in message.lower()
            else "CONFLICTO_COMERCIAL"
        )
        operation.mensaje_error = message
        return await self._register_review(operation)

    async def _register_review(self, operation: SyncOperation) -> SyncConflict | None:
        """Crea el registro para el supervisor. Devuelve None si ya existía."""
        if await self.repository.conflict(operation.id_operacion) is not None:
            return None
        return await self.repository.add(
            SyncConflict(
                id_tenant=operation.id_tenant,
                id_operacion=operation.id_operacion,
                tipo=operation.codigo_error or "CONFLICTO_COMERCIAL",
                detalle={
                    "mensaje": operation.mensaje_error,
                    "tipo_operacion": operation.tipo,
                },
                estado="PENDIENTE",
                # Se asigna aquí: el server_default no se relee tras el INSERT.
                created_at=datetime.now(UTC),
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

    # ── Resolución de conflictos (fase 5) ─────────────────────────────────

    SUPERVISOR_ROLES = frozenset({"ADMIN", "ADMINISTRADOR", "ENCARGADO_SUCURSAL"})
    ALL_BRANCH_ROLES = frozenset({"ADMIN", "ADMINISTRADOR"})
    REAPPLICABLE = frozenset({"STOCK_INSUFICIENTE", "CONFLICTO_COMERCIAL", "ERROR_INTERNO"})
    REASONS = {
        "STOCK_INSUFICIENTE": "No había stock: otra venta o reserva se registró antes",
        "CONFLICTO_COMERCIAL": "Choca con otra operación (precio, reserva o pedido)",
        "DATOS_INVALIDOS": "Faltan datos o no son válidos",
        "ERROR_INTERNO": "Error del servidor al registrarla",
    }
    CONFLICTS_ROUTE = "/admin/conflictos"
    DEVICE_ROUTE = "/admin/offline"

    @classmethod
    def _supervisor_scope(cls, principal: CurrentPrincipal) -> int | None:
        """Sucursal que puede revisar (None = todas). Lanza si no es supervisor."""
        roles = {role.upper() for role in principal.roles}
        all_branches = (
            bool(roles & cls.ALL_BRANCH_ROLES)
            or "ventas.sucursales_todas" in principal.permissions
        )
        if not all_branches and "ENCARGADO_SUCURSAL" not in roles:
            raise SyncForbiddenError("Solo un encargado o administrador revisa conflictos")
        if all_branches:
            return None
        if principal.id_sucursal is None:
            raise SyncForbiddenError("El encargado no tiene una sucursal asignada")
        return principal.id_sucursal

    @staticmethod
    def _branch_of(operation: SyncOperation) -> int | None:
        value = (operation.payload or {}).get("id_sucursal")
        return value if isinstance(value, int) else None

    @staticmethod
    def _items_of(operation: SyncOperation) -> list[tuple[int, int]]:
        items = []
        for raw in (operation.payload or {}).get("items") or []:
            if isinstance(raw, dict) and isinstance(raw.get("id_variante"), int):
                items.append((raw["id_variante"], int(raw.get("cantidad") or 0)))
        return items

    async def _conflict_responses(
        self, rows: list[tuple[SyncConflict, SyncOperation]]
    ) -> list[SyncConflictResponse]:
        variant_ids = {vid for _, op in rows for vid, _ in self._items_of(op)}
        user_ids = {op.id_usuario for _, op in rows} | {
            c.resuelto_por for c, _ in rows if c.resuelto_por is not None
        }
        labels = await self.repository.variant_labels(variant_ids)
        names = await self.repository.user_names(user_ids)
        responses = []
        for conflict, operation in rows:
            total = (operation.payload or {}).get("total_cobrado_centavos")
            responses.append(
                SyncConflictResponse(
                    id_conflicto=conflict.id_conflicto,
                    id_operacion=operation.id_operacion,
                    tipo_operacion=operation.tipo,
                    codigo=conflict.tipo,
                    mensaje=operation.mensaje_error,
                    estado=conflict.estado,
                    id_sucursal=self._branch_of(operation),
                    id_vendedor=operation.id_usuario,
                    vendedor=names.get(operation.id_usuario),
                    items=[
                        SyncConflictItem(
                            id_variante=vid,
                            cantidad=qty,
                            descripcion=labels.get(vid, f"Variante #{vid}"),
                        )
                        for vid, qty in self._items_of(operation)
                    ],
                    total_cobrado_centavos=total if isinstance(total, int) else None,
                    fecha_cliente=operation.fecha_cliente,
                    created_at=conflict.created_at,
                    puede_reaplicar=conflict.estado == "PENDIENTE"
                    and conflict.tipo in self.REAPPLICABLE,
                    accion=(conflict.detalle or {}).get("accion"),
                    resolucion=conflict.resolucion,
                    resuelto_por=names.get(conflict.resuelto_por)
                    if conflict.resuelto_por is not None
                    else None,
                    resuelto_at=conflict.resuelto_at,
                )
            )
        return responses

    async def _notify_supervisors(
        self, conflicts: list[tuple[SyncConflict, SyncOperation]]
    ) -> None:
        """Push + notificación en bandeja a encargados de la sucursal y admins."""
        if not conflicts:
            return
        try:
            for conflict, operation in conflicts:
                recipients = await self.repository.conflict_supervisors(
                    self._branch_of(operation)
                )
                recipients.discard(operation.id_usuario)  # Ya tiene su alerta local.
                if not recipients:
                    continue
                [summary] = await self._conflict_responses([(conflict, operation)])
                items = ", ".join(item.descripcion for item in summary.items)
                label = "Venta" if operation.tipo == "VENTA" else "Reserva"
                await self.commerce.notify_users(
                    recipients,
                    "SYNC_CONFLICTO",
                    f"⚠ {label} offline no registrada",
                    f"{summary.vendedor or 'Un vendedor'} · {items or 'sin detalle'} · "
                    f"{self.REASONS.get(conflict.tipo, 'Requiere revisión')}",
                    data={
                        "route": self.CONFLICTS_ROUTE,
                        "type": "SYNC_CONFLICTO",
                        "id": conflict.id_conflicto,
                    },
                )
            await self.session.commit()
        except Exception:
            # El aviso nunca debe romper la sincronización ya guardada.
            logger.exception("No se pudo avisar a los supervisores del conflicto")
            await self.session.rollback()

    async def list_conflicts(
        self,
        principal: CurrentPrincipal,
        *,
        state: str | None = "PENDIENTE",
        branch_id: int | None = None,
    ) -> list[SyncConflictResponse]:
        tenant_id = self._require_offline(principal)
        scope = self._supervisor_scope(principal)
        if scope is not None:
            if branch_id is not None and branch_id != scope:
                raise SyncForbiddenError("Solo puede revisar conflictos de su sucursal")
            branch_id = scope
        rows = await self.repository.conflicts(tenant_id, state=state, branch_id=branch_id)
        return await self._conflict_responses(rows)

    async def resolve_conflict(
        self,
        principal: CurrentPrincipal,
        conflict_id: int,
        payload: SyncConflictResolveRequest,
    ) -> SyncConflictResponse:
        tenant_id = self._require_offline(principal)
        scope = self._supervisor_scope(principal)
        conflict = await self.repository.conflict_by_id(conflict_id, lock=True)
        if conflict is None or conflict.id_tenant != tenant_id:
            raise SyncNotFoundError("El conflicto no existe")
        operation = await self.repository.operation(conflict.id_operacion, lock=True)
        if operation is None:
            raise SyncNotFoundError("La operación del conflicto ya no existe")
        branch_id = self._branch_of(operation)
        if scope is not None and branch_id != scope:
            raise SyncForbiddenError("Solo puede resolver conflictos de su sucursal")
        if conflict.estado != "PENDIENTE":
            raise SyncConflictError("Este conflicto ya fue resuelto")

        now = datetime.now(UTC)
        if payload.accion == "REAPLICAR":
            if conflict.tipo not in self.REAPPLICABLE:
                raise SyncConflictError(
                    "Una operación con datos inválidos no puede reaplicarse; anúlala"
                )
            try:
                parsed = self._parse_stored(operation)
                # Se registra a nombre del vendedor original; el permiso de
                # sucursal ya lo validó el supervisor.
                result = await self._apply(operation.id_usuario, parsed, all_branches=True)
            except CommerceConflictError as exc:
                raise SyncConflictError(
                    f"Todavía no se puede registrar: {exc.detail}. "
                    "Si hay stock real, ajusta primero el inventario."
                ) from exc
            except (
                ValidationError,
                ValueError,
                CommerceNotFoundError,
                CommerceForbiddenError,
                InvalidCommerceOperationError,
            ) as exc:
                raise SyncConflictError(
                    f"No se puede registrar: {self._safe_message(exc)}"
                ) from exc
            operation.estado = "APLICADA"
            operation.resultado = result.model_dump(mode="json")
            operation.codigo_error = None
            operation.mensaje_error = None
            operation.procesada_at = now
            conflict.estado = "RESUELTO"
            action = "REAPLICADA"
        else:
            conflict.estado = "DESCARTADO"
            action = "ANULADA"
        conflict.detalle = {**(conflict.detalle or {}), "accion": action}
        conflict.resolucion = payload.nota
        conflict.resuelto_por = principal.user.id_usuario
        conflict.resuelto_at = now
        await self.session.commit()

        [response] = await self._conflict_responses([(conflict, operation)])
        await self._notify_seller(response, principal)
        return response

    async def _notify_seller(
        self, conflict: SyncConflictResponse, principal: CurrentPrincipal
    ) -> None:
        if conflict.id_vendedor == principal.user.id_usuario:
            return
        try:
            label = "Venta" if conflict.tipo_operacion == "VENTA" else "Reserva"
            items = ", ".join(item.descripcion for item in conflict.items)
            outcome = (
                "registrada por el supervisor"
                if conflict.accion == "REAPLICADA"
                else "anulada por el supervisor"
            )
            await self.commerce.notify_users(
                {conflict.id_vendedor},
                "SYNC_CONFLICTO_RESUELTO",
                f"{label} offline {outcome}",
                f"{items or 'Operación'}"
                + (f" · {conflict.resolucion}" if conflict.resolucion else ""),
                data={"route": self.DEVICE_ROUTE, "type": "SYNC_CONFLICTO"},
            )
            await self.session.commit()
        except Exception:
            logger.exception("No se pudo avisar al vendedor de la resolución")
            await self.session.rollback()

    async def operation_status(
        self, principal: CurrentPrincipal, ids: list[UUID]
    ) -> list[SyncOperationStatusResponse]:
        """El dispositivo pregunta cómo quedaron sus operaciones fallidas."""
        self._require_offline(principal)
        rows = await self.repository.operations_with_conflicts(
            ids[:100], principal.user.id_usuario
        )
        return [
            SyncOperationStatusResponse(
                id_operacion=operation.id_operacion,
                estado=operation.estado,
                codigo_error=operation.codigo_error,
                mensaje_error=operation.mensaje_error,
                conflicto_estado=conflict.estado if conflict else None,
                accion=(conflict.detalle or {}).get("accion") if conflict else None,
                resolucion=conflict.resolucion if conflict else None,
            )
            for operation, conflict in rows
        ]

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

