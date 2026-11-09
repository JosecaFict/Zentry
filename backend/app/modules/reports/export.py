from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

from app.modules.reports.branding import ReportBrand
from app.modules.reports.layout import ReportLayout, ReportSection, render_excel, render_pdf
from app.modules.reports.schemas import (
    AIReportPlan,
    CustomerReport,
    InventoryReport,
    ProductReport,
    SalesReport,
)


def _ai_rows(plan: AIReportPlan, data: dict[str, Any]) -> tuple[list[str], list[list[object]]]:
    if plan.tipo_reporte == "VENTAS" and "sucursales" in data:
        return ["Sucursal", "Ventas", "Unidades", "Ingresos (Bs)", "Participación (%)"], [
            [
                item["sucursal"],
                item["ventas"],
                item["unidades"],
                float(item["ingresos"]),
                float(item["participacion"]),
            ]
            for item in data["sucursales"]
        ]
    if plan.tipo_reporte == "VENTAS":
        return ["Fecha", "Ventas", "Unidades", "Ingresos (Bs)"], [
            [item["fecha"], item["ventas"], item["unidades"], float(item["ingresos"])]
            for item in data.get("serie", [])
        ]
    if plan.tipo_reporte == "PRODUCTOS":
        return ["Posición", "Producto", "Categoría", "Unidades", "Ingresos (Bs)"], [
            [
                item["posicion"],
                item["producto"],
                item["categoria"],
                item["unidades"],
                float(item["ingresos"]),
            ]
            for item in data.get("productos", [])
        ]
    if plan.tipo_reporte == "INVENTARIO":
        return [
            "Producto",
            "Categoría",
            "Talla",
            "Color",
            "SKU",
            "Sucursal",
            "Disponible",
            "Mínimo",
            "Valor (Bs)",
        ], [
            [
                item["producto"],
                item["categoria"],
                item["talla"],
                item["color"],
                item["sku"],
                item["sucursal"],
                item["stock_disponible"],
                item["stock_minimo"],
                float(item["valor_inventario"]),
            ]
            for item in data.get("items", [])
        ]
    if plan.tipo_reporte == "INGRESOS_CATEGORIA":
        return ["Categoría", "Unidades", "Ingresos (Bs)", "Participación (%)"], [
            [
                item["categoria"],
                item["unidades"],
                float(item["ingresos"]),
                float(item["participacion"]),
            ]
            for item in data.get("categorias", [])
        ]
    if plan.tipo_reporte == "CLIENTES":
        return ["Cliente", "Correo", "Compras", "Unidades", "Gasto (Bs)", "Última compra"], [
            [
                item["cliente"],
                item["correo"],
                item["compras"],
                item["unidades"],
                float(item["gasto_total"]),
                item["ultima_compra"],
            ]
            for item in data.get("clientes", [])
        ]
    return ["Indicador", "Valor"], [["Resultado", "Resumen ejecutivo generado"]]


def _brand(value: ReportBrand | str) -> ReportBrand:
    return ReportBrand(value) if isinstance(value, str) else value


def _section(title: str, plan: AIReportPlan, data: dict[str, Any]) -> ReportSection:
    headers, rows = _ai_rows(plan, data)
    return ReportSection(title, headers, rows)


def _period(value: object) -> object:
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return value


def _sales_metrics(data: dict) -> list[tuple[str, int | Decimal]]:
    metrics = [
        ("Ventas", int(data.get("total_ventas", 0))),
        ("Unidades vendidas", int(data.get("total_unidades", 0))),
        ("Ingresos (Bs)", Decimal(str(data.get("ingresos", 0)))),
    ]
    if "ticket_promedio" in data:
        metrics.append(("Ticket promedio (Bs)", Decimal(str(data["ticket_promedio"]))))
    return metrics


def _inventory_metrics(data: dict) -> list[tuple[str, int | Decimal]]:
    return [
        ("Unidades disponibles", int(data.get("unidades_disponibles", 0))),
        ("Ítems críticos", int(data.get("items_criticos", 0))),
        ("Valor de inventario (Bs)", Decimal(str(data.get("valor_total", 0)))),
    ]


def _consolidated_sections(sales, products, inventory, customers) -> list[ReportSection]:
    return [
        _section(title, AIReportPlan(tipo_reporte=kind), data)
        for title, kind, data in (
            ("Ventas diarias", "VENTAS", sales),
            ("Productos", "PRODUCTOS", products),
            ("Inventario", "INVENTARIO", inventory),
            ("Clientes", "CLIENTES", customers),
        )
    ]


