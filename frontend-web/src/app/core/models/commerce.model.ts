export interface CommerceLine {
  id_detalle: number;
  id_variante: number;
  sku: string;
  producto: string;
  talla: string;
  color: string;
  cantidad: number;
  precio_unitario: string;
  subtotal: string;
  stock_disponible: number;
  activo: boolean;
  imagen_url: string | null;
}

export interface Cart {
  id_carrito: number;
  estado: string;
  id_sucursal?: number | null;
  sucursal?: string | null;
  items: CommerceLine[];
  total: string;
}

export interface Address {
  id_direccion: number;
  id_ciudad: number;
  ciudad: string;
  alias: string | null;
  zona: string | null;
  direccion: string;
  referencia: string | null;
  latitud: string | null;
  longitud: string | null;
  es_principal: boolean;
  activo: boolean;
}

export interface Reservation {
  id_reserva: number;
  id_sucursal: number;
  sucursal: string;
  direccion_sucursal: string;
  id_cliente?: number | null;
  cliente_nombre?: string | null;
  cliente_correo?: string | null;
  cliente_telefono?: string | null;
  fecha_reserva: string;
  fecha_cita: string | null;
  fecha_expiracion: string | null;
  estado: string;
  observacion: string | null;
  items: CommerceLine[];
}

export interface Sale {
  id_venta: number;
  id_cliente: number | null;
  id_sucursal: number;
  sucursal: string;
  cliente_nombre?: string | null;
  cliente_ci_nit?: string | null;
  cliente_correo?: string | null;
  cliente_telefono?: string | null;
  id_empleado: number | null;
  empleado_nombre?: string | null;
  id_reserva: number | null;
  canal_venta: string;
  modalidad_entrega: string;
  metodo_pago?: string | null;
  estado: string;
  subtotal: string;
  costo_envio: string;
  total: string;
  fecha_venta: string;
  items: CommerceLine[];
}

export interface Order {
  id_pedido: number;
  id_venta: number;
  id_cliente?: number | null;
  cliente_nombre?: string | null;
  cliente_correo?: string | null;
  cliente_telefono?: string | null;
  estado: string;
  modalidad_entrega: 'RETIRO_SUCURSAL' | 'DELIVERY';
  id_sucursal: number;
  sucursal: string;
  direccion_sucursal: string;
  id_direccion: number | null;
  direccion_entrega: string | null;
  total: string;
  fecha_creacion: string;
  fecha_preparacion: string | null;
  fecha_finalizacion: string | null;
  items: CommerceLine[];
  receipt_url?: string | null;
}

export interface StripeCheckoutSession {
  session_id: string;
  checkout_url: string;
  expires_at: string;
}

export interface StripeCheckoutStatus {
  status: 'PROCESANDO' | 'PAGADO' | 'CANCELADO' | 'RECHAZADO';
  message: string;
  order: Order | null;
  receipt_url?: string | null;
}

export interface ShippingQuote {
  id_cotizacion: number;
  id_sucursal: number;
  id_direccion: number;
  distancia_km: string;
  duracion_estimada_min: number | null;
  costo_estimado: string;
  proveedor_rutas: string;
  fecha_cotizacion: string;
  expira_en: string | null;
}

export interface ReturnRequest {
  id_devolucion: number;
  id_venta: number;
  tipo_solicitud: 'DEVOLUCION' | 'CAMBIO_TALLA' | 'CAMBIO_COLOR' | 'CAMBIO_PRENDA' | 'REEMBOLSO' | 'CREDITO';
  id_cliente?: number | null;
  cliente_nombre?: string | null;
  motivo: string;
  estado: string;
  fecha_solicitud: string;
  fecha_resolucion: string | null;
  items: Array<{
    id_detalle_devolucion: number;
    id_detalle_venta: number;
    id_variante: number;
    producto: string;
    talla: string;
    color: string;
    cantidad: number;
    estado_prenda: string;
  }>;
}

