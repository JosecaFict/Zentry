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
