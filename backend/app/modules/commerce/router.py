from datetime import UTC, date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.modules.auth.dependencies import (
    CurrentPrincipal,
    get_current_principal,
    get_optional_principal,
    require_permission,
)
from app.modules.auth.exceptions import PermissionDeniedError
from app.modules.commerce.dependencies import get_commerce_service
from app.modules.commerce.exceptions import PaymentGatewayError
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
    DeviceTokenRegisterRequest,
    DeviceTokenResponse,
    ManualNotificationCreate,
    NotificationResponse,
    OrderResponse,
    OrderStatusUpdate,
    PromotionCreate,
    PromotionResponse,
    PromotionUpdate,
    ReservationCreate,
    ReservationResponse,
    ReservationStatusUpdate,
    ReturnCreate,
    ReturnResponse,
    ReturnStatusUpdate,
    ReturnSettlement,
    SaleCreate,
    SaleResponse,
    SaleReturnInspectionResponse,
    ShippingQuoteCreate,
    ShippingQuoteResponse,
    StripeCheckoutResponse,
    StripeCheckoutStatusResponse,
    SupplierPurchaseHistoryPage,
)
from app.modules.commerce.service import CommerceService

router = APIRouter(tags=["cycle ii commerce"])
Authenticated = Annotated[CurrentPrincipal, Depends(get_current_principal)]
OptionalPrincipal = Annotated[CurrentPrincipal | None, Depends(get_optional_principal)]
Service = Annotated[CommerceService, Depends(get_commerce_service)]


@router.get("/cart", response_model=CartResponse)  # [CU-09] Consultar carrito activo
async def get_cart(principal: Authenticated, service: Service):
    return await service.get_cart(principal.user.id_usuario)


@router.post("/cart/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)  # [CU-09] Agregar prenda al carrito
async def add_cart_item(payload: CartItemCreate, principal: Authenticated, service: Service):
    return await service.add_cart_item(principal.user.id_usuario, payload)


@router.patch("/cart/items/{item_id}", response_model=CartResponse)  # [CU-09] Modificar cantidad en carrito
async def update_cart_item(
    item_id: int, payload: CartItemUpdate, principal: Authenticated, service: Service
):
    return await service.update_cart_item(principal.user.id_usuario, item_id, payload)


@router.post("/cart/items/{item_id}/remove", response_model=CartResponse)  # [CU-09] Quitar prenda del carrito
async def remove_cart_item(item_id: int, principal: Authenticated, service: Service):
    return await service.remove_cart_item(principal.user.id_usuario, item_id)


@router.post("/cart/clear", response_model=CartResponse)  # [CU-09] Vaciar carrito de compras
async def clear_cart(principal: Authenticated, service: Service):
    return await service.clear_cart(principal.user.id_usuario)


@router.get("/addresses", response_model=list[AddressResponse])  # [CU-09] Listar direcciones de entrega
async def list_addresses(principal: Authenticated, service: Service):
    return await service.list_addresses(principal.user.id_usuario)


@router.post("/addresses", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)  # [CU-09] Guardar dirección de entrega
async def create_address(payload: AddressCreate, principal: Authenticated, service: Service):
    return await service.create_address(principal.user.id_usuario, payload)


@router.patch("/addresses/{address_id}", response_model=AddressResponse)  # [CU-09] Actualizar dirección de entrega
async def update_address(
    address_id: int, payload: AddressUpdate, principal: Authenticated, service: Service
):
    return await service.update_address(principal.user.id_usuario, address_id, payload)


@router.get("/reservations", response_model=list[ReservationResponse])  # [CU-10] Mis reservas activas
async def list_customer_reservations(principal: Authenticated, service: Service):
    return await service.list_reservations(principal.user.id_usuario, operational=False)


@router.post(  # [CU-10] Crear reserva de prenda (48h hábiles)
    "/reservations", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED
)
async def create_reservation(
    payload: ReservationCreate, principal: Authenticated, service: Service
):
    return await service.create_reservation(principal.user.id_usuario, payload)


@router.get("/reservations/{reservation_id}", response_model=ReservationResponse)  # [CU-10] Detalle de reserva
async def get_customer_reservation(reservation_id: int, principal: Authenticated, service: Service):
    return await service.get_reservation(
        principal.user.id_usuario, reservation_id, operational=False
    )


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationResponse)  # [CU-10] Cancelar reserva
async def cancel_reservation(reservation_id: int, principal: Authenticated, service: Service):
    return await service.cancel_reservation(principal.user.id_usuario, reservation_id)


