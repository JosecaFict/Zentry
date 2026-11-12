export type OfflineOperationType = 'VENTA' | 'RESERVA';
export type OfflineOperationStatus =
  | 'PENDIENTE'
  | 'ENVIANDO'
  | 'APLICADA'
  | 'CONFLICTO'
  | 'RECHAZADA'
  | 'CONFIRMADA';

export interface OfflineScope {
  tenantId: number;
  userId: number;
  branchId: number;
}

export interface OfflineSyncMeta extends OfflineScope {
  key: 'scope';
  deviceId: string;
  catalogVersion: string | null;
  lastCatalogSyncAt: string | null;
  lastSuccessfulSyncAt: string | null;
}

export interface OfflineOperationSummary {
  pending: number;
  conflicts: number;
  rejected: number;
}

export interface OfflineCatalogItem {
  id_variante: number;
  sku: string;
  producto: string;
  talla: string;
  color: string;
  precio: string;
  stock_fisico: number;
  stock_reservado: number;
  stock_disponible: number;
  updated_at: string | null;
}

export interface OfflineCustomerItem {
  id_cliente: number;
  nombre_completo: string;
  correo: string;
  telefono: string | null;
}

export interface CatalogSnapshot {
  id_sucursal: number;
  generado_at: string;
  version: string;
  items: OfflineCatalogItem[];
}

export interface PendingOfflineOperation extends OfflineScope {
  id_operacion: string;
  tipo: OfflineOperationType;
  fecha_cliente: string;
  payload: Record<string, unknown>;
  estado: OfflineOperationStatus;
  intentos: number;
  codigo_error: string | null;
  mensaje_error: string | null;
  id_lote: string | null;
  created_at: string;
  updated_at: string;
  /** Cuándo el vendedor marcó como revisada una operación no registrada. */
  revisada_at?: string | null;
  /** Decisión del encargado en el servidor (reaplicada o anulada, con su nota). */
  resolucion_servidor?: { accion: 'REAPLICADA' | 'ANULADA'; nota: string | null } | null;
}

/** Estado en el servidor de una operación del dispositivo. */
export interface SyncOperationStatus {
  id_operacion: string;
  estado: string;
  codigo_error: string | null;
  mensaje_error: string | null;
  conflicto_estado: string | null;
  accion: 'REAPLICADA' | 'ANULADA' | null;
  resolucion: string | null;
}

/** Texto de la decisión del encargado, o null si todavía no decidió. */
export function serverResolutionLabel(operation: PendingOfflineOperation): string | null {
  const resolution = operation.resolucion_servidor;
  if (!resolution) return null;
  const head = resolution.accion === 'REAPLICADA'
    ? 'Tu encargado la registró (reaplicada).'
    : 'Tu encargado la anuló.';
  return resolution.nota ? `${head} Nota: ${resolution.nota}` : head;
}

/** Motivo de una operación no registrada, en lenguaje claro. */
export function offlineFailureReason(code: string | null | undefined): string {
  switch (code) {
    case 'STOCK_INSUFICIENTE':
      return 'No había stock: otra venta o reserva se registró antes.';
    case 'CONFLICTO_COMERCIAL':
      return 'Choca con otra operación (precio, reserva o estado del pedido).';
    case 'DATOS_INVALIDOS':
      return 'Faltan datos o no son válidos: revisa la operación.';
    case 'ERROR_INTERNO':
      return 'Hubo un error del servidor al registrarla.';
    default:
      return 'El servidor no aceptó la operación.';
  }
}

/**
 * Solo una operación rechazada por datos inválidos se vuelve a cargar en el
 * carrito: las demás las resuelve un encargado en el servidor (reaplicar o
 * anular) y registrarlas de nuevo duplicaría la venta.
 */
export function canReloadOfflineOperation(operation: PendingOfflineOperation): boolean {
  return operation.estado === 'RECHAZADA' && operation.codigo_error === 'DATOS_INVALIDOS' &&
    !operation.resolucion_servidor;
}

export type SyncConflictState = 'PENDIENTE' | 'RESUELTO' | 'DESCARTADO';

export interface SyncConflictItem {
  id_variante: number;
  cantidad: number;
  descripcion: string;
}

/** Operación offline no registrada, vista por un encargado o administrador. */
export interface SyncConflict {
  id_conflicto: number;
  id_operacion: string;
  tipo_operacion: OfflineOperationType;
  codigo: string;
  mensaje: string | null;
  estado: SyncConflictState;
  id_sucursal: number | null;
  id_vendedor: number;
  vendedor: string | null;
  items: SyncConflictItem[];
  total_cobrado_centavos: number | null;
  fecha_cliente: string;
  created_at: string;
  puede_reaplicar: boolean;
  accion: 'REAPLICADA' | 'ANULADA' | null;
  resolucion: string | null;
  resuelto_por: string | null;
  resuelto_at: string | null;
}

/**
 * Quién revisa conflictos (mismas reglas que el backend): administrador,
 * permiso de todas las sucursales o encargado con sucursal asignada.
 */
export function canReviewSyncConflicts(user: {
  roles: readonly string[];
  permisos: readonly string[];
  id_sucursal?: number | null;
} | null | undefined): boolean {
  if (!user) return false;
  const roles = user.roles.map((role) => role.toUpperCase());
  if (roles.includes('ADMIN') || roles.includes('ADMINISTRADOR')) return true;
  if (user.permisos.includes('ventas.sucursales_todas')) return true;
  return roles.includes('ENCARGADO_SUCURSAL') && user.id_sucursal != null;
}

/** Qué le conviene hacer al encargado según el motivo del conflicto. */
export function syncConflictAdvice(code: string): string {
  switch (code) {
    case 'STOCK_INSUFICIENTE':
      return 'Si la prenda sí estaba en la tienda, ajusta el inventario y reaplica. ' +
        'Si no, anúlala y anota cómo se resolvió con el cliente.';
    case 'CONFLICTO_COMERCIAL':
      return 'Revisa la reserva o el precio en conflicto; luego reaplica o anula.';
    case 'ERROR_INTERNO':
      return 'Fue un error del servidor: intenta reaplicarla.';
    case 'DATOS_INVALIDOS':
      return 'No se puede reaplicar tal cual. Anúlala; el vendedor puede volver a cargar ' +
        'la venta corregida.';
    default:
      return 'Revisa la operación y decide si reaplicarla o anularla.';
  }
}

export interface LocalSyncBatch extends OfflineScope {
  id_lote: string;
  deviceId: string;
  estado: string;
  total_operaciones: number;
  total_aplicadas: number;
  total_conflictos: number;
  total_rechazadas: number;
  created_at: string;
  confirmed_at: string | null;
}

export interface SyncDeviceResponse {
  id_dispositivo: string;
  nombre: string;
  plataforma: 'PWA' | 'ANDROID' | 'IOS';
  version_app: string | null;
  id_sucursal: number | null;
  estado: string;
  ultima_sincronizacion: string | null;
}

export interface SyncOperationResponse {
  id_operacion: string;
  tipo: OfflineOperationType;
  estado: OfflineOperationStatus;
  resultado: Record<string, unknown> | null;
  codigo_error: string | null;
  mensaje_error: string | null;
  procesada_at: string | null;
}

export interface SyncBatchResponse {
  id_lote: string;
  id_dispositivo: string;
  estado: string;
  recibido_at: string;
  procesado_at: string | null;
  confirmado_at: string | null;
  total_operaciones: number;
  total_aplicadas: number;
  total_conflictos: number;
  total_rechazadas: number;
  operaciones: SyncOperationResponse[];
}
