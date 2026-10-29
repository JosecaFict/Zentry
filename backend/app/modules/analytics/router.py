from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.analytics.dependencies import get_analytics_service
from app.modules.analytics.schemas import AnalyticsDashboard
from app.modules.analytics.service import AnalyticsService
from app.modules.auth.dependencies import CurrentPrincipal, require_permission
from app.modules.auth.exceptions import PermissionDeniedError

router = APIRouter(prefix="/admin/analytics", tags=["analytics"])
Principal = Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))]
Service = Annotated[AnalyticsService, Depends(get_analytics_service)]


@router.get("/dashboard", response_model=AnalyticsDashboard)
async def analytics_dashboard(
    principal: Principal,
    service: Service,
    id_sucursal: int | None = Query(default=None, gt=0),
):
    if not principal.permite_reportes_ia:
        raise HTTPException(
            status_code=403,
            detail="La analítica inteligente está disponible en el plan Profesional",
        )
    if principal.id_tenant is None:
        raise PermissionDeniedError
    if "inventario.ver" not in principal.permissions and "ADMIN" not in principal.roles:
        raise PermissionDeniedError
    can_view_all = "ventas.sucursales_todas" in principal.permissions or "ADMIN" in principal.roles
    branch_id = id_sucursal if can_view_all else principal.id_sucursal
    branch_name = None if can_view_all and branch_id is None else principal.sucursal
    return await service.dashboard(
        tenant_id=principal.id_tenant,
        branch_id=branch_id,
        branch_name=branch_name,
    )