@router.get("/admin/reservations", response_model=list[ReservationResponse])  # [CU-10] Listar reservas operativas
async def list_operational_reservations(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("reservas.ver"))],
    service: Service,
    estado: str | None = None,
    sucursal: int | None = Query(default=None, gt=0),
):
    return await service.list_reservations(
        principal.user.id_usuario,
        operational=True,
        state=estado,
        branch_id=sucursal,
        all_branches="ADMIN" in principal.roles,
    )


@router.patch("/admin/reservations/{reservation_id}/status", response_model=ReservationResponse)  # [CU-10] Actualizar estado de reserva
async def update_reservation_status(
    reservation_id: int,
    payload: ReservationStatusUpdate,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("reservas.gestionar"))],
    service: Service,
):
    return await service.update_reservation_status(
        principal.user.id_usuario,
        reservation_id,
        payload,
        all_branches="ADMIN" in principal.roles,
    )


@router.post("/sales/pos", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)  # [CU-11] Registrar venta en punto de venta (POS)
async def create_pos_sale(
    payload: SaleCreate,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.crear"))],
    service: Service,
):
    if payload.registrar_efectivo and "pagos.registrar" not in principal.permissions:
        raise PermissionDeniedError
    return await service.create_pos_sale(
        principal.user.id_usuario, payload, all_branches="ADMIN" in principal.roles
    )


@router.get("/sales", response_model=list[SaleResponse])  # [CU-11] Listar ventas registradas
async def list_sales(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Service,
    sucursal: int | None = Query(default=None, gt=0),
    canal: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
):
    return await service.list_sales(
        principal.user.id_usuario,
        branch_id=sucursal,
        all_branches="ADMIN" in principal.roles,
        channel=canal,
        date_from=(datetime.combine(fecha_desde, time.min, tzinfo=UTC) if fecha_desde else None),
        date_to=(datetime.combine(fecha_hasta, time.max, tzinfo=UTC) if fecha_hasta else None),
    )


@router.get("/sales/{sale_id}", response_model=SaleResponse)  # [CU-11] Ver detalle de venta
async def get_sale(sale_id: int, principal: Authenticated, service: Service):
    return await service.get_sale(
        principal.user.id_usuario,
        sale_id,
        all_branches="ADMIN" in principal.roles,
    )


@router.get("/history/purchases", response_model=list[SaleResponse])  # [CU-11] Historial de compras de cliente
async def customer_purchase_history(principal: Authenticated, service: Service):
    return await service.list_customer_sales(principal.user.id_usuario)


@router.get("/history/reservations", response_model=list[ReservationResponse])  # [CU-10] Historial de reservas de cliente
async def customer_reservation_history(principal: Authenticated, service: Service):
    return await service.list_reservations(principal.user.id_usuario, operational=False)


@router.post(  # [CU-12] Iniciar checkout con Stripe
    "/checkout", response_model=StripeCheckoutResponse, status_code=status.HTTP_201_CREATED
)
async def checkout(
    payload: CheckoutCreate, principal: Authenticated, service: Service, request: Request
):
    client_origin = request.headers.get("origin") or request.headers.get("referer")
    return await service.checkout(
        principal.user.id_usuario, payload, client_origin=client_origin
    )


@router.get("/checkout/{session_id}/status", response_model=StripeCheckoutStatusResponse)  # [CU-12] Consultar estado de sesión Stripe
async def stripe_checkout_status(
    session_id: str, principal: OptionalPrincipal, service: Service
):
    user_id = principal.user.id_usuario if principal else None
    return await service.stripe_checkout_status(session_id, user_id=user_id)


