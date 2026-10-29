from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.modules.auth.dependencies import CurrentPrincipal, require_permission
from app.modules.auth.exceptions import PermissionDeniedError
from app.modules.reports.ai import AIReportInterpreter, AIReportInterpreterError
from app.modules.reports.dependencies import get_ai_report_interpreter, get_reports_service
from app.modules.reports.export import generate_excel, generate_pdf
from app.modules.reports.schemas import (
    AIReportRequest,
    AIReportResponse,
    BranchSalesReport,
    CategoryRevenueReport,
    CustomerReport,
    InventoryReport,
    ProductReport,
    SalesReport,
)
from app.modules.reports.service import ReportsService

router = APIRouter(prefix="/admin/reports", tags=["reports"])
Reports = Annotated[ReportsService, Depends(get_reports_service)]
AIInterpreter = Annotated[AIReportInterpreter | None, Depends(get_ai_report_interpreter)]
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


def _tenant(principal: CurrentPrincipal) -> int:
    if principal.id_tenant is None:
        raise PermissionDeniedError
    return principal.id_tenant


def _summary(report_type: str, data: dict) -> tuple[str, str]:
    if report_type == "VENTAS":
        return (
            "Rendimiento de ventas",
            f"Se registraron {data['total_ventas']} ventas por Bs {data['ingresos']}.",
        )
    if report_type == "PRODUCTOS":
        return "Productos destacados", f"Se encontraron {len(data['productos'])} productos."
    if report_type == "INVENTARIO":
        return (
            "Estado del inventario",
            f"Hay {data['unidades_disponibles']} unidades y "
            f"{data['items_criticos']} ítems críticos.",
        )
    if report_type == "CLIENTES":
        return "Clientes destacados", f"Se encontraron {len(data['clientes'])} clientes."
    if report_type == "INGRESOS_CATEGORIA":
        return (
            "Ingresos por categoría",
            f"Las categorías generaron Bs {data['ingresos']} en el período solicitado.",
        )
    return "Resumen ejecutivo", "Resumen comercial consolidado del período solicitado."


@router.post("/ai/query", response_model=AIReportResponse)
async def ai_report_query(
    payload: AIReportRequest,
    principal: SalesPrincipal,
    service: Reports,
    interpreter: AIInterpreter,
):
    if not principal.permite_reportes_ia:
        raise HTTPException(
            status_code=403,
            detail="Los reportes con IA están disponibles en el plan Profesional",
        )
    if interpreter is None:
        raise HTTPException(status_code=503, detail="El asistente de IA no está configurado")
    if "inventario.ver" not in principal.permissions and "ADMIN" not in principal.roles:
        raise PermissionDeniedError
    question = payload.pregunta.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Escribe una pregunta para el asistente")
    try:
        plan = await interpreter.interpret(question, reference_date=date.today())
    except AIReportInterpreterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if plan.necesita_aclaracion:
        return AIReportResponse(
            pregunta=question,
            interpretacion=plan,
            titulo="Necesito un dato más",
            resumen=plan.pregunta_aclaracion or "Aclara los filtros del reporte.",
            datos={},
        )

    end = plan.fecha_hasta or date.today()
    start = plan.fecha_desde or (end - timedelta(days=plan.dias - 1))
    tenant_id = _tenant(principal)
    branch_id = _branch(principal, payload.id_sucursal)
    if plan.sucursal:
        resolved_branch = await service.resolve_branch_id(tenant_id, plan.sucursal)
        if resolved_branch is None:
            plan.necesita_aclaracion = True
            plan.pregunta_aclaracion = (
                f"No encontré la sucursal ‘{plan.sucursal}’. "
                "Indica una sucursal existente o selecciónala en el filtro."
            )
            return AIReportResponse(
                pregunta=question,
                interpretacion=plan,
                titulo="No pude identificar la sucursal",
                resumen=plan.pregunta_aclaracion,
                datos={},
            )
        branch_id = _branch(principal, resolved_branch)
    if plan.tipo_reporte == "VENTAS":
        if plan.agrupacion == "SUCURSAL":
            data = (
                await service.sales_by_branch(tenant_id, start, end, branch_id)
            ).model_dump(mode="json")
        else:
            data = (
                await service.sales(tenant_id, start, end, branch_id)
            ).model_dump(mode="json")
    elif plan.tipo_reporte == "PRODUCTOS":
        data = (
            await service.products(
                tenant_id, start, end, branch_id, plan.limite, plan.categoria, plan.producto
            )
        ).model_dump(mode="json")
    elif plan.tipo_reporte == "INVENTARIO":
        data = (
            await service.inventory(
                tenant_id, branch_id, plan.solo_criticos, plan.categoria, plan.producto
            )
        ).model_dump(mode="json")
    elif plan.tipo_reporte == "CLIENTES":
        data = (
            await service.customers(tenant_id, start, end, branch_id, plan.limite)
        ).model_dump(mode="json")
    elif plan.tipo_reporte == "INGRESOS_CATEGORIA":
        data = (
            await service.revenue_by_category(
                tenant_id, start, end, branch_id, plan.categoria
            )
        ).model_dump(mode="json")
    elif plan.tipo_reporte == "RESUMEN":
        data = {
            "ventas": (
                await service.sales(tenant_id, start, end, branch_id)
            ).model_dump(mode="json"),
            "productos": (
                await service.products(tenant_id, start, end, branch_id, plan.limite)
            ).model_dump(mode="json"),
            "inventario": (
                await service.inventory(tenant_id, branch_id, plan.solo_criticos)
            ).model_dump(mode="json"),
            "clientes": (
                await service.customers(tenant_id, start, end, branch_id, plan.limite)
            ).model_dump(mode="json"),
        }
    else:
        raise HTTPException(status_code=422, detail="Tipo de reporte no soportado")
    title, summary = _summary(plan.tipo_reporte, data)
    return AIReportResponse(
        pregunta=question,
        interpretacion=plan,
        titulo=title,
        resumen=summary,
        datos=data,
    )


