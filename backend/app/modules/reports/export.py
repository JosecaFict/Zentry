# ruff: noqa: E501

from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.reports.schemas import (
    AIReportPlan,
    CustomerReport,
    InventoryReport,
    ProductReport,
    SalesReport,
)


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell(reference: str, value: object) -> str:
    if isinstance(value, (int, float)):
        return f'<c r="{reference}"><v>{value}</v></c>'
    return f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def _sheet(rows: list[list[object]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(
            _cell(f"{_column_name(column_index)}{row_index}", value)
            for column_index, value in enumerate(row, start=1)
        )
        xml_rows.append(f'<row r="{row_index}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(xml_rows)}</sheetData></worksheet>"
    )


def generate_excel(
    sales: SalesReport,
    products: ProductReport,
    inventory: InventoryReport,
    customers: CustomerReport,
) -> bytes:
    sheets = [
        (
            "Resumen",
            [
                ["Indicador", "Valor"],
                ["Desde", sales.desde.isoformat()],
                ["Hasta", sales.hasta.isoformat()],
                ["Ventas", sales.total_ventas],
                ["Unidades", sales.total_unidades],
                ["Ingresos (Bs)", float(sales.ingresos)],
                ["Ticket promedio (Bs)", float(sales.ticket_promedio)],
                ["Inventario valorizado (Bs)", float(inventory.valor_total)],
            ],
        ),
        (
            "Ventas diarias",
            [["Fecha", "Ventas", "Unidades", "Ingresos (Bs)"]]
            + [
                [item.fecha.isoformat(), item.ventas, item.unidades, float(item.ingresos)]
                for item in sales.serie
            ],
        ),
        (
            "Productos",
            [["Producto", "Categoría", "Unidades", "Ingresos (Bs)"]]
            + [
                [item.producto, item.categoria, item.unidades, float(item.ingresos)]
                for item in products.productos
            ],
        ),
        (
            "Inventario",
            [["Producto", "SKU", "Sucursal", "Disponible", "Mínimo", "Valor (Bs)", "Crítico"]]
            + [
                [
                    item.producto,
                    item.sku,
                    item.sucursal,
                    item.stock_disponible,
                    item.stock_minimo,
                    float(item.valor_inventario),
                    "Sí" if item.critico else "No",
                ]
                for item in inventory.items
            ],
        ),
        (
            "Clientes",
            [["Cliente", "Correo", "Compras", "Unidades", "Gasto (Bs)", "Última compra"]]
            + [
                [
                    item.cliente,
                    item.correo,
                    item.compras,
                    item.unidades,
                    float(item.gasto_total),
                    item.ultima_compra.isoformat(),
                ]
                for item in customers.clientes
            ],
        ),
    ]
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(len(sheets)))
        archive.writestr("_rels/.rels", _root_rels())
        archive.writestr("xl/workbook.xml", _workbook([name for name, _ in sheets]))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels(len(sheets)))
        for index, (_, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet(rows))
    return output.getvalue()


def _ai_rows(plan: AIReportPlan, data: dict[str, Any]) -> tuple[list[str], list[list[object]]]:
    if plan.tipo_reporte == "VENTAS" and "sucursales" in data:
        return ["Sucursal", "Ventas", "Unidades", "Ingresos (Bs)", "Participación (%)"], [
            [item["sucursal"], item["ventas"], item["unidades"], float(item["ingresos"]), float(item["participacion"])]
            for item in data["sucursales"]
        ]
    if plan.tipo_reporte == "VENTAS":
        return ["Fecha", "Ventas", "Unidades", "Ingresos (Bs)"], [
            [item["fecha"], item["ventas"], item["unidades"], float(item["ingresos"])]
            for item in data.get("serie", [])
        ]
    if plan.tipo_reporte == "PRODUCTOS":
        return ["Posición", "Producto", "Categoría", "Unidades", "Ingresos (Bs)"], [
            [item["posicion"], item["producto"], item["categoria"], item["unidades"], float(item["ingresos"])]
            for item in data.get("productos", [])
        ]
    if plan.tipo_reporte == "INVENTARIO":
        return ["Producto", "Categoría", "Talla", "Color", "SKU", "Sucursal", "Disponible", "Mínimo", "Valor (Bs)"], [
            [
                item["producto"], item["categoria"], item["talla"], item["color"],
                item["sku"], item["sucursal"], item["stock_disponible"],
                item["stock_minimo"], float(item["valor_inventario"]),
            ]
            for item in data.get("items", [])
        ]
    if plan.tipo_reporte == "INGRESOS_CATEGORIA":
        return ["Categoría", "Unidades", "Ingresos (Bs)", "Participación (%)"], [
            [item["categoria"], item["unidades"], float(item["ingresos"]), float(item["participacion"])]
            for item in data.get("categorias", [])
        ]
    if plan.tipo_reporte == "CLIENTES":
        return ["Cliente", "Correo", "Compras", "Unidades", "Gasto (Bs)", "Última compra"], [
            [
                item["cliente"], item["correo"], item["compras"], item["unidades"],
                float(item["gasto_total"]), item["ultima_compra"],
            ]
            for item in data.get("clientes", [])
        ]
    return ["Indicador", "Valor"], [["Resultado", "Resumen ejecutivo generado"]]


