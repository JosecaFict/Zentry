from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.modules.auth.dependencies import CurrentPrincipal, require_permission
from app.modules.auth.exceptions import PermissionDeniedError
from app.modules.reports.dependencies import get_reports_service
from app.modules.reports.export import generate_excel, generate_pdf
from app.modules.reports.schemas import CustomerReport, InventoryReport, ProductReport, SalesReport
from app.modules.reports.service import ReportsService

router = APIRouter(prefix="/admin/reports", tags=["reports"])
Reports = Annotated[ReportsService, Depends(get_reports_service)]
SalesPrincipal = Annotated[CurrentPrincipal, Depends(require_permission("ventas.ver"))]
InventoryPrincipal = Annotated[CurrentPrincipal, Depends(require_permission("inventario.ver"))]


def _dates(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=89))
    if start > end:
        raise HTTPException(status_code=422, detail="La fecha desde no puede ser posterior a hasta")
    if (end - start).days > 730:
        raise HTTPException(status_code=422, detail="El rango máximo permitido es de 731 días")
    return start, end


def _branch(principal: CurrentPrincipal, requested: int | None) -> int | None:
    if "ventas.sucursales_todas" in principal.permissions or "ADMIN" in principal.roles:
        return requested
    return principal.id_sucursal


@router.get("/sales", response_model=SalesReport)
async def sales_report(
    principal: SalesPrincipal,
    service: Reports,
    desde: date | None = None,
    hasta: date | None = None,
    id_sucursal: int | None = Query(default=None, gt=0),
):
    start, end = _dates(desde, hasta)
    return await service.sales(start, end, _branch(principal, id_sucursal))


@router.get("/products", response_model=ProductReport)
async def products_report(
    principal: SalesPrincipal,
    service: Reports,
    desde: date | None = None,
    hasta: date | None = None,
    id_sucursal: int | None = Query(default=None, gt=0),
    limite: int = Query(default=20, ge=1, le=100),
):
    start, end = _dates(desde, hasta)
    return await service.products(start, end, _branch(principal, id_sucursal), limite)


@router.get("/inventory", response_model=InventoryReport)
async def inventory_report(
    principal: InventoryPrincipal,
    service: Reports,
    id_sucursal: int | None = Query(default=None, gt=0),
    solo_criticos: bool = False,
):
    return await service.inventory(_branch(principal, id_sucursal), solo_criticos)


@router.get("/customers", response_model=CustomerReport)
async def customers_report(
    principal: SalesPrincipal,
    service: Reports,
    desde: date | None = None,
    hasta: date | None = None,
    id_sucursal: int | None = Query(default=None, gt=0),
    limite: int = Query(default=20, ge=1, le=100),
):
    start, end = _dates(desde, hasta)
    return await service.customers(start, end, _branch(principal, id_sucursal), limite)


@router.get("/export/{file_format}")
async def export_report(
    file_format: Literal["xlsx", "pdf"],
    principal: SalesPrincipal,
    service: Reports,
    desde: date | None = None,
    hasta: date | None = None,
    id_sucursal: int | None = Query(default=None, gt=0),
):
    if "inventario.ver" not in principal.permissions and "ADMIN" not in principal.roles:
        raise PermissionDeniedError
    start, end = _dates(desde, hasta)
    branch_id = _branch(principal, id_sucursal)
    sales = await service.sales(start, end, branch_id)
    products = await service.products(start, end, branch_id, 100)
    inventory = await service.inventory(branch_id, False)
    customers = await service.customers(start, end, branch_id, 100)
    filename = f"reporte-comercial-{start:%Y%m%d}-{end:%Y%m%d}.{file_format}"
    if file_format == "xlsx":
        content = generate_excel(sales, products, inventory, customers)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = generate_pdf(
            sales, products, inventory, customers, principal.tenant_slug or "Zentry"
        )
        media_type = "application/pdf"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
