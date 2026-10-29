export interface SalesPoint { fecha: string; ventas: number; unidades: number; ingresos: number; }
export interface SalesReport {
  desde: string; hasta: string; total_ventas: number; total_unidades: number;
  ingresos: number; ticket_promedio: number; serie: SalesPoint[];
}
export interface ProductPerformance {
  id_producto: number; producto: string; categoria: string; unidades: number; ingresos: number;
}
export interface ProductReport { desde: string; hasta: string; productos: ProductPerformance[]; }
export interface InventoryItem {
  id_variante: number; producto: string; sku: string; sucursal: string;
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
