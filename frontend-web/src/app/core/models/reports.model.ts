export interface SalesPoint { fecha: string; ventas: number; unidades: number; ingresos: number; }
export interface SalesReport {
  desde: string; hasta: string; total_ventas: number; total_unidades: number;
  ingresos: number; ticket_promedio: number; serie: SalesPoint[];
}
export interface BranchSalesItem {
  id_sucursal: number; sucursal: string; ventas: number; unidades: number;
  ingresos: number; participacion: number;
}
export interface BranchSalesReport {
  desde: string; hasta: string; total_ventas: number; total_unidades: number;
  ingresos: number; sucursales: BranchSalesItem[];
}
export interface ProductPerformance {
  posicion: number; id_producto: number; producto: string; categoria: string; unidades: number; ingresos: number;
}
export interface ProductReport { desde: string; hasta: string; productos: ProductPerformance[]; }
export interface InventoryItem {
  id_variante: number; producto: string; categoria: string; talla: string; color: string;
  sku: string; sucursal: string;
  stock_fisico: number; stock_reservado: number; stock_disponible: number;
  stock_minimo: number; costo_promedio: number; valor_inventario: number; critico: boolean;
}
export interface InventoryReport {
  unidades_disponibles: number; valor_total: number; items_criticos: number; items: InventoryItem[];
}
export interface CustomerPerformance {
  id_cliente: number; cliente: string; correo: string; compras: number; unidades: number;
  gasto_total: number; ticket_promedio: number; ultima_compra: string;
}
export interface CustomerReport { desde: string; hasta: string; clientes: CustomerPerformance[]; }
export interface CategoryRevenueItem {
  id_categoria: number; categoria: string; unidades: number; ingresos: number; participacion: number;
}
export interface CategoryRevenueReport {
  desde: string; hasta: string; total_unidades: number; ingresos: number; categorias: CategoryRevenueItem[];
}
export type AIReportType = 'VENTAS' | 'PRODUCTOS' | 'INVENTARIO' | 'CLIENTES' | 'INGRESOS_CATEGORIA' | 'RESUMEN';
export interface AIReportPlan {
  tipo_reporte: AIReportType; dias: number; fecha_desde: string | null; fecha_hasta: string | null;
  sucursal: string | null; categoria: string | null; producto: string | null;
  agrupacion: 'DIA' | 'SEMANA' | 'MES' | 'SUCURSAL' | 'CATEGORIA' | 'PRODUCTO' | 'NINGUNA';
  visualizacion: 'TABLA' | 'BARRAS' | 'LINEAS' | 'CIRCULAR' | 'INDICADORES';
  ordenar_por: 'INGRESOS' | 'UNIDADES' | 'VENTAS' | 'STOCK' | 'NOMBRE'; direccion: 'ASC' | 'DESC';
  limite: number; solo_criticos: boolean; necesita_aclaracion: boolean; pregunta_aclaracion: string | null;
}
export interface AIReportResponse {
  pregunta: string; interpretacion: AIReportPlan; titulo: string; resumen: string;
  datos: Record<string, unknown>;
}
export interface ForecastPoint {
  semana: string; unidades_estimadas: number; ingresos_estimados: number;
  intervalo_inferior: number; intervalo_superior: number;
}
export interface DemandForecast {
  modelo: string; objetivo: string; semanas_entrenamiento: number; fecha_entrenamiento: string;
  mae_unidades: number; r2_unidades: number; tendencia_por_semana: number;
  confianza: 'ALTA' | 'MEDIA' | 'BAJA'; advertencia: string | null; pronostico: ForecastPoint[];
}
export interface CustomerSegment {
  segmento: 'LEALES' | 'POTENCIALES' | 'EN_RIESGO'; descripcion: string; clientes: number;
  porcentaje: number; recencia_promedio_dias: number; frecuencia_promedio: number;
  gasto_promedio: number; accion_recomendada: string;
}
export interface CustomerSegmentation {
  modelo: string; variables: string[]; clientes_analizados: number; segmentos: CustomerSegment[];
}
export interface AnalyticsDashboard {
  generado_en: string; periodo_desde: string; periodo_hasta: string; sucursal: string;
  prediccion_demanda: DemandForecast; segmentacion_clientes: CustomerSegmentation;
}
