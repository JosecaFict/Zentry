from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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


class BranchSalesItem(BaseModel):
    id_sucursal: int
    sucursal: str
    ventas: int
    unidades: int
    ingresos: Decimal
    participacion: Decimal


class BranchSalesReport(BaseModel):
    desde: date
    hasta: date
    total_ventas: int
    total_unidades: int
    ingresos: Decimal
    sucursales: list[BranchSalesItem]


class ProductPerformance(BaseModel):
    posicion: int
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
    categoria: str
    talla: str
    color: str
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


class CategoryRevenueItem(BaseModel):
    id_categoria: int
    categoria: str
    unidades: int
    ingresos: Decimal
    participacion: Decimal


class CategoryRevenueReport(BaseModel):
    desde: date
    hasta: date
    total_unidades: int
    ingresos: Decimal
    categorias: list[CategoryRevenueItem]


class AIReportRequest(BaseModel):
    pregunta: str = Field(min_length=1, max_length=500)
    id_sucursal: int | None = Field(default=None, gt=0)


class AIReportPlan(BaseModel):
    tipo_reporte: Literal[
        "VENTAS",
        "PRODUCTOS",
        "INVENTARIO",
        "CLIENTES",
        "INGRESOS_CATEGORIA",
        "RESUMEN",
    ]
    dias: int = Field(default=90, ge=1, le=731)
    fecha_desde: date | None = None
    fecha_hasta: date | None = None
    sucursal: str | None = Field(default=None, max_length=120)
    categoria: str | None = Field(default=None, max_length=120)
    producto: str | None = Field(default=None, max_length=160)
    agrupacion: Literal[
        "DIA", "SEMANA", "MES", "SUCURSAL", "CATEGORIA", "PRODUCTO", "NINGUNA"
    ] = "NINGUNA"
    visualizacion: Literal["TABLA", "BARRAS", "LINEAS", "CIRCULAR", "INDICADORES"] = (
        "TABLA"
    )
    ordenar_por: Literal["INGRESOS", "UNIDADES", "VENTAS", "STOCK", "NOMBRE"] = (
        "INGRESOS"
    )
    direccion: Literal["ASC", "DESC"] = "DESC"
    limite: int = Field(default=20, ge=1, le=100)
    solo_criticos: bool = False
    necesita_aclaracion: bool = False
    pregunta_aclaracion: str | None = Field(default=None, max_length=300)

    @field_validator("dias", mode="before")
    @classmethod
    def normalize_nullable_days(cls, value):
        return 90 if value is None else value

    @model_validator(mode="after")
    def validate_dates_and_clarification(self):
        if (self.fecha_desde is None) != (self.fecha_hasta is None):
            raise ValueError("fecha_desde y fecha_hasta deben informarse juntas")
        if self.fecha_desde and self.fecha_hasta:
            if self.fecha_desde > self.fecha_hasta:
                raise ValueError("fecha_desde no puede ser posterior a fecha_hasta")
            if (self.fecha_hasta - self.fecha_desde).days > 730:
                raise ValueError("el período máximo permitido es de 731 días")
        if self.necesita_aclaracion and not self.pregunta_aclaracion:
            raise ValueError("una consulta ambigua debe incluir pregunta_aclaracion")
        return self


class AIReportResponse(BaseModel):
    pregunta: str
    interpretacion: AIReportPlan
    titulo: str
    resumen: str
    datos: dict[str, Any]
