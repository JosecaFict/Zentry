from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zipfile import ZipFile

import pytest
from PIL import Image

from app.modules.platform.models import Tenant
from app.modules.reports.branding import load_report_brand
from app.modules.reports.export import (
    generate_ai_excel,
    generate_ai_pdf,
    generate_excel,
    generate_pdf,
)
from app.modules.reports.router import _dates, _summary
from app.modules.reports.schemas import AIReportPlan, CustomerReport, ProductReport
from app.modules.reports.service import ReportsService


class _EmptyMappings:
    def all(self) -> list[dict]:
        return []


class _EmptyResult:
    def mappings(self) -> _EmptyMappings:
        return _EmptyMappings()


class _CapturingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.commits = 0

    async def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))
        return _EmptyResult()

    async def commit(self) -> None:
        self.commits += 1


def test_sales_report_calculates_totals_and_average() -> None:
    rows = [
        {
            "fecha": date(2026, 10, 20),
            "ventas": 2,
            "unidades": 3,
            "ingresos": Decimal("450.00"),
        },
        {
            "fecha": date(2026, 10, 21),
            "ventas": 1,
            "unidades": 2,
            "ingresos": Decimal("210.00"),
        },
    ]

    report = ReportsService.summarize_sales(date(2026, 10, 1), date(2026, 10, 31), rows)

    assert report.total_ventas == 3
    assert report.total_unidades == 5
    assert report.ingresos == Decimal("660.00")
    assert report.ticket_promedio == Decimal("220.00")
    assert len(report.serie) == 2


def test_inventory_report_summarizes_valuation_and_critical_items() -> None:
    rows = [
        {
            "id_variante": 10,
            "producto": "Polo clásico mujer",
            "categoria": "Polos",
            "talla": "XS",
            "color": "Azul",
            "sku": "POLO-M-XS-AZ",
            "sucursal": "Central",
            "stock_fisico": 8,
            "stock_reservado": 2,
            "stock_disponible": 6,
            "stock_minimo": 3,
            "costo_promedio": Decimal("70.00"),
            "valor_inventario": Decimal("420.00"),
            "critico": False,
        },
        {
            "id_variante": 11,
            "producto": "Blusa manga larga",
            "categoria": "Blusas",
            "talla": "S",
            "color": "Blanco",
            "sku": "BLUSA-S-BC",
            "sucursal": "Central",
            "stock_fisico": 3,
            "stock_reservado": 1,
            "stock_disponible": 2,
            "stock_minimo": 2,
            "costo_promedio": Decimal("80.00"),
            "valor_inventario": Decimal("160.00"),
            "critico": True,
        },
    ]

    report = ReportsService.summarize_inventory(rows)

    assert report.unidades_disponibles == 8
    assert report.valor_total == Decimal("580.00")
    assert report.items_criticos == 1


def test_report_date_range_rejects_reversed_dates() -> None:
    with pytest.raises(Exception) as error:
        _dates(date(2026, 10, 2), date(2026, 10, 1))
    assert getattr(error.value, "status_code", None) == 422


def test_report_exports_generate_valid_files() -> None:
    date_from = date(2026, 10, 1)
    date_to = date(2026, 10, 31)
    sales = ReportsService.summarize_sales(date_from, date_to, [])
    inventory = ReportsService.summarize_inventory([])
    products = ProductReport(desde=date_from, hasta=date_to, productos=[])
    customers = CustomerReport(desde=date_from, hasta=date_to, clientes=[])

    excel = generate_excel(sales, products, inventory, customers)
    pdf = generate_pdf(sales, products, inventory, customers, "Casa Elena")

    assert excel.startswith(b"PK")
    assert b"xl/workbook.xml" in excel
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_generated_category_report_exports_the_same_dynamic_rows() -> None:
    plan = AIReportPlan(
        tipo_reporte="INGRESOS_CATEGORIA",
        fecha_desde="2026-10-01",
        fecha_hasta="2026-10-29",
        agrupacion="CATEGORIA",
        visualizacion="BARRAS",
    )
    data = {
        "total_unidades": 18,
        "ingresos": "5062.00",
        "categorias": [
            {
                "id_categoria": 1,
                "categoria": "Camisas",
                "unidades": 18,
                "ingresos": "5062.00",
                "participacion": "100.00",
            }
        ],
    }

    excel = generate_ai_excel("Ingresos por categoría", "altura-comercial", plan, data)
    pdf = generate_ai_pdf("Ingresos por categoría", "altura-comercial", plan, data)

    assert excel.startswith(b"PK")
    with ZipFile(BytesIO(excel)) as workbook:
        assert b"Camisas" in workbook.read("xl/sharedStrings.xml")
        assert b'autoFilter ref="A1:D2"' in workbook.read("xl/worksheets/sheet2.xml")
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_ai_summary_formats_bolivianos_for_spanish_reading() -> None:
    _, summary = _summary(
        "INGRESOS_CATEGORIA",
        {"ingresos": "16099.00", "categorias": []},
    )

    assert "Bs 16.099,00" in summary


