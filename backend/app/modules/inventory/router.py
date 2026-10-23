from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.modules.auth.dependencies import (
    CurrentPrincipal,
    build_request_audit_context,
    require_permission,
)
from app.modules.auth.exceptions import PermissionDeniedError
from app.modules.inventory.dependencies import get_inventory_service
from app.modules.inventory.schemas import (
    AdjustmentCreate,
    InventoryResponse,
    LotResponse,
    MinimumStockUpdate,
    MovementResponse,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
    ReceiptCreate,
    ReceiptResponse,
    SupplierCreate,
    SupplierProductRequest,
    SupplierProductResponse,
    SupplierResponse,
    SupplierUpdate,
    TransferCreate,
    TransferResponse,
    TransferStatusUpdate,
)
from app.modules.inventory.service import InventoryService

router = APIRouter(tags=["suppliers, purchasing and inventory"])


def audit_for(request: Request, principal: CurrentPrincipal):
    return build_request_audit_context(
        request,
        user_id=principal.user.id_usuario,
        session_id=principal.session_id,
        tenant_id=principal.id_tenant,
    )


def assigned_branch(principal: CurrentPrincipal, requested: int | None = None) -> int | None:
    if "ADMIN" in principal.roles:
        return requested
    if principal.id_sucursal is None:
        raise PermissionDeniedError
    if requested is not None and requested != principal.id_sucursal:
        raise PermissionDeniedError
    return principal.id_sucursal


@router.get("/suppliers", response_model=list[SupplierResponse])  # [CU-06] Listar proveedores
async def list_suppliers(
    _: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.list_suppliers()


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)  # [CU-06] Detalle de proveedor
async def get_supplier(
    supplier_id: int,
    _: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.get_supplier(supplier_id)


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)  # [CU-06] Registrar proveedor
async def create_supplier(
    payload: SupplierCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.gestionar"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.create_supplier(payload, audit_for(request, principal))


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)  # [CU-06] Actualizar datos de proveedor
async def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.gestionar"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.update_supplier(supplier_id, payload, audit_for(request, principal))


