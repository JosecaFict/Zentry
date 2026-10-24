from typing import Any, TypeVar

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Ciudad, Empleado, Sucursal
from app.modules.catalog.models import (
    Categoria,
    Color,
    InventarioSucursal,
    Producto,
    Talla,
    VarianteProducto,
)
from app.modules.inventory.models import (
    DetalleOrdenCompra,
    DetalleRecepcion,
    DetalleTransferencia,
    LoteInventario,
    MovimientoInventario,
    MovimientoLote,
    OrdenCompra,
    ProductoProveedor,
    Proveedor,
    RecepcionMercaderia,
    TransferenciaInventario,
)

ModelT = TypeVar("ModelT")


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get(self, model: type[ModelT], identity: int) -> ModelT | None:
        return await self.session.get(model, identity)

    async def flush(self) -> None:
        await self.session.flush()

    async def remove(self, entity: object) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def list_suppliers(self) -> list[Proveedor]:
        statement = select(Proveedor).order_by(Proveedor.razon_social)
        return list((await self.session.scalars(statement)).all())

    async def supplier_by_nit(self, nit: str, exclude_id: int | None = None) -> Proveedor | None:
        statement = select(Proveedor).where(func.lower(Proveedor.nit) == nit.strip().lower())
        if exclude_id is not None:
            statement = statement.where(Proveedor.id_proveedor != exclude_id)
        return await self.session.scalar(statement)

    async def list_supplier_products(self, supplier_id: int) -> list[tuple[ProductoProveedor, str]]:
        rows = (
            await self.session.execute(
                select(ProductoProveedor, Producto.nombre)
                .join(Producto, Producto.id_producto == ProductoProveedor.id_producto)
                .where(ProductoProveedor.id_proveedor == supplier_id)
                .order_by(Producto.nombre)
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def supplier_product_link(
        self, supplier_id: int, product_id: int
    ) -> ProductoProveedor | None:
        return await self.session.scalar(
            select(ProductoProveedor).where(
                ProductoProveedor.id_proveedor == supplier_id,
                ProductoProveedor.id_producto == product_id,
            )
        )

    async def list_purchase_orders(self, branch_id: int | None = None) -> list[OrdenCompra]:
        statement = select(OrdenCompra)
        if branch_id is not None:
            statement = statement.where(OrdenCompra.id_sucursal == branch_id)
        return list(
            (await self.session.scalars(statement.order_by(OrdenCompra.fecha_orden.desc()))).all()
        )

    async def purchase_details(self, order_id: int) -> list[DetalleOrdenCompra]:
        return list(
            (
                await self.session.scalars(
                    select(DetalleOrdenCompra).where(DetalleOrdenCompra.id_orden_compra == order_id)
                )
            ).all()
        )

    async def purchase_order_for_update(self, order_id: int) -> OrdenCompra | None:
        return await self.session.scalar(
            select(OrdenCompra).where(OrdenCompra.id_orden_compra == order_id).with_for_update()
        )

    async def received_quantities(self, order_id: int) -> dict[int, int]:
        rows = (
            await self.session.execute(
                select(DetalleRecepcion.id_variante, func.sum(DetalleRecepcion.cantidad_recibida))
                .join(
                    RecepcionMercaderia,
                    RecepcionMercaderia.id_recepcion == DetalleRecepcion.id_recepcion,
                )
                .where(
                    RecepcionMercaderia.id_orden_compra == order_id,
                    RecepcionMercaderia.estado == "CONFIRMADA",
                )
                .group_by(DetalleRecepcion.id_variante)
            )
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    async def list_receipts(self, branch_id: int | None = None) -> list[RecepcionMercaderia]:
        statement = select(RecepcionMercaderia)
        if branch_id is not None:
            statement = statement.where(RecepcionMercaderia.id_sucursal == branch_id)
        return list(
            (
                await self.session.scalars(
                    statement.order_by(RecepcionMercaderia.fecha_recepcion.desc())
                )
            ).all()
        )

    async def receipt_details(
        self, receipt_id: int
    ) -> list[tuple[DetalleRecepcion, LoteInventario]]:
        rows = (
            await self.session.execute(
                select(DetalleRecepcion, LoteInventario)
                .join(
                    RecepcionMercaderia,
                    RecepcionMercaderia.id_recepcion == DetalleRecepcion.id_recepcion,
                )
                .join(
                    LoteInventario,
                    and_(
                        LoteInventario.id_detalle_recepcion
                        == DetalleRecepcion.id_detalle_recepcion,
                        LoteInventario.id_sucursal == RecepcionMercaderia.id_sucursal,
                        LoteInventario.id_variante == DetalleRecepcion.id_variante,
                    ),
                )
                .where(DetalleRecepcion.id_recepcion == receipt_id)
                .order_by(DetalleRecepcion.id_detalle_recepcion)
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def get_or_create_inventory(self, branch_id: int, variant_id: int) -> InventarioSucursal:
        inventory = await self.session.scalar(
            select(InventarioSucursal)
            .where(
                InventarioSucursal.id_sucursal == branch_id,
                InventarioSucursal.id_variante == variant_id,
            )
            .with_for_update()
        )
        if inventory is None:
            inventory = InventarioSucursal(id_sucursal=branch_id, id_variante=variant_id)
            await self.add(inventory)
        return inventory

    async def inventory_for_update(self, inventory_id: int) -> InventarioSucursal | None:
        return await self.session.scalar(
            select(InventarioSucursal)
            .where(InventarioSucursal.id_inventario == inventory_id)
            .with_for_update()
        )

    @staticmethod
    def _inventory_statement():
        weighted_cost = (
            select(
                func.sum(LoteInventario.cantidad_disponible * LoteInventario.costo_unitario)
                / func.nullif(func.sum(LoteInventario.cantidad_disponible), 0)
            )
            .where(
                LoteInventario.id_sucursal == InventarioSucursal.id_sucursal,
                LoteInventario.id_variante == InventarioSucursal.id_variante,
                LoteInventario.activo.is_(True),
                LoteInventario.cantidad_disponible > 0,
            )
            .scalar_subquery()
        )
        return (
            select(
                InventarioSucursal,
                Sucursal.nombre,
                VarianteProducto.sku,
                Producto.nombre,
                Talla.codigo,
                Color.nombre,
                Categoria.nombre,
                weighted_cost,
                Color.codigo_hex,
            )
            .join(Sucursal, Sucursal.id_sucursal == InventarioSucursal.id_sucursal)
            .join(VarianteProducto, VarianteProducto.id_variante == InventarioSucursal.id_variante)
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
            .join(Color, Color.id_color == VarianteProducto.id_color)
            .join(Categoria, Categoria.id_categoria == Producto.id_categoria)
            .where(Producto.activo.is_(True), VarianteProducto.activo.is_(True))
        )

    async def list_inventory(self, **filters: Any) -> list[Any]:
        conditions = []
        mapping = {
            "branch_id": InventarioSucursal.id_sucursal,
            "product_id": Producto.id_producto,
            "variant_id": InventarioSucursal.id_variante,
            "size_id": Talla.id_talla,
            "color_id": Color.id_color,
            "category_id": Categoria.id_categoria,
        }
        for key, column in mapping.items():
            if filters.get(key) is not None:
                conditions.append(column == filters[key])
        available = InventarioSucursal.stock_fisico - InventarioSucursal.stock_reservado
        if filters.get("low_stock") is True:
            conditions.extend([available > 0, available <= InventarioSucursal.stock_minimo])
        if filters.get("out_of_stock") is True:
            conditions.append(available == 0)
        statement = (
            self._inventory_statement()
            .where(*conditions)
            .order_by(Sucursal.nombre, Producto.nombre)
        )
        return list((await self.session.execute(statement)).all())

    async def get_inventory_record(self, inventory_id: int) -> Any | None:
        return (
            await self.session.execute(
                self._inventory_statement().where(InventarioSucursal.id_inventario == inventory_id)
            )
        ).one_or_none()

    async def fifo_lots(self, branch_id: int, variant_id: int) -> list[LoteInventario]:
        return list(
            (
                await self.session.scalars(
                    select(LoteInventario)
                    .where(
                        LoteInventario.id_sucursal == branch_id,
                        LoteInventario.id_variante == variant_id,
                        LoteInventario.activo.is_(True),
                        LoteInventario.cantidad_disponible > 0,
                    )
                    .order_by(LoteInventario.fecha_ingreso, LoteInventario.id_lote)
                    .with_for_update()
                )
            ).all()
        )

    async def lots_with_capacity(self, branch_id: int, variant_id: int) -> list[LoteInventario]:
        return list(
            (
                await self.session.scalars(
                    select(LoteInventario)
                    .where(
                        LoteInventario.id_sucursal == branch_id,
                        LoteInventario.id_variante == variant_id,
                        LoteInventario.activo.is_(True),
                        LoteInventario.cantidad_disponible < LoteInventario.cantidad_inicial,
                    )
                    .order_by(LoteInventario.fecha_ingreso.desc(), LoteInventario.id_lote.desc())
                    .with_for_update()
                )
            ).all()
        )

    async def list_lots(self, **filters: Any) -> list[Any]:
        statement = (
            select(
                LoteInventario,
                Sucursal.nombre,
                Producto.nombre,
                VarianteProducto.sku,
                Talla.codigo,
                Color.nombre,
                Color.codigo_hex,
            )
            .join(Sucursal, Sucursal.id_sucursal == LoteInventario.id_sucursal)
            .join(VarianteProducto, VarianteProducto.id_variante == LoteInventario.id_variante)
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
            .join(Color, Color.id_color == VarianteProducto.id_color)
            .join(
                DetalleRecepcion,
                DetalleRecepcion.id_detalle_recepcion == LoteInventario.id_detalle_recepcion,
            )
            .join(
                RecepcionMercaderia,
                RecepcionMercaderia.id_recepcion == DetalleRecepcion.id_recepcion,
            )
            .outerjoin(
                OrdenCompra, OrdenCompra.id_orden_compra == RecepcionMercaderia.id_orden_compra
            )
        )
        mapping = {
            "branch_id": LoteInventario.id_sucursal,
            "variant_id": LoteInventario.id_variante,
            "product_id": VarianteProducto.id_producto,
            "supplier_id": OrdenCompra.id_proveedor,
            "active": LoteInventario.activo,
        }
        for key, column in mapping.items():
            if filters.get(key) is not None:
                statement = statement.where(column == filters[key])
        if filters.get("with_stock") is not None:
            operator = (
                LoteInventario.cantidad_disponible > 0
                if filters["with_stock"]
                else LoteInventario.cantidad_disponible == 0
            )
            statement = statement.where(operator)
        return list(
            (
                await self.session.execute(
                    statement.order_by(
                        LoteInventario.fecha_ingreso.desc(),
                        LoteInventario.id_lote.desc(),
                    )
                )
            ).all()
        )

    async def list_movements(self, **filters: Any) -> list[Any]:
        statement = (
            select(
                MovimientoInventario,
                Sucursal.nombre,
                Producto.nombre,
                VarianteProducto.sku,
                Talla.codigo,
                Color.nombre,
                Color.codigo_hex,
            )
            .join(
                InventarioSucursal,
                InventarioSucursal.id_inventario == MovimientoInventario.id_inventario,
            )
            .join(Sucursal, Sucursal.id_sucursal == InventarioSucursal.id_sucursal)
            .join(VarianteProducto, VarianteProducto.id_variante == InventarioSucursal.id_variante)
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
            .join(Color, Color.id_color == VarianteProducto.id_color)
        )
        mapping = {
            "inventory_id": MovimientoInventario.id_inventario,
            "branch_id": InventarioSucursal.id_sucursal,
            "variant_id": InventarioSucursal.id_variante,
            "movement_type": MovimientoInventario.tipo_movimiento,
        }
        for key, column in mapping.items():
            if filters.get(key) is not None:
                statement = statement.where(column == filters[key])
        if filters.get("date_from") is not None:
            statement = statement.where(MovimientoInventario.fecha_hora >= filters["date_from"])
        if filters.get("date_to") is not None:
            statement = statement.where(MovimientoInventario.fecha_hora <= filters["date_to"])
        return list(
            (
                await self.session.execute(
                    statement.order_by(
                        MovimientoInventario.fecha_hora.desc(),
                        MovimientoInventario.id_movimiento.desc(),
                    )
                )
            ).all()
        )

    async def movement_lots(self, movement_id: int) -> list[MovimientoLote]:
        return list(
            (
                await self.session.scalars(
                    select(MovimientoLote).where(MovimientoLote.id_movimiento == movement_id)
                )
            ).all()
        )

    async def list_transfers(self) -> list[TransferenciaInventario]:
        return list(
            (
                await self.session.scalars(
                    select(TransferenciaInventario).order_by(
                        TransferenciaInventario.fecha_solicitud.desc()
                    )
                )
            ).all()
        )

    async def transfer_for_update(self, transfer_id: int) -> TransferenciaInventario | None:
        return await self.session.scalar(
            select(TransferenciaInventario)
            .where(TransferenciaInventario.id_transferencia == transfer_id)
            .with_for_update()
        )

    async def transfer_details(self, transfer_id: int) -> list[DetalleTransferencia]:
        return list(
            (
                await self.session.scalars(
                    select(DetalleTransferencia).where(
                        DetalleTransferencia.id_transferencia == transfer_id
                    )
                )
            ).all()
        )

    async def movement_exists(self, reference_id: int, movement_type: str) -> bool:
        return (
            await self.session.scalar(
                select(MovimientoInventario.id_movimiento).where(
                    MovimientoInventario.referencia_tipo == "TRANSFERENCIA",
                    MovimientoInventario.referencia_id == reference_id,
                    MovimientoInventario.tipo_movimiento == movement_type,
                )
            )
            is not None
        )

    async def referenced_movement(
        self, reference_id: int, movement_type: str, inventory_id: int
    ) -> MovimientoInventario | None:
        return await self.session.scalar(
            select(MovimientoInventario).where(
                MovimientoInventario.referencia_tipo == "TRANSFERENCIA",
                MovimientoInventario.referencia_id == reference_id,
                MovimientoInventario.tipo_movimiento == movement_type,
                MovimientoInventario.id_inventario == inventory_id,
            )
        )

    async def employee(self, employee_id: int) -> Empleado | None:
        return await self.get(Empleado, employee_id)

    async def employee_by_user(self, user_id: int) -> Empleado | None:
        return await self.session.scalar(select(Empleado).where(Empleado.id_usuario == user_id))

    async def branch(self, branch_id: int) -> Sucursal | None:
        return await self.get(Sucursal, branch_id)

    async def city(self, city_id: int) -> Ciudad | None:
        return await self.get(Ciudad, city_id)

    async def variant(self, variant_id: int) -> VarianteProducto | None:
        return await self.get(VarianteProducto, variant_id)

    async def product(self, product_id: int) -> Producto | None:
        return await self.get(Producto, product_id)
