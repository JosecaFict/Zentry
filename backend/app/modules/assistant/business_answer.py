"""Render company figures from authorized report results, without model arithmetic."""

from decimal import Decimal
from datetime import date
from calendar import monthrange

MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')


def _period(data: dict) -> str:
    if not data.get('desde') or not data.get('hasta'):
        return 'el período consultado'
    start, end = date.fromisoformat(str(data['desde'])), date.fromisoformat(str(data['hasta']))
    if start.year == end.year and start.month == end.month and start.day == 1 and end.day == monthrange(end.year, end.month)[1]:
        return f'{MONTHS[start.month - 1]} de {start.year}'
    if start == end:
        return f'el {start.day} de {MONTHS[start.month - 1]} de {start.year}'
    return f'el período del {start.day} de {MONTHS[start.month - 1]} de {start.year} al {end.day} de {MONTHS[end.month - 1]} de {end.year}'


def _money(value) -> str:
    amount = f"{Decimal(str(value or 0)):,.2f}"
    return "Bs " + amount.replace(",", "_").replace(".", ",").replace("_", ".")


def _text(value) -> str:
    # Catalog text must not create Markdown columns, emphasis or extra rows.
    return str(value).replace("|", "/").replace("\n", " ").replace("\r", " ").replace("*", "")


def _table(headers, rows) -> str:
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(_text(cell) for cell in row) + " |" for row in rows[:20]),
    ])


def business_answer(kind: str, data: dict) -> str:
    period = f"Para {_period(data)}, estos son los resultados:\n\n" if data.get('desde') and data.get('hasta') else ''
    if kind == "PRODUCTOS":
        products = data.get("productos", [])
        if not products:
            return period + "No encontré ventas de productos con esos filtros."
        if len(products) == 1:
            product = products[0]
            return (
                f"Claro. Para {_period(data)}, encontré este resultado:\n\n"
                f"Producto: {_text(product['producto'])}\n"
                f"Categoría: {_text(product['categoria']).capitalize()}\n"
                f"Unidades vendidas: {product['unidades']}\n"
                f"Ingresos: {_money(product['ingresos'])}\n\n"
                "¿Quieres que revisemos también las ventas por sucursal?"
            )
        return period + "Estos son los productos del reporte:\n\n" + _table(
            ["Producto", "Unidades", "Ingresos"],
            [[row['producto'], row['unidades'], _money(row['ingresos'])] for row in products],
        )
    if kind == "VENTAS":
        summary = f"Se registraron {data['total_ventas']} ventas, con {data['total_unidades']} unidades e ingresos de {_money(data['ingresos'])}."
        if data.get('sucursales'):
            return period + summary + "\n\n" + _table(
                ["Sucursal", "Ventas", "Ingresos"],
                [[row['sucursal'], row['ventas'], _money(row['ingresos'])] for row in data['sucursales']],
            )
        return period + summary
    if kind == "INVENTARIO":
        summary = f"Hay {data['unidades_disponibles']} unidades disponibles y {data['items_criticos']} variantes con stock crítico."
        if not data.get('items'):
            return summary + " No encontré prendas con los filtros solicitados."
        return summary + "\n\n" + _table(
            ["Prenda", "Talla / color", "Sucursal", "Disponible"],
            [[row['producto'], f"{row['talla']} / {row['color']}", row['sucursal'], row['stock_disponible']] for row in data['items']],
        )
    if kind == "CLIENTES":
        if not data.get('clientes'):
            return period + "No encontré clientes con compras para esos filtros."
        return period + "Estos son los clientes del reporte:\n\n" + _table(
            ["Cliente", "Compras", "Importe comprado"],
            [[row['cliente'], row['compras'], _money(row['gasto_total'])] for row in data['clientes']],
        )
    if kind == "INGRESOS_CATEGORIA":
        summary = period + f"Los ingresos por categoría suman {_money(data['ingresos'])}."
        return summary + ("\n\n" + _table(
            ["Categoría", "Unidades", "Ingresos"],
            [[row['categoria'], row['unidades'], _money(row['ingresos'])] for row in data['categorias']],
        ) if data.get('categorias') else " No encontré categorías con ventas para esos filtros.")
    if kind == "RESUMEN":
        return business_answer('VENTAS', data['ventas']) + "\n\n" + business_answer('PRODUCTOS', data['productos']) + "\n\n" + business_answer('INVENTARIO', data['inventario'])
    return "Puedes abrir el reporte para revisar sus resultados."
