from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.modules.auth.dependencies import (
    CurrentPrincipal,
    build_request_audit_context,
    require_permission,
)
from app.modules.customers.dependencies import get_customer_admin_service
from app.modules.customers.schemas import (
    CustomerAdminDetail,
    CustomerAdminSummary,
    CustomerAdminUpdateRequest,
    CustomerQuickCreateRequest,
)
from app.modules.customers.service import CustomerAdminService

router = APIRouter(tags=["customer administration"])


@router.get("/customers", response_model=list[CustomerAdminSummary])  # [CU-01 / CU-11] Listar clientes en panel/POS
async def list_customers(
    _: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Annotated[CustomerAdminService, Depends(get_customer_admin_service)],
    q: str | None = Query(default=None),
    estado: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[CustomerAdminSummary]:
    return await service.list_customers(q=q, estado=estado, limit=limit, offset=offset)


@router.get("/customers/{customer_id}", response_model=CustomerAdminDetail)  # [CU-01] Consultar detalle de cliente
async def get_customer(
    customer_id: int,
    _: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Annotated[CustomerAdminService, Depends(get_customer_admin_service)],
) -> CustomerAdminDetail:
    return await service.get_customer(customer_id)


@router.patch("/customers/{customer_id}", response_model=CustomerAdminDetail)  # [CU-01] Actualizar cliente desde administración
async def update_customer(
    customer_id: int,
    payload: CustomerAdminUpdateRequest,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Annotated[CustomerAdminService, Depends(get_customer_admin_service)],
) -> CustomerAdminDetail:
    audit_context = build_request_audit_context(
        request,
        user_id=principal.user.id_usuario,
        session_id=principal.session_id,
        tenant_id=principal.id_tenant,
    )
    return await service.update_customer(
        customer_id=customer_id,
        payload=payload,
        actor=principal,
        audit_context=audit_context,
    )


@router.post(  # [CU-11] Alta rápida de cliente desde caja POS
    "/customers/quick",
    response_model=CustomerAdminSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_quick_customer(
    payload: CustomerQuickCreateRequest,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))],
    service: Annotated[CustomerAdminService, Depends(get_customer_admin_service)],
) -> CustomerAdminSummary:
    audit_context = build_request_audit_context(
        request,
        user_id=principal.user.id_usuario,
        session_id=principal.session_id,
        tenant_id=principal.id_tenant,
    )
    return await service.create_quick_customer(
        payload=payload,
        actor=principal,
        audit_context=audit_context,
    )
