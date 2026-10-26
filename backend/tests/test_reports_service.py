from datetime import date
from decimal import Decimal

import pytest

from app.modules.reports.export import generate_excel, generate_pdf
from app.modules.reports.router import _dates
from app.modules.reports.schemas import CustomerReport, ProductReport
from app.modules.reports.service import ReportsService


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