export interface ReturnItemConditionUpdate {
  id_detalle_devolucion: number;
  estado_prenda: 'APTA_REINGRESO' | 'NO_APTA';
}

export interface ReturnStatusUpdatePayload {
  estado: 'PENDIENTE' | 'APROBADA' | 'COMPLETADA' | 'RECHAZADA';
  items?: ReturnItemConditionUpdate[];
  observaciones?: string | null;
}

export interface SaleReturnLineInspection {
  id_detalle_venta: number;
  id_variante: number;
  sku: string;
  producto: string;
  talla: string;
  color: string;
  cantidad_vendida: number;
  cantidad_devuelta: number;
  cantidad_disponible: number;
  precio_unitario: string;
  imagen_url?: string | null;
}

export interface SaleReturnInspectionResponse {
  id_venta: number;
  id_cliente: number | null;
  cliente_nombre?: string | null;
  cliente_correo?: string | null;
  cliente_telefono?: string | null;
  id_sucursal: number;
  sucursal: string;
  canal_venta: string;
  modalidad_entrega: string;
  total: string;
  fecha_venta: string;
  es_retornable: boolean;
  dias_habiles_transcurridos: number;
  dias_habiles_limite: number;
  fecha_limite_devolucion: string;
  motivo_invalidez?: string | null;
  items: SaleReturnLineInspection[];
}

export interface AdminReturnCreate {
  id_venta: number;
  motivo: string;
  items: Array<{
    id_detalle_venta: number;
    cantidad: number;
    estado_prenda: 'APTA_REINGRESO' | 'NO_APTA';
  }>;
  completar_inmediato: boolean;
}

export interface OperationalNotification {
  id_notificacion: number;
  tipo: string;
  titulo: string | null;
  contenido: string;
  estado: string;
  fecha_creacion: string;
}

export interface AdminOperationalNotification {
  id_notificacion: number;
  id_usuario: number | null;
  destinatario_nombre: string | null;
  destinatario_email: string | null;
  tipo: string;
  canal: string;
  proveedor: string;
  destinatario: string | null;
  titulo: string | null;
  contenido: string;
  estado: 'PENDIENTE' | 'ENVIADO' | 'FALLIDO';
  external_message_id: string | null;
  fecha_creacion: string;
  fecha_envio: string | null;
  fecha_entrega: string | null;
  error_mensaje: string | null;
}

export interface NotificationKpis {
  total: number;
  enviadas: number;
  pendientes: number;
  fallidas: number;
}

export interface AdminNotificationPage {
  items: AdminOperationalNotification[];
  total: number;
  kpis: NotificationKpis;
  page: number;
  page_size: number;
}

export interface ManualNotificationPayload {
  id_usuario: number;
  titulo: string;
  contenido: string;
  canal?: 'SISTEMA' | 'EMAIL';
  tipo?: string;
}

export interface SupplierPurchaseHistoryPage {
  items: Array<Record<string, string | number | null>>;
  total: number;
  page: number;
  page_size: number;
}

export interface CustomerAddressItem {
  id_direccion: number;
  id_ciudad: number;
  ciudad: string;
  departamento: string;
  alias: string | null;
  zona: string | null;
  direccion: string;
  referencia: string | null;
  es_principal: boolean;
  activo: boolean;
}

export interface CustomerAdminSummary {
  id_cliente: number;
  id_usuario: number;
  nombres: string;
  apellidos: string;
  nombre_completo: string;
  correo: string;
  ci: string | null;
  telefono: string | null;
  fecha_nacimiento: string | null;
  estado: string;
  total_pedidos: number;
  total_reservas: number;
  total_ventas: number;
  created_at: string;
  updated_at: string;
}

export interface CustomerAdminDetail extends CustomerAdminSummary {
  direcciones: CustomerAddressItem[];
}

export interface CustomerAdminUpdateRequest {
  nombres?: string;
  apellidos?: string;
  correo?: string;
  telefono?: string | null;
  ci?: string | null;
  fecha_nacimiento?: string | null;
  estado?: 'ACTIVO' | 'INACTIVO';
  nuevo_password?: string;
}

