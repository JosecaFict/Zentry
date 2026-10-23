from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from app.modules.auth.dependencies import (
    CurrentPrincipal,
    require_global_permission,
    require_permission,
)
from app.modules.platform.dependencies import get_platform_service
from app.modules.platform.schemas import (
    PlanResponse,
    PlatformOverview,
    SubscriptionPaymentCreate,
    SubscriptionPaymentResponse,
    TenantBrandUpdate,
    TenantContextResponse,
    TenantCreate,
    TenantDetail,
    TenantListItem,
    TenantStatusUpdate,
    TenantUpdate,
)
from app.modules.platform.service import PlatformService

router = APIRouter(prefix="/platform", tags=["platform"])
tenant_router = APIRouter(prefix="/tenant", tags=["tenant"])


@tenant_router.get("/context", response_model=TenantContextResponse)
async def tenant_context(
    request: Request,
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> TenantContextResponse:
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se indicó el subdominio de la empresa",
        )
    return await service.tenant_context(tenant_id)


@tenant_router.put("/brand", response_model=TenantContextResponse)
async def update_tenant_brand(
    payload: TenantBrandUpdate,
    principal: Annotated[
        CurrentPrincipal,
        Depends(require_permission("permisos.asignar")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> TenantContextResponse:
    if principal.id_tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta no pertenece a una empresa",
        )
    return await service.update_tenant_brand(principal.id_tenant, payload)


@router.get("/overview", response_model=PlatformOverview)
async def overview(
    _: Annotated[
        CurrentPrincipal,
        Depends(require_global_permission("platform.overview.ver")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> PlatformOverview:
    return await service.overview()


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(
    _: Annotated[
        CurrentPrincipal,
        Depends(require_global_permission("platform.plans.ver")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> list[PlanResponse]:
    return await service.list_plans()


@router.get("/tenants", response_model=list[TenantListItem])
async def list_tenants(
    _: Annotated[
        CurrentPrincipal,
        Depends(require_global_permission("platform.tenants.ver")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> list[TenantListItem]:
    return await service.list_tenants()


@router.post("/tenants", response_model=TenantDetail, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    _: Annotated[
        CurrentPrincipal,
        Depends(require_global_permission("platform.tenants.gestionar")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> TenantDetail:
    return await service.create_tenant(payload)


@router.get("/tenants/{tenant_id}", response_model=TenantDetail)
async def tenant_detail(
    tenant_id: Annotated[int, Path(gt=0)],
    _: Annotated[
        CurrentPrincipal,
        Depends(require_global_permission("platform.tenants.ver")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> TenantDetail:
    return await service.tenant_detail(tenant_id)


@router.put("/tenants/{tenant_id}", response_model=TenantDetail)
async def update_tenant(
    tenant_id: Annotated[int, Path(gt=0)],
    payload: TenantUpdate,
    _: Annotated[
        CurrentPrincipal,
        Depends(require_global_permission("platform.tenants.gestionar")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> TenantDetail:
    return await service.update_tenant(tenant_id, payload)


@router.patch("/tenants/{tenant_id}/status", response_model=TenantDetail)
async def update_tenant_status(
    tenant_id: Annotated[int, Path(gt=0)],
    payload: TenantStatusUpdate,
    _: Annotated[
        CurrentPrincipal,
        Depends(require_global_permission("platform.tenants.gestionar")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> TenantDetail:
    return await service.update_tenant_status(tenant_id, payload)


@router.get(
    "/tenants/{tenant_id}/payments",
    response_model=list[SubscriptionPaymentResponse],
)
async def tenant_payments(
    tenant_id: Annotated[int, Path(gt=0)],
    _: Annotated[CurrentPrincipal, Depends(require_global_permission("platform.tenants.ver"))],
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> list[SubscriptionPaymentResponse]:
    return await service.list_payments(tenant_id)


@router.post("/tenants/{tenant_id}/payments", response_model=TenantDetail)
async def register_tenant_payment(
    tenant_id: Annotated[int, Path(gt=0)],
    payload: SubscriptionPaymentCreate,
    _: Annotated[
        CurrentPrincipal,
        Depends(require_global_permission("platform.tenants.gestionar")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
) -> TenantDetail:
    return await service.register_payment(tenant_id, payload)
