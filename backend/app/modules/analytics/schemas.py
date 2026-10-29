from datetime import date
from typing import Literal

from pydantic import BaseModel


class ForecastPoint(BaseModel):
    fecha: date
    unidades_estimadas: int
    ingresos_estimados: float
    intervalo_inferior: int
    intervalo_superior: int


class DemandForecast(BaseModel):
    modelo: str
    objetivo: str
    granularidad: Literal["DIA", "SEMANA", "MES"]
    observaciones_entrenamiento: int
    fecha_entrenamiento: date
    mae_unidades: float
    r2_unidades: float
    tendencia_por_periodo: float
    confianza: Literal["ALTA", "MEDIA", "BAJA"]
    advertencia: str | None
    pronostico: list[ForecastPoint]


class CustomerSegment(BaseModel):
    segmento: Literal["LEALES", "POTENCIALES", "EN_RIESGO"]
    descripcion: str
    clientes: int
    porcentaje: float
    recencia_promedio_dias: float
    frecuencia_promedio: float
    gasto_promedio: float
    accion_recomendada: str


class CustomerSegmentation(BaseModel):
    modelo: str
    variables: list[str]
    clientes_analizados: int
    segmentos: list[CustomerSegment]


class AnalyticsDashboard(BaseModel):
    generado_en: date
    periodo_desde: date
    periodo_hasta: date
    sucursal: str
    periodo: Literal["SEMANAL", "MENSUAL", "TRIMESTRAL", "SEMESTRAL"]
    prediccion_demanda: DemandForecast
    segmentacion_clientes: CustomerSegmentation
