from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class SalesPoint(BaseModel):
    fecha: date
    ventas: int
    unidades: int
    ingresos: Decimal


class SalesReport(BaseModel):
    desde: date
    hasta: date
    total_ventas: int
    total_unidades: int
    ingresos: Decimal
    ticket_promedio: Decimal
    serie: list[SalesPoint]


class ProductPerformance(BaseModel):
    id_producto: int
    producto: str
    categoria: str
    unidades: int
    ingresos: Decimal


class ProductReport(BaseModel):
    desde: date
    hasta: date
    productos: list[ProductPerformance]


class InventoryItem(BaseModel):
    id_variante: int
    producto: str
    sku: str
    sucursal: str
    stock_fisico: int
    stock_reservado: int
    stock_disponible: int
    stock_minimo: int
    costo_promedio: Decimal
    valor_inventario: Decimal
    critico: bool


class InventoryReport(BaseModel):
    unidades_disponibles: int
    valor_total: Decimal
    items_criticos: int
    items: list[InventoryItem]


class CustomerPerformance(BaseModel):
    id_cliente: int
    cliente: str
    correo: str
    compras: int
    unidades: int
    gasto_total: Decimal
    ticket_promedio: Decimal
    ultima_compra: date


class CustomerReport(BaseModel):
    desde: date
    hasta: date
    clientes: list[CustomerPerformance]


class AIReportRequest(BaseModel):
    pregunta: str = Field(min_length=1, max_length=500)
    id_sucursal: int | None = Field(default=None, gt=0)


class AIReportPlan(BaseModel):
    tipo_reporte: Literal["VENTAS", "PRODUCTOS", "INVENTARIO", "CLIENTES", "RESUMEN"]
    dias: int = Field(default=90, ge=1, le=731)
    limite: int = Field(default=20, ge=1, le=100)
    solo_criticos: bool = False


class AIReportResponse(BaseModel):
    pregunta: str
    interpretacion: AIReportPlan
    titulo: str
    resumen: str
    datos: dict[str, Any]