@router.post("/checkout/{session_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)  # [CU-12] Cancelar sesión de checkout
async def cancel_stripe_checkout(
    session_id: str, principal: Authenticated, service: Service
) -> Response:
    await service.cancel_stripe_checkout(principal.user.id_usuario, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/payments/stripe/webhook", include_in_schema=False)  # [CU-12] Webhook Stripe (pago y facturación)
async def stripe_webhook(request: Request, service: Service) -> dict[str, bool]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Falta la firma de Stripe")
    try:
        event = service.construct_stripe_event(payload, signature)
    except PaymentGatewayError:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="La firma de Stripe no es válida") from exc
    await service.process_stripe_event(event)
    return {"received": True}


@router.get("/orders", response_model=list[OrderResponse])  # [CU-13] Listar pedidos online del cliente
async def list_customer_orders(principal: Authenticated, service: Service):
    return await service.list_orders(principal.user.id_usuario, operational=False)


@router.get("/orders/{order_id}", response_model=OrderResponse)  # [CU-13] Detalle de pedido online
async def get_customer_order(order_id: int, principal: Authenticated, service: Service):
    return await service.get_order(principal.user.id_usuario, order_id, operational=False)


@router.post("/orders/{order_id}/confirm-delivery", response_model=OrderResponse)  # [CU-13] Confirmar entrega de pedido
async def confirm_order_delivery(order_id: int, principal: Authenticated, service: Service):
    return await service.confirm_delivery(principal.user.id_usuario, order_id)


@router.get("/orders/{order_id}/invoice")  # [CU-12] Descargar factura PDF de pedido
async def get_order_invoice(order_id: int, principal: Authenticated, service: Service) -> Response:
    pdf_bytes = await service.get_order_invoice_pdf(principal.user.id_usuario, order_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="Factura_Pedido_{order_id}.pdf"',
        },
    )


@router.get("/sales/{sale_id}/invoice")  # [CU-12] Descargar factura PDF de venta
async def get_sale_invoice(sale_id: int, principal: Authenticated, service: Service) -> Response:
    pdf_bytes = await service.get_sale_invoice_pdf(principal.user.id_usuario, sale_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="Factura_Venta_{sale_id}.pdf"',
        },
    )


@router.get("/admin/orders", response_model=list[OrderResponse])  # [CU-13] Listar pedidos operativos/despacho
async def list_operational_orders(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Service,
    estado: str | None = None,
    sucursal: int | None = Query(default=None, gt=0),
):
    return await service.list_orders(
        principal.user.id_usuario,
        operational=True,
        state=estado,
        branch_id=sucursal,
        all_branches="ADMIN" in principal.roles,
    )


@router.patch("/admin/orders/{order_id}/status", response_model=OrderResponse)  # [CU-13] Actualizar estado logístico del pedido
async def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.crear"))],
    service: Service,
):
    return await service.update_order_status(
        principal.user.id_usuario,
        order_id,
        payload,
        all_branches="ADMIN" in principal.roles,
    )


@router.post(  # [CU-09] Cotizar flete de envío a domicilio
    "/shipping-quotes", response_model=ShippingQuoteResponse, status_code=status.HTTP_201_CREATED
)
async def quote_shipping(payload: ShippingQuoteCreate, principal: Authenticated, service: Service):
    return await service.quote_shipping(principal.user.id_usuario, payload)


@router.get("/returns", response_model=list[ReturnResponse])  # [CU-14] Listar solicitudes de devolución
async def list_customer_returns(principal: Authenticated, service: Service):
    return await service.list_returns(principal.user.id_usuario, operational=False)


@router.post("/returns", response_model=ReturnResponse, status_code=status.HTTP_201_CREATED)  # [CU-14] Solicitar devolución de producto
async def create_return(payload: ReturnCreate, principal: Authenticated, service: Service):
    return await service.create_return(principal.user.id_usuario, payload)


@router.get("/admin/returns", response_model=list[ReturnResponse])  # [CU-14] Listar devoluciones operativas
async def list_operational_returns(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Service,
):
    return await service.list_returns(
        principal.user.id_usuario,
        operational=True,
        all_branches="ADMIN" in principal.roles,
    )


@router.get(  # [CU-14] Inspeccionar venta para devolución
    "/admin/returns/inspect-sale/{sale_id}",
    response_model=SaleReturnInspectionResponse,
)
async def inspect_sale_for_return(
    sale_id: int,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Service,
):
    return await service.inspect_sale_for_return(
        principal.user.id_usuario,
        sale_id,
        all_branches="ADMIN" in principal.roles,
    )