def _ai_filters(plan: AIReportPlan) -> list[list[object]]:
    return [
        ["Desde", plan.fecha_desde.isoformat() if plan.fecha_desde else f"Últimos {plan.dias} días"],
        ["Hasta", plan.fecha_hasta.isoformat() if plan.fecha_hasta else "Fecha actual"],
        ["Sucursal", plan.sucursal or "Todas"],
        ["Categoría", plan.categoria or "Todas"],
        ["Producto", plan.producto or "Todos"],
        ["Agrupación", plan.agrupacion],
    ]


def generate_ai_excel(
    title: str,
    tenant_name: str,
    plan: AIReportPlan,
    data: dict[str, Any],
) -> bytes:
    headers, detail_rows = _ai_rows(plan, data)
    rows: list[list[object]] = [
        [title],
        ["Empresa", tenant_name],
        ["Generado", datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")],
        [],
        ["Filtros aplicados"],
        *_ai_filters(plan),
        [],
        headers,
        *detail_rows,
    ]
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(1))
        archive.writestr("_rels/.rels", _root_rels())
        archive.writestr("xl/workbook.xml", _workbook(["Reporte generado"]))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels(1))
        archive.writestr("xl/worksheets/sheet1.xml", _sheet(rows))
    return output.getvalue()


def generate_ai_pdf(
    title: str,
    tenant_name: str,
    plan: AIReportPlan,
    data: dict[str, Any],
) -> bytes:
    headers, detail_rows = _ai_rows(plan, data)
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(escape(title), styles["Title"]),
        Paragraph(f"Empresa: {escape(tenant_name)}", styles["Normal"]),
        Paragraph(
            f"Generado: {datetime.now(UTC):%d/%m/%Y %H:%M} UTC",
            styles["Normal"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("Filtros aplicados", styles["Heading2"]),
        _pdf_table(_ai_filters(plan)),
        Spacer(1, 6 * mm),
        Paragraph("Resultados", styles["Heading2"]),
        _pdf_table([headers, *detail_rows]),
    ]
    document.build(story)
    return output.getvalue()


def _content_types(count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + overrides
        + "</Types>"
    )


def _root_rels() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'


def _workbook(names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + sheets
        + "</sheets></workbook>"
    )


def _workbook_rels(count: int) -> str:
    relationships = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + relationships
        + "</Relationships>"
    )


def generate_pdf(
    sales: SalesReport,
    products: ProductReport,
    inventory: InventoryReport,
    customers: CustomerReport,
    tenant_name: str,
) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Reporte comercial · {escape(tenant_name)}", styles["Title"]),
        Paragraph(f"Periodo: {sales.desde:%d/%m/%Y} al {sales.hasta:%d/%m/%Y}", styles["Normal"]),
        Spacer(1, 6 * mm),
    ]
    summary = [
        ["Ventas", "Unidades", "Ingresos", "Ticket promedio", "Inventario valorizado"],
        [
            sales.total_ventas,
            sales.total_unidades,
            f"Bs {sales.ingresos:,.2f}",
            f"Bs {sales.ticket_promedio:,.2f}",
            f"Bs {inventory.valor_total:,.2f}",
        ],
    ]
    story.extend(
        [
            _pdf_table(summary),
            Spacer(1, 7 * mm),
            Paragraph("Productos con mayor movimiento", styles["Heading2"]),
            _pdf_table(
                [["Producto", "Categoría", "Unidades", "Ingresos"]]
                + [
                    [item.producto, item.categoria, item.unidades, f"Bs {item.ingresos:,.2f}"]
                    for item in products.productos
                ]
            ),
            PageBreak(),
            Paragraph("Clientes con mayor actividad", styles["Heading2"]),
            _pdf_table(
                [["Cliente", "Correo", "Compras", "Unidades", "Gasto", "Última compra"]]
                + [
                    [
                        item.cliente,
                        item.correo,
                        item.compras,
                        item.unidades,
                        f"Bs {item.gasto_total:,.2f}",
                        f"{item.ultima_compra:%d/%m/%Y}",
                    ]
                    for item in customers.clientes
                ]
            ),
            Spacer(1, 7 * mm),
            Paragraph("Inventario crítico", styles["Heading2"]),
            _pdf_table(
                [["Producto", "SKU", "Sucursal", "Disponible", "Mínimo"]]
                + [
                    [
                        item.producto,
                        item.sku,
                        item.sucursal,
                        item.stock_disponible,
                        item.stock_minimo,
                    ]
                    for item in inventory.items
                    if item.critico
                ]
            ),
        ]
    )
    document.build(story)
    return output.getvalue()


def _pdf_table(rows: list[list[object]]) -> Table:
    safe_rows = rows if len(rows) > 1 else rows + [["Sin datos"] + [""] * (len(rows[0]) - 1)]
    table = Table(safe_rows, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#121720")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD0D6")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F8")]),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table