@router.get("/suppliers/{supplier_id}/products", response_model=list[SupplierProductResponse])  # [CU-06] Listar productos de proveedor
async def list_supplier_products(
    supplier_id: int,
    _: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.list_supplier_products(supplier_id)


@router.post(  # [CU-06] Asociar prenda al proveedor
    "/suppliers/{supplier_id}/products/{product_id}",
    response_model=SupplierProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_supplier_product(
    supplier_id: int,
    product_id: int,
    payload: SupplierProductRequest,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.gestionar"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.add_supplier_product(
        supplier_id, product_id, payload, audit_for(request, principal)
    )


@router.delete(  # [CU-06] Desasociar prenda del proveedor
    "/suppliers/{supplier_id}/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_supplier_product(
    supplier_id: int,
    product_id: int,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.gestionar"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    await service.remove_supplier_product(supplier_id, product_id, audit_for(request, principal))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/purchase-orders", response_model=list[PurchaseOrderResponse])  # [CU-06] Listar órdenes de compra
async def list_purchase_orders(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.list_purchase_orders(assigned_branch(principal))


@router.get("/purchase-orders/{order_id}", response_model=PurchaseOrderResponse)  # [CU-06] Detalle de orden de compra
async def get_purchase_order(
    order_id: int,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.get_purchase_order(order_id, assigned_branch(principal))


@router.post(  # [CU-06] Emitir orden de compra
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.gestionar"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.create_purchase_order(
        payload,
        audit_for(request, principal),
        assigned_branch(principal, payload.id_sucursal),
    )


@router.patch("/purchase-orders/{order_id}", response_model=PurchaseOrderResponse)  # [CU-06] Actualizar orden de compra
async def update_purchase_order(
    order_id: int,
    payload: PurchaseOrderUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("proveedores.gestionar"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.update_purchase_order(
        order_id,
        payload,
        audit_for(request, principal),
        assigned_branch(principal),
    )


@router.get("/receipts", response_model=list[ReceiptResponse])  # [CU-06] Listar notas de recepción
async def list_receipts(
    principal: Annotated[CurrentPrincipal, Depends(require_permission("recepcion.registrar"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.list_receipts(assigned_branch(principal))


@router.get("/receipts/{receipt_id}", response_model=ReceiptResponse)  # [CU-06] Detalle de recepción
async def get_receipt(
    receipt_id: int,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("recepcion.registrar"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.get_receipt(receipt_id, assigned_branch(principal))


@router.post("/receipts", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)  # [CU-06] Recepción de mercadería (lotes y kardex)
async def create_receipt(
    payload: ReceiptCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("recepcion.registrar"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.create_receipt(
        payload,
        audit_for(request, principal),
        assigned_branch(principal),
    )


@router.get("/inventory/lots", response_model=list[LotResponse])  # [CU-06] Consultar lotes recibidos
async def list_lots(
    _: Annotated[CurrentPrincipal, Depends(require_permission("inventario.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    sucursal: int | None = Query(default=None, gt=0),
    variante: int | None = Query(default=None, gt=0),
    producto: int | None = Query(default=None, gt=0),
    proveedor: int | None = Query(default=None, gt=0),
    activo: bool | None = None,
    con_stock: bool | None = None,
):
    return await service.list_lots(
        branch_id=sucursal,
        variant_id=variante,
        product_id=producto,
        supplier_id=proveedor,
        active=activo,
        with_stock=con_stock,
    )


@router.get("/inventory", response_model=list[InventoryResponse])  # [CU-15] Consultar existencias de stock
async def list_inventory(
    _: Annotated[CurrentPrincipal, Depends(require_permission("inventario.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    sucursal: int | None = Query(default=None, gt=0),
    producto: int | None = Query(default=None, gt=0),
    variante: int | None = Query(default=None, gt=0),
    talla: int | None = Query(default=None, gt=0),
    color: int | None = Query(default=None, gt=0),
    categoria: int | None = Query(default=None, gt=0),
    stock_bajo: bool | None = None,
    agotado: bool | None = None,
):
    return await service.list_inventory(
        branch_id=sucursal,
        product_id=producto,
        variant_id=variante,
        size_id=talla,
        color_id=color,
        category_id=categoria,
        low_stock=stock_bajo,
        out_of_stock=agotado,
    )


@router.patch("/inventory/{inventory_id}/minimum-stock", response_model=InventoryResponse)  # [CU-15] Configurar stock mínimo
async def update_minimum_stock(
    inventory_id: int,
    payload: MinimumStockUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("inventario.movimiento"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.update_minimum_stock(inventory_id, payload, audit_for(request, principal))


@router.get("/inventory/movements", response_model=list[MovementResponse])  # [CU-15] Kardex de movimientos
async def list_movements(
    _: Annotated[CurrentPrincipal, Depends(require_permission("inventario.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    inventario: int | None = Query(default=None, gt=0),
    sucursal: int | None = Query(default=None, gt=0),
    variante: int | None = Query(default=None, gt=0),
    tipo_movimiento: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
):
    return await service.list_movements(
        inventory_id=inventario,
        branch_id=sucursal,
        variant_id=variante,
        movement_type=tipo_movimiento,
        date_from=fecha_desde,
        date_to=fecha_hasta,
    )


@router.get("/inventory/movements/{movement_id}", response_model=MovementResponse)  # [CU-15] Detalle de movimiento
async def get_movement(
    movement_id: int,
    _: Annotated[CurrentPrincipal, Depends(require_permission("inventario.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.get_movement(movement_id)


@router.post("/inventory/{inventory_id}/adjustments", response_model=MovementResponse)  # [CU-15] Ajuste manual de inventario
async def adjust_inventory(
    inventory_id: int,
    payload: AdjustmentCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("inventario.movimiento"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.adjust_inventory(
        inventory_id,
        payload,
        principal.user.id_usuario,
        audit_for(request, principal),
    )


@router.get("/inventory/transfers", response_model=list[TransferResponse])  # [CU-07] Listar transferencias intersucursal
async def list_transfers(
    _: Annotated[CurrentPrincipal, Depends(require_permission("inventario.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.list_transfers()


@router.get("/inventory/transfers/{transfer_id}", response_model=TransferResponse)  # [CU-07] Detalle de transferencia
async def get_transfer(
    transfer_id: int,
    _: Annotated[CurrentPrincipal, Depends(require_permission("inventario.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.get_transfer(transfer_id)


@router.post(  # [CU-07] Crear transferencia entre sucursales
    "/inventory/transfers",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transfer(
    payload: TransferCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("inventario.movimiento"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.create_transfer(payload, audit_for(request, principal))


@router.patch("/inventory/transfers/{transfer_id}/status", response_model=TransferResponse)  # [CU-07] Cambiar estado transferencia (despachar/recibir)
async def update_transfer_status(
    transfer_id: int,
    payload: TransferStatusUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("inventario.movimiento"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.update_transfer_status(transfer_id, payload, audit_for(request, principal))


@router.get("/inventory/{inventory_id}", response_model=InventoryResponse)  # [CU-15] Detalle de stock de variante
async def get_inventory(
    inventory_id: int,
    _: Annotated[CurrentPrincipal, Depends(require_permission("inventario.ver"))],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    return await service.get_inventory(inventory_id)