export interface Campaign {
  id_campania: number;
  nombre: string;
  descripcion: string | null;
  asunto_email: string | null;
  segmento_objetivo: string | null;
  fecha_inicio: string | null;
  fecha_fin: string | null;
  estado: 'BORRADOR' | 'PROGRAMADA' | 'ENVIANDO' | 'FINALIZADA' | 'CANCELADA';
  created_at: string;
  updated_at: string;
  total_notificaciones: number;
}

export interface CampaignCreate {
  nombre: string;
  descripcion: string;
  asunto_email?: string | null;
  segmento_objetivo?: string;
  fecha_inicio?: string | null;
  fecha_fin?: string | null;
}

export interface CampaignUpdate {
  nombre?: string;
  descripcion?: string;
  asunto_email?: string | null;
  segmento_objetivo?: string;
  fecha_inicio?: string | null;
  fecha_fin?: string | null;
  estado?: 'BORRADOR' | 'PROGRAMADA' | 'CANCELADA';
}

export interface CampaignLaunchResponse {
  id_campania: number;
  nombre: string;
  estado: string;
  destinatarios_notificados: number;
  mensaje: string;
}

export interface Promotion {
  id_promocion: number;
  nombre: string;
  descripcion?: string | null;
  porcentaje_descuento: number;
  fecha_inicio: string;
  fecha_fin: string;
  activo: boolean;
  created_at: string;
  updated_at: string;
  producto_ids: number[];
  categoria_ids: number[];
  temporada_ids: number[];
  productos_count: number;
  categorias_count: number;
  temporadas_count: number;
  estado_vigencia: 'VIGENTE' | 'PROGRAMADA' | 'EXPIRADA' | 'INACTIVA';
}

export interface PromotionCreate {
  nombre: string;
  descripcion?: string | null;
  porcentaje_descuento: number;
  fecha_inicio: string;
  fecha_fin: string;
  activo: boolean;
  producto_ids?: number[];
  categoria_ids?: number[];
  temporada_ids?: number[];
}

export interface PromotionUpdate {
  nombre?: string;
  descripcion?: string | null;
  porcentaje_descuento?: number;
  fecha_inicio?: string;
  fecha_fin?: string;
  activo?: boolean;
  producto_ids?: number[];
  categoria_ids?: number[];
  temporada_ids?: number[];
}

export interface ActivePromotionItem {
  id_promocion: number;
  nombre: string;
  descripcion?: string | null;
  porcentaje_descuento: number;
  fecha_inicio: string;
  fecha_fin: string;
  productos_count: number;
  categorias_count: number;
  temporadas_count: number;
}

export interface DashboardKpis {
  ventas_mes_total: number;
  ventas_crecimiento_pct: number;
  pedidos_pendientes: number;
  reservas_hoy: number;
  alertas_stock_critico: number;
}

export interface DashboardDailyRevenue {
  fecha: string;
  dia_nombre: string;
  total: number;
}

export interface DashboardBranchShare {
  id_sucursal: number | null;
  nombre: string;
  total: number;
  porcentaje: number;
}

export interface DashboardUrgentOrder {
  id_pedido: number;
  id_venta: number;
  cliente_nombre: string;
  tipo_entrega: string;
  estado: string;
  total: number;
  fecha_creacion: string;
}

export interface DashboardTopProduct {
  id_producto: number;
  nombre: string;
  categoria: string;
  marca: string;
  unidades_vendidas: number;
  total_recaudado: number;
  imagen_url: string | null;
}

export interface AdminDashboardSummary {
  kpis: DashboardKpis;
  tendencia_semanal: DashboardDailyRevenue[];
  ventas_por_sucursal: DashboardBranchShare[];
  pedidos_urgentes: DashboardUrgentOrder[];
  top_productos: DashboardTopProduct[];
}