def _ai_layout(
    title: str,
    brand: ReportBrand | str,
    plan: AIReportPlan,
    data: dict[str, Any],
    branch: str | None,
) -> ReportLayout:
    kind = plan.tipo_reporte
    sales = data.get("ventas", {}) if kind == "RESUMEN" else data
    insight = None
    if kind == "VENTAS":
        metrics = _sales_metrics(data)
    elif kind == "INVENTARIO":
        metrics = _inventory_metrics(data)
    elif kind == "PRODUCTOS":
        products = data.get("productos", [])
        metrics = [
            ("Productos en el resultado", len(products)),
            ("Unidades del resultado", sum(item["unidades"] for item in products)),
            (
                "Ingresos del resultado (Bs)",
                sum((Decimal(str(item["ingresos"])) for item in products), Decimal(0)),
            ),
        ]
        if products:
            first = min(products, key=lambda item: item["posicion"])
            insight = (
                f"{first['producto']} ocupa la primera posición "
                f"con {first['unidades']} unidades vendidas."
            )
    elif kind == "CLIENTES":
        customers = data.get("clientes", [])
        metrics = [
            ("Clientes en el resultado", len(customers)),
            ("Compras del resultado", sum(item["compras"] for item in customers)),
            (
                "Gasto del resultado (Bs)",
                sum((Decimal(str(item["gasto_total"])) for item in customers), Decimal(0)),
            ),
        ]
    elif kind == "INGRESOS_CATEGORIA":
        metrics = [
            ("Categorías", len(data.get("categorias", []))),
            ("Unidades vendidas", int(data.get("total_unidades", 0))),
            ("Ingresos (Bs)", Decimal(str(data.get("ingresos", 0)))),
        ]
    else:
        metrics = _sales_metrics(sales)
        metrics.append(
            (
                "Valor de inventario (Bs)",
                Decimal(str(data.get("inventario", {}).get("valor_total", 0))),
            )
        )

    filters = [("Sucursal", branch or plan.sucursal or "Todas las sucursales")]
    start = sales.get("desde") or plan.fecha_desde
    end = sales.get("hasta") or plan.fecha_hasta
    if kind != "INVENTARIO":
        filters = [
            ("Desde", _period(start) if start else f"Últimos {plan.dias} días"),
            ("Hasta", _period(end) if end else "Fecha de la consulta"),
            *filters,
        ]
    if kind in {"PRODUCTOS", "INVENTARIO", "INGRESOS_CATEGORIA"}:
        filters.append(("Categoría", plan.categoria or "Todas"))
    if kind in {"PRODUCTOS", "INVENTARIO"}:
        filters.append(("Producto", plan.producto or "Todos"))
    if plan.agrupacion != "NINGUNA":
        filters.append(
            (
                "Agrupación",
                {"DIA": "Día", "CATEGORIA": "Categoría"}.get(
                    plan.agrupacion, plan.agrupacion.capitalize()
                ),
            )
        )
    if kind in {"RESUMEN", "INVENTARIO"} and plan.solo_criticos:
        filters.append(("Inventario", "Solo existencias críticas"))
    if kind in {"PRODUCTOS", "CLIENTES", "RESUMEN"}:
        filters.append(("Límite de resultados", str(plan.limite)))

    sections = (
        _consolidated_sections(
            sales,
            data.get("productos", {}),
            data.get("inventario", {}),
            data.get("clientes", {}),
        )
        if kind == "RESUMEN"
        else [_section("Detalle", plan, data)]
    )
    return ReportLayout(
        title, _brand(brand), "Reporte comercial con IA", metrics, filters, sections, insight
    )


def generate_ai_excel(
    title: str,
    tenant_name: ReportBrand | str,
    plan: AIReportPlan,
    data: dict[str, Any],
    *,
    branch: str | None = None,
) -> bytes:
    return render_excel(_ai_layout(title, tenant_name, plan, data, branch))


def generate_ai_pdf(
    title: str,
    tenant_name: ReportBrand | str,
    plan: AIReportPlan,
    data: dict[str, Any],
    *,
    branch: str | None = None,
) -> bytes:
    return render_pdf(_ai_layout(title, tenant_name, plan, data, branch))


def _commercial_layout(
    sales: SalesReport,
    products: ProductReport,
    inventory: InventoryReport,
    customers: CustomerReport,
    brand: ReportBrand | str,
    branch: str | None,
) -> ReportLayout:
    sales_data = sales.model_dump()
    metrics = [*_sales_metrics(sales_data), ("Valor de inventario (Bs)", inventory.valor_total)]
    filters = [
        ("Desde", sales.desde),
        ("Hasta", sales.hasta),
        ("Sucursal", branch or "Todas las sucursales"),
    ]
    sections = _consolidated_sections(
        sales_data, products.model_dump(), inventory.model_dump(), customers.model_dump()
    )
    inventory_section = sections[2]
    sections[2] = ReportSection(
        inventory_section.title,
        [*inventory_section.headers, "Crítico"],
        [
            [*row, "Sí" if item.critico else "No"]
            for row, item in zip(inventory_section.rows, inventory.items, strict=True)
        ],
    )
    return ReportLayout(
        "Reporte comercial", _brand(brand), "Reporte convencional", metrics, filters, sections
    )


def generate_excel(
    sales: SalesReport,
    products: ProductReport,
    inventory: InventoryReport,
    customers: CustomerReport,
    tenant_name: ReportBrand | str = "Zentry",
    *,
    branch: str | None = None,
) -> bytes:
    return render_excel(
        _commercial_layout(sales, products, inventory, customers, tenant_name, branch)
    )


def generate_pdf(
    sales: SalesReport,
    products: ProductReport,
    inventory: InventoryReport,
    customers: CustomerReport,
    tenant_name: ReportBrand | str,
    *,
    branch: str | None = None,
) -> bytes:
    report = _commercial_layout(sales, products, inventory, customers, tenant_name, branch)
    _, products_section, stock, clients_section = report.sections
    critical = ReportSection(
        "Inventario crítico",
        stock.headers[:-1],
        [row[:-1] for row, item in zip(stock.rows, inventory.items, strict=True) if item.critico],
    )
    return render_pdf(replace(report, sections=[products_section, clients_section, critical]))
