import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import asin, ceil, cos, radians, sin, sqrt
from urllib.parse import urlparse

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.integrations.openrouteservice import OpenRouteServiceClient
from app.integrations.stripe_checkout import StripeCheckoutGateway
from app.modules.auth.models import Cliente, Empleado, Sucursal, Usuario
from app.modules.catalog.models import (
    Categoria,
    ImagenProducto,
    InventarioSucursal,
    Marca,
    Producto,
    VarianteProducto,
)
from app.modules.commerce.business_days import (
    calculate_business_days_elapsed,
    is_return_window_valid,
)
from app.modules.commerce.exceptions import (
    CommerceConflictError,
    CommerceForbiddenError,
    CommerceNotFoundError,
    InvalidCommerceOperationError,
    PaymentGatewayError,
)
from app.modules.commerce.fcm_sender import FcmPushSender, get_fcm_sender
from app.modules.commerce.invoice_mailer import InvoiceMailer
from app.modules.commerce.invoice_service import (
    InvoiceData,
    InvoiceItem,
    generate_invoice_pdf,
)
from app.modules.commerce.models import (
    Campania,
    Carrito,
    CotizacionEnvio,
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
    Reserva,
    TransaccionPasarela,
    Venta,
)
from app.modules.commerce.repository import CommerceRepository
from app.modules.commerce.schemas import (
    ActivePromotionItem,
    AddressCreate,
    AddressResponse,
    AddressUpdate,
    AdminDashboardSummaryResponse,
    AdminNotificationPage,
    AdminNotificationResponse,
    AdminReturnCreate,
    CampaignCreate,
    CampaignLaunchResponse,
    CampaignResponse,
    CampaignUpdate,
    CartItemCreate,
    CartItemUpdate,
    CartResponse,
    CheckoutCreate,
    CommerceLineRequest,
    CommerceLineResponse,
    DashboardBranchShare,
    DashboardDailyRevenue,
    DashboardKpis,
    DashboardTopProduct,
    DashboardUrgentOrder,
    DeviceTokenRegisterRequest,
    DeviceTokenResponse,
    ManualNotificationCreate,
    NotificationKpis,
    OrderResponse,
    OrderStatusUpdate,
    PromotionCreate,
    PromotionResponse,
    PromotionUpdate,
    ReservationCreate,
    ReservationResponse,
    ReservationStatusUpdate,
    ReturnCreate,
    ReturnLineResponse,
    ReturnResponse,
    ReturnStatusUpdate,
    SaleCreate,
    SaleResponse,
    SaleReturnInspectionResponse,
    SaleReturnLineInspection,
    ShippingQuoteCreate,
    StripeCheckoutResponse,
    StripeCheckoutStatusResponse,
    SupplierPurchaseHistoryPage,
)
from app.modules.inventory.models import MovimientoInventario, MovimientoLote

logger = logging.getLogger(__name__)

RESERVATION_TRANSITIONS = {
    "PENDIENTE": {"CONFIRMADA", "CANCELADA", "EXPIRADA"},
    "CONFIRMADA": {"PREPARANDO", "CANCELADA", "EXPIRADA"},
    "PREPARANDO": {"LISTA", "CANCELADA"},
    "LISTA": {"CLIENTE_PRESENTE", "CONVERTIDA", "CANCELADA", "EXPIRADA"},
    "CLIENTE_PRESENTE": {"CONVERTIDA", "CANCELADA"},
}
ORDER_TRANSITIONS = {
    "PENDIENTE": {"PREPARANDO", "CANCELADO"},
    "PREPARANDO": {"LISTO_PARA_RETIRO", "LISTO_PARA_ENVIO", "CANCELADO"},
    "LISTO_PARA_RETIRO": {"RETIRADO", "RECOGIDO", "CANCELADO"},
    "LISTO_PARA_ENVIO": {"RECOGIDO", "EN_CAMINO", "CANCELADO"},
    "RECOGIDO": {"EN_CAMINO", "ENTREGADO"},
    "EN_CAMINO": {"ENTREGADO"},
}
RETURN_TRANSITIONS = {
    "PENDIENTE": {"APROBADA", "RECHAZADA"},
    "APROBADA": {"COMPLETADA", "RECHAZADA"},
}