@router.get("/sales", response_model=SalesReport)
async def sales_report(
    principal: SalesPrincipal,
    service: Reports,
    desde: date | None = None,
    hasta: date | None = None,
    id_sucursal: int | None = Query(default=None, gt=0),
):
    start, end = _dates(desde, hasta)
    return await service.sales(
        _tenant(principal), start, end, _branch(principal, id_sucursal)
    )


@router.get("/sales-by-branch", response_model=BranchSalesReport)
async def sales_by_branch_report(
    principal: SalesPrincipal,
    service: Reports,
    desde: date | None = None,
    hasta: date | None = None,
    id_sucursal: int | None = Query(default=None, gt=0),
):
    start, end = _dates(desde, hasta)
    return await service.sales_by_branch(
        _tenant(principal), start, end, _branch(principal, id_sucursal)
    )


@router.get("/categories", response_model=CategoryRevenueReport)
async def category_revenue_report(
    principal: SalesPrincipal,
    service: Reports,
    desde: date | None = None,
    hasta: date | None = None,
    id_sucursal: int | None = Query(default=None, gt=0),
    categoria: str | None = Query(default=None, max_length=120),
):
    start, end = _dates(desde, hasta)
    return await service.revenue_by_category(
        _tenant(principal), start, end, _branch(principal, id_sucursal), categoria
    )


@router.get("/products", response_model=ProductReport)
async def products_report(
    principal: SalesPrincipal,
    service: Reports,
    desde: date | None = None,
    hasta: date | None = None,
    id_sucursal: int | None = Query(default=None, gt=0),
    limite: int = Query(default=20, ge=1, le=100),
    categoria: str | None = Query(default=None, max_length=120),
    producto: str | None = Query(default=None, max_length=160),
):
    start, end = _dates(desde, hasta)
    return await service.products(
        _tenant(principal),
        start,
        end,
        _branch(principal, id_sucursal),
        limite,
        categoria,
        producto,
    )


@router.get("/inventory", response_model=InventoryReport)
async def inventory_report(
    principal: InventoryPrincipal,
    service: Reports,
    id_sucursal: int | None = Query(default=None, gt=0),
    solo_criticos: bool = False,
    categoria: str | None = Query(default=None, max_length=120),
    producto: str | None = Query(default=None, max_length=160),
):
    return await service.inventory(
        _tenant(principal),
        _branch(principal, id_sucursal),
        solo_criticos,
        categoria,
        producto,
    )


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
    return await service.customers(
        _tenant(principal), start, end, _branch(principal, id_sucursal), limite
    )


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
    tenant_id = _tenant(principal)
    branch_id = _branch(principal, id_sucursal)
    sales = await service.sales(tenant_id, start, end, branch_id)
    products = await service.products(tenant_id, start, end, branch_id, 100)
    inventory = await service.inventory(tenant_id, branch_id, False)
    customers = await service.customers(tenant_id, start, end, branch_id, 100)
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
