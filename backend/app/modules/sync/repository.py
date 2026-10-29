from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Sucursal
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