class CommerceService:
    def __init__(
        self,
        session: AsyncSession,
        repository: CommerceRepository,
        *,
        stripe_gateway: StripeCheckoutGateway | None = None,
        route_client: OpenRouteServiceClient | None = None,
        invoice_mailer: InvoiceMailer | None = None,
        fcm_sender: FcmPushSender | None = None,
        public_web_url: str = "http://localhost:4200",
        checkout_expire_minutes: int = 30,
    ) -> None:
        self.session = session
        self.repository = repository
        self.stripe_gateway = stripe_gateway
        self.route_client = route_client
        self.invoice_mailer = invoice_mailer or InvoiceMailer()
        self.fcm_sender = fcm_sender or get_fcm_sender()
        self.public_web_url = public_web_url.rstrip("/")
        self.checkout_expire_minutes = checkout_expire_minutes

    async def _customer(self, user_id: int) -> Cliente:
        customer = await self.repository.customer_by_user(user_id)
        if customer is None or customer.estado != "ACTIVO":
            raise CommerceNotFoundError("El usuario no tiene un perfil de cliente activo")
        return customer

    async def _employee(self, user_id: int):
        employee = await self.repository.employee_by_user(user_id)
        if employee is None or employee.estado_laboral != "ACTIVO":
            raise CommerceNotFoundError("El usuario no tiene un perfil de empleado activo")
        return employee

    @staticmethod
    def _validate_unique_lines(lines: list[CommerceLineRequest]) -> None:
        identifiers = [item.id_variante for item in lines]
        if len(identifiers) != len(set(identifiers)):
            raise InvalidCommerceOperationError("No repita una variante en la misma operación")

    @staticmethod
    def _validate_transition(current: str, target: str, transitions: dict[str, set[str]]) -> None:
        if target == current:
            return
        if target not in transitions.get(current, set()):
            raise InvalidCommerceOperationError(
                f"No se puede cambiar el estado de {current} a {target}"
            )

    async def _active_cart(
        self, customer_id: int, *, create: bool = True, lock: bool = False
    ) -> Carrito:
        cart = await self.repository.active_cart(customer_id, lock=lock)
        if cart is None and create:
            cart = await self.repository.add(Carrito(id_cliente=customer_id, estado="ACTIVO"))
        if cart is None:
            raise CommerceNotFoundError("No existe un carrito activo")
        return cart

    async def _line(
        self, detail_id: int, variant_id: int, quantity: int, branch_id: int | None = None
    ) -> CommerceLineResponse:
        row = await self.repository.variant_row(variant_id, branch_id=branch_id)
        if row is None:
            raise CommerceNotFoundError("La variante no existe")
        price = Decimal(row["precio"] or 0)
        return CommerceLineResponse(
            id_detalle=detail_id,
            id_variante=variant_id,
            sku=row["sku"],
            producto=row["producto"],
            talla=row["talla"],
            color=row["color"],
            cantidad=quantity,
            precio_unitario=price,
            subtotal=price * quantity,
            stock_disponible=int(row["stock_disponible"] or 0),
            activo=bool(row["activo"]),
            imagen_url=row["imagen_url"],
        )

    async def _cart_response(self, cart: Carrito) -> CartResponse:
        branch_name = None
        if cart.id_sucursal:
            branch = await self.repository.get(Sucursal, cart.id_sucursal)
            if branch:
                branch_name = branch.nombre
        items = [
            await self._line(
                item.id_detalle_carrito,
                item.id_variante,
                item.cantidad,
                branch_id=cart.id_sucursal,
            )
            for item in await self.repository.cart_details(cart.id_carrito)
        ]
        return CartResponse(
            id_carrito=cart.id_carrito,
            estado=cart.estado,
            id_sucursal=cart.id_sucursal,
            sucursal=branch_name,
            items=items,
            total=sum((item.subtotal for item in items), Decimal(0)),
        )

    async def get_cart(self, user_id: int) -> CartResponse:
        customer = await self._customer(user_id)
        cart = await self._active_cart(customer.id_cliente)
        await self.session.commit()
        return await self._cart_response(cart)

    async def add_cart_item(self, user_id: int, payload: CartItemCreate) -> CartResponse:
        customer = await self._customer(user_id)
        cart = await self._active_cart(customer.id_cliente, lock=True)
        cart_items = await self.repository.cart_details(cart.id_carrito)

        # Regla 1 Carrito = 1 Sucursal: validar conflicto si ya hay prendas de otra sucursal
        if (
            cart_items
            and cart.id_sucursal
            and payload.id_sucursal
            and cart.id_sucursal != payload.id_sucursal
        ):
            current_branch = await self.repository.get(Sucursal, cart.id_sucursal)
            branch_label = current_branch.nombre if current_branch else f"Sucursal #{cart.id_sucursal}"
            raise CommerceConflictError(
                f"Tu carrito contiene prendas de {branch_label}. Para comprar en otra sucursal, debes vaciar el carrito actual."
            )

        target_branch_id = payload.id_sucursal or cart.id_sucursal
        if not cart_items:
            cart.id_sucursal = payload.id_sucursal
            target_branch_id = payload.id_sucursal
        elif not cart.id_sucursal and payload.id_sucursal:
            cart.id_sucursal = payload.id_sucursal
            target_branch_id = payload.id_sucursal

        row = await self.repository.variant_row(payload.id_variante, branch_id=target_branch_id)
        if row is None or not row["activo"]:
            raise InvalidCommerceOperationError("La variante no está disponible")

        current = await self.repository.cart_item_by_variant(cart.id_carrito, payload.id_variante)
        new_quantity = payload.cantidad + (current.cantidad if current else 0)
        stock_available = int(row["stock_disponible"] or 0)
        if new_quantity > stock_available:
            raise CommerceConflictError("La cantidad solicitada supera el stock disponible en la sucursal")

        if current:
            current.cantidad = new_quantity
        else:
            await self.repository.add(
                DetalleCarrito(
                    id_carrito=cart.id_carrito,
                    id_variante=payload.id_variante,
                    cantidad=payload.cantidad,
                )
            )
        await self.session.commit()
        return await self._cart_response(cart)

    async def update_cart_item(
        self, user_id: int, item_id: int, payload: CartItemUpdate
    ) -> CartResponse:
        customer = await self._customer(user_id)
        cart = await self._active_cart(customer.id_cliente, lock=True)
        item = await self.repository.cart_item(cart.id_carrito, item_id)
        if item is None:
            raise CommerceNotFoundError("El artículo no pertenece al carrito")
        row = await self.repository.variant_row(item.id_variante, branch_id=cart.id_sucursal)
        if row is None or not row["activo"] or payload.cantidad > int(row["stock_disponible"] or 0):
            raise CommerceConflictError("La cantidad solicitada no está disponible")
        item.cantidad = payload.cantidad
        await self.session.commit()
        return await self._cart_response(cart)

    async def remove_cart_item(self, user_id: int, item_id: int) -> CartResponse:
        customer = await self._customer(user_id)
        cart = await self._active_cart(customer.id_cliente, lock=True)
        item = await self.repository.cart_item(cart.id_carrito, item_id)
        if item is None:
            raise CommerceNotFoundError("El artículo no pertenece al carrito")
        await self.repository.delete(item)
        remaining = await self.repository.cart_details(cart.id_carrito)
        if not remaining:
            cart.id_sucursal = None
        await self.session.commit()
        return await self._cart_response(cart)

    async def clear_cart(self, user_id: int) -> CartResponse:
        customer = await self._customer(user_id)
        cart = await self._active_cart(customer.id_cliente, lock=True)
        await self.repository.clear_cart_items(cart.id_carrito)
        cart.id_sucursal = None
        await self.session.commit()
        return await self._cart_response(cart)

    @staticmethod
    def _address_response(address: DireccionCliente, city: str) -> AddressResponse:
        return AddressResponse(
            id_direccion=address.id_direccion,
            id_ciudad=address.id_ciudad,
            ciudad=city,
            alias=address.alias,
            zona=address.zona,
            direccion=address.direccion,
            referencia=address.referencia,
            latitud=address.latitud,
            longitud=address.longitud,
            es_principal=address.es_principal,
            activo=address.activo,
        )

    async def list_addresses(self, user_id: int) -> list[AddressResponse]:
        customer = await self._customer(user_id)
        return [
            self._address_response(address, city)
            for address, city in await self.repository.address_rows(customer.id_cliente)
        ]

    async def create_address(self, user_id: int, payload: AddressCreate) -> AddressResponse:
        customer = await self._customer(user_id)
        if payload.es_principal:
            await self.repository.unset_primary_addresses(customer.id_cliente)
        address = await self.repository.add(
            DireccionCliente(id_cliente=customer.id_cliente, **payload.model_dump())
        )
        await self.session.commit()
        rows = await self.repository.address_rows(customer.id_cliente, active_only=False)
        city = next(city for item, city in rows if item.id_direccion == address.id_direccion)
        return self._address_response(address, city)

    async def update_address(
        self, user_id: int, address_id: int, payload: AddressUpdate
    ) -> AddressResponse:
        customer = await self._customer(user_id)
        address = await self.repository.get(DireccionCliente, address_id)
        if address is None or address.id_cliente != customer.id_cliente:
            raise CommerceNotFoundError("La dirección no existe")
        if payload.es_principal:
            await self.repository.unset_primary_addresses(customer.id_cliente, address_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(address, field, value)
        await self.session.commit()
        rows = await self.repository.address_rows(customer.id_cliente, active_only=False)
        city = next(city for item, city in rows if item.id_direccion == address.id_direccion)
        return self._address_response(address, city)

    async def _reserve_stock(
        self,
        branch_id: int,
        reservation_id: int,
        lines: list[CommerceLineRequest],
        employee_id: int | None = None,
    ) -> None:
        for line in lines:
            row = await self.repository.variant_row(line.id_variante)
            inventory = await self.repository.inventory_for_update(branch_id, line.id_variante)
            if row is None or not row["activo"] or inventory is None:
                raise CommerceConflictError("Una variante no está disponible en la sucursal")
            if inventory.stock_fisico - inventory.stock_reservado < line.cantidad:
                raise CommerceConflictError(
                    f"Stock insuficiente para {row['producto']} {row['talla']} {row['color']}"
                )
            await self.repository.add(
                DetalleReserva(
                    id_reserva=reservation_id, id_variante=line.id_variante, cantidad=line.cantidad
                )
            )
            await self.repository.add(
                MovimientoInventario(
                    id_inventario=inventory.id_inventario,
                    id_empleado=employee_id,
                    tipo_movimiento="RESERVA",
                    cantidad=line.cantidad,
                    referencia_tipo="RESERVA",
                    referencia_id=reservation_id,
                    motivo="Reserva web",
                )
            )

    async def create_reservation(
        self, user_id: int, payload: ReservationCreate
    ) -> ReservationResponse:
        customer = await self._customer(user_id)
        self._validate_unique_lines(payload.items)
        branch = await self.repository.get(Sucursal, payload.id_sucursal)
        if branch is None or not branch.activo:
            raise CommerceNotFoundError("La sucursal no está disponible")
        now = datetime.now(UTC)
        expiration: datetime
        if payload.fecha_cita:
            appointment = (
                payload.fecha_cita
                if payload.fecha_cita.tzinfo
                else payload.fecha_cita.replace(tzinfo=UTC)
            )
            if appointment <= now:
                raise InvalidCommerceOperationError("La fecha de cita debe ser futura")
            if (
                branch.hora_apertura
                and branch.hora_cierre
                and not (
                    branch.hora_apertura
                    <= appointment.timetz().replace(tzinfo=None)
                    <= branch.hora_cierre
                )
            ):
                raise InvalidCommerceOperationError(
                    "La cita debe estar dentro del horario de la sucursal"
                )
            expiration = appointment + timedelta(hours=2)
        else:
            expiration = now + timedelta(hours=48)
        try:
            reservation = await self.repository.add(
                Reserva(
                    id_cliente=customer.id_cliente,
                    id_sucursal=payload.id_sucursal,
                    fecha_cita=payload.fecha_cita,
                    fecha_expiracion=expiration,
                    observacion=payload.observacion,
                    estado="PENDIENTE",
                )
            )
            await self._reserve_stock(payload.id_sucursal, reservation.id_reserva, payload.items)
            active_cart = await self.repository.active_cart(customer.id_cliente, lock=True)
            if active_cart:
                await self.repository.clear_cart_items(active_cart.id_carrito)
                active_cart.id_sucursal = None
            branch = await self.repository.get(Sucursal, payload.id_sucursal)
            branch_name = getattr(branch, "nombre", None) or f"Sucursal #{payload.id_sucursal}"
            cust_user = await self.repository.get(Usuario, user_id)
            cust_name = (
                f"{getattr(cust_user, 'nombres', '')} {getattr(cust_user, 'apellidos', '')}".strip()
                if cust_user and hasattr(cust_user, "nombres")
                else "Cliente"
            ) or "Cliente"
            await self._notify(
                user_id,
                "RESERVA_CREADA",
                "¡Reserva confirmada! 📋",
                f"Tu reserva #{reservation.id_reserva} fue registrada en {branch_name}.",
                data={
                    "type": "RESERVA",
                    "id": str(reservation.id_reserva),
                    "route": "/reservas",
                },
            )
            await self._notify_staff_and_admins(
                payload.id_sucursal,
                "NUEVA_RESERVA",
                f"Nueva Reserva #{reservation.id_reserva} de prendas 📋",
                f"{cust_name} apartó {len(payload.items)} prenda(s) en {branch_name} para prueba o retiro.",
                data={
                    "type": "NUEVA_RESERVA",
                    "id": str(reservation.id_reserva),
                    "route": "/reservas",
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return await self._reservation_response(reservation)

    async def _reservation_response(self, reservation: Reserva) -> ReservationResponse:
        branch = await self.repository.get(Sucursal, reservation.id_sucursal)
        details = await self.repository.reservation_details(reservation.id_reserva)
        items = [
            await self._line(item.id_detalle_reserva, item.id_variante, item.cantidad)
            for item in details
        ]
        cliente_nombre = None
        cliente_correo = None
        cliente_telefono = None
        if reservation.id_cliente:
            customer = await self.repository.get(Cliente, reservation.id_cliente)
            if customer:
                c_user = await self.repository.get(Usuario, customer.id_usuario)
                if c_user:
                    cliente_nombre = f"{c_user.nombres} {c_user.apellidos}".strip()
                    cliente_correo = c_user.correo
                    cliente_telefono = c_user.telefono

        return ReservationResponse(
            id_reserva=reservation.id_reserva,
            id_sucursal=reservation.id_sucursal,
            sucursal=branch.nombre,
            direccion_sucursal=branch.direccion,
            id_cliente=reservation.id_cliente,
            cliente_nombre=cliente_nombre,
            cliente_correo=cliente_correo,
            cliente_telefono=cliente_telefono,
            fecha_reserva=reservation.fecha_reserva,
            fecha_cita=reservation.fecha_cita,
            fecha_expiracion=reservation.fecha_expiracion,
            estado=reservation.estado,
            observacion=reservation.observacion,
            items=items,
        )

    async def list_reservations(
        self,
        user_id: int,
        *,
        operational: bool,
        state: str | None = None,
        branch_id: int | None = None,
        all_branches: bool = False,
    ) -> list[ReservationResponse]:
        if operational:
            if not all_branches:
                branch_id = (await self._employee(user_id)).id_sucursal
            rows = await self.repository.all_reservations(state=state, branch_id=branch_id)
        else:
            customer = await self._customer(user_id)
            rows = await self.repository.customer_reservations(customer.id_cliente)
        return [await self._reservation_response(item) for item in rows]

    async def get_reservation(
        self, user_id: int, reservation_id: int, *, operational: bool
    ) -> ReservationResponse:
        reservation = await self.repository.get(Reserva, reservation_id)
        if reservation is None:
            raise CommerceNotFoundError("La reserva no existe")
        if not operational:
            customer = await self._customer(user_id)
            if reservation.id_cliente != customer.id_cliente:
                raise CommerceNotFoundError("La reserva no existe")
        return await self._reservation_response(reservation)

    async def _release_reservation(
        self, reservation: Reserva, employee_id: int | None = None
    ) -> None:
        for detail in await self.repository.reservation_details(reservation.id_reserva):
            inventory = await self.repository.inventory_for_update(
                reservation.id_sucursal, detail.id_variante
            )
            if inventory is None:
                raise CommerceConflictError("No existe inventario para liberar la reserva")
            await self.repository.add(
                MovimientoInventario(
                    id_inventario=inventory.id_inventario,
                    id_empleado=employee_id,
                    tipo_movimiento="LIBERACION_RESERVA",
                    cantidad=detail.cantidad,
                    referencia_tipo="RESERVA",
                    referencia_id=reservation.id_reserva,
                    motivo="Cancelación o expiración",
                )
            )

    async def cancel_reservation(self, user_id: int, reservation_id: int) -> ReservationResponse:
        customer = await self._customer(user_id)
        reservation = await self.repository.get(Reserva, reservation_id)
        if reservation is None or reservation.id_cliente != customer.id_cliente:
            raise CommerceNotFoundError("La reserva no existe")
        self._validate_transition(reservation.estado, "CANCELADA", RESERVATION_TRANSITIONS)
        try:
            await self._release_reservation(reservation)
            reservation.estado = "CANCELADA"
            await self._notify(
                user_id,
                "RESERVA_CANCELADA",
                "Reserva cancelada",
                f"La reserva #{reservation.id_reserva} fue cancelada.",
                data={
                    "type": "RESERVA",
                    "id": str(reservation.id_reserva),
                    "route": "/reservas",
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return await self._reservation_response(reservation)

    async def expire_stale_reservations(self) -> int:
        stale = await self.repository.stale_reservations()
        count = 0
        for reservation in stale:
            try:
                await self._release_reservation(reservation)
                reservation.estado = "EXPIRADA"
                count += 1
            except Exception:
                continue
        if count > 0:
            await self.session.commit()
        return count

    async def update_reservation_status(
        self,
        user_id: int,
        reservation_id: int,
        payload: ReservationStatusUpdate,
        *,
        all_branches: bool = False,
    ) -> ReservationResponse:
        employee = await self._employee(user_id)
        reservation = await self.repository.get(Reserva, reservation_id)
        if reservation is None:
            raise CommerceNotFoundError("La reserva no existe")
        if not all_branches and reservation.id_sucursal != employee.id_sucursal:
            raise CommerceNotFoundError("La reserva no existe")
        self._validate_transition(reservation.estado, payload.estado, RESERVATION_TRANSITIONS)
        if payload.estado in {"CANCELADA", "EXPIRADA"}:
            await self._release_reservation(reservation, employee.id_empleado)
        reservation.estado = payload.estado
        customer = await self.repository.get(Cliente, reservation.id_cliente)
        await self._notify(
            customer.id_usuario,
            f"RESERVA_{payload.estado}",
            "Estado de reserva actualizado",
            f"Tu reserva #{reservation.id_reserva} ahora está {payload.estado.lower()}.",
            data={
                "type": "RESERVA",
                "id": str(reservation.id_reserva),
                "route": "/reservas",
            },
        )
        await self.session.commit()
        return await self._reservation_response(reservation)

    async def _consume_fifo(
        self, inventory: InventarioSucursal, quantity: int, movement_id: int
    ) -> None:
        remaining = quantity
        for lot in await self.repository.fifo_lots(inventory.id_sucursal, inventory.id_variante):
            used = min(remaining, lot.cantidad_disponible)
            if used:
                await self.repository.add(
                    MovimientoLote(
                        id_movimiento=movement_id,
                        id_lote=lot.id_lote,
                        cantidad=used,
                        costo_unitario=lot.costo_unitario,
                    )
                )
                set_committed_value(lot, "cantidad_disponible", lot.cantidad_disponible - used)
                remaining -= used
            if remaining == 0:
                break
        if remaining:
            raise CommerceConflictError("Los lotes FIFO no cubren la cantidad disponible")

    async def _create_sale(
        self,
        *,
        customer_id: int | None,
        employee_id: int | None,
        branch_id: int,
        channel: str,
        mode: str,
        lines: list[CommerceLineRequest],
        reservation_id: int | None = None,
        shipping_cost: Decimal = Decimal(0),
        cash: bool = False,
        state: str | None = None,
        payment_method_code: str = "EFECTIVO",
        payment_reference: str | None = None,
    ) -> Venta:
        self._validate_unique_lines(lines)
        priced: list[tuple[CommerceLineRequest, Decimal, InventarioSucursal]] = []
        for line in lines:
            row = await self.repository.variant_row(line.id_variante)
            inventory = await self.repository.inventory_for_update(branch_id, line.id_variante)
            if (
                row is None
                or not row["activo"]
                or Decimal(row["precio"] or 0) <= 0
                or inventory is None
            ):
                raise CommerceConflictError("Una variante no puede venderse en esta sucursal")
            available = (
                inventory.stock_reservado
                if reservation_id
                else inventory.stock_fisico - inventory.stock_reservado
            )
            if available < line.cantidad:
                raise CommerceConflictError("Stock insuficiente para completar la venta")
            priced.append((line, Decimal(row["precio"]), inventory))
        subtotal = sum((price * line.cantidad for line, price, _ in priced), Decimal(0))
        sale = await self.repository.add(
            Venta(
                id_cliente=customer_id,
                id_sucursal=branch_id,
                id_empleado=employee_id,
                id_reserva=reservation_id,
                canal_venta=channel,
                modalidad_entrega=mode,
                estado="PAGADA" if cash else (state or "CONFIRMADA"),
                subtotal=subtotal,
                descuento_total=0,
                costo_envio=shipping_cost,
                total=subtotal + shipping_cost,
            )
        )
        for line, price, inventory in priced:
            await self.repository.add(
                DetalleVenta(
                    id_venta=sale.id_venta,
                    id_variante=line.id_variante,
                    cantidad=line.cantidad,
                    precio_unitario=price,
                    descuento=0,
                    subtotal=price * line.cantidad,
                )
            )
            movement = await self.repository.add(
                MovimientoInventario(
                    id_inventario=inventory.id_inventario,
                    id_empleado=employee_id,
                    tipo_movimiento="VENTA_RESERVA" if reservation_id else "VENTA",
                    cantidad=line.cantidad,
                    referencia_tipo="VENTA",
                    referencia_id=sale.id_venta,
                    motivo="Venta presencial" if channel == "PRESENCIAL" else "Compra web",
                )
            )
            await self._consume_fifo(inventory, line.cantidad, movement.id_movimiento)
            remaining_available = (
                inventory.stock_fisico - line.cantidad - inventory.stock_reservado
                if not reservation_id
                else inventory.stock_fisico - inventory.stock_reservado
            )
            if remaining_available <= inventory.stock_minimo:
                variant_info = await self.repository.variant_row(line.id_variante)
                product_label = (
                    f"{variant_info['producto']} ({variant_info['color']}, Talla {variant_info['talla']})"
                    if variant_info
                    else f"Variante #{line.id_variante}"
                )
                await self._notify_branch_staff(
                    inventory.id_sucursal,
                    "Alerta de Stock Crítico",
                    f"{product_label} alcanzó el stock mínimo en tu sucursal ({remaining_available} unidades restantes).",
                    data={
                        "type": "STOCK_CRITICO",
                        "id": str(inventory.id_inventario),
                        "route": "/admin/inventario",
                    },
                )
        if cash:
            method_code = payment_method_code or "EFECTIVO"
            method = await self.repository.payment_method(method_code)
            if method is None:
                method_name = {
                    "EFECTIVO": "Efectivo",
                    "TARJETA": "Tarjeta (POS)",
                    "QR": "Pago QR",
                }.get(method_code, method_code.title())
                method = await self.repository.add(
                    MetodoPago(codigo=method_code, nombre=method_name, tipo=method_code, activo=True)
                )
            pago = await self.repository.add(
                Pago(
                    id_venta=sale.id_venta,
                    id_metodo_pago=method.id_metodo_pago,
                    monto=sale.total,
                    estado="PAGADO",
                    fecha_confirmacion=datetime.now(UTC),
                )
            )
            if payment_reference:
                await self.repository.add(
                    TransaccionPasarela(
                        id_pago=pago.id_pago,
                        proveedor=method_code,
                        external_payment_id=payment_reference,
                        estado="SUCCEEDED",
                        monto=sale.total,
                        fecha_confirmacion=datetime.now(UTC),
                    )
                )
        return sale

    async def create_pos_sale(
        self, user_id: int, payload: SaleCreate, *, all_branches: bool = False
    ) -> SaleResponse:
        employee = await self._employee(user_id)
        if not all_branches and employee.id_sucursal != payload.id_sucursal:
            raise InvalidCommerceOperationError("El cajero solo puede vender en su sucursal")
        customer_id = payload.id_cliente
        reservation = None
        if payload.id_reserva:
            reservation = await self.repository.get(Reserva, payload.id_reserva)
            if reservation is None or (not all_branches and reservation.id_sucursal != payload.id_sucursal):
                raise InvalidCommerceOperationError("La reserva no corresponde a la sucursal")
            if reservation.estado in {"CANCELADA", "CONVERTIDA", "EXPIRADA"}:
                raise InvalidCommerceOperationError("La reserva ya fue finalizada o cancelada")
            reserved_lines = {
                item.id_variante: item.cantidad
                for item in await self.repository.reservation_details(reservation.id_reserva)
            }
            requested_lines = {item.id_variante: item.cantidad for item in payload.items}
            if requested_lines != reserved_lines:
                raise InvalidCommerceOperationError(
                    "La venta debe contener exactamente las prendas reservadas"
                )
            if customer_id is not None and customer_id != reservation.id_cliente:
                raise InvalidCommerceOperationError("El cliente no corresponde a la reserva")
            customer_id = reservation.id_cliente
        try:
            sale = await self._create_sale(
                customer_id=customer_id,
                employee_id=employee.id_empleado,
                branch_id=payload.id_sucursal,
                channel="PRESENCIAL",
                mode=payload.modalidad_entrega,
                lines=payload.items,
                reservation_id=payload.id_reserva,
                cash=payload.registrar_efectivo,
                payment_method_code=payload.metodo_pago or "EFECTIVO",
                payment_reference=payload.referencia_pago,
            )
            if reservation:
                reservation.estado = "CONVERTIDA"
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        if sale.id_cliente:
            await self._dispatch_order_invoice_email(None, sale)

        return await self._sale_response(sale)

    @staticmethod
    def _stripe_amount(amount: Decimal) -> int:
        return int((amount * 100).quantize(Decimal("1")))

    def _resolve_client_origin(self, origin_candidate: str | None) -> str:
        if not origin_candidate:
            return self.public_web_url
        parsed = urlparse(origin_candidate.strip())
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        return self.public_web_url

    async def checkout(
        self, user_id: int, payload: CheckoutCreate, client_origin: str | None = None
    ) -> StripeCheckoutResponse:
        if self.stripe_gateway is None:
            raise PaymentGatewayError("Stripe todavía no está configurado en el servidor")
        customer = await self._customer(user_id)
        cart = await self._active_cart(customer.id_cliente, create=False, lock=True)
        details = await self.repository.cart_details(cart.id_carrito)
        if not details:
            raise InvalidCommerceOperationError("El carrito está vacío")
        if cart.id_sucursal and payload.id_sucursal != cart.id_sucursal:
            current_branch = await self.repository.get(Sucursal, cart.id_sucursal)
            branch_label = (
                current_branch.nombre if current_branch else f"Sucursal #{cart.id_sucursal}"
            )
            raise InvalidCommerceOperationError(
                f"La sucursal seleccionada no coincide con la sucursal asignada a los productos de tu carrito ({branch_label})"
            )
        if not cart.id_sucursal:
            cart.id_sucursal = payload.id_sucursal
        address = None
        quote = None
        shipping_cost = Decimal(0)
        if payload.modalidad_entrega == "DELIVERY":
            address = await self.repository.get(DireccionCliente, payload.id_direccion)
            if address is None or address.id_cliente != customer.id_cliente or not address.activo:
                raise InvalidCommerceOperationError("La dirección de entrega no es válida")
            quote = await self.repository.get(CotizacionEnvio, payload.id_cotizacion)
            if (
                quote is None
                or quote.id_direccion != address.id_direccion
                or quote.id_sucursal != payload.id_sucursal
            ):
                raise InvalidCommerceOperationError("La cotización de envío no corresponde al pedido")
            if quote.expira_en and quote.expira_en < datetime.now(UTC):
                raise InvalidCommerceOperationError("La cotización de envío ha expirado")
            shipping_cost = quote.costo_estimado

        base_web_url = self._resolve_client_origin(payload.return_url or client_origin)
        customer_user = await self.repository.get(Usuario, customer.id_usuario)
        customer_email = customer_user.correo if customer_user else None

        lines = [CommerceLineRequest(id_variante=i.id_variante, cantidad=i.cantidad) for i in details]
        stripe_session = None
        try:
            sale = await self._create_sale(
                customer_id=customer.id_cliente,
                employee_id=None,
                branch_id=payload.id_sucursal,
                channel="WEB",
                mode=payload.modalidad_entrega,
                lines=lines,
                shipping_cost=shipping_cost,
                state="PENDIENTE",
            )
            order = await self.repository.add(
                Pedido(
                    id_venta=sale.id_venta,
                    id_direccion=address.id_direccion if address else None,
                    id_cotizacion=quote.id_cotizacion if quote else None,
                    estado="PENDIENTE",
                )
            )
            method = await self.repository.payment_method("STRIPE")
            if method is None:
                raise InvalidCommerceOperationError("El método STRIPE no está configurado")
            payment = await self.repository.add(
                Pago(
                    id_venta=sale.id_venta,
                    id_metodo_pago=method.id_metodo_pago,
                    monto=sale.total,
                    moneda="BOB",
                    estado="PROCESANDO",
                )
            )
            transaction = await self.repository.add(
                TransaccionPasarela(
                    id_pago=payment.id_pago,
                    proveedor="STRIPE",
                    estado="CREANDO",
                    monto=sale.total,
                    moneda="BOB",
                    respuesta_resumen={
                        "cart_id": cart.id_carrito,
                        "order_id": order.id_pedido,
                    },
                )
            )
            sale_response = await self._sale_response(sale)
            line_items = [
                {
                    "price_data": {
                        "currency": "bob",
                        "product_data": {
                            "name": f"{item.producto} · {item.color} · {item.talla}",
                        },
                        "unit_amount": self._stripe_amount(item.precio_unitario),
                    },
                    "quantity": item.cantidad,
                }
                for item in sale_response.items
            ]
            if shipping_cost > 0:
                line_items.append(
                    {
                        "price_data": {
                            "currency": "bob",
                            "product_data": {"name": "Envío"},
                            "unit_amount": self._stripe_amount(shipping_cost),
                        },
                        "quantity": 1,
                    }
                )
            expires_at = datetime.now(UTC) + timedelta(
                minutes=self.checkout_expire_minutes,
                seconds=60,
            )
            payment_intent_data: dict = {
                "metadata": {
                    "payment_id": str(payment.id_pago),
                    "sale_id": str(sale.id_venta),
                    "order_id": str(order.id_pedido),
                }
            }
            if customer_email:
                payment_intent_data["receipt_email"] = customer_email

            try:
                stripe_session = await self.stripe_gateway.create_session(
                    mode="payment",
                    payment_method_types=["card"],
                    line_items=line_items,
                    customer_email=customer_email,
                    client_reference_id=str(order.id_pedido),
                    metadata={
                        "payment_id": str(payment.id_pago),
                        "sale_id": str(sale.id_venta),
                        "order_id": str(order.id_pedido),
                    },
                    payment_intent_data=payment_intent_data,
                    success_url=(
                        f"{base_web_url}/checkout?session_id={{CHECKOUT_SESSION_ID}}"
                        + ("&source=mobile" if (payload.return_url and "source=mobile" in payload.return_url) else "")
                    ),
                    cancel_url=(
                        f"{base_web_url}/checkout?pago_cancelado=1"
                        + ("&source=mobile" if (payload.return_url and "source=mobile" in payload.return_url) else "")
                    ),
                    expires_at=int(expires_at.timestamp()),
                    locale="es",
                    idempotency_key=f"capricho-checkout-{payment.id_pago}",
                )
            except Exception as exc:
                raise PaymentGatewayError(f"No pudimos iniciar el pago seguro con Stripe: {exc}") from exc
            session_id = str(stripe_session["id"])
            checkout_url = str(stripe_session["url"])
            transaction.external_session_id = session_id
            transaction.estado = str(stripe_session.get("status") or "open").upper()
            cart.estado = "CONVERTIDO"
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            if stripe_session and stripe_session.get("id"):
                try:
                    await self.stripe_gateway.expire_session(str(stripe_session["id"]))
                except Exception:
                    pass
            raise
        return StripeCheckoutResponse(
            session_id=session_id,
            checkout_url=checkout_url,
            expires_at=expires_at,
        )

    def construct_stripe_event(self, payload: bytes, signature: str) -> dict:
        if self.stripe_gateway is None:
            raise PaymentGatewayError("Stripe todavía no está configurado en el servidor")
        return self.stripe_gateway.construct_event(payload, signature)

    async def _stripe_transaction(self, session_id: str, *, lock: bool = False):
        transaction = await self.repository.gateway_transaction_by_session(session_id, lock=lock)
        if transaction is None:
            raise CommerceNotFoundError("La sesión de pago no pertenece a Capricho Store")
        payment = await self.repository.payment(transaction.id_pago, lock=lock)
        if payment is None:
            raise CommerceNotFoundError("El pago asociado no existe")
        sale = await self.repository.get(Venta, payment.id_venta)
        if sale is None:
            raise CommerceNotFoundError("La venta asociada no existe")
        order = await self.repository.order_by_sale(sale.id_venta)
        if order is None:
            raise CommerceNotFoundError("El pedido asociado no existe")
        return transaction, payment, sale, order

    async def _complete_stripe_checkout(self, stripe_session: dict) -> None:
        session_id = str(stripe_session.get("id") or "")
        transaction, payment, sale, order = await self._stripe_transaction(session_id, lock=True)
        if payment.estado == "PAGADO":
            return
        amount_total = int(stripe_session.get("amount_total") or 0)
        currency = str(stripe_session.get("currency") or "").upper()
        if stripe_session.get("payment_status") != "paid":
            raise InvalidCommerceOperationError("Stripe todavía no confirmó el pago")
        if amount_total != self._stripe_amount(payment.monto) or currency != payment.moneda:
            raise CommerceConflictError("El monto confirmado por Stripe no coincide con la venta")
        payment_intent = stripe_session.get("payment_intent")
        pi_id = (
            payment_intent.get("id")
            if isinstance(payment_intent, dict)
            else (str(payment_intent or "") or None)
        )
        latest_charge = (
            payment_intent.get("latest_charge")
            if isinstance(payment_intent, dict) and isinstance(payment_intent.get("latest_charge"), dict)
            else {}
        )
        receipt_url = latest_charge.get("receipt_url") if isinstance(latest_charge, dict) else None
        now = datetime.now(UTC)
        payment.estado = "PAGADO"
        payment.fecha_confirmacion = now
        sale.estado = "PAGADA"
        transaction.estado = "PAGADO"
        transaction.external_payment_id = pi_id
        transaction.external_customer_id = str(stripe_session.get("customer") or "") or None
        transaction.fecha_confirmacion = now
        transaction.respuesta_resumen = {
            **(transaction.respuesta_resumen or {}),
            "payment_status": stripe_session.get("payment_status"),
            "status": stripe_session.get("status"),
            **({"receipt_url": receipt_url} if receipt_url else {}),
        }
        cart_id = (transaction.respuesta_resumen or {}).get("cart_id")
        if cart_id:
            cart = await self.repository.get(Carrito, int(cart_id))
            if cart:
                cart.estado = "CONVERTIDO"
                cart.id_sucursal = None
                await self.repository.clear_cart_items(cart.id_carrito)
        customer_name = "Cliente"
        if sale.id_cliente:
            customer = await self.repository.get(Cliente, sale.id_cliente)
            if customer and customer.id_usuario:
                cust_user = await self.repository.get(Usuario, customer.id_usuario)
                if cust_user and hasattr(cust_user, "nombres"):
                    nombres = getattr(cust_user, "nombres", "")
                    apellidos = getattr(cust_user, "apellidos", "")
                    customer_name = f"{nombres} {apellidos}".strip() or "Cliente"
                await self._notify(
                    customer.id_usuario,
                    "PAGO_CONFIRMADO",
                    "¡Compra confirmada! 💳",
                    f"Recibimos tu pago por Bs {sale.total:,.2f} para el Pedido #{order.id_pedido}. Te avisaremos cuando comencemos a prepararlo.",
                    data={
                        "type": "PEDIDO",
                        "id": str(order.id_pedido),
                        "route": f"/pedidos/{order.id_pedido}",
                    },
                )
        branch = await self.repository.get(Sucursal, sale.id_sucursal)
        branch_name = getattr(branch, "nombre", None) or f"Sucursal #{sale.id_sucursal}"
        mode_label = "Retiro en tienda" if sale.modalidad_entrega == "RETIRO_SUCURSAL" else "Delivery"
        await self._notify_staff_and_admins(
            sale.id_sucursal,
            "NUEVO_PEDIDO",
            f"Nuevo Pedido #{order.id_pedido} por preparar 🛍️",
            f"{customer_name} realizó un pedido por Bs {sale.total:,.2f} ({mode_label} - {branch_name}). Requiere preparación.",
            data={
                "type": "NUEVO_PEDIDO",
                "id": str(order.id_pedido),
                "route": "/pedidos",
            },
        )
        if sale.modalidad_entrega == "DELIVERY":
            await self._dispatch_order_invoice_email(order, sale)
        await self.session.commit()

    async def _restore_checkout_cart(self, transaction: TransaccionPasarela) -> None:
        summary = transaction.respuesta_resumen or {}
        cart_id = summary.get("cart_id")
        if not cart_id:
            return
        old_cart = await self.repository.get(Carrito, int(cart_id))
        if old_cart is None:
            return
        active = await self.repository.active_cart(old_cart.id_cliente, lock=True)
        if active is None:
            old_cart.estado = "ACTIVO"
            return
        if active.id_carrito == old_cart.id_carrito:
            return
        for item in await self.repository.cart_details(old_cart.id_carrito):
            current = await self.repository.cart_item_by_variant(
                active.id_carrito, item.id_variante
            )
            if current:
                current.cantidad += item.cantidad
            else:
                await self.repository.add(
                    DetalleCarrito(
                        id_carrito=active.id_carrito,
                        id_variante=item.id_variante,
                        cantidad=item.cantidad,
                    )
                )

    async def _cancel_stripe_checkout(self, session_id: str, *, rejected: bool = False) -> None:
        transaction, payment, sale, order = await self._stripe_transaction(session_id, lock=True)
        if payment.estado == "PAGADO" or sale.estado == "PAGADA":
            return
        if payment.estado in {"CANCELADO", "RECHAZADO"}:
            return
        if sale.estado != "ANULADA":
            await self._restore_sale_stock(
                sale,
                employee_id=None,
                reference_type="PAGO_STRIPE",
                reference_id=payment.id_pago,
            )
        payment.estado = "RECHAZADO" if rejected else "CANCELADO"
        sale.estado = "ANULADA"
        order.estado = "CANCELADO"
        transaction.estado = payment.estado
        await self._restore_checkout_cart(transaction)
        await self.session.commit()

    async def process_stripe_event(self, event: dict) -> None:
        event_type = str(event.get("type") or "")
        stripe_session = dict(event.get("data", {}).get("object", {}))
        if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            await self._complete_stripe_checkout(stripe_session)
        elif event_type == "checkout.session.async_payment_failed":
            await self._cancel_stripe_checkout(str(stripe_session.get("id") or ""), rejected=True)
        elif event_type == "checkout.session.expired":
            await self._cancel_stripe_checkout(str(stripe_session.get("id") or ""))

    async def stripe_checkout_status(
        self, session_id: str, user_id: int | None = None
    ) -> StripeCheckoutStatusResponse:
        if self.stripe_gateway is None:
            raise PaymentGatewayError("Stripe todavía no está configurado en el servidor")
        transaction, payment, sale, order = await self._stripe_transaction(session_id)
        try:
            remote = await self.stripe_gateway.retrieve_session(
                session_id, expand=["payment_intent.latest_charge"]
            )
        except Exception as exc:
            raise PaymentGatewayError(f"No pudimos consultar el estado del pago en Stripe: {exc}") from exc
        if remote.get("payment_status") == "paid":
            await self._complete_stripe_checkout(remote)
        elif remote.get("status") == "expired":
            await self._cancel_stripe_checkout(session_id)
        transaction, payment, sale, order = await self._stripe_transaction(session_id)
        receipt_url = (transaction.respuesta_resumen or {}).get("receipt_url")
        if payment.estado == "PAGADO":
            return StripeCheckoutStatusResponse(
                status="PAGADO",
                message="Stripe confirmó el pago y la compra quedó registrada.",
                order=await self._order_response(order),
                receipt_url=receipt_url,
            )
        if payment.estado in {"CANCELADO", "RECHAZADO"}:
            return StripeCheckoutStatusResponse(
                status=payment.estado,
                message="El pago no se completó y las prendas volvieron a tu carrito.",
                receipt_url=receipt_url,
            )
        return StripeCheckoutStatusResponse(
            status="PROCESANDO",
            message="Stripe está terminando de confirmar el pago.",
            receipt_url=receipt_url,
        )

    async def _reconcile_pending_stripe_orders(self, customer_id: int | None = None) -> None:
        if self.stripe_gateway is None:
            return
        try:
            session_ids = await self.repository.pending_stripe_sessions(customer_id)
            for sid in session_ids:
                try:
                    remote = await self.stripe_gateway.retrieve_session(
                        sid, expand=["payment_intent.latest_charge"]
                    )
                    if remote.get("payment_status") == "paid":
                        await self._complete_stripe_checkout(remote)
                    elif remote.get("status") == "expired":
                        await self._cancel_stripe_checkout(sid)
                except Exception:
                    continue
        except Exception:
            pass

    async def cancel_stripe_checkout(self, user_id: int, session_id: str) -> None:
        if self.stripe_gateway is None:
            raise PaymentGatewayError("Stripe todavía no está configurado en el servidor")
        customer = await self._customer(user_id)
        _, payment, sale, _ = await self._stripe_transaction(session_id)
        if sale.id_cliente != customer.id_cliente:
            raise CommerceNotFoundError("La sesión de pago no existe")
        if payment.estado == "PAGADO":
            return
        try:
            remote = await self.stripe_gateway.retrieve_session(session_id)
            if remote.get("payment_status") == "paid":
                await self._complete_stripe_checkout(remote)
                return
            if remote.get("status") == "open":
                await self.stripe_gateway.expire_session(session_id)
        except Exception as exc:
            raise PaymentGatewayError("No pudimos cancelar la sesión de Stripe") from exc
        await self._cancel_stripe_checkout(session_id)

    async def _sale_response(self, sale: Venta) -> SaleResponse:
        branch = await self.repository.get(Sucursal, sale.id_sucursal)
        details = await self.repository.sale_details(sale.id_venta)
        items = [
            await self._line(item.id_detalle_venta, item.id_variante, item.cantidad)
            for item in details
        ]
        for response, detail in zip(items, details, strict=True):
            response.precio_unitario = detail.precio_unitario
            response.subtotal = detail.subtotal

        cliente_nombre = None
        cliente_correo = None
        cliente_telefono = None
        if sale.id_cliente:
            customer = await self.repository.get(Cliente, sale.id_cliente)
            if customer:
                user = await self.repository.get(Usuario, customer.id_usuario)
                if user:
                    cliente_nombre = f"{user.nombres} {user.apellidos or ''}".strip()
                    cliente_correo = (
                        user.correo if not user.correo.endswith("@pos.caprichostore.com") else None
                    )
                    cliente_telefono = user.telefono

        empleado_nombre = None
        if sale.id_empleado:
            employee = await self.repository.get(Empleado, sale.id_empleado)
            if employee:
                user = await self.repository.get(Usuario, employee.id_usuario)
                if user:
                    empleado_nombre = f"{user.nombres} {user.apellidos or ''}".strip()

        metodo_pago = None
        try:
            payment_row = await self.repository.sale_payment(sale.id_venta)
            if payment_row and isinstance(payment_row, (tuple, list)) and len(payment_row) >= 2:
                _pago, metodo = payment_row
                metodo_pago = getattr(metodo, "nombre", None) or getattr(metodo, "codigo", None)
        except Exception:
            metodo_pago = None

        return SaleResponse(
            id_venta=sale.id_venta,
            id_cliente=sale.id_cliente,
            cliente_nombre=cliente_nombre,
            cliente_correo=cliente_correo,
            cliente_telefono=cliente_telefono,
            id_sucursal=sale.id_sucursal,
            sucursal=branch.nombre,
            id_empleado=sale.id_empleado,
            empleado_nombre=empleado_nombre,
            id_reserva=sale.id_reserva,
            canal_venta=sale.canal_venta,
            modalidad_entrega=sale.modalidad_entrega,
            metodo_pago=metodo_pago,
            estado=sale.estado,
            subtotal=sale.subtotal,
            costo_envio=sale.costo_envio,
            total=sale.total,
            fecha_venta=sale.fecha_venta,
            items=items,
        )

    async def list_sales(
        self,
        user_id: int,
        *,
        branch_id: int | None = None,
        all_branches: bool = False,
        channel: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[SaleResponse]:
        if not all_branches:
            branch_id = (await self._employee(user_id)).id_sucursal
        return [
            await self._sale_response(item)
            for item in await self.repository.sales(
                branch_id=branch_id,
                channel=channel,
                date_from=date_from,
                date_to=date_to,
            )
        ]

    async def list_customer_sales(self, user_id: int) -> list[SaleResponse]:
        customer = await self._customer(user_id)
        return [
            await self._sale_response(item)
            for item in await self.repository.customer_sales(customer.id_cliente)
        ]

    async def get_sale(
        self, user_id: int, sale_id: int, *, all_branches: bool = False
    ) -> SaleResponse:
        sale = await self.repository.get(Venta, sale_id)
        if sale is None:
            raise CommerceNotFoundError("La venta no existe")

        customer = await self.repository.customer_by_user(user_id)
        if customer and sale.id_cliente == customer.id_cliente:
            return await self._sale_response(sale)

        employee = await self.repository.employee_by_user(user_id)
        if employee and employee.estado_laboral == "ACTIVO":
            if not all_branches and sale.id_sucursal != employee.id_sucursal:
                raise CommerceNotFoundError("La venta no existe")
            return await self._sale_response(sale)

        raise CommerceForbiddenError("No tienes permiso para ver esta venta")

    async def _restore_sale_stock(
        self,
        sale: Venta,
        *,
        employee_id: int | None,
        reference_type: str,
        reference_id: int,
    ) -> None:
        for detail in await self.repository.sale_details(sale.id_venta):
            inventory = await self.repository.inventory_for_update(
                sale.id_sucursal, detail.id_variante
            )
            if inventory is None:
                raise CommerceConflictError("No existe inventario para revertir la venta")
            movement = await self.repository.add(
                MovimientoInventario(
                    id_inventario=inventory.id_inventario,
                    id_empleado=employee_id,
                    tipo_movimiento="DEVOLUCION",
                    cantidad=detail.cantidad,
                    referencia_tipo=reference_type,
                    referencia_id=reference_id,
                    motivo="Cancelación de pedido",
                )
            )
            remaining = detail.cantidad
            allocations = await self.repository.sale_lot_allocations(
                sale.id_venta, detail.id_variante
            )
            for allocation, lot in allocations:
                restored = min(remaining, allocation.cantidad)
                lot.cantidad_disponible += restored
                await self.repository.add(
                    MovimientoLote(
                        id_movimiento=movement.id_movimiento,
                        id_lote=lot.id_lote,
                        cantidad=restored,
                        costo_unitario=allocation.costo_unitario,
                    )
                )
                remaining -= restored
                if not remaining:
                    break
            if remaining:
                raise CommerceConflictError("No fue posible restaurar las capas FIFO de la venta")

    async def _order_response(self, order: Pedido) -> OrderResponse:
        sale = await self.repository.get(Venta, order.id_venta)
        branch = await self.repository.get(Sucursal, sale.id_sucursal)
        address = (
            await self.repository.get(DireccionCliente, order.id_direccion)
            if order.id_direccion
            else None
        )
        sale_response = await self._sale_response(sale)
        payment = await self.repository.payment_by_sale(order.id_venta)
        receipt_url = None
        if payment:
            tx = await self.repository.gateway_transaction_by_payment(payment.id_pago)
            if tx and tx.respuesta_resumen:
                receipt_url = tx.respuesta_resumen.get("receipt_url")

        cliente_nombre = None
        cliente_correo = None
        cliente_telefono = None
        if sale.id_cliente:
            customer = await self.repository.get(Cliente, sale.id_cliente)
            if customer:
                c_user = await self.repository.get(Usuario, customer.id_usuario)
                if c_user:
                    cliente_nombre = f"{c_user.nombres} {c_user.apellidos}".strip()
                    cliente_correo = c_user.correo
                    cliente_telefono = c_user.telefono

        return OrderResponse(
            id_pedido=order.id_pedido,
            id_venta=order.id_venta,
            id_cliente=sale.id_cliente,
            cliente_nombre=cliente_nombre,
            cliente_correo=cliente_correo,
            cliente_telefono=cliente_telefono,
            estado=order.estado,
            modalidad_entrega=sale.modalidad_entrega,
            id_sucursal=sale.id_sucursal,
            sucursal=branch.nombre,
            direccion_sucursal=branch.direccion,
            id_direccion=order.id_direccion,
            direccion_entrega=address.direccion if address else None,
            total=sale.total,
            fecha_creacion=order.fecha_creacion,
            fecha_preparacion=order.fecha_preparacion,
            fecha_finalizacion=order.fecha_finalizacion,
            items=sale_response.items,
            receipt_url=receipt_url,
        )

    async def _assemble_invoice(
        self, order: Pedido | None, sale: Venta
    ) -> tuple[InvoiceData, bytes]:
        branch = await self.repository.get(Sucursal, sale.id_sucursal)
        address = (
            await self.repository.get(DireccionCliente, order.id_direccion)
            if order and order.id_direccion
            else None
        )
        customer = await self.repository.get(Cliente, sale.id_cliente) if sale.id_cliente else None
        c_user = (
            await self.repository.get(Usuario, customer.id_usuario)
            if customer and customer.id_usuario
            else None
        )
        payment = await self.repository.payment_by_sale(sale.id_venta)
        tx = (
            await self.repository.gateway_transaction_by_payment(payment.id_pago)
            if payment
            else None
        )

        sucursal_nombre = branch.nombre if branch else "Sucursal Central"
        sucursal_direccion = (
            branch.direccion if branch and branch.direccion else "Santa Cruz, Bolivia"
        )
        sucursal_telefono = branch.telefono if branch and branch.telefono else "+591 70000000"

        cliente_nombre = (
            f"{c_user.nombres} {c_user.apellidos}".strip()
            if c_user
            else "Consumidor Final"
        )
        cliente_doc = c_user.ci if c_user and c_user.ci else "S/N"
        cliente_correo = c_user.correo if c_user else ""
        cliente_telefono = c_user.telefono if c_user and c_user.telefono else ""

        if sale.modalidad_entrega == "DELIVERY":
            destino_parts = []
            if address:
                destino_parts.append(address.direccion)
                if address.zona:
                    destino_parts.append(f"Zona {address.zona}")
                if address.referencia:
                    destino_parts.append(f"(Ref: {address.referencia})")
            destino_entrega = ", ".join(destino_parts) if destino_parts else "Entrega a domicilio"
        elif sale.modalidad_entrega == "ENTREGA_DIRECTA" or order is None:
            destino_entrega = f"Venta directa en mostrador: {sucursal_nombre}"
        else:
            destino_entrega = f"Retiro en sucursal: {sucursal_nombre}"

        if tx and tx.proveedor == "STRIPE":
            ext_id = tx.external_payment_id or "Stripe"
            metodo_pago = f"Tarjeta Crédito / Débito (Stripe - Ref: {ext_id})"
        elif payment:
            metodo_pago = "Efectivo / En Sucursal"
        else:
            metodo_pago = "Pendiente de pago"

        raw_items = await self.repository.sale_invoice_items(sale.id_venta)
        invoice_items = [
            InvoiceItem(
                marca=row["marca"] or "Capricho",
                producto=row["producto"],
                color=row["color"],
                talla=row["talla"],
                cantidad=row["cantidad"],
                precio_unitario=Decimal(str(row["precio_unitario"])),
                subtotal=Decimal(str(row["subtotal"])),
            )
            for row in raw_items
        ]

        invoice_num = (
            f"FAC-{order.id_pedido:06d}" if order else f"FAC-POS-{sale.id_venta:06d}"
        )
        fecha_emision = order.fecha_creacion if order else sale.fecha_venta

        data = InvoiceData(
            numero_factura=invoice_num,
            fecha_emision=fecha_emision,
            estado_pago=sale.estado,
            tienda_nombre="CAPRICHO STORE",
            tienda_nit="102938475",
            sucursal_nombre=sucursal_nombre,
            sucursal_direccion=sucursal_direccion,
            sucursal_telefono=sucursal_telefono,
            cliente_nombre=cliente_nombre,
            cliente_doc=cliente_doc,
            cliente_correo=cliente_correo,
            cliente_telefono=cliente_telefono,
            modalidad_entrega=sale.modalidad_entrega,
            destino_entrega=destino_entrega,
            subtotal=sale.subtotal,
            descuento=sale.descuento_total,
            costo_envio=sale.costo_envio,
            total=sale.total,
            metodo_pago=metodo_pago,
            items=invoice_items,
        )

        pdf_bytes = generate_invoice_pdf(data)
        return data, pdf_bytes

    async def _dispatch_order_invoice_email(
        self, order: Pedido | None, sale: Venta
    ) -> None:
        try:
            invoice_data, pdf_bytes = await self._assemble_invoice(order, sale)
            if not invoice_data.cliente_correo:
                ref_label = f"pedido #{order.id_pedido}" if order else f"venta #{sale.id_venta}"
                logger.info(
                    "La %s no tiene correo de cliente; se omite el despacho de factura.",
                    ref_label,
                )
                return
            order_id = order.id_pedido if order else sale.id_venta
            mailer = self.invoice_mailer or InvoiceMailer()
            await mailer.send_invoice_email(
                recipient_email=invoice_data.cliente_correo,
                recipient_name=invoice_data.cliente_nombre,
                order_id=order_id,
                total_bob=f"{invoice_data.total:.2f}",
                delivery_mode=sale.modalidad_entrega,
                pdf_bytes=pdf_bytes,
            )
        except Exception as exc:
            ref_label = f"pedido #{order.id_pedido}" if order else f"venta #{sale.id_venta}"
            logger.warning(
                "No se pudo despachar el correo de factura para la %s: %s",
                ref_label,
                exc,
            )

    async def get_order_invoice_pdf(self, user_id: int, order_id: int) -> bytes:
        order = await self.repository.get(Pedido, order_id)
        if order is None:
            raise CommerceNotFoundError("El pedido no existe")
        sale = await self.repository.get(Venta, order.id_venta)
        if sale is None:
            raise CommerceNotFoundError("La venta asociada no existe")

        customer = await self.repository.customer_by_user(user_id)
        is_owner = customer is not None and sale.id_cliente == customer.id_cliente

        if not is_owner:
            employee = await self.repository.employee_by_user(user_id)
            if employee is None or employee.estado_laboral != "ACTIVO":
                raise CommerceForbiddenError("No tienes permiso para ver esta factura")

        _, pdf_bytes = await self._assemble_invoice(order, sale)
        return pdf_bytes

    async def get_sale_invoice_pdf(self, user_id: int, sale_id: int) -> bytes:
        sale = await self.repository.get(Venta, sale_id)
        if sale is None:
            raise CommerceNotFoundError("La venta no existe")

        customer = await self.repository.customer_by_user(user_id)
        is_owner = customer is not None and sale.id_cliente == customer.id_cliente

        if not is_owner:
            employee = await self.repository.employee_by_user(user_id)
            if employee is None or employee.estado_laboral != "ACTIVO":
                raise CommerceForbiddenError("No tienes permiso para ver esta factura")

        order = await self.repository.order_by_sale(sale.id_venta)
        _, pdf_bytes = await self._assemble_invoice(order, sale)
        return pdf_bytes

    async def list_orders(
        self,
        user_id: int,
        *,
        operational: bool,
        state: str | None = None,
        branch_id: int | None = None,
        all_branches: bool = False,
    ) -> list[OrderResponse]:
        if operational:
            await self._reconcile_pending_stripe_orders()
            if not all_branches:
                branch_id = (await self._employee(user_id)).id_sucursal
            rows = await self.repository.orders(state=state, branch_id=branch_id)
        else:
            customer = await self.repository.customer_by_user(user_id)
            if customer is None:
                return []
            await self._reconcile_pending_stripe_orders(customer.id_cliente)
            rows = await self.repository.customer_orders(customer.id_cliente)
        return [await self._order_response(item) for item in rows]

    async def get_order(self, user_id: int, order_id: int, *, operational: bool) -> OrderResponse:
        order = await self.repository.get(Pedido, order_id)
        if order is None:
            raise CommerceNotFoundError("El pedido no existe")
        sale = await self.repository.get(Venta, order.id_venta)
        if sale is None or sale.estado != "PAGADA":
            raise CommerceNotFoundError("El pedido no existe")
        if not operational:
            customer = await self._customer(user_id)
            if sale.id_cliente != customer.id_cliente:
                raise CommerceNotFoundError("El pedido no existe")
        return await self._order_response(order)

    async def update_order_status(
        self,
        user_id: int,
        order_id: int,
        payload: OrderStatusUpdate,
        *,
        all_branches: bool = False,
    ) -> OrderResponse:
        employee = await self._employee(user_id)
        order = await self.repository.get(Pedido, order_id)
        if order is None:
            raise CommerceNotFoundError("El pedido no existe")
        sale = await self.repository.get(Venta, order.id_venta)
        if not all_branches and sale.id_sucursal != employee.id_sucursal:
            raise CommerceNotFoundError("El pedido no existe")
        self._validate_transition(order.estado, payload.estado, ORDER_TRANSITIONS)
        if sale.modalidad_entrega == "RETIRO_SUCURSAL" and payload.estado in {
            "LISTO_PARA_ENVIO",
            "EN_CAMINO",
            "ENTREGADO",
        }:
            raise InvalidCommerceOperationError("Ese estado corresponde a un pedido con delivery")
        if sale.modalidad_entrega == "DELIVERY" and payload.estado in {
            "LISTO_PARA_RETIRO",
            "RETIRADO",
        }:
            raise InvalidCommerceOperationError("Ese estado corresponde a retiro en sucursal")
        order.estado = payload.estado
        if payload.estado == "PREPARANDO":
            order.fecha_preparacion = datetime.now(UTC)
        if payload.estado in {"ENTREGADO", "RETIRADO", "CANCELADO"}:
            order.fecha_finalizacion = datetime.now(UTC)
        if payload.estado in {"RETIRADO", "ENTREGADO"}:
            await self._dispatch_order_invoice_email(order, sale)
        if payload.estado == "CANCELADO":
            await self._restore_sale_stock(
                sale,
                employee_id=employee.id_empleado,
                reference_type="PEDIDO_CANCELADO",
                reference_id=order.id_pedido,
            )
            sale.estado = "ANULADA"
        customer = await self.repository.get(Cliente, sale.id_cliente) if sale.id_cliente else None
        if customer:
            branch = await self.repository.get(Sucursal, sale.id_sucursal)
            branch_name = getattr(branch, "nombre", None) or "Capricho Store"
            branch_dir = getattr(branch, "direccion", None)
            branch_address = f" ({branch_dir})" if branch_dir else ""

            status_messages = {
                "PREPARANDO": (
                    "Tu pedido está en preparación 📦",
                    f"Nuestro equipo en {branch_name} está alistando y empaquetando tus prendas del Pedido #{order.id_pedido}.",
                ),
                "LISTO_PARA_RETIRO": (
                    "¡Tu pedido está listo para retirar! 🎉",
                    f"Tu Pedido #{order.id_pedido} ya está listo en {branch_name}{branch_address}. ¡Ya puedes pasar a recogerlo con tu CI!",
                ),
                "LISTO_PARA_ENVIO": (
                    "Pedido empaquetado para envío 📦",
                    f"Tu Pedido #{order.id_pedido} está empaquetado y listo para ser recogido por el repartidor.",
                ),
                "EN_CAMINO": (
                    "Tu pedido va en camino 🛵",
                    f"El repartidor está llevando tu Pedido #{order.id_pedido} hacia tu dirección de entrega.",
                ),
                "RETIRADO": (
                    "¡Pedido retirado con éxito! ✨",
                    f"Has retirado tu Pedido #{order.id_pedido} en {branch_name}. Te enviamos tu factura oficial por correo. ¡Gracias por tu compra!",
                ),
                "ENTREGADO": (
                    "¡Pedido entregado con éxito! ✨",
                    f"Tu Pedido #{order.id_pedido} ha sido entregado en tu dirección. ¡Gracias por confiar en Capricho Store!",
                ),
                "CANCELADO": (
                    "Pedido cancelado",
                    f"Tu Pedido #{order.id_pedido} ha sido cancelado. Si tienes alguna consulta, contáctanos.",
                ),
            }

            title, content = status_messages.get(
                payload.estado,
                (
                    "Estado de pedido actualizado",
                    f"Tu pedido #{order.id_pedido} ahora está {payload.estado.lower().replace('_', ' ')}.",
                ),
            )

            await self._notify(
                customer.id_usuario,
                f"PEDIDO_{payload.estado}",
                title,
                content,
                data={
                    "type": f"PEDIDO_{payload.estado}",
                    "id": str(order.id_pedido),
                    "route": f"/pedidos/{order.id_pedido}",
                },
            )
        await self.session.commit()
        return await self._order_response(order)

    async def confirm_delivery(self, user_id: int, order_id: int) -> OrderResponse:
        customer = await self._customer(user_id)
        order = await self.repository.get(Pedido, order_id)
        if order is None:
            raise CommerceNotFoundError("El pedido no existe")
        sale = await self.repository.get(Venta, order.id_venta)
        if sale is None or sale.id_cliente != customer.id_cliente:
            raise CommerceNotFoundError("El pedido no existe")

        if sale.modalidad_entrega != "DELIVERY":
            raise InvalidCommerceOperationError("Este pedido no corresponde a entrega por delivery")

        if order.estado == "ENTREGADO":
            return await self._order_response(order)

        if order.estado != "EN_CAMINO":
            raise InvalidCommerceOperationError(
                "Solo puedes confirmar la recepción de un pedido que se encuentre en camino"
            )

        order.estado = "ENTREGADO"
        order.fecha_finalizacion = datetime.now(UTC)

        await self._dispatch_order_invoice_email(order, sale)

        # Notificar al cliente
        await self._notify(
            customer.id_usuario,
            "PEDIDO_ENTREGADO",
            "¡Entrega confirmada! ✨",
            f"Confirmaste la recepción de tu Pedido #{order.id_pedido}. ¡Muchas gracias por tu compra en Capricho Store!",
            data={
                "type": "PEDIDO_ENTREGADO",
                "id": str(order.id_pedido),
                "route": "/pedidos",
            },
        )

        # Notificar a los administradores y personal de la sucursal
        user = await self.repository.get(Usuario, customer.id_usuario)
        customer_name = (
            f"{user.nombres} {user.apellidos}".strip()
            if user and (user.nombres or user.apellidos)
            else "El cliente"
        )
        await self._notify_staff_and_admins(
            branch_id=sale.id_sucursal,
            kind="PEDIDO_ENTREGADO",
            title=f"Entrega confirmada - Pedido #{order.id_pedido} 🛵",
            content=f"{customer_name} confirmó la recepción de su pedido por delivery.",
            data={
                "type": "PEDIDO_ENTREGADO",
                "id": str(order.id_pedido),
                "route": "/admin/pedidos",
            },
        )

        await self.session.commit()
        return await self._order_response(order)

    @staticmethod
    def _distance_km(branch: Sucursal, address: DireccionCliente) -> Decimal:
        b_lat = branch.latitud if branch.latitud is not None else Decimal("-17.7833")
        b_lon = branch.longitud if branch.longitud is not None else Decimal("-63.1821")
        a_lat = address.latitud if address.latitud is not None else Decimal("-17.7833")
        a_lon = address.longitud if address.longitud is not None else Decimal("-63.1821")
        lat1, lon1, lat2, lon2 = map(
            radians,
            map(float, (b_lat, b_lon, a_lat, a_lon)),
        )
        value = (
            2
            * 6371
            * asin(
                sqrt(
                    sin((lat2 - lat1) / 2) ** 2
                    + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
                )
            )
        )
        return Decimal(str(round(value, 2)))

    async def quote_shipping(self, user_id: int, payload: ShippingQuoteCreate):
        customer = await self._customer(user_id)
        branch = await self.repository.get(Sucursal, payload.id_sucursal)
        address = await self.repository.get(DireccionCliente, payload.id_direccion)
        rate = await self.repository.active_rate()
        if (
            branch is None
            or not branch.activo
            or address is None
            or address.id_cliente != customer.id_cliente
            or not address.activo
        ):
            raise CommerceNotFoundError("No se pudo encontrar la sucursal o dirección")
        if rate is None:
            raise InvalidCommerceOperationError("No existe una tarifa de envío activa")

        # Fallback de coordenadas (Centro de Santa Cruz) si alguna es nula para evitar interrupción del checkout
        branch_lat = branch.latitud if branch.latitud is not None else Decimal("-17.7833")
        branch_lng = branch.longitud if branch.longitud is not None else Decimal("-63.1821")
        addr_lat = address.latitud if address.latitud is not None else Decimal("-17.7833")
        addr_lng = address.longitud if address.longitud is not None else Decimal("-63.1821")

        route_estimate = None
        if self.route_client:
            route_estimate = await self.route_client.calculate_route(
                start_lat=float(branch_lat),
                start_lng=float(branch_lng),
                end_lat=float(addr_lat),
                end_lng=float(addr_lng),
            )

        if route_estimate:
            distance = route_estimate.distance_km
            duration = route_estimate.duration_min
            provider = route_estimate.provider
        else:
            distance = self._distance_km(branch, address)
            duration = None
            provider = "HAVERSINE"

        if distance <= rate.distancia_base_km:
            cost = rate.tarifa_base
        else:
            km_adicionales = Decimal(str(ceil(float(distance - rate.distancia_base_km))))
            cost = rate.tarifa_base + km_adicionales * rate.costo_km_adicional
        quote = await self.repository.add(
            CotizacionEnvio(
                id_cliente=customer.id_cliente,
                id_sucursal=branch.id_sucursal,
                id_direccion=address.id_direccion,
                id_tarifa=rate.id_tarifa,
                distancia_km=distance,
                duracion_estimada_min=duration,
                costo_estimado=cost.quantize(Decimal("0.01")),
                proveedor_rutas=provider,
                expira_en=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        await self.session.commit()
        return quote

    async def create_return(self, user_id: int, payload: ReturnCreate) -> ReturnResponse:
        customer = await self._customer(user_id)
        sale = await self.repository.get(Venta, payload.id_venta)
        if sale is None or sale.id_cliente != customer.id_cliente:
            raise CommerceNotFoundError("La compra no existe")
        if sale.estado not in {"PAGADA", "CONFIRMADA"}:
            raise InvalidCommerceOperationError("La compra no admite devolución")

        is_valid, remaining, deadline = is_return_window_valid(sale.fecha_venta, max_days=5)
        if not is_valid:
            raise CommerceConflictError(
                "El plazo máximo para solicitar devolución es de 5 días hábiles a partir de la compra"
            )

        sale_details = {
            item.id_detalle_venta: item
            for item in await self.repository.sale_details(sale.id_venta)
        }
        identifiers = [item.id_detalle_venta for item in payload.items]
        if len(identifiers) != len(set(identifiers)):
            raise InvalidCommerceOperationError("No repita un artículo en la devolución")
        for item in payload.items:
            detail = sale_details.get(item.id_detalle_venta)
            if detail is None:
                raise InvalidCommerceOperationError("Un artículo no pertenece a la compra")
            if (
                item.cantidad + await self.repository.returned_quantity(item.id_detalle_venta)
                > detail.cantidad
            ):
                raise CommerceConflictError("La cantidad a devolver supera la cantidad comprada")
        returned = await self.repository.add(
            Devolucion(
                id_venta=sale.id_venta,
                id_cliente=customer.id_cliente,
                motivo=payload.motivo,
                estado="PENDIENTE",
            )
        )
        for item in payload.items:
            await self.repository.add(
                DetalleDevolucion(id_devolucion=returned.id_devolucion, **item.model_dump())
            )
        await self._notify(
            customer.id_usuario,
            "DEVOLUCION_PENDIENTE",
            "Solicitud de devolución registrada 🔄",
            f"Recibimos tu solicitud de devolución #{returned.id_devolucion}. La revisaremos a la brevedad.",
            data={
                "type": "DEVOLUCION_PENDIENTE",
                "id_devolucion": str(returned.id_devolucion),
                "id_venta": str(returned.id_venta),
            },
        )
        await self._notify_staff_and_admins(
            sale.id_sucursal,
            "NUEVA_DEVOLUCION",
            "Nueva Solicitud de Devolución 🔄",
            f"El cliente solicitó devolución #{returned.id_devolucion} para la venta #{sale.id_venta}.",
            data={
                "type": "NUEVA_DEVOLUCION",
                "id_devolucion": str(returned.id_devolucion),
                "id_venta": str(returned.id_venta),
            },
        )
        await self.session.commit()
        return await self._return_response(returned)

    async def _return_response(self, returned: Devolucion) -> ReturnResponse:
        items = []
        for detail in await self.repository.return_details(returned.id_devolucion):
            sale_detail = await self.repository.get(DetalleVenta, detail.id_detalle_venta)
            line = await self._line(
                detail.id_detalle_devolucion, sale_detail.id_variante, detail.cantidad
            )
            items.append(
                ReturnLineResponse(
                    id_detalle_devolucion=detail.id_detalle_devolucion,
                    id_detalle_venta=detail.id_detalle_venta,
                    id_variante=sale_detail.id_variante,
                    producto=line.producto,
                    talla=line.talla,
                    color=line.color,
                    cantidad=detail.cantidad,
                    estado_prenda=detail.estado_prenda,
                )
            )

        cliente_nombre = None
        if returned.id_cliente:
            customer = await self.repository.get(Cliente, returned.id_cliente)
            if customer:
                user = await self.repository.get(Usuario, customer.id_usuario)
                if user:
                    cliente_nombre = f"{user.nombres} {user.apellidos or ''}".strip()
        else:
            cliente_nombre = "Consumidor Final"

        return ReturnResponse(
            id_devolucion=returned.id_devolucion,
            id_venta=returned.id_venta,
            id_cliente=returned.id_cliente,
            cliente_nombre=cliente_nombre,
            motivo=returned.motivo,
            estado=returned.estado,
            fecha_solicitud=returned.fecha_solicitud,
            fecha_resolucion=returned.fecha_resolucion,
            items=items,
        )

    async def inspect_sale_for_return(
        self, user_id: int, sale_id: int, *, all_branches: bool = False
    ) -> SaleReturnInspectionResponse:
        sale = await self.repository.get(Venta, sale_id)
        if sale is None:
            raise CommerceNotFoundError("La venta no existe")

        employee = await self.repository.employee_by_user(user_id)
        customer = await self.repository.customer_by_user(user_id)

        if employee and employee.estado_laboral == "ACTIVO":
            if not all_branches and sale.id_sucursal != employee.id_sucursal:
                raise CommerceNotFoundError("La venta no pertenece a tu sucursal asignada")
        elif customer and sale.id_cliente == customer.id_cliente:
            pass
        else:
            raise CommerceForbiddenError("No tienes permiso para consultar esta venta")

        branch = await self.repository.get(Sucursal, sale.id_sucursal)
        branch_name = branch.nombre if branch else f"Sucursal #{sale.id_sucursal}"

        cliente_nombre = None
        cliente_correo = None
        cliente_telefono = None
        if sale.id_cliente:
            c = await self.repository.get(Cliente, sale.id_cliente)
            if c:
                u = await self.repository.get(Usuario, c.id_usuario)
                if u:
                    cliente_nombre = f"{u.nombres} {u.apellidos or ''}".strip()
                    cliente_correo = (
                        u.correo if not u.correo.endswith("@pos.caprichostore.com") else None
                    )
                    cliente_telefono = u.telefono
        else:
            cliente_nombre = "Consumidor Final"

        is_valid, remaining, deadline = is_return_window_valid(sale.fecha_venta, max_days=5)
        elapsed = calculate_business_days_elapsed(sale.fecha_venta)

        es_retornable = True
        motivo_invalidez = None

        if sale.estado not in {"PAGADA", "CONFIRMADA"}:
            es_retornable = False
            motivo_invalidez = (
                f"La venta se encuentra en estado {sale.estado}, no admite devolución"
            )
        elif not is_valid:
            es_retornable = False
            motivo_invalidez = (
                f"El plazo máximo de 5 días hábiles ha expirado (transcurrieron {elapsed} días hábiles)"
            )

        sale_details = await self.repository.sale_details(sale.id_venta)
        items: list[SaleReturnLineInspection] = []
        total_available = 0

        for item in sale_details:
            returned_qty = await self.repository.returned_quantity(item.id_detalle_venta)
            available_qty = max(0, item.cantidad - returned_qty)
            total_available += available_qty
            line = await self._line(item.id_detalle_venta, item.id_variante, item.cantidad)
            items.append(
                SaleReturnLineInspection(
                    id_detalle_venta=item.id_detalle_venta,
                    id_variante=item.id_variante,
                    sku=line.sku,
                    producto=line.producto,
                    talla=line.talla,
                    color=line.color,
                    cantidad_vendida=item.cantidad,
                    cantidad_devuelta=returned_qty,
                    cantidad_disponible=available_qty,
                    precio_unitario=item.precio_unitario,
                    imagen_url=line.imagen_url,
                )
            )

        if total_available == 0 and es_retornable:
            es_retornable = False
            motivo_invalidez = "Todos los artículos de esta venta ya han sido devueltos"

        return SaleReturnInspectionResponse(
            id_venta=sale.id_venta,
            id_cliente=sale.id_cliente,
            cliente_nombre=cliente_nombre,
            cliente_correo=cliente_correo,
            cliente_telefono=cliente_telefono,
            id_sucursal=sale.id_sucursal,
            sucursal=branch_name,
            canal_venta=sale.canal_venta,
            modalidad_entrega=sale.modalidad_entrega,
            total=sale.total,
            fecha_venta=sale.fecha_venta,
            es_retornable=es_retornable,
            dias_habiles_transcurridos=elapsed,
            dias_habiles_limite=5,
            fecha_limite_devolucion=deadline,
            motivo_invalidez=motivo_invalidez,
            items=items,
        )

    async def create_admin_return(
        self, user_id: int, payload: AdminReturnCreate, *, all_branches: bool = False
    ) -> ReturnResponse:
        employee = await self._employee(user_id)
        sale = await self.repository.get(Venta, payload.id_venta)
        if sale is None:
            raise CommerceNotFoundError("La venta no existe")
        if not all_branches and sale.id_sucursal != employee.id_sucursal:
            raise CommerceNotFoundError("La venta no pertenece a tu sucursal asignada")
        if sale.estado not in {"PAGADA", "CONFIRMADA"}:
            raise InvalidCommerceOperationError(
                "La compra no admite devolución en su estado actual"
            )

        is_valid, remaining, deadline = is_return_window_valid(sale.fecha_venta, max_days=5)
        if not is_valid:
            raise CommerceConflictError(
                "El plazo máximo para registrar devolución es de 5 días hábiles a partir de la compra"
            )

        sale_details = {
            item.id_detalle_venta: item
            for item in await self.repository.sale_details(sale.id_venta)
        }
        identifiers = [item.id_detalle_venta for item in payload.items]
        if len(identifiers) != len(set(identifiers)):
            raise InvalidCommerceOperationError("No repita un artículo en la devolución")

        for item in payload.items:
            detail = sale_details.get(item.id_detalle_venta)
            if detail is None:
                raise InvalidCommerceOperationError("Un artículo no pertenece a la compra")
            returned_qty = await self.repository.returned_quantity(item.id_detalle_venta)
            if item.cantidad + returned_qty > detail.cantidad:
                raise CommerceConflictError(
                    "La cantidad a devolver supera la cantidad comprada disponible"
                )

        initial_state = "COMPLETADA" if payload.completar_inmediato else "PENDIENTE"
        resolution_date = datetime.now(UTC) if payload.completar_inmediato else None

        returned = await self.repository.add(
            Devolucion(
                id_venta=sale.id_venta,
                id_cliente=sale.id_cliente,
                id_empleado=employee.id_empleado,
                motivo=payload.motivo,
                estado=initial_state,
                fecha_resolucion=resolution_date,
            )
        )
        for item in payload.items:
            await self.repository.add(
                DetalleDevolucion(
                    id_devolucion=returned.id_devolucion,
                    id_detalle_venta=item.id_detalle_venta,
                    cantidad=item.cantidad,
                    estado_prenda=item.estado_prenda,
                )
            )

        if payload.completar_inmediato:
            for item in payload.items:
                if item.estado_prenda != "APTA_REINGRESO":
                    continue
                sale_detail = sale_details[item.id_detalle_venta]
                inventory = await self.repository.inventory_for_update(
                    sale.id_sucursal, sale_detail.id_variante
                )
                movement = await self.repository.add(
                    MovimientoInventario(
                        id_inventario=inventory.id_inventario,
                        id_empleado=employee.id_empleado,
                        tipo_movimiento="DEVOLUCION",
                        cantidad=item.cantidad,
                        referencia_tipo="DEVOLUCION",
                        referencia_id=returned.id_devolucion,
                        motivo=returned.motivo,
                    )
                )
                remaining = item.cantidad
                restored_before = await self.repository.restored_sale_lots(
                    sale.id_venta, sale_detail.id_variante
                )
                for allocation, lot in await self.repository.sale_lot_allocations(
                    sale.id_venta, sale_detail.id_variante
                ):
                    capacity = max(
                        0,
                        allocation.cantidad - restored_before.get(lot.id_lote, 0),
                    )
                    restored = min(remaining, capacity)
                    if not restored:
                        continue
                    lot.cantidad_disponible += restored
                    await self.repository.add(
                        MovimientoLote(
                            id_movimiento=movement.id_movimiento,
                            id_lote=lot.id_lote,
                            cantidad=restored,
                            costo_unitario=allocation.costo_unitario,
                        )
                    )
                    remaining -= restored
                    if not remaining:
                        break
                if remaining:
                    raise CommerceConflictError(
                        "No fue posible restaurar las capas FIFO de la venta"
                    )

        if sale.id_cliente:
            customer = await self.repository.get(Cliente, sale.id_cliente)
            if customer:
                await self._notify(
                    customer.id_usuario,
                    f"DEVOLUCION_{initial_state}",
                    "Devolución registrada en mostrador",
                    f"Se ha registrado tu devolución #{returned.id_devolucion} con estado {initial_state.lower()}.",
                )

        await self.session.commit()
        return await self._return_response(returned)

    async def list_returns(
        self, user_id: int, *, operational: bool, all_branches: bool = False
    ) -> list[ReturnResponse]:
        if operational:
            branch_id = None if all_branches else (await self._employee(user_id)).id_sucursal
            rows = await self.repository.returns(branch_id=branch_id)
        else:
            rows = await self.repository.customer_returns(
                (await self._customer(user_id)).id_cliente
            )
        return [await self._return_response(item) for item in rows]

    async def update_return_status(
        self,
        user_id: int,
        return_id: int,
        payload: ReturnStatusUpdate,
        *,
        all_branches: bool = False,
    ) -> ReturnResponse:
        employee = await self._employee(user_id)
        returned = await self.repository.get(Devolucion, return_id)
        if returned is None:
            raise CommerceNotFoundError("La devolución no existe")
        sale = await self.repository.get(Venta, returned.id_venta)
        if not all_branches and sale.id_sucursal != employee.id_sucursal:
            raise CommerceNotFoundError("La devolución no existe")
        self._validate_transition(returned.estado, payload.estado, RETURN_TRANSITIONS)
        try:
            if payload.items:
                details_map = {
                    d.id_detalle_devolucion: d
                    for d in await self.repository.return_details(returned.id_devolucion)
                }
                for item_upd in payload.items:
                    detail = details_map.get(item_upd.id_detalle_devolucion)
                    if detail:
                        detail.estado_prenda = item_upd.estado_prenda

            if payload.observaciones:
                obs = payload.observaciones.strip()
                if obs and obs not in returned.motivo:
                    returned.motivo = f"{returned.motivo} [Nota: {obs}]"[:255]

            if payload.estado == "COMPLETADA":
                for detail in await self.repository.return_details(returned.id_devolucion):
                    if detail.estado_prenda != "APTA_REINGRESO":
                        continue
                    sale_detail = await self.repository.get(DetalleVenta, detail.id_detalle_venta)
                    inventory = await self.repository.inventory_for_update(
                        sale.id_sucursal, sale_detail.id_variante
                    )
                    movement = await self.repository.add(
                        MovimientoInventario(
                            id_inventario=inventory.id_inventario,
                            id_empleado=employee.id_empleado,
                            tipo_movimiento="DEVOLUCION",
                            cantidad=detail.cantidad,
                            referencia_tipo="DEVOLUCION",
                            referencia_id=returned.id_devolucion,
                            motivo=returned.motivo,
                        )
                    )
                    remaining = detail.cantidad
                    restored_before = await self.repository.restored_sale_lots(
                        sale.id_venta, sale_detail.id_variante
                    )
                    for allocation, lot in await self.repository.sale_lot_allocations(
                        sale.id_venta, sale_detail.id_variante
                    ):
                        capacity = max(
                            0,
                            allocation.cantidad - restored_before.get(lot.id_lote, 0),
                        )
                        restored = min(remaining, capacity)
                        if not restored:
                            continue
                        lot.cantidad_disponible += restored
                        await self.repository.add(
                            MovimientoLote(
                                id_movimiento=movement.id_movimiento,
                                id_lote=lot.id_lote,
                                cantidad=restored,
                                costo_unitario=allocation.costo_unitario,
                            )
                        )
                        remaining -= restored
                        if not remaining:
                            break
                    if remaining:
                        raise CommerceConflictError(
                            "No fue posible restaurar las capas FIFO de la venta"
                        )
                returned.fecha_resolucion = datetime.now(UTC)
            elif payload.estado == "RECHAZADA":
                returned.fecha_resolucion = datetime.now(UTC)
            returned.id_empleado = employee.id_empleado
            returned.estado = payload.estado
            customer = (
                await self.repository.get(Cliente, returned.id_cliente)
                if returned.id_cliente
                else None
            )
            if customer:
                if payload.estado == "APROBADA":
                    notif_title = "Solicitud de devolución aprobada 📋"
                    notif_body = (
                        f"Tu solicitud de devolución #{returned.id_devolucion} fue aprobada. "
                        "Por favor acércate a la sucursal con tus prendas para la inspección física y recepción."
                    )
                elif payload.estado == "COMPLETADA":
                    notif_title = "Devolución completada con éxito ✅"
                    notif_body = (
                        f"Tu devolución #{returned.id_devolucion} ha sido completada exitosamente. "
                        "Se procesó la recepción física en tienda."
                    )
                elif payload.estado == "RECHAZADA":
                    notif_title = "Solicitud de devolución no aprobada ✕"
                    notif_body = (
                        f"Tu solicitud de devolución #{returned.id_devolucion} no fue aprobada."
                    )
                else:
                    notif_title = "Estado de devolución actualizado"
                    notif_body = f"Tu devolución #{returned.id_devolucion} ahora está {payload.estado.lower()}."

                await self._notify(
                    customer.id_usuario,
                    f"DEVOLUCION_{payload.estado}",
                    notif_title,
                    notif_body,
                    data={
                        "type": f"DEVOLUCION_{payload.estado}",
                        "id_devolucion": str(returned.id_devolucion),
                        "id_venta": str(returned.id_venta),
                    },
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return await self._return_response(returned)

    async def _notify(
        self,
        user_id: int,
        kind: str,
        title: str,
        content: str,
        data: dict | None = None,
    ) -> None:
        try:
            now = datetime.now(UTC)
            device_tokens = await self.repository.get_user_device_tokens(user_id)
            estado = "ENVIADO"
            fecha_envio = now
            error_msg = None

            if device_tokens:
                push_data = dict(data or {})
                push_data.setdefault("type", kind)
                delivered = await self.fcm_sender.send_push_notification(
                    tokens=device_tokens,
                    title=title,
                    body=content,
                    data=push_data,
                )
                delivered_count = int(delivered) if isinstance(delivered, (int, float)) else (1 if delivered else 0)
                if delivered_count > 0:
                    estado = "ENVIADO"
                    fecha_envio = datetime.now(UTC)
                else:
                    estado = "FALLIDO"
                    error_msg = "FCM no pudo entregar el push a los dispositivos registrados"
            else:
                estado = "ENVIADO"
                fecha_envio = now

            notif = Notificacion(
                id_usuario=user_id,
                id_campania=None,
                tipo=kind,
                canal="PUSH",
                proveedor="SISTEMA",
                titulo=title,
                contenido=content,
                estado=estado,
                fecha_creacion=now,
                fecha_envio=fecha_envio,
                fecha_entrega=fecha_envio if estado == "ENVIADO" else None,
                error_mensaje=error_msg,
            )
            await self.repository.add(notif)
        except Exception as exc:
            logger.warning("No se pudo registrar la notificacion: %s", exc)

    async def _notify_branch_staff(
        self,
        branch_id: int,
        title: str,
        content: str,
        data: dict | None = None,
    ) -> None:
        await self._notify_staff_and_admins(
            branch_id=branch_id,
            kind="STOCK_CRITICO",
            title=title,
            content=content,
            data=data,
        )

    async def _notify_staff_and_admins(
        self,
        branch_id: int | None,
        kind: str,
        title: str,
        content: str,
        data: dict | None = None,
    ) -> None:
        try:
            from app.modules.auth.models import Empleado, Rol, Usuario, UsuarioRol

            user_ids_to_notify: set[int] = set()

            def _parse_row_uid(row) -> int | None:
                if row is None:
                    return None
                if isinstance(row, (tuple, list)) or hasattr(row, "__getitem__"):
                    try:
                        return int(row[0])
                    except (IndexError, TypeError, ValueError):
                        pass
                try:
                    return int(row)
                except (TypeError, ValueError):
                    return None

            # 1. Colaboradores activos de la sucursal asignada (Cajero, Encargado, Auxiliar)
            if branch_id is not None:
                try:
                    b_id = int(branch_id)
                except (TypeError, ValueError):
                    b_id = branch_id

                stmt_branch = (
                    select(Empleado.id_usuario)
                    .join(Usuario, Usuario.id_usuario == Empleado.id_usuario)
                    .where(
                        Empleado.id_sucursal == b_id,
                        func.trim(func.upper(func.coalesce(Empleado.estado_laboral, "ACTIVO"))) != "INACTIVO",
                        func.trim(func.upper(func.coalesce(Usuario.estado, "ACTIVO"))) != "INACTIVO",
                    )
                )
                res_branch = await self.session.execute(stmt_branch)
                rows_branch = res_branch.all() if res_branch else []
                if hasattr(rows_branch, "__await__"):
                    rows_branch = await rows_branch
                for r in (rows_branch or []):
                    uid = _parse_row_uid(r)
                    if uid is not None:
                        user_ids_to_notify.add(uid)

            # 2. Administradores y propietarios globales activos (reciben notificaciones de TODAS las sucursales)
            stmt_admin = (
                select(UsuarioRol.id_usuario)
                .join(Rol, Rol.id_rol == UsuarioRol.id_rol)
                .join(Usuario, Usuario.id_usuario == UsuarioRol.id_usuario)
                .where(
                    func.trim(func.upper(Rol.nombre)).in_([
                        "ADMIN",
                        "ADMINISTRADOR",
                        "PROPIETARIO",
                        "DUEÑO",
                        "DUENO",
                        "GERENTE",
                    ]),
                    func.trim(func.upper(func.coalesce(Usuario.estado, "ACTIVO"))) != "INACTIVO",
                )
            )
            res_admin = await self.session.execute(stmt_admin)
            rows_admin = res_admin.all() if res_admin else []
            if hasattr(rows_admin, "__await__"):
                rows_admin = await rows_admin
            for r in (rows_admin or []):
                uid = _parse_row_uid(r)
                if uid is not None:
                    user_ids_to_notify.add(uid)

            logger.info(
                "_notify_staff_and_admins: branch_id=%s, kind=%s -> destinatarios resueltos: %s",
                branch_id,
                kind,
                user_ids_to_notify,
            )

            for uid in user_ids_to_notify:
                await self._notify(uid, kind, title, content, data=data)
        except Exception as exc:
            logger.warning("No se pudo notificar al personal y administradores: %s", exc)

    async def register_device_token(
        self, user_id: int, payload: DeviceTokenRegisterRequest
    ) -> DeviceTokenResponse:
        await self.repository.register_device_token(
            user_id=user_id,
            token=payload.token,
            plataforma=payload.plataforma,
            dispositivo_info=payload.dispositivo_info,
        )
        await self.session.commit()
        return DeviceTokenResponse(
            mensaje="Dispositivo registrado exitosamente para notificaciones push.",
            registrado=True,
        )

    async def _backfill_pending_order_notifications(self, user_id: int) -> None:
        """
        Sincroniza pedidos recientes en estado 'PENDIENTE' (Por Preparar) que aún no
        tienen registro en la bandeja de notificaciones para este colaborador o administrador.
        """
        from datetime import timedelta

        from app.modules.auth.models import Empleado, Rol, Sucursal, UsuarioRol

        user_roles_stmt = (
            select(func.upper(Rol.nombre))
            .join(UsuarioRol, UsuarioRol.id_rol == Rol.id_rol)
            .where(UsuarioRol.id_usuario == user_id)
        )
        roles = set((await self.session.scalars(user_roles_stmt)).all())
        is_global_admin = any(
            r in {"ADMIN", "ADMINISTRADOR", "PROPIETARIO", "DUEÑO", "DUENO", "GERENTE"}
            for r in roles
        )

        emp_stmt = select(Empleado.id_sucursal).where(
            Empleado.id_usuario == user_id,
            func.trim(func.upper(func.coalesce(Empleado.estado_laboral, "ACTIVO"))) != "INACTIVO",
        )
        emp_branch = (await self.session.scalars(emp_stmt)).first()

        if not is_global_admin and emp_branch is None:
            return

        since = datetime.now(UTC) - timedelta(hours=48)
        stmt_orders = (
            select(Pedido, Venta)
            .join(Venta, Venta.id_venta == Pedido.id_venta)
            .where(
                Pedido.estado == "PENDIENTE",
                Pedido.fecha_creacion >= since,
            )
        )
        if not is_global_admin and emp_branch is not None:
            stmt_orders = stmt_orders.where(Venta.id_sucursal == emp_branch)

        res = await self.session.execute(stmt_orders)
        orders_sales = res.all() if res else []
        added_any = False

        for row in orders_sales:
            order, sale = row[0], row[1]
            notif_exists_stmt = select(Notificacion.id_notificacion).where(
                Notificacion.id_usuario == user_id,
                Notificacion.tipo == "NUEVO_PEDIDO",
                Notificacion.contenido.like(f"%Pedido #{order.id_pedido}%"),
            )
            exists = (await self.session.scalars(notif_exists_stmt)).first()
            if not exists:
                branch = await self.repository.get(Sucursal, sale.id_sucursal)
                branch_name = getattr(branch, "nombre", None) or f"Sucursal #{sale.id_sucursal}"
                mode_label = "Retiro en tienda" if sale.modalidad_entrega == "RETIRO_SUCURSAL" else "Delivery"
                now = datetime.now(UTC)
                notif = Notificacion(
                    id_usuario=user_id,
                    id_campania=None,
                    tipo="NUEVO_PEDIDO",
                    canal="PUSH",
                    proveedor="SISTEMA",
                    titulo=f"Nuevo Pedido #{order.id_pedido} por preparar 🛍️",
                    contenido=f"Pedido por Bs {sale.total:,.2f} ({mode_label} - {branch_name}). Requiere preparación.",
                    estado="ENVIADO",
                    fecha_creacion=order.fecha_creacion or now,
                    fecha_envio=order.fecha_creacion or now,
                    fecha_entrega=order.fecha_creacion or now,
                )
                self.session.add(notif)
                added_any = True

        if added_any:
            await self.session.commit()

    async def list_notifications(self, user_id: int):
        try:
            await self._backfill_pending_order_notifications(user_id)
        except Exception as exc:
            logger.debug("No se pudo ejecutar backfill de pedidos pendientes para notificaciones: %s", exc)
        return await self.repository.notifications(user_id)

    async def mark_notification_as_read(
        self, user_id: int, notification_id: int, is_admin: bool = False
    ) -> None:
        stmt = select(Notificacion).where(
            Notificacion.id_notificacion == notification_id,
        )
        if not is_admin:
            stmt = stmt.where(Notificacion.id_usuario == user_id)

        res = await self.session.execute(stmt)
        notification = res.scalar_one_or_none()
        if notification:
            notification.estado = "LEIDO"
            await self.session.commit()

    async def mark_all_notifications_as_read(
        self, user_id: int, is_admin: bool = False
    ) -> None:
        if is_admin:
            stmt = (
                update(Notificacion)
                .where(
                    (Notificacion.id_usuario == user_id) | (Notificacion.id_usuario.is_(None)),
                    Notificacion.estado != "LEIDO",
                )
                .values(estado="LEIDO")
            )
        else:
            stmt = (
                update(Notificacion)
                .where(
                    Notificacion.id_usuario == user_id,
                    Notificacion.estado != "LEIDO",
                )
                .values(estado="LEIDO")
            )
        await self.session.execute(stmt)
        await self.session.commit()

    async def admin_list_notifications(
        self,
        *,
        estado: str | None = None,
        canal: str | None = None,
        tipo: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> AdminNotificationPage:
        rows, total, kpi_dict = await self.repository.admin_notifications(
            estado=estado,
            canal=canal,
            tipo=tipo,
            search=search,
            page=page,
            page_size=page_size,
        )
        items = []
        for notif, nombres, apellidos, correo in rows:
            dest_nombre = f"{nombres} {apellidos}".strip() if (nombres or apellidos) else None
            items.append(
                AdminNotificationResponse(
                    id_notificacion=notif.id_notificacion,
                    id_usuario=notif.id_usuario,
                    destinatario_nombre=dest_nombre,
                    destinatario_email=correo or notif.destinatario,
                    tipo=notif.tipo,
                    canal=notif.canal,
                    proveedor=notif.proveedor,
                    destinatario=notif.destinatario or correo,
                    titulo=notif.titulo,
                    contenido=notif.contenido,
                    estado=notif.estado,
                    external_message_id=notif.external_message_id,
                    fecha_creacion=notif.fecha_creacion,
                    fecha_envio=notif.fecha_envio,
                    fecha_entrega=notif.fecha_entrega,
                    error_mensaje=notif.error_mensaje,
                )
            )
        return AdminNotificationPage(
            items=items,
            total=total,
            kpis=NotificationKpis(**kpi_dict),
            page=page,
            page_size=page_size,
        )

    async def send_manual_notification(
        self, payload: ManualNotificationCreate
    ) -> AdminNotificationResponse:
        user = await self.repository.get(Usuario, payload.id_usuario)
        if not user:
            raise CommerceNotFoundError("El usuario destinatario no existe")

        dest_name = f"{user.nombres} {user.apellidos}".strip()
        dest_email = user.correo
        canal = (payload.canal or "SISTEMA").upper()
        now = datetime.now(UTC)

        estado = "PENDIENTE"
        fecha_envio = None
        fecha_entrega = None
        error_msg = None

        if canal == "EMAIL":
            sent = await self.mailer.send_operational_email(
                recipient_email=dest_email,
                recipient_name=dest_name,
                title=payload.titulo,
                content=payload.contenido,
            )
            if sent:
                estado = "ENVIADO"
                fecha_envio = now
                fecha_entrega = now
            else:
                estado = "PENDIENTE"
        elif canal == "PUSH":
            estado = "ENVIADO"
            fecha_envio = now
            fecha_entrega = now
            tokens = await self.repository.get_user_device_tokens(user.id_usuario)
            if tokens:
                await self.fcm_sender.send_push_notification(
                    tokens=tokens,
                    title=payload.titulo,
                    body=payload.contenido,
                    data={"type": payload.tipo},
                )
        else:
            estado = "ENVIADO"
            fecha_envio = now
            fecha_entrega = now

        notif = Notificacion(
            id_usuario=user.id_usuario,
            id_campania=None,
            tipo=payload.tipo.upper() if payload.tipo else "AVISO_OPERATIVO",
            canal=canal,
            proveedor="BREVO" if canal == "EMAIL" else "SISTEMA",
            destinatario=dest_email,
            titulo=payload.titulo,
            contenido=payload.contenido,
            estado=estado,
            fecha_creacion=now,
            fecha_envio=fecha_envio,
            fecha_entrega=fecha_entrega,
            error_mensaje=error_msg,
        )
        await self.repository.add(notif)
        await self.session.commit()

        return AdminNotificationResponse(
            id_notificacion=notif.id_notificacion,
            id_usuario=notif.id_usuario,
            destinatario_nombre=dest_name,
            destinatario_email=dest_email,
            tipo=notif.tipo,
            canal=notif.canal,
            proveedor=notif.proveedor,
            destinatario=notif.destinatario,
            titulo=notif.titulo,
            contenido=notif.contenido,
            estado=notif.estado,
            external_message_id=notif.external_message_id,
            fecha_creacion=notif.fecha_creacion,
            fecha_envio=notif.fecha_envio,
            fecha_entrega=notif.fecha_entrega,
            error_mensaje=notif.error_mensaje,
        )

    async def resend_notification(
        self, notification_id: int
    ) -> AdminNotificationResponse:
        row = await self.repository.notification_detail(notification_id)
        if not row:
            raise CommerceNotFoundError("La notificación no existe")

        notif, nombres, apellidos, correo = row
        dest_name = f"{nombres} {apellidos}".strip() if (nombres or apellidos) else "Cliente"
        dest_email = correo or notif.destinatario
        now = datetime.now(UTC)

        if notif.canal == "EMAIL" and dest_email:
            sent = await self.mailer.send_operational_email(
                recipient_email=dest_email,
                recipient_name=dest_name,
                title=notif.titulo or "Aviso de Capricho Store",
                content=notif.contenido,
            )
            if sent:
                notif.estado = "ENVIADO"
                notif.fecha_envio = now
                notif.fecha_entrega = now
                notif.error_mensaje = None
            else:
                notif.estado = "FALLIDO"
                notif.error_mensaje = "No se pudo conectar con el proveedor de correo Brevo"
        else:
            notif.estado = "ENVIADO"
            notif.fecha_envio = now
            notif.fecha_entrega = now
            notif.error_mensaje = None

        await self.session.commit()

        return AdminNotificationResponse(
            id_notificacion=notif.id_notificacion,
            id_usuario=notif.id_usuario,
            destinatario_nombre=dest_name,
            destinatario_email=dest_email,
            tipo=notif.tipo,
            canal=notif.canal,
            proveedor=notif.proveedor,
            destinatario=notif.destinatario or dest_email,
            titulo=notif.titulo,
            contenido=notif.contenido,
            estado=notif.estado,
            external_message_id=notif.external_message_id,
            fecha_creacion=notif.fecha_creacion,
            fecha_envio=notif.fecha_envio,
            fecha_entrega=notif.fecha_entrega,
            error_mensaje=notif.error_mensaje,
        )

    async def supplier_purchase_history(
        self, user_id: int, *, all_branches: bool = False, **filters
    ) -> SupplierPurchaseHistoryPage:
        if not all_branches:
            filters["branch_id"] = (await self._employee(user_id)).id_sucursal
        rows, total = await self.repository.supplier_history(**filters)
        return SupplierPurchaseHistoryPage(
            items=list(rows), total=total, page=filters["page"], page_size=filters["page_size"]
        )

    async def list_campaigns(self, state: str | None = None) -> list[CampaignResponse]:
        rows = await self.repository.list_campaigns(state=state)
        return [
            CampaignResponse(
                id_campania=c.id_campania,
                nombre=c.nombre,
                descripcion=c.descripcion,
                asunto_email=c.asunto_email,
                segmento_objetivo=c.segmento_objetivo,
                fecha_inicio=c.fecha_inicio,
                fecha_fin=c.fecha_fin,
                estado=c.estado,
                created_at=c.created_at,
                updated_at=c.updated_at,
                total_notificaciones=notif_count,
            )
            for c, notif_count in rows
        ]

    async def create_campaign(self, payload: CampaignCreate) -> CampaignResponse:
        campaign = Campania(
            nombre=payload.nombre.strip(),
            descripcion=payload.descripcion.strip(),
            asunto_email=payload.asunto_email.strip() if payload.asunto_email else None,
            segmento_objetivo=(
                payload.segmento_objetivo.strip() if payload.segmento_objetivo else "TODOS"
            ),
            fecha_inicio=payload.fecha_inicio,
            fecha_fin=payload.fecha_fin,
            estado="BORRADOR",
        )
        await self.repository.add(campaign)
        await self.session.commit()
        await self.session.refresh(campaign)
        return CampaignResponse(
            id_campania=campaign.id_campania,
            nombre=campaign.nombre,
            descripcion=campaign.descripcion,
            asunto_email=campaign.asunto_email,
            segmento_objetivo=campaign.segmento_objetivo,
            fecha_inicio=campaign.fecha_inicio,
            fecha_fin=campaign.fecha_fin,
            estado=campaign.estado,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
            total_notificaciones=0,
        )

    async def get_campaign(self, campaign_id: int) -> CampaignResponse:
        campaign = await self.repository.get_campaign(campaign_id)
        if not campaign:
            raise CommerceNotFoundError(f"Campaña con ID {campaign_id} no encontrada.")
        count = await self.repository.get_campaign_notifications_count(campaign_id)
        return CampaignResponse(
            id_campania=campaign.id_campania,
            nombre=campaign.nombre,
            descripcion=campaign.descripcion,
            asunto_email=campaign.asunto_email,
            segmento_objetivo=campaign.segmento_objetivo,
            fecha_inicio=campaign.fecha_inicio,
            fecha_fin=campaign.fecha_fin,
            estado=campaign.estado,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
            total_notificaciones=count,
        )

    async def update_campaign(self, campaign_id: int, payload: CampaignUpdate) -> CampaignResponse:
        campaign = await self.repository.get_campaign(campaign_id)
        if not campaign:
            raise CommerceNotFoundError(f"Campaña con ID {campaign_id} no encontrada.")
        if campaign.estado not in ("BORRADOR", "PROGRAMADA"):
            raise InvalidCommerceOperationError(
                f"No se puede modificar una campaña en estado {campaign.estado}."
            )
        if payload.nombre is not None:
            campaign.nombre = payload.nombre.strip()
        if payload.descripcion is not None:
            campaign.descripcion = payload.descripcion.strip()
        if payload.asunto_email is not None:
            campaign.asunto_email = payload.asunto_email.strip() if payload.asunto_email else None
        if payload.segmento_objetivo is not None:
            campaign.segmento_objetivo = payload.segmento_objetivo.strip()
        if payload.fecha_inicio is not None:
            campaign.fecha_inicio = payload.fecha_inicio
        if payload.fecha_fin is not None:
            campaign.fecha_fin = payload.fecha_fin
        if payload.estado is not None:
            campaign.estado = payload.estado

        await self.session.commit()
        await self.session.refresh(campaign)
        count = await self.repository.get_campaign_notifications_count(campaign_id)
        return CampaignResponse(
            id_campania=campaign.id_campania,
            nombre=campaign.nombre,
            descripcion=campaign.descripcion,
            asunto_email=campaign.asunto_email,
            segmento_objetivo=campaign.segmento_objetivo,
            fecha_inicio=campaign.fecha_inicio,
            fecha_fin=campaign.fecha_fin,
            estado=campaign.estado,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
            total_notificaciones=count,
        )

    async def launch_campaign(self, campaign_id: int) -> CampaignLaunchResponse:
        campaign = await self.repository.get_campaign(campaign_id)
        if not campaign:
            raise CommerceNotFoundError(f"Campaña con ID {campaign_id} no encontrada.")
        if campaign.estado == "FINALIZADA":
            raise InvalidCommerceOperationError("Esta campaña ya fue enviada y finalizada.")

        campaign.estado = "ENVIANDO"
        target_users = await self.repository.get_target_users_for_campaign(
            campaign.segmento_objetivo or "TODOS"
        )

        now = datetime.now(UTC)
        for user in target_users:
            notif = Notificacion(
                id_usuario=user.id_usuario,
                id_campania=campaign.id_campania,
                tipo="CAMPAÑA_PROMOCIONAL",
                canal="PUSH",
                proveedor="SISTEMA",
                destinatario=user.correo,
                titulo=campaign.nombre,
                contenido=campaign.descripcion,
                estado="ENVIADO",
                fecha_envio=now,
                fecha_entrega=now,
            )
            await self.repository.add(notif)
            try:
                tokens = await self.repository.get_user_device_tokens(user.id_usuario)
                if tokens:
                    await self.fcm_sender.send_push_notification(
                        tokens=tokens,
                        title=campaign.nombre,
                        body=campaign.descripcion,
                        data={
                            "type": "CAMPAÑA_PROMOCIONAL",
                            "campaign_id": str(campaign.id_campania),
                        },
                    )
            except Exception as exc:
                logger.warning(
                    "Error al emitir push de campaña al usuario %s: %s", user.id_usuario, exc
                )

        campaign.estado = "FINALIZADA"
        campaign.fecha_inicio = campaign.fecha_inicio or now
        await self.session.commit()

        msg = (
            f"Campaña '{campaign.nombre}' difundida con éxito "
            f"a {len(target_users)} cliente(s)."
        )
        return CampaignLaunchResponse(
            id_campania=campaign.id_campania,
            nombre=campaign.nombre,
            estado=campaign.estado,
            destinatarios_notificados=len(target_users),
            mensaje=msg,
        )

    async def list_promotions(self) -> list[PromotionResponse]:
        raw_items = await self.repository.list_promotions()
        return [
            PromotionResponse(
                id_promocion=item["promotion"].id_promocion,
                nombre=item["promotion"].nombre,
                descripcion=item["promotion"].descripcion,
                porcentaje_descuento=item["promotion"].porcentaje_descuento,
                fecha_inicio=item["promotion"].fecha_inicio,
                fecha_fin=item["promotion"].fecha_fin,
                activo=item["promotion"].activo,
                created_at=item["promotion"].created_at,
                updated_at=item["promotion"].updated_at,
                producto_ids=item["producto_ids"],
                categoria_ids=item["categoria_ids"],
                temporada_ids=item["temporada_ids"],
                productos_count=len(item["producto_ids"]),
                categorias_count=len(item["categoria_ids"]),
                temporadas_count=len(item["temporada_ids"]),
                estado_vigencia=item["estado_vigencia"],
            )
            for item in raw_items
        ]

    async def get_promotion(self, promo_id: int) -> PromotionResponse:
        details = await self.repository.get_promotion_details(promo_id)
        if not details:
            raise CommerceNotFoundError("Promoción no encontrada")
        p = details["promotion"]
        return PromotionResponse(
            id_promocion=p.id_promocion,
            nombre=p.nombre,
            descripcion=p.descripcion,
            porcentaje_descuento=p.porcentaje_descuento,
            fecha_inicio=p.fecha_inicio,
            fecha_fin=p.fecha_fin,
            activo=p.activo,
            created_at=p.created_at,
            updated_at=p.updated_at,
            producto_ids=details["producto_ids"],
            categoria_ids=details["categoria_ids"],
            temporada_ids=details["temporada_ids"],
            productos_count=len(details["producto_ids"]),
            categorias_count=len(details["categoria_ids"]),
            temporadas_count=len(details["temporada_ids"]),
            estado_vigencia=details["estado_vigencia"],
        )

    async def create_promotion(self, payload: PromotionCreate) -> PromotionResponse:
        promo = Promocion(
            nombre=payload.nombre,
            descripcion=payload.descripcion,
            porcentaje_descuento=payload.porcentaje_descuento,
            fecha_inicio=payload.fecha_inicio,
            fecha_fin=payload.fecha_fin,
            activo=payload.activo,
        )
        await self.repository.add(promo)
        await self.repository.set_promotion_associations(
            promo.id_promocion,
            product_ids=payload.producto_ids,
            category_ids=payload.categoria_ids,
            season_ids=payload.temporada_ids,
        )
        await self.session.commit()
        return await self.get_promotion(promo.id_promocion)

    async def update_promotion(
        self, promo_id: int, payload: PromotionUpdate
    ) -> PromotionResponse:
        promo = await self.repository.get_promotion(promo_id)
        if not promo:
            raise CommerceNotFoundError("Promoción no encontrada")

        if payload.nombre is not None:
            promo.nombre = payload.nombre
        if payload.descripcion is not None:
            promo.descripcion = payload.descripcion
        if payload.porcentaje_descuento is not None:
            promo.porcentaje_descuento = payload.porcentaje_descuento
        if payload.fecha_inicio is not None:
            promo.fecha_inicio = payload.fecha_inicio
        if payload.fecha_fin is not None:
            promo.fecha_fin = payload.fecha_fin
        if payload.activo is not None:
            promo.activo = payload.activo

        if promo.fecha_fin <= promo.fecha_inicio:
            raise InvalidCommerceOperationError(
                "La fecha de fin debe ser posterior a la fecha de inicio"
            )

        if (
            payload.producto_ids is not None
            or payload.categoria_ids is not None
            or payload.temporada_ids is not None
        ):
            await self.repository.set_promotion_associations(
                promo.id_promocion,
                product_ids=payload.producto_ids,
                category_ids=payload.categoria_ids,
                season_ids=payload.temporada_ids,
            )

        await self.session.commit()
        return await self.get_promotion(promo.id_promocion)

    async def delete_promotion(self, promo_id: int) -> dict:
        promo = await self.repository.get_promotion(promo_id)
        if not promo:
            raise CommerceNotFoundError("Promoción no encontrada")
        await self.repository.delete_promotion(promo)
        await self.session.commit()
        return {"mensaje": f"Promoción '{promo.nombre}' eliminada con éxito"}

    async def list_active_promotions_public(self) -> list[ActivePromotionItem]:
        promos = await self.repository.get_active_promotions()
        results: list[ActivePromotionItem] = []
        for p in promos:
            details = await self.repository.get_promotion_details(p.id_promocion)
            if details:
                results.append(
                    ActivePromotionItem(
                        id_promocion=p.id_promocion,
                        nombre=p.nombre,
                        descripcion=p.descripcion,
                        porcentaje_descuento=p.porcentaje_descuento,
                        fecha_inicio=p.fecha_inicio,
                        fecha_fin=p.fecha_fin,
                        productos_count=len(details["producto_ids"]),
                        categorias_count=len(details["categoria_ids"]),
                        temporadas_count=len(details["temporada_ids"]),
                    )
                )
        return results

    async def get_admin_dashboard_summary(
        self, id_sucursal: int | None = None
    ) -> AdminDashboardSummaryResponse:
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 1:
            prev_month_start = month_start.replace(year=month_start.year - 1, month=12)
        else:
            prev_month_start = month_start.replace(month=month_start.month - 1)
        prev_month_end = month_start - timedelta(microseconds=1)

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # 1. Ventas Mes Actual
        stmt_sales_month = (
            select(func.coalesce(func.sum(Venta.total), 0))
            .where(Venta.estado == "PAGADA", Venta.fecha_venta >= month_start)
        )
        if id_sucursal:
            stmt_sales_month = stmt_sales_month.where(Venta.id_sucursal == id_sucursal)
        sales_month_total = Decimal(str(await self.session.scalar(stmt_sales_month) or 0))

        # 1b. Ventas Mes Anterior
        stmt_sales_prev = (
            select(func.coalesce(func.sum(Venta.total), 0))
            .where(
                Venta.estado == "PAGADA",
                Venta.fecha_venta >= prev_month_start,
                Venta.fecha_venta <= prev_month_end,
            )
        )
        if id_sucursal:
            stmt_sales_prev = stmt_sales_prev.where(Venta.id_sucursal == id_sucursal)
        sales_prev_total = Decimal(str(await self.session.scalar(stmt_sales_prev) or 0))

        if sales_prev_total > 0:
            growth_pct = float(round(((sales_month_total - sales_prev_total) / sales_prev_total) * 100, 1))
        else:
            growth_pct = 0.0

        # 2. Pedidos Pendientes
        stmt_pending_orders = (
            select(func.count(Pedido.id_pedido))
            .join(Venta, Venta.id_venta == Pedido.id_venta)
            .where(
                Venta.estado == "PAGADA",
                Pedido.estado.in_(["PAGADO", "PREPARANDO", "LISTO_PARA_ENVIO", "LISTO_PARA_RETIRO", "EN_CAMINO"]),
            )
        )
        if id_sucursal:
            stmt_pending_orders = stmt_pending_orders.where(Venta.id_sucursal == id_sucursal)
        pending_orders_count = int(await self.session.scalar(stmt_pending_orders) or 0)

        # 3. Reservas Hoy
        stmt_reservations_today = (
            select(func.count(Reserva.id_reserva))
            .where(
                Reserva.estado.in_(["PENDIENTE", "CONFIRMADA"]),
                or_(
                    and_(Reserva.fecha_cita >= today_start, Reserva.fecha_cita < today_end),
                    and_(Reserva.fecha_cita.is_(None), Reserva.fecha_reserva >= today_start, Reserva.fecha_reserva < today_end),
                ),
            )
        )
        if id_sucursal:
            stmt_reservations_today = stmt_reservations_today.where(Reserva.id_sucursal == id_sucursal)
        reservations_today_count = int(await self.session.scalar(stmt_reservations_today) or 0)

        # 4. Alertas de Stock Crítico
        critical_threshold = case(
            (InventarioSucursal.stock_minimo > 3, InventarioSucursal.stock_minimo),
            else_=3,
        )
        stmt_stock_alerts = (
            select(func.count(InventarioSucursal.id_inventario))
            .where(
                (InventarioSucursal.stock_fisico - InventarioSucursal.stock_reservado) <= critical_threshold
            )
        )
        if id_sucursal:
            stmt_stock_alerts = stmt_stock_alerts.where(InventarioSucursal.id_sucursal == id_sucursal)
        stock_alerts_count = int(await self.session.scalar(stmt_stock_alerts) or 0)

        kpis = DashboardKpis(
            ventas_mes_total=sales_month_total,
            ventas_crecimiento_pct=growth_pct,
            pedidos_pendientes=pending_orders_count,
            reservas_hoy=reservations_today_count,
            alertas_stock_critico=stock_alerts_count,
        )

        # 5. Tendencia Semanal (Últimos 7 días)
        day_names_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        tendencia_semanal: list[DashboardDailyRevenue] = []
        for i in range(6, -1, -1):
            day_dt = today_start - timedelta(days=i)
            day_next = day_dt + timedelta(days=1)
            stmt_day = (
                select(func.coalesce(func.sum(Venta.total), 0))
                .where(
                    Venta.estado == "PAGADA",
                    Venta.fecha_venta >= day_dt,
                    Venta.fecha_venta < day_next,
                )
            )
            if id_sucursal:
                stmt_day = stmt_day.where(Venta.id_sucursal == id_sucursal)
            day_total = Decimal(str(await self.session.scalar(stmt_day) or 0))
            dia_nombre = day_names_es[day_dt.weekday()]
            tendencia_semanal.append(
                DashboardDailyRevenue(
                    fecha=day_dt.strftime("%Y-%m-%d"),
                    dia_nombre=dia_nombre,
                    total=day_total,
                )
            )

        # 6. Ventas por Sucursal
        stmt_branches = select(Sucursal).where(Sucursal.activo.is_(True)).order_by(Sucursal.id_sucursal)
        branches = list((await self.session.scalars(stmt_branches)).all())
        ventas_por_sucursal: list[DashboardBranchShare] = []
        total_all_branches = Decimal("0")

        branch_totals: list[tuple[Sucursal, Decimal]] = []
        for b in branches:
            stmt_b_sales = (
                select(func.coalesce(func.sum(Venta.total), 0))
                .where(
                    Venta.estado == "PAGADA",
                    Venta.id_sucursal == b.id_sucursal,
                    Venta.fecha_venta >= month_start,
                )
            )
            b_total = Decimal(str(await self.session.scalar(stmt_b_sales) or 0))
            branch_totals.append((b, b_total))
            total_all_branches += b_total

        for b, b_total in branch_totals:
            pct = float(round((b_total / total_all_branches * 100), 1)) if total_all_branches > 0 else 0.0
            ventas_por_sucursal.append(
                DashboardBranchShare(
                    id_sucursal=b.id_sucursal,
                    nombre=b.nombre,
                    total=b_total,
                    porcentaje=pct,
                )
            )

        # 7. Pedidos Urgentes (5 más recientes)
        stmt_urgent = (
            select(Pedido, Venta, Cliente, Usuario)
            .join(Venta, Venta.id_venta == Pedido.id_venta)
            .outerjoin(Cliente, Cliente.id_cliente == Venta.id_cliente)
            .outerjoin(Usuario, Usuario.id_usuario == Cliente.id_usuario)
            .where(
                Venta.estado == "PAGADA",
                Pedido.estado.in_(["PAGADO", "PREPARANDO", "LISTO_PARA_ENVIO", "LISTO_PARA_RETIRO", "EN_CAMINO"]),
            )
        )
        if id_sucursal:
            stmt_urgent = stmt_urgent.where(Venta.id_sucursal == id_sucursal)
        stmt_urgent = stmt_urgent.order_by(Pedido.fecha_creacion.desc()).limit(5)
        urgent_rows = (await self.session.execute(stmt_urgent)).all()

        pedidos_urgentes: list[DashboardUrgentOrder] = []
        for ped, vta, _cli, usr in urgent_rows:
            client_name = (
                f"{usr.nombres} {usr.apellidos}".strip()
                if usr and (usr.nombres or usr.apellidos)
                else (usr.correo if usr else "Cliente Mostrador")
            )
            pedidos_urgentes.append(
                DashboardUrgentOrder(
                    id_pedido=ped.id_pedido,
                    id_venta=vta.id_venta,
                    cliente_nombre=client_name,
                    tipo_entrega=vta.modalidad_entrega,
                    estado=ped.estado,
                    total=vta.total,
                    fecha_creacion=ped.fecha_creacion,
                )
            )

        # 8. Top 5 Productos Más Vendidos
        stmt_top = (
            select(
                Producto.id_producto,
                Producto.nombre,
                Categoria.nombre.label("categoria_nombre"),
                Marca.nombre.label("marca_nombre"),
                func.sum(DetalleVenta.cantidad).label("unidades"),
                func.sum(DetalleVenta.subtotal).label("recaudado"),
            )
            .select_from(DetalleVenta)
            .join(VarianteProducto, VarianteProducto.id_variante == DetalleVenta.id_variante)
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .join(Categoria, Categoria.id_categoria == Producto.id_categoria)
            .join(Marca, Marca.id_marca == Producto.id_marca)
            .join(Venta, Venta.id_venta == DetalleVenta.id_venta)
            .where(Venta.estado == "PAGADA")
        )
        if id_sucursal:
            stmt_top = stmt_top.where(Venta.id_sucursal == id_sucursal)
        stmt_top = (
            stmt_top.group_by(
                Producto.id_producto,
                Producto.nombre,
                Categoria.nombre,
                Marca.nombre,
            )
            .order_by(func.sum(DetalleVenta.cantidad).desc())
            .limit(5)
        )
        top_rows = (await self.session.execute(stmt_top)).all()

        top_productos: list[DashboardTopProduct] = []
        for p_id, p_nom, c_nom, m_nom, unids, rec in top_rows:
            stmt_img = (
                select(ImagenProducto.secure_url)
                .where(ImagenProducto.id_producto == p_id, ImagenProducto.es_principal.is_(True))
                .limit(1)
            )
            img_url = await self.session.scalar(stmt_img)
            top_productos.append(
                DashboardTopProduct(
                    id_producto=p_id,
                    nombre=p_nom,
                    categoria=c_nom,
                    marca=m_nom,
                    unidades_vendidas=int(unids or 0),
                    total_recaudado=Decimal(str(rec or 0)),
                    imagen_url=img_url,
                )
            )

        return AdminDashboardSummaryResponse(
            kpis=kpis,
            tendencia_semanal=tendencia_semanal,
            ventas_por_sucursal=ventas_por_sucursal,
            pedidos_urgentes=pedidos_urgentes,
            top_productos=top_productos,
        )



