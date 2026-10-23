from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Ciudad, Cliente, Empleado, Sucursal, Usuario
from app.modules.catalog.models import (
    Color,
    HistorialPrecio,
    ImagenProducto,
    InventarioSucursal,
    Marca,
    Producto,
    ProductoTemporada,
    Talla,
    VarianteProducto,
)
from app.modules.commerce.models import (
    Campania,
    Carrito,
    DetalleCarrito,
    DetalleDevolucion,
    DetalleReserva,
    DetalleVenta,
    Devolucion,
    DireccionCliente,
    MetodoPago,
    Notificacion,
    Pago,
    Pedido,
    Promocion,
    PromocionCategoria,
    PromocionProducto,
    PromocionTemporada,
    Reserva,
    TarifaEnvio,
    TransaccionPasarela,
    Venta,
)
from app.modules.inventory.models import (
    DetalleRecepcion,
    LoteInventario,
    MovimientoInventario,
    MovimientoLote,
    OrdenCompra,
    Proveedor,
    RecepcionMercaderia,
)


class CommerceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, model, identity: int):
        return await self.session.get(model, identity)

    async def add(self, entity):
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def customer_by_user(self, user_id: int) -> Cliente | None:
        return await self.session.scalar(select(Cliente).where(Cliente.id_usuario == user_id))

    async def employee_by_user(self, user_id: int) -> Empleado | None:
        return await self.session.scalar(select(Empleado).where(Empleado.id_usuario == user_id))

    async def active_cart(self, customer_id: int, *, lock: bool = False) -> Carrito | None:
        statement = select(Carrito).where(
            Carrito.id_cliente == customer_id, Carrito.estado == "ACTIVO"
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def cart_item(self, cart_id: int, item_id: int) -> DetalleCarrito | None:
        return await self.session.scalar(
            select(DetalleCarrito).where(
                DetalleCarrito.id_carrito == cart_id,
                DetalleCarrito.id_detalle_carrito == item_id,
            )
        )

    async def cart_item_by_variant(self, cart_id: int, variant_id: int) -> DetalleCarrito | None:
        return await self.session.scalar(
            select(DetalleCarrito).where(
                DetalleCarrito.id_carrito == cart_id,
                DetalleCarrito.id_variante == variant_id,
            )
        )

    async def cart_details(self, cart_id: int) -> list[DetalleCarrito]:
        return list(
            (
                await self.session.scalars(
                    select(DetalleCarrito)
                    .where(DetalleCarrito.id_carrito == cart_id)
                    .order_by(DetalleCarrito.id_detalle_carrito)
                )
            ).all()
        )

    async def clear_cart_items(self, cart_id: int) -> None:
        await self.session.execute(
            delete(DetalleCarrito).where(DetalleCarrito.id_carrito == cart_id)
        )

    async def variant_row(self, variant_id: int, branch_id: int | None = None):
        price = (
            select(HistorialPrecio.precio)
            .where(
                HistorialPrecio.id_producto == Producto.id_producto,
                HistorialPrecio.fecha_fin.is_(None),
            )
            .order_by(HistorialPrecio.fecha_inicio.desc())
            .limit(1)
            .scalar_subquery()
        )
        image = (
            select(ImagenProducto.secure_url)
            .where(
                ImagenProducto.id_producto == Producto.id_producto,
                or_(
                    ImagenProducto.id_color == VarianteProducto.id_color,
                    ImagenProducto.id_color.is_(None),
                ),
            )
            .order_by(ImagenProducto.es_principal.desc(), ImagenProducto.orden)
            .limit(1)
            .scalar_subquery()
        )
        conditions = [InventarioSucursal.id_variante == VarianteProducto.id_variante]
        if branch_id is not None:
            conditions.append(InventarioSucursal.id_sucursal == branch_id)

        available = (
            select(
                func.coalesce(
                    func.sum(InventarioSucursal.stock_fisico - InventarioSucursal.stock_reservado),
                    0,
                )
            )
            .where(*conditions)
            .scalar_subquery()
        )
        statement = (
            select(
                VarianteProducto.id_variante,
                VarianteProducto.sku,
                Producto.id_producto,
                Producto.nombre.label("producto"),
                Talla.codigo.label("talla"),
                Color.nombre.label("color"),
                (VarianteProducto.activo & Producto.activo).label("activo"),
                func.coalesce(price, 0).label("precio"),
                available.label("stock_disponible"),
                image.label("imagen_url"),
            )
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
            .join(Color, Color.id_color == VarianteProducto.id_color)
            .where(VarianteProducto.id_variante == variant_id)
        )
        return (await self.session.execute(statement)).mappings().one_or_none()

    async def inventory_for_update(
        self, branch_id: int, variant_id: int
    ) -> InventarioSucursal | None:
        return await self.session.scalar(
            select(InventarioSucursal)
            .where(
                InventarioSucursal.id_sucursal == branch_id,
                InventarioSucursal.id_variante == variant_id,
            )
            .with_for_update()
        )

    async def reservation_details(self, reservation_id: int) -> list[DetalleReserva]:
        return list(
            (
                await self.session.scalars(
                    select(DetalleReserva).where(DetalleReserva.id_reserva == reservation_id)
                )
            ).all()
        )

    async def customer_reservations(self, customer_id: int) -> list[Reserva]:
        return list(
            (
                await self.session.scalars(
                    select(Reserva)
                    .where(Reserva.id_cliente == customer_id)
                    .order_by(Reserva.fecha_reserva.desc())
                )
            ).all()
        )

    async def all_reservations(
        self, *, state: str | None = None, branch_id: int | None = None
    ) -> list[Reserva]:
        statement = select(Reserva)
        if state:
            statement = statement.where(Reserva.estado == state)
        if branch_id:
            statement = statement.where(Reserva.id_sucursal == branch_id)
        return list(
            (await self.session.scalars(statement.order_by(Reserva.fecha_reserva.desc()))).all()
        )

    async def sale_details(self, sale_id: int) -> list[DetalleVenta]:
        return list(
            (
                await self.session.scalars(
                    select(DetalleVenta).where(DetalleVenta.id_venta == sale_id)
                )
            ).all()
        )

    async def sale_invoice_items(self, sale_id: int):
        statement = (
            select(
                DetalleVenta.cantidad,
                DetalleVenta.precio_unitario,
                DetalleVenta.subtotal,
                Producto.nombre.label("producto"),
                Marca.nombre.label("marca"),
                Color.nombre.label("color"),
                Talla.codigo.label("talla"),
            )
            .select_from(DetalleVenta)
            .join(VarianteProducto, VarianteProducto.id_variante == DetalleVenta.id_variante)
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .outerjoin(Marca, Marca.id_marca == Producto.id_marca)
            .join(Color, Color.id_color == VarianteProducto.id_color)
            .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
            .where(DetalleVenta.id_venta == sale_id)
            .order_by(DetalleVenta.id_detalle_venta)
        )
        return (await self.session.execute(statement)).mappings().all()

    async def customer_sales(self, customer_id: int) -> list[Venta]:
        return list(
            (
                await self.session.scalars(
                    select(Venta)
                    .where(Venta.id_cliente == customer_id, Venta.estado == "PAGADA")
                    .order_by(Venta.fecha_venta.desc())
                )
            ).all()
        )

    async def sales(
        self,
        *,
        branch_id: int | None = None,
        channel: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Venta]:
        statement = select(Venta)
        if branch_id:
            statement = statement.where(Venta.id_sucursal == branch_id)
        if channel:
            statement = statement.where(Venta.canal_venta == channel)
        if date_from:
            statement = statement.where(Venta.fecha_venta >= date_from)
        if date_to:
            statement = statement.where(Venta.fecha_venta <= date_to)
        return list(
            (await self.session.scalars(statement.order_by(Venta.fecha_venta.desc()))).all()
        )

    async def sale_payment(self, sale_id: int) -> tuple[Pago, MetodoPago] | None:
        statement = (
            select(Pago, MetodoPago)
            .join(MetodoPago, MetodoPago.id_metodo_pago == Pago.id_metodo_pago)
            .where(Pago.id_venta == sale_id)
            .order_by(Pago.fecha_creacion.desc())
        )
        return (await self.session.execute(statement)).first()

    async def customer_orders(self, customer_id: int) -> list[Pedido]:
        statement = (
            select(Pedido)
            .join(Venta, Venta.id_venta == Pedido.id_venta)
            .where(Venta.id_cliente == customer_id, Venta.estado == "PAGADA")
            .order_by(Pedido.fecha_creacion.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def order_by_sale(self, sale_id: int) -> Pedido | None:
        statement = select(Pedido).where(Pedido.id_venta == sale_id)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def pending_stripe_sessions(self, customer_id: int | None = None) -> list[str]:
        statement = (
            select(TransaccionPasarela.external_session_id)
            .join(Pago, Pago.id_pago == TransaccionPasarela.id_pago)
            .join(Venta, Venta.id_venta == Pago.id_venta)
            .where(
                Venta.estado == "PENDIENTE",
                TransaccionPasarela.proveedor == "STRIPE",
                TransaccionPasarela.external_session_id.is_not(None),
            )
        )
        if customer_id is not None:
            statement = statement.where(Venta.id_cliente == customer_id)
        statement = statement.order_by(TransaccionPasarela.fecha_creacion.desc()).limit(20)
        return [str(sid) for sid in (await self.session.scalars(statement)).all() if sid]

    async def customer_pending_stripe_sessions(self, customer_id: int) -> list[str]:
        return await self.pending_stripe_sessions(customer_id=customer_id)

    async def orders(
        self, *, state: str | None = None, branch_id: int | None = None
    ) -> list[Pedido]:
        statement = (
            select(Pedido)
            .join(Venta, Venta.id_venta == Pedido.id_venta)
            .where(Venta.estado == "PAGADA")
        )
        if state:
            statement = statement.where(Pedido.estado == state)
        if branch_id:
            statement = statement.where(Venta.id_sucursal == branch_id)
        return list(
            (await self.session.scalars(statement.order_by(Pedido.fecha_creacion.desc()))).all()
        )

    async def address_rows(self, customer_id: int, *, active_only: bool = True):
        statement = (
            select(DireccionCliente, Ciudad.nombre.label("ciudad"))
            .join(Ciudad, Ciudad.id_ciudad == DireccionCliente.id_ciudad)
            .where(DireccionCliente.id_cliente == customer_id)
        )
        if active_only:
            statement = statement.where(DireccionCliente.activo.is_(True))
        return (
            await self.session.execute(
                statement.order_by(
                    DireccionCliente.es_principal.desc(), DireccionCliente.created_at.desc()
                )
            )
        ).all()

    async def unset_primary_addresses(self, customer_id: int, except_id: int | None = None) -> None:
        addresses = await self.session.scalars(
            select(DireccionCliente).where(
                DireccionCliente.id_cliente == customer_id, DireccionCliente.es_principal.is_(True)
            )
        )
        for address in addresses:
            if except_id is None or address.id_direccion != except_id:
                address.es_principal = False

    async def active_rate(self) -> TarifaEnvio | None:
        now = func.now()
        return await self.session.scalar(
            select(TarifaEnvio)
            .where(
                TarifaEnvio.activo.is_(True),
                TarifaEnvio.vigente_desde <= now,
                or_(TarifaEnvio.vigente_hasta.is_(None), TarifaEnvio.vigente_hasta > now),
            )
            .order_by(TarifaEnvio.vigente_desde.desc())
            .limit(1)
        )

    async def returned_quantity(self, sale_detail_id: int) -> int:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(DetalleDevolucion.cantidad), 0))
            .join(Devolucion, Devolucion.id_devolucion == DetalleDevolucion.id_devolucion)
            .where(
                DetalleDevolucion.id_detalle_venta == sale_detail_id,
                Devolucion.estado.in_(["PENDIENTE", "APROBADA", "COMPLETADA"]),
            )
        )
        return int(value or 0)

    async def customer_returns(self, customer_id: int) -> list[Devolucion]:
        return list(
            (
                await self.session.scalars(
                    select(Devolucion)
                    .where(Devolucion.id_cliente == customer_id)
                    .order_by(Devolucion.fecha_solicitud.desc())
                )
            ).all()
        )

    async def returns(self, *, branch_id: int | None = None) -> list[Devolucion]:
        statement = select(Devolucion).join(Venta, Venta.id_venta == Devolucion.id_venta)
        if branch_id:
            statement = statement.where(Venta.id_sucursal == branch_id)
        return list(
            (
                await self.session.scalars(statement.order_by(Devolucion.fecha_solicitud.desc()))
            ).all()
        )

    async def return_details(self, return_id: int) -> list[DetalleDevolucion]:
        return list(
            (
                await self.session.scalars(
                    select(DetalleDevolucion).where(DetalleDevolucion.id_devolucion == return_id)
                )
            ).all()
        )

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

    async def sale_lot_allocations(self, sale_id: int, variant_id: int):
        statement = (
            select(MovimientoLote, LoteInventario)
            .join(
                MovimientoInventario,
                MovimientoInventario.id_movimiento == MovimientoLote.id_movimiento,
            )
            .join(LoteInventario, LoteInventario.id_lote == MovimientoLote.id_lote)
            .where(
                MovimientoInventario.referencia_tipo == "VENTA",
                MovimientoInventario.referencia_id == sale_id,
                LoteInventario.id_variante == variant_id,
            )
            .order_by(LoteInventario.fecha_ingreso.desc(), LoteInventario.id_lote.desc())
            .with_for_update()
        )
        return (await self.session.execute(statement)).all()

    async def restored_sale_lots(self, sale_id: int, variant_id: int) -> dict[int, int]:
        statement = (
            select(
                MovimientoLote.id_lote,
                func.sum(MovimientoLote.cantidad).label("cantidad"),
            )
            .join(
                MovimientoInventario,
                MovimientoInventario.id_movimiento == MovimientoLote.id_movimiento,
            )
            .join(
                Devolucion,
                Devolucion.id_devolucion == MovimientoInventario.referencia_id,
            )
            .join(LoteInventario, LoteInventario.id_lote == MovimientoLote.id_lote)
            .where(
                MovimientoInventario.referencia_tipo == "DEVOLUCION",
                Devolucion.id_venta == sale_id,
                LoteInventario.id_variante == variant_id,
            )
            .group_by(MovimientoLote.id_lote)
        )
        return {
            int(lot_id): int(quantity)
            for lot_id, quantity in (await self.session.execute(statement)).all()
        }

    async def notifications(self, user_id: int) -> list[Notificacion]:
        return list(
            (
                await self.session.scalars(
                    select(Notificacion)
                    .where(
                        Notificacion.id_usuario == user_id,
                        Notificacion.id_campania.is_(None),
                        Notificacion.tipo != "REGISTRO_DISPOSITIVO",
                    )
                    .order_by(Notificacion.fecha_creacion.desc())
                    .limit(100)
                )
            ).all()
        )

    async def register_device_token(
        self,
        *,
        user_id: int,
        token: str,
        plataforma: str,
        dispositivo_info: str | None = None,
    ) -> Notificacion:
        existing = (
            await self.session.scalars(
                select(Notificacion).where(
                    Notificacion.id_usuario == user_id,
                    Notificacion.tipo == "REGISTRO_DISPOSITIVO",
                    Notificacion.destinatario == token,
                )
            )
        ).first()

        now = datetime.now(UTC)
        if existing:
            existing.estado = "ACTIVO"
            existing.titulo = plataforma.lower()
            existing.contenido = dispositivo_info or "Dispositivo Móvil"
            existing.fecha_envio = now
            self.session.add(existing)
            await self.session.flush()
            return existing

        notif = Notificacion(
            id_usuario=user_id,
            id_campania=None,
            tipo="REGISTRO_DISPOSITIVO",
            canal="PUSH",
            proveedor="FCM",
            destinatario=token,
            titulo=plataforma.lower(),
            contenido=dispositivo_info or "Dispositivo Móvil",
            estado="ACTIVO",
            fecha_creacion=now,
            fecha_envio=now,
        )
        self.session.add(notif)
        await self.session.flush()
        return notif

    async def get_user_device_tokens(self, user_id: int) -> list[str]:
        tokens = (
            await self.session.scalars(
                select(Notificacion.destinatario).where(
                    Notificacion.id_usuario == user_id,
                    Notificacion.tipo == "REGISTRO_DISPOSITIVO",
                    Notificacion.estado == "ACTIVO",
                )
            )
        ).all()
        return [t for t in tokens if t]

    async def admin_notifications(
        self,
        *,
        estado: str | None = None,
        canal: str | None = None,
        tipo: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[tuple[Notificacion, str | None, str | None, str | None]], int, dict[str, int]]:
        kpi_statement = select(
            func.count(Notificacion.id_notificacion).label("total"),
            func.count(Notificacion.id_notificacion)
            .filter(Notificacion.estado == "ENVIADO")
            .label("enviadas"),
            func.count(Notificacion.id_notificacion)
            .filter(Notificacion.estado == "PENDIENTE")
            .label("pendientes"),
            func.count(Notificacion.id_notificacion)
            .filter(Notificacion.estado == "FALLIDO")
            .label("fallidas"),
        ).where(
            Notificacion.id_campania.is_(None),
            Notificacion.tipo != "REGISTRO_DISPOSITIVO",
        )
        kpi_row = (await self.session.execute(kpi_statement)).one()
        kpis = {
            "total": int(kpi_row.total or 0),
            "enviadas": int(kpi_row.enviadas or 0),
            "pendientes": int(kpi_row.pendientes or 0),
            "fallidas": int(kpi_row.fallidas or 0),
        }

        conditions = [
            Notificacion.id_campania.is_(None),
            Notificacion.tipo != "REGISTRO_DISPOSITIVO",
        ]
        if estado:
            conditions.append(Notificacion.estado == estado.upper())
        if canal:
            conditions.append(Notificacion.canal == canal.upper())
        if tipo:
            tipo_upper = tipo.upper()
            if tipo_upper == "PEDIDOS":
                conditions.append(Notificacion.tipo.like("PEDIDO%"))
            elif tipo_upper == "RESERVAS":
                conditions.append(Notificacion.tipo.like("RESERVA%"))
            elif tipo_upper == "DEVOLUCIONES":
                conditions.append(Notificacion.tipo.like("DEVOLUCION%"))
            elif tipo_upper == "AVISOS":
                conditions.append(Notificacion.tipo.like("AVISO%"))
            else:
                conditions.append(Notificacion.tipo == tipo_upper)

        if search:
            search_pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Notificacion.titulo.ilike(search_pattern),
                    Notificacion.contenido.ilike(search_pattern),
                    Notificacion.destinatario.ilike(search_pattern),
                    Usuario.nombres.ilike(search_pattern),
                    Usuario.apellidos.ilike(search_pattern),
                    Usuario.correo.ilike(search_pattern),
                )
            )

        count_stmt = (
            select(func.count(Notificacion.id_notificacion))
            .select_from(Notificacion)
            .outerjoin(Usuario, Notificacion.id_usuario == Usuario.id_usuario)
            .where(*conditions)
        )
        total_filtered = int((await self.session.scalar(count_stmt)) or 0)

        query = (
            select(Notificacion, Usuario.nombres, Usuario.apellidos, Usuario.correo)
            .outerjoin(Usuario, Notificacion.id_usuario == Usuario.id_usuario)
            .where(*conditions)
            .order_by(Notificacion.fecha_creacion.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list((await self.session.execute(query)).all())
        return rows, total_filtered, kpis

    async def notification_detail(
        self, notification_id: int
    ) -> tuple[Notificacion, str | None, str | None, str | None] | None:
        query = (
            select(Notificacion, Usuario.nombres, Usuario.apellidos, Usuario.correo)
            .outerjoin(Usuario, Notificacion.id_usuario == Usuario.id_usuario)
            .where(Notificacion.id_notificacion == notification_id)
        )
        return (await self.session.execute(query)).first()

    async def payment_method(self, code: str) -> MetodoPago | None:
        return await self.session.scalar(
            select(MetodoPago).where(MetodoPago.codigo == code, MetodoPago.activo.is_(True))
        )

    async def payment(self, payment_id: int, *, lock: bool = False) -> Pago | None:
        statement = select(Pago).where(Pago.id_pago == payment_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def gateway_transaction_by_session(
        self, session_id: str, *, lock: bool = False
    ) -> TransaccionPasarela | None:
        statement = select(TransaccionPasarela).where(
            TransaccionPasarela.proveedor == "STRIPE",
            TransaccionPasarela.external_session_id == session_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def payment_by_sale(self, sale_id: int) -> Pago | None:
        return await self.session.scalar(
            select(Pago).where(Pago.id_venta == sale_id).order_by(Pago.id_pago.desc())
        )

    async def gateway_transaction_by_payment(
        self, payment_id: int
    ) -> TransaccionPasarela | None:
        return await self.session.scalar(
            select(TransaccionPasarela).where(TransaccionPasarela.id_pago == payment_id)
        )

    async def supplier_history(
        self,
        *,
        page: int,
        page_size: int,
        supplier_id: int | None,
        product_id: int | None,
        branch_id: int | None,
        state: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ):
        total_purchase = func.sum(
            DetalleRecepcion.cantidad_recibida * DetalleRecepcion.costo_unitario
        ).over(partition_by=RecepcionMercaderia.id_recepcion)
        statement = (
            select(
                RecepcionMercaderia.fecha_recepcion,
                Proveedor.razon_social.label("proveedor"),
                RecepcionMercaderia.id_orden_compra,
                RecepcionMercaderia.id_recepcion,
                Producto.nombre.label("producto"),
                VarianteProducto.id_variante,
                VarianteProducto.sku,
                Talla.codigo.label("talla"),
                Color.nombre.label("color"),
                DetalleRecepcion.cantidad_recibida.label("cantidad"),
                DetalleRecepcion.costo_unitario.label("precio_unitario"),
                (DetalleRecepcion.cantidad_recibida * DetalleRecepcion.costo_unitario).label(
                    "subtotal"
                ),
                total_purchase.label("total_compra"),
                Sucursal.nombre.label("sucursal"),
                RecepcionMercaderia.estado,
                func.concat(Usuario.nombres, " ", Usuario.apellidos).label("usuario_responsable"),
            )
            .join(
                DetalleRecepcion, DetalleRecepcion.id_recepcion == RecepcionMercaderia.id_recepcion
            )
            .join(VarianteProducto, VarianteProducto.id_variante == DetalleRecepcion.id_variante)
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
            .join(Color, Color.id_color == VarianteProducto.id_color)
            .join(Sucursal, Sucursal.id_sucursal == RecepcionMercaderia.id_sucursal)
            .outerjoin(
                OrdenCompra, OrdenCompra.id_orden_compra == RecepcionMercaderia.id_orden_compra
            )
            .outerjoin(Proveedor, Proveedor.id_proveedor == OrdenCompra.id_proveedor)
            .outerjoin(Empleado, Empleado.id_empleado == RecepcionMercaderia.id_empleado)
            .outerjoin(Usuario, Usuario.id_usuario == Empleado.id_usuario)
        )
        filters = []
        if supplier_id:
            filters.append(Proveedor.id_proveedor == supplier_id)
        if product_id:
            filters.append(Producto.id_producto == product_id)
        if branch_id:
            filters.append(Sucursal.id_sucursal == branch_id)
        if state:
            filters.append(RecepcionMercaderia.estado == state)
        if date_from:
            filters.append(RecepcionMercaderia.fecha_recepcion >= date_from)
        if date_to:
            filters.append(RecepcionMercaderia.fecha_recepcion <= date_to)
        if filters:
            statement = statement.where(and_(*filters))
        count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
        total = int(await self.session.scalar(count_statement) or 0)
        rows = (
            (
                await self.session.execute(
                    statement.order_by(
                        RecepcionMercaderia.fecha_recepcion.desc(),
                        RecepcionMercaderia.id_recepcion.desc(),
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .mappings()
            .all()
        )
        return rows, total

    async def stale_reservations(self) -> list[Reserva]:
        now = datetime.now(UTC)
        statement = (
            select(Reserva)
            .where(
                Reserva.estado.in_(["PENDIENTE", "CONFIRMADA"]),
                Reserva.fecha_expiracion.is_not(None),
                Reserva.fecha_expiracion < now,
            )
            .with_for_update()
        )
        return list((await self.session.scalars(statement)).all())

    async def list_campaigns(self, state: str | None = None) -> list[tuple[Campania, int]]:
        count_subq = (
            select(func.count(Notificacion.id_notificacion))
            .where(Notificacion.id_campania == Campania.id_campania)
            .scalar_subquery()
        )
        statement = select(Campania, count_subq.label("total_notif"))
        if state:
            statement = statement.where(Campania.estado == state)
        statement = statement.order_by(Campania.created_at.desc())
        result = await self.session.execute(statement)
        return [(row[0], int(row[1] or 0)) for row in result.all()]

    async def get_campaign(self, campaign_id: int) -> Campania | None:
        return await self.session.get(Campania, campaign_id)

    async def get_campaign_notifications_count(self, campaign_id: int) -> int:
        statement = select(func.count(Notificacion.id_notificacion)).where(
            Notificacion.id_campania == campaign_id
        )
        return int(await self.session.scalar(statement) or 0)

    async def get_target_users_for_campaign(self, segment: str = "TODOS") -> list[Usuario]:
        statement = (
            select(Usuario)
            .join(Cliente, Cliente.id_usuario == Usuario.id_usuario)
            .where(Usuario.estado == "ACTIVO")
        )
        if segment == "CON_COMPRAS":
            statement = statement.join(Venta, Venta.id_cliente == Cliente.id_cliente).distinct()
        elif segment == "CON_RESERVAS":
            statement = statement.join(Reserva, Reserva.id_cliente == Cliente.id_cliente).distinct()
        result = await self.session.scalars(statement)
        return list(result.all())

    async def list_promotions(self) -> list[dict]:
        statement = select(Promocion).order_by(Promocion.created_at.desc())
        promos = list((await self.session.scalars(statement)).all())
        results: list[dict] = []
        now = datetime.now(UTC)
        for p in promos:
            prod_ids = list(
                (
                    await self.session.scalars(
                        select(PromocionProducto.id_producto).where(
                            PromocionProducto.id_promocion == p.id_promocion
                        )
                    )
                ).all()
            )
            cat_ids = list(
                (
                    await self.session.scalars(
                        select(PromocionCategoria.id_categoria).where(
                            PromocionCategoria.id_promocion == p.id_promocion
                        )
                    )
                ).all()
            )
            temp_ids = list(
                (
                    await self.session.scalars(
                        select(PromocionTemporada.id_temporada).where(
                            PromocionTemporada.id_promocion == p.id_promocion
                        )
                    )
                ).all()
            )
            if not p.activo:
                vigencia = "INACTIVA"
            elif p.fecha_inicio > now:
                vigencia = "PROGRAMADA"
            elif p.fecha_fin < now:
                vigencia = "EXPIRADA"
            else:
                vigencia = "VIGENTE"

            results.append(
                {
                    "promotion": p,
                    "producto_ids": prod_ids,
                    "categoria_ids": cat_ids,
                    "temporada_ids": temp_ids,
                    "estado_vigencia": vigencia,
                }
            )
        return results

    async def get_promotion(self, promo_id: int) -> Promocion | None:
        return await self.session.get(Promocion, promo_id)

    async def get_promotion_details(self, promo_id: int) -> dict | None:
        p = await self.session.get(Promocion, promo_id)
        if not p:
            return None
        prod_ids = list(
            (
                await self.session.scalars(
                    select(PromocionProducto.id_producto).where(
                        PromocionProducto.id_promocion == p.id_promocion
                    )
                )
            ).all()
        )
        cat_ids = list(
            (
                await self.session.scalars(
                    select(PromocionCategoria.id_categoria).where(
                        PromocionCategoria.id_promocion == p.id_promocion
                    )
                )
            ).all()
        )
        temp_ids = list(
            (
                await self.session.scalars(
                    select(PromocionTemporada.id_temporada).where(
                        PromocionTemporada.id_promocion == p.id_promocion
                    )
                )
            ).all()
        )
        now = datetime.now(UTC)
        if not p.activo:
            vigencia = "INACTIVA"
        elif p.fecha_inicio > now:
            vigencia = "PROGRAMADA"
        elif p.fecha_fin < now:
            vigencia = "EXPIRADA"
        else:
            vigencia = "VIGENTE"

        return {
            "promotion": p,
            "producto_ids": prod_ids,
            "categoria_ids": cat_ids,
            "temporada_ids": temp_ids,
            "estado_vigencia": vigencia,
        }

    async def set_promotion_associations(
        self,
        promo_id: int,
        product_ids: list[int] | None = None,
        category_ids: list[int] | None = None,
        season_ids: list[int] | None = None,
    ) -> None:
        if product_ids is not None:
            await self.session.execute(
                delete(PromocionProducto).where(PromocionProducto.id_promocion == promo_id)
            )
            for pid in set(product_ids):
                self.session.add(PromocionProducto(id_promocion=promo_id, id_producto=pid))
        if category_ids is not None:
            await self.session.execute(
                delete(PromocionCategoria).where(PromocionCategoria.id_promocion == promo_id)
            )
            for cid in set(category_ids):
                self.session.add(PromocionCategoria(id_promocion=promo_id, id_categoria=cid))
        if season_ids is not None:
            await self.session.execute(
                delete(PromocionTemporada).where(PromocionTemporada.id_promocion == promo_id)
            )
            for sid in set(season_ids):
                self.session.add(PromocionTemporada(id_promocion=promo_id, id_temporada=sid))
        await self.session.flush()

    async def delete_promotion(self, promo: Promocion) -> None:
        await self.session.delete(promo)
        await self.session.flush()

    async def get_active_promotions(self) -> list[Promocion]:
        now = datetime.now(UTC)
        statement = (
            select(Promocion)
            .where(
                Promocion.activo.is_(True),
                Promocion.fecha_inicio <= now,
                Promocion.fecha_fin >= now,
            )
            .order_by(Promocion.porcentaje_descuento.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def get_active_discounts_for_products(
        self, product_ids: list[int]
    ) -> dict[int, tuple[Decimal, int, str]]:
        if not product_ids:
            return {}

        promos = await self.get_active_promotions()
        if not promos:
            return {}

        products_stmt = select(Producto.id_producto, Producto.id_categoria).where(
            Producto.id_producto.in_(product_ids)
        )
        product_rows = (await self.session.execute(products_stmt)).all()
        prod_cats = {r[0]: r[1] for r in product_rows}

        temp_stmt = select(
            ProductoTemporada.id_producto, ProductoTemporada.id_temporada
        ).where(ProductoTemporada.id_producto.in_(product_ids))
        temp_rows = (await self.session.execute(temp_stmt)).all()
        prod_temps: dict[int, set[int]] = {}
        for pid, tid in temp_rows:
            prod_temps.setdefault(pid, set()).add(tid)

        discounts: dict[int, tuple[Decimal, int, str]] = {}

        for promo in promos:
            p_ids = set(
                (
                    await self.session.scalars(
                        select(PromocionProducto.id_producto).where(
                            PromocionProducto.id_promocion == promo.id_promocion
                        )
                    )
                ).all()
            )
            c_ids = set(
                (
                    await self.session.scalars(
                        select(PromocionCategoria.id_categoria).where(
                            PromocionCategoria.id_promocion == promo.id_promocion
                        )
                    )
                ).all()
            )
            t_ids = set(
                (
                    await self.session.scalars(
                        select(PromocionTemporada.id_temporada).where(
                            PromocionTemporada.id_promocion == promo.id_promocion
                        )
                    )
                ).all()
            )

            is_storewide = not p_ids and not c_ids and not t_ids

            for pid in product_ids:
                matches = False
                if is_storewide:
                    matches = True
                elif pid in p_ids:
                    matches = True
                elif prod_cats.get(pid) in c_ids:
                    matches = True
                elif pid in prod_temps and bool(prod_temps[pid] & t_ids):
                    matches = True

                if matches:
                    current_best = discounts.get(pid)
                    if current_best is None or promo.porcentaje_descuento > current_best[0]:
                        discounts[pid] = (
                            promo.porcentaje_descuento,
                            promo.id_promocion,
                            promo.nombre,
                        )

        return discounts