async def test_exports_use_the_authenticated_company_logo_and_color(monkeypatch) -> None:
    def png(color: str) -> bytes:
        output = BytesIO()
        Image.new("RGB", (90, 40), color).save(output, format="PNG")
        return output.getvalue()

    logos = {
        "https://res.cloudinary.com/demo/image/upload/linea.png": png("#0F766E"),
        "https://res.cloudinary.com/demo/image/upload/horizonte.png": png("#4338CA"),
    }
    tenants = {
        21: SimpleNamespace(
            nombre="Línea Urbana", color_primario="#0F766E", logo_url=next(iter(logos))
        ),
        22: SimpleNamespace(
            nombre="Horizonte Textil", color_primario="#4338CA", logo_url=list(logos)[1]
        ),
    }
    session = SimpleNamespace(get=AsyncMock(side_effect=lambda _, tenant_id: tenants[tenant_id]))
    monkeypatch.setattr(
        "app.modules.reports.branding._logo", AsyncMock(side_effect=logos.__getitem__)
    )
    plan = AIReportPlan(tipo_reporte="PRODUCTOS")
    for tenant_id, tenant in tenants.items():
        brand = await load_report_brand(session, tenant_id)
        session.get.assert_awaited_with(Tenant, tenant_id)
        pdf = generate_ai_pdf("Productos destacados", brand, plan, {"productos": []})
        assert b"/Subtype /Image" in pdf
        assert b"/ca .065" in pdf
        with ZipFile(BytesIO(generate_ai_excel("Productos destacados", brand, plan, {}))) as xlsx:
            assert xlsx.read("xl/media/image1.png") == logos[tenant.logo_url]
            assert tenant.nombre.encode() in xlsx.read("xl/sharedStrings.xml")
            assert tenant.color_primario[1:].encode() in xlsx.read("xl/worksheets/sheet1.xml")


@pytest.mark.asyncio
async def test_every_report_query_filters_the_authenticated_tenant() -> None:
    session = _CapturingSession()
    service = ReportsService(session)  # type: ignore[arg-type]
    start = date(2026, 10, 1)
    end = date(2026, 10, 29)

    await service.sales(42, start, end, None)
    await service.sales_by_branch(42, start, end, None)
    await service.products(42, start, end, None, 10)
    await service.inventory(42, None, False)
    await service.revenue_by_category(42, start, end, None)
    await service.customers(42, start, end, None, 10)

    assert len(session.calls) == 6
    for statement, parameters in session.calls:
        assert "id_tenant = :tenant_id" in statement
        assert parameters["tenant_id"] == 42


@pytest.mark.asyncio
async def test_report_audit_persists_only_sanitized_metadata() -> None:
    session = _CapturingSession()
    service = ReportsService(session)  # type: ignore[arg-type]

    await service.audit_access(
        tenant_id=42,
        user_id=9,
        session_id="session-1",
        action="EXPORTAR",
        entity="REPORTE_IA",
        record_id="VENTAS",
        metadata={"formato": "pdf", "id_sucursal": 3},
    )

    statement, parameters = session.calls[0]
    assert "INSERT INTO capricho.bitacora" in statement
    assert parameters["tenant_id"] == 42
    assert parameters["user_id"] == 9
    assert parameters["metadata"] == '{"formato": "pdf", "id_sucursal": 3}'
    assert "pregunta" not in parameters["metadata"]
    assert session.commits == 1