@router.post(  # [CU-14] Registrar devolución en punto de venta
    "/admin/returns",
    response_model=ReturnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_return(
    payload: AdminReturnCreate,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.crear"))],
    service: Service,
):
    return await service.create_admin_return(
        principal.user.id_usuario,
        payload,
        all_branches="ADMIN" in principal.roles,
    )


@router.post("/admin/returns/{return_id}/quote")
async def quote_return(
    return_id: int,
    payload: ReturnSettlement,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.crear"))],
    service: Service,
):
    return await service.quote_return(
        principal.user.id_usuario, return_id, payload, all_branches="ADMIN" in principal.roles,
    )


@router.get("/returns/{return_id}/receipt")
async def get_return_receipt(return_id: int, principal: Authenticated, service: Service):
    pdf = await service.get_return_receipt(
        principal.user.id_usuario, return_id,
        operational="ventas.ver" in principal.permissions or "ADMIN" in principal.roles,
        all_branches="ADMIN" in principal.roles,
    )
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="devolucion-{return_id}.pdf"',
        "Cache-Control": "no-store",
    })


@router.patch("/admin/returns/{return_id}/status", response_model=ReturnResponse)
async def update_return_status(
    return_id: int,
    payload: ReturnStatusUpdate,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.crear"))],
    service: Service,
):
    return await service.update_return_status(
        principal.user.id_usuario,
        return_id,
        payload,
        all_branches="ADMIN" in principal.roles,
    )


@router.get("/notifications", response_model=list[NotificationResponse])  # [CU-20] Bandeja de notificaciones
async def list_notifications(principal: Authenticated, service: Service):
    return await service.list_notifications(principal.user.id_usuario)


@router.post("/notifications/devices", response_model=DeviceTokenResponse)  # [CU-20] Registrar token FCM
async def register_device_token(
    payload: DeviceTokenRegisterRequest,
    principal: Authenticated,
    service: Service,
):
    return await service.register_device_token(principal.user.id_usuario, payload)


@router.patch("/notifications/read-all")  # [CU-20] Marcar todas las notificaciones como leídas
async def mark_all_notifications_as_read(
    principal: Authenticated,
    service: Service,
):
    is_admin = any(
        r.upper() in ["ADMINISTRADOR", "PROPIETARIO", "ADMIN"]
        for r in (principal.roles or [])
    )
    await service.mark_all_notifications_as_read(principal.user.id_usuario, is_admin=is_admin)
    return {"mensaje": "Todas las notificaciones marcadas como leídas.", "ok": True}


@router.patch("/notifications/{notification_id}/read")  # [CU-20] Marcar notificación como leída
async def mark_notification_as_read(
    notification_id: int,
    principal: Authenticated,
    service: Service,
):
    is_admin = any(
        r.upper() in ["ADMINISTRADOR", "PROPIETARIO", "ADMIN"]
        for r in (principal.roles or [])
    )
    await service.mark_notification_as_read(
        principal.user.id_usuario, notification_id, is_admin=is_admin
    )
    return {"mensaje": "Notificación marcada como leída.", "ok": True}


@router.get("/admin/notifications", response_model=AdminNotificationPage)  # [CU-20] Auditoría de notificaciones enviadas
async def admin_list_notifications(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Service,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    estado: str | None = None,
    canal: str | None = None,
    tipo: str | None = None,
    search: str | None = None,
):
    return await service.admin_list_notifications(
        estado=estado,
        canal=canal,
        tipo=tipo,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.post(  # [CU-20] Enviar notificación manual (push/in-app)
    "/admin/notifications",
    response_model=AdminNotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_manual_notification(
    payload: ManualNotificationCreate,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Service,
):
    return await service.send_manual_notification(payload)


@router.post(  # [CU-20] Reintentar envío de notificación
    "/admin/notifications/{notification_id}/resend",
    response_model=AdminNotificationResponse,
)
async def resend_notification(
    notification_id: int,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Service,
):
    return await service.resend_notification(notification_id)


@router.get("/supplier-purchase-history", response_model=SupplierPurchaseHistoryPage)  # [CU-06] Histórico de compras a proveedores
async def supplier_purchase_history(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.ver"))],
    service: Service,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    proveedor: int | None = Query(default=None, gt=0),
    producto: int | None = Query(default=None, gt=0),
    sucursal: int | None = Query(default=None, gt=0),
    estado: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
):
    return await service.supplier_purchase_history(
        principal.user.id_usuario,
        all_branches="ADMIN" in principal.roles,
        page=page,
        page_size=page_size,
        supplier_id=proveedor,
        product_id=producto,
        branch_id=sucursal,
        state=estado,
        date_from=(datetime.combine(fecha_desde, time.min, tzinfo=UTC) if fecha_desde else None),
        date_to=(datetime.combine(fecha_hasta, time.max, tzinfo=UTC) if fecha_hasta else None),
    )


@router.get("/admin/campaigns", response_model=list[CampaignResponse])  # [CU-19] Listar campañas comerciales
async def list_campaigns(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("promociones.gestionar"))],
    service: Service,
    estado: str | None = None,
):
    return await service.list_campaigns(state=estado)


