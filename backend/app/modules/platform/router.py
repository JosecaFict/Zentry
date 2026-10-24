from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
    status,
)

from app.integrations.cloudinary import CloudinaryError, CloudinaryStorage
from app.modules.auth.dependencies import (
    CurrentPrincipal,
    require_global_permission,
    require_permission,
)
from app.modules.platform.dependencies import get_platform_cloudinary_storage, get_platform_service
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
    TenantPublicResponse,
    TenantStatusUpdate,
    TenantUpdate,
)
from app.modules.platform.service import PlatformService

router = APIRouter(prefix="/platform", tags=["platform"])
tenant_router = APIRouter(prefix="/tenant", tags=["tenant"])
public_router = APIRouter(prefix="/public", tags=["public"])

MAX_TENANT_LOGO_BYTES = 2 * 1024 * 1024
ALLOWED_TENANT_LOGO_TYPES = {"image/jpeg", "image/png", "image/webp"}


@public_router.get("/tenants", response_model=list[TenantPublicResponse])
async def search_public_tenants(
    service: Annotated[PlatformService, Depends(get_platform_service)],
    query: Annotated[str, Query(max_length=100)] = "",
) -> list[TenantPublicResponse]:
    return await service.search_public_tenants(query.strip())


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


@tenant_router.post("/brand/logo", response_model=TenantContextResponse)
async def upload_tenant_logo(
    principal: Annotated[
        CurrentPrincipal,
        Depends(require_permission("permisos.asignar")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
    storage: Annotated[CloudinaryStorage, Depends(get_platform_cloudinary_storage)],
    file: Annotated[UploadFile, File()],
) -> TenantContextResponse:
    if principal.id_tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta no pertenece a una empresa",
        )
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_TENANT_LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Usa un logotipo JPG, PNG o WebP",
        )
    content = await file.read(MAX_TENANT_LOGO_BYTES + 1)
    await file.close()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El archivo del logotipo está vacío",
        )
    if len(content) > MAX_TENANT_LOGO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El logotipo no debe superar 2 MB",
        )

    current = await service.tenant_context(principal.id_tenant)
    try:
        uploaded = await storage.upload_tenant_logo(
            content=content,
            filename=file.filename or "logo",
            content_type=content_type,
        )
    except CloudinaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        updated = await service.update_tenant_logo(principal.id_tenant, uploaded.secure_url)
    except Exception:
        await storage.destroy(uploaded.public_id)
        raise

    previous_public_id = storage.public_id_from_url(current.logo_url)
    if previous_public_id and previous_public_id != uploaded.public_id:
        await storage.destroy(previous_public_id)
    return updated


@tenant_router.delete("/brand/logo", response_model=TenantContextResponse)
async def delete_tenant_logo(
    principal: Annotated[
        CurrentPrincipal,
        Depends(require_permission("permisos.asignar")),
    ],
    service: Annotated[PlatformService, Depends(get_platform_service)],
    storage: Annotated[CloudinaryStorage, Depends(get_platform_cloudinary_storage)],
) -> TenantContextResponse:
    if principal.id_tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta no pertenece a una empresa",
        )
    current = await service.tenant_context(principal.id_tenant)
    updated = await service.update_tenant_logo(principal.id_tenant, None)
    previous_public_id = storage.public_id_from_url(current.logo_url)
    if previous_public_id:
        await storage.destroy(previous_public_id)
    return updated


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
