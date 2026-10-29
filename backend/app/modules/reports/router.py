import logging
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from app.core.config import get_settings
from app.modules.auth.dependencies import CurrentPrincipal, require_permission
from app.modules.auth.exceptions import PermissionDeniedError
from app.modules.reports.ai import AIReportInterpreter, AIReportInterpreterError
from app.modules.reports.dependencies import (
    get_ai_report_interpreter,
    get_reports_service,
    get_speech_transcriber,
)
from app.modules.reports.export import (
    generate_ai_excel,
    generate_ai_pdf,
    generate_excel,
    generate_pdf,
)
from app.modules.reports.schemas import (
    AIReportExportRequest,
    AIReportPlan,
    AIReportRequest,
    AIReportResponse,
    BranchSalesReport,
    CategoryRevenueReport,
    CustomerReport,
    InventoryReport,
    ProductReport,
    SalesReport,
    VoiceTranscriptionResponse,
)
from app.modules.reports.service import ReportsService
from app.modules.reports.speech import GroqSpeechTranscriber, SpeechTranscriptionError

router = APIRouter(prefix="/admin/reports", tags=["reports"])
logger = logging.getLogger("zentry.reports")
Reports = Annotated[ReportsService, Depends(get_reports_service)]
AIInterpreter = Annotated[AIReportInterpreter | None, Depends(get_ai_report_interpreter)]
SpeechTranscriber = Annotated[GroqSpeechTranscriber | None, Depends(get_speech_transcriber)]
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


async def _audit(
    service: ReportsService,
    principal: CurrentPrincipal,
    *,
    action: str,
    entity: str,
    record_id: str | None,
    metadata: dict,
) -> None:
    await service.audit_access(
        tenant_id=_tenant(principal),
        user_id=principal.user.id_usuario,
        session_id=principal.session_id,
        action=action,
        entity=entity,
        record_id=record_id,
        metadata=metadata,
    )


def _money(value: object) -> str:
    formatted = f"{float(value):,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _summary(report_type: str, data: dict) -> tuple[str, str]:
    if report_type == "VENTAS":
        return (
            "Rendimiento de ventas",
            f"Se registraron {data['total_ventas']} ventas por Bs {_money(data['ingresos'])}.",
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
            f"Las categorías generaron Bs {_money(data['ingresos'])} en el período solicitado.",
        )
    return "Resumen ejecutivo", "Resumen comercial consolidado del período solicitado."