@router.post(  # [CU-19] Crear campaña comercial
    "/admin/campaigns",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    payload: CampaignCreate,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("promociones.gestionar"))],
    service: Service,
):
    return await service.create_campaign(payload)


@router.get("/admin/campaigns/{campaign_id}", response_model=CampaignResponse)  # [CU-19] Detalle de campaña
async def get_campaign(
    campaign_id: int,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("promociones.gestionar"))],
    service: Service,
):
    return await service.get_campaign(campaign_id)


@router.patch("/admin/campaigns/{campaign_id}", response_model=CampaignResponse)  # [CU-19] Actualizar campaña
async def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("promociones.gestionar"))],
    service: Service,
):
    return await service.update_campaign(campaign_id, payload)


@router.post(  # [CU-19 / CU-20] Lanzar campaña y despachar notificaciones push
    "/admin/campaigns/{campaign_id}/send",
    response_model=CampaignLaunchResponse,
)
async def launch_campaign(
    campaign_id: int,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("promociones.gestionar"))],
    service: Service,
):
    return await service.launch_campaign(campaign_id)


@router.get("/admin/promotions", response_model=list[PromotionResponse])  # [CU-19] Listar promociones de descuento
async def list_promotions_admin(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("promociones.gestionar"))],
    service: Service,
):
    return await service.list_promotions()


@router.post(  # [CU-19] Crear regla de promoción
    "/admin/promotions",
    response_model=PromotionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_promotion(
    payload: PromotionCreate,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("promociones.gestionar"))],
    service: Service,
):
    return await service.create_promotion(payload)


@router.get("/admin/promotions/{promotion_id}", response_model=PromotionResponse)  # [CU-19] Detalle de promoción
async def get_promotion_admin(
    promotion_id: int,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("promociones.gestionar"))],
    service: Service,
):
    return await service.get_promotion(promotion_id)


@router.patch("/admin/promotions/{promotion_id}", response_model=PromotionResponse)  # [CU-19] Modificar promoción
async def update_promotion_admin(
    promotion_id: int,
    payload: PromotionUpdate,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("promociones.gestionar"))],
    service: Service,
):
    return await service.update_promotion(promotion_id, payload)


@router.delete("/admin/promotions/{promotion_id}")  # [CU-19] Eliminar promoción
async def delete_promotion_admin(
    promotion_id: int,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("promociones.gestionar"))],
    service: Service,
):
    return await service.delete_promotion(promotion_id)


@router.get("/promotions/active", response_model=list[ActivePromotionItem])  # [CU-19] Promociones vigentes públicas
async def list_active_promotions_public(service: Service):
    return await service.list_active_promotions_public()


@router.get("/admin/dashboard/summary", response_model=AdminDashboardSummaryResponse)  # [CU-16] Métricas y KPIs de dashboard
async def get_admin_dashboard_summary(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Service,
    id_sucursal: int | None = Query(default=None),
):
    target_sucursal = id_sucursal
    if "ventas.sucursales_todas" not in principal.permissions and "ADMIN" not in principal.roles and principal.id_sucursal:
        target_sucursal = principal.id_sucursal
    return await service.get_admin_dashboard_summary(id_sucursal=target_sucursal)


