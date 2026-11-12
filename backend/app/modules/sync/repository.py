from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Empleado, Rol, Sucursal, Usuario, UsuarioRol
from app.modules.catalog.models import (
    Color,
    HistorialPrecio,
    InventarioSucursal,
    Producto,
    Talla,
    VarianteProducto,
)
from app.modules.sync.models import SyncBatch, SyncConflict, SyncDevice, SyncOperation


class SyncRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, entity):
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def device(self, device_id: UUID, *, lock: bool = False) -> SyncDevice | None:
        statement = select(SyncDevice).where(SyncDevice.id_dispositivo == device_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def batch(self, batch_id: UUID, *, lock: bool = False) -> SyncBatch | None:
        statement = select(SyncBatch).where(SyncBatch.id_lote == batch_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def operation(
        self, operation_id: UUID, *, lock: bool = False
    ) -> SyncOperation | None:
        statement = select(SyncOperation).where(SyncOperation.id_operacion == operation_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def operations(self, batch_id: UUID) -> list[SyncOperation]:
        result = await self.session.scalars(
            select(SyncOperation)
            .where(SyncOperation.id_lote == batch_id)
            .order_by(SyncOperation.created_at, SyncOperation.id_operacion)
        )
        return list(result.all())

    async def conflict(self, operation_id: UUID) -> SyncConflict | None:
        return await self.session.scalar(
            select(SyncConflict).where(SyncConflict.id_operacion == operation_id)
        )

    async def conflict_by_id(
        self, conflict_id: int, *, lock: bool = False
    ) -> SyncConflict | None:
        statement = select(SyncConflict).where(SyncConflict.id_conflicto == conflict_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def conflicts(
        self,
        tenant_id: int,
        *,
        state: str | None,
        branch_id: int | None,
        limit: int = 200,
    ) -> list[tuple[SyncConflict, SyncOperation]]:
        """Conflictos con su operación; la sucursal sale del payload offline."""
        statement = (
            select(SyncConflict, SyncOperation)
            .join(SyncOperation, SyncOperation.id_operacion == SyncConflict.id_operacion)
            .where(SyncConflict.id_tenant == tenant_id)
            .order_by(SyncConflict.created_at.desc(), SyncConflict.id_conflicto.desc())
            .limit(limit)
        )
        if state is not None:
            statement = statement.where(SyncConflict.estado == state)
        if branch_id is not None:
            statement = statement.where(
                SyncOperation.payload["id_sucursal"].as_integer() == branch_id
            )
        return [(row[0], row[1]) for row in (await self.session.execute(statement)).all()]

    async def operations_with_conflicts(
        self, ids: list[UUID], user_id: int
    ) -> list[tuple[SyncOperation, SyncConflict | None]]:
        """Estado actual de operaciones propias del vendedor (para su dispositivo)."""
        if not ids:
            return []
        statement = (
            select(SyncOperation, SyncConflict)
            .outerjoin(SyncConflict, SyncConflict.id_operacion == SyncOperation.id_operacion)
            .where(
                SyncOperation.id_operacion.in_(ids),
                SyncOperation.id_usuario == user_id,
            )
        )
        return [(row[0], row[1]) for row in (await self.session.execute(statement)).all()]

    async def user_names(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rows = await self.session.execute(
            select(Usuario.id_usuario, Usuario.nombres, Usuario.apellidos).where(
                Usuario.id_usuario.in_(user_ids)
            )
        )
        return {
            int(row.id_usuario): f"{row.nombres} {row.apellidos}".strip()
            for row in rows.all()
        }

    async def variant_labels(self, variant_ids: set[int]) -> dict[int, str]:
        """id_variante → "Polo básico M Negro"."""
        if not variant_ids:
            return {}
        rows = await self.session.execute(
            select(
                VarianteProducto.id_variante,
                Producto.nombre,
                Talla.codigo,
                Color.nombre.label("color"),
            )
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
            .join(Color, Color.id_color == VarianteProducto.id_color)
            .where(VarianteProducto.id_variante.in_(variant_ids))
        )
        return {
            int(row.id_variante): f"{row.nombre} {row.codigo} {row.color}"
            for row in rows.all()
        }

    async def conflict_supervisors(self, branch_id: int | None) -> set[int]:
        """Encargados activos de la sucursal y administradores de la empresa."""
        active_user = func.upper(func.coalesce(Usuario.estado, "ACTIVO")) != "INACTIVO"
        admins = (
            select(UsuarioRol.id_usuario)
            .join(Rol, Rol.id_rol == UsuarioRol.id_rol)
            .join(Usuario, Usuario.id_usuario == UsuarioRol.id_usuario)
            .where(func.upper(Rol.nombre).in_(["ADMIN", "ADMINISTRADOR"]), active_user)
        )
        ids = {int(uid) for uid in (await self.session.scalars(admins)).all()}
        if branch_id is not None:
            managers = (
                select(Empleado.id_usuario)
                .join(Usuario, Usuario.id_usuario == Empleado.id_usuario)
                .join(UsuarioRol, UsuarioRol.id_usuario == Empleado.id_usuario)
                .join(Rol, Rol.id_rol == UsuarioRol.id_rol)
                .where(
                    Empleado.id_sucursal == branch_id,
                    func.upper(Rol.nombre) == "ENCARGADO_SUCURSAL",
                    func.upper(func.coalesce(Empleado.estado_laboral, "ACTIVO")) != "INACTIVO",
                    active_user,
                )
            )
            ids |= {int(uid) for uid in (await self.session.scalars(managers)).all()}
        return ids

    async def branch(self, branch_id: int) -> Sucursal | None:
        return await self.session.get(Sucursal, branch_id)

    async def catalog_snapshot(self, branch_id: int):
        current_price = (
            select(HistorialPrecio.precio)
            .where(
                HistorialPrecio.id_producto == Producto.id_producto,
                HistorialPrecio.fecha_fin.is_(None),
            )
            .order_by(HistorialPrecio.fecha_inicio.desc())
            .limit(1)
            .scalar_subquery()
        )
        statement = (
            select(
                VarianteProducto.id_variante,
                VarianteProducto.sku,
                Producto.nombre.label("producto"),
                Talla.codigo.label("talla"),
                Color.nombre.label("color"),
                func.coalesce(current_price, 0).label("precio"),
                func.coalesce(InventarioSucursal.stock_fisico, 0).label("stock_fisico"),
                func.coalesce(InventarioSucursal.stock_reservado, 0).label("stock_reservado"),
                (
                    func.coalesce(InventarioSucursal.stock_fisico, 0)
                    - func.coalesce(InventarioSucursal.stock_reservado, 0)
                ).label("stock_disponible"),
                InventarioSucursal.updated_at,
            )
            .select_from(VarianteProducto)
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
            .join(Color, Color.id_color == VarianteProducto.id_color)
            .outerjoin(
                InventarioSucursal,
                (InventarioSucursal.id_variante == VarianteProducto.id_variante)
                & (InventarioSucursal.id_sucursal == branch_id),
            )
            .where(VarianteProducto.activo.is_(True), Producto.activo.is_(True))
            .order_by(Producto.nombre, Talla.orden, Color.nombre)
        )
        return (await self.session.execute(statement)).mappings().all()