async def _execute_ai_plan(
    plan: AIReportPlan,
    principal: CurrentPrincipal,
    service: ReportsService,
    requested_branch: int | None,
) -> dict:
    today = date.today()
    end = min(plan.fecha_hasta or today, today)
    start = plan.fecha_desde or (end - timedelta(days=plan.dias - 1))
    plan.fecha_hasta = end if plan.fecha_hasta else None
    if start > end:
        raise HTTPException(status_code=422, detail="El período solicitado todavía no ha comenzado")
    tenant_id = _tenant(principal)
    branch_id = _branch(principal, requested_branch)
    if plan.sucursal:
        resolved_branch = await service.resolve_branch_id(tenant_id, plan.sucursal)
        if resolved_branch is None:
            raise HTTPException(
                status_code=422,
                detail=f"No encontré la sucursal ‘{plan.sucursal}’ en esta empresa",
            )
        branch_id = _branch(principal, resolved_branch)

    if plan.tipo_reporte == "VENTAS":
        report = (
            await service.sales_by_branch(tenant_id, start, end, branch_id)
            if plan.agrupacion == "SUCURSAL"
            else await service.sales(tenant_id, start, end, branch_id)
        )
        return report.model_dump(mode="json")
    if plan.tipo_reporte == "PRODUCTOS":
        return (
            await service.products(
                tenant_id, start, end, branch_id, plan.limite, plan.categoria, plan.producto
            )
        ).model_dump(mode="json")
    if plan.tipo_reporte == "INVENTARIO":
        return (
            await service.inventory(
                tenant_id, branch_id, plan.solo_criticos, plan.categoria, plan.producto
            )
        ).model_dump(mode="json")
    if plan.tipo_reporte == "CLIENTES":
        return (
            await service.customers(tenant_id, start, end, branch_id, plan.limite)
        ).model_dump(mode="json")
    if plan.tipo_reporte == "INGRESOS_CATEGORIA":
        return (
            await service.revenue_by_category(
                tenant_id, start, end, branch_id, plan.categoria
            )
        ).model_dump(mode="json")
    if plan.tipo_reporte == "RESUMEN":
        return {
            "ventas": (await service.sales(tenant_id, start, end, branch_id)).model_dump(
                mode="json"
            ),
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
    raise HTTPException(status_code=422, detail="Tipo de reporte no soportado")


@router.post("/ai/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_ai_question(
    principal: SalesPrincipal,
    service: Reports,
    transcriber: SpeechTranscriber,
    audio: Annotated[UploadFile, File()],
):
    if not principal.permite_reportes_ia:
        raise HTTPException(
            status_code=403,
            detail="La consulta por voz está disponible en el plan Profesional",
        )
    if "inventario.ver" not in principal.permissions and "ADMIN" not in principal.roles:
        raise PermissionDeniedError
    if transcriber is None:
        raise HTTPException(status_code=503, detail="La consulta por voz no está configurada")

    allowed_types = {
        "audio/flac",
        "audio/m4a",
        "audio/mp4",
        "audio/mpeg",
        "audio/mp3",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
        "audio/x-m4a",
        "audio/x-wav",
    }
    content_type = (audio.content_type or "").lower().split(";", 1)[0]
    if content_type not in allowed_types:
        raise HTTPException(status_code=415, detail="El formato de audio no es compatible")

    max_bytes = get_settings().voice_max_file_size_mb * 1024 * 1024
    content = await audio.read(max_bytes + 1)
    if not content:
        raise HTTPException(status_code=422, detail="La grabación está vacía")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="La grabación supera el tamaño permitido")

    try:
        text = await transcriber.transcribe(
            audio.filename or "consulta.webm",
            content_type,
            content,
        )
    except SpeechTranscriptionError as exc:
        logger.warning("No se pudo transcribir una consulta (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="No pudimos transcribir la grabación en este momento",
        ) from exc

    await _audit(
        service,
        principal,
        action="TRANSCRIBIR",
        entity="REPORTE_IA",
        record_id="VOZ",
        metadata={
            "tipo_audio": content_type,
            "bytes": len(content),
            "modelo": transcriber.model,
        },
    )
    return VoiceTranscriptionResponse(texto=text)


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
        logger.warning(
            "No se pudo interpretar una consulta generativa (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="El asistente no pudo procesar la consulta en este momento",
        ) from exc

    if plan.necesita_aclaracion:
        return AIReportResponse(
            pregunta=question,
            interpretacion=plan,
            titulo="Necesito un dato más",
            resumen=plan.pregunta_aclaracion or "Aclara los filtros del reporte.",
            datos={},
        )

    try:
        data = await _execute_ai_plan(plan, principal, service, payload.id_sucursal)
    except HTTPException as exc:
        if plan.sucursal and exc.status_code == 422:
            plan.necesita_aclaracion = True
            plan.pregunta_aclaracion = f"{exc.detail}. Selecciona una sucursal disponible."
            return AIReportResponse(
                pregunta=question,
                interpretacion=plan,
                titulo="No pude identificar la sucursal",
                resumen=plan.pregunta_aclaracion,
                datos={},
            )
        raise
    title, summary = _summary(plan.tipo_reporte, data)
    await _audit(
        service,
        principal,
        action="CONSULTAR",
        entity="REPORTE_IA",
        record_id=plan.tipo_reporte,
        metadata={
            "id_sucursal": _branch(principal, payload.id_sucursal),
            "fecha_desde": plan.fecha_desde,
            "fecha_hasta": plan.fecha_hasta,
            "agrupacion": plan.agrupacion,
            "visualizacion": plan.visualizacion,
        },
    )
    return AIReportResponse(
        pregunta=question,
        interpretacion=plan,
        titulo=title,
        resumen=summary,
        datos=data,
    )


@router.post("/ai/export/{file_format}")
async def export_ai_report(
    file_format: Literal["xlsx", "pdf"],
    payload: AIReportExportRequest,
    principal: SalesPrincipal,
    service: Reports,
):
    if not principal.permite_reportes_ia:
        raise HTTPException(
            status_code=403,
            detail="Los reportes con IA están disponibles en el plan Profesional",
        )
    if "inventario.ver" not in principal.permissions and "ADMIN" not in principal.roles:
        raise PermissionDeniedError
    plan = payload.interpretacion.model_copy(deep=True)
    if plan.necesita_aclaracion:
        raise HTTPException(status_code=422, detail="Completa la consulta antes de exportarla")
    data = await _execute_ai_plan(plan, principal, service, payload.id_sucursal)
    title, _ = _summary(plan.tipo_reporte, data)
    tenant_name = principal.tenant_slug or "Zentry"
    filename = f"reporte-generado-{plan.tipo_reporte.lower().replace('_', '-')}.{file_format}"
    if file_format == "xlsx":
        content = generate_ai_excel(title, tenant_name, plan, data)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = generate_ai_pdf(title, tenant_name, plan, data)
        media_type = "application/pdf"
    await _audit(
        service,
        principal,
        action="EXPORTAR",
        entity="REPORTE_IA",
        record_id=plan.tipo_reporte,
        metadata={
            "formato": file_format,
            "id_sucursal": _branch(principal, payload.id_sucursal),
            "fecha_desde": plan.fecha_desde,
            "fecha_hasta": plan.fecha_hasta,
        },
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    await _audit(
        service,
        principal,
        action="EXPORTAR",
        entity="REPORTE_COMERCIAL",
        record_id=file_format.upper(),
        metadata={
            "formato": file_format,
            "id_sucursal": branch_id,
            "fecha_desde": start,
            "fecha_hasta": end,
        },
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
