import { Injectable, signal } from '@angular/core';
import Dexie, { Table } from 'dexie';

import {
  CatalogSnapshot,
  LocalSyncBatch,
  OfflineCatalogItem,
  OfflineOperationType,
  OfflineScope,
  OfflineSyncMeta,
  PendingOfflineOperation,
  SyncBatchResponse,
} from './offline.models';

class ZentryOfflineDatabase extends Dexie {
  syncMeta!: Table<OfflineSyncMeta, string>;
  catalogItems!: Table<OfflineCatalogItem, number>;
  pendingOperations!: Table<PendingOfflineOperation, string>;
  syncBatches!: Table<LocalSyncBatch, string>;

  constructor(name: string) {
    super(name);
    this.version(1).stores({
      syncMeta: '&key, tenantId, userId, branchId, deviceId',
      catalogItems: '&id_variante, sku, producto, talla, color, stock_disponible, updated_at',
      pendingOperations:
        '&id_operacion, estado, tipo, created_at, updated_at, id_lote, [estado+created_at]',
      syncBatches: '&id_lote, estado, created_at, confirmed_at',
    });
  }
}

@Injectable({ providedIn: 'root' })
export class OfflineDatabaseService {
  private database: ZentryOfflineDatabase | null = null;
  private readonly scopeState = signal<OfflineScope | null>(null);

  readonly scope = this.scopeState.asReadonly();

  async openScope(scope: OfflineScope): Promise<OfflineSyncMeta> {
    this.assertPositiveScope(scope);
    const name = this.databaseName(scope);
    if (this.database?.name !== name) {
      this.database?.close();
      this.database = new ZentryOfflineDatabase(name);
      await this.database.open();
    }
    this.scopeState.set(scope);

    const current = await this.database.syncMeta.get('scope');
    if (current) return current;

    const meta: OfflineSyncMeta = {
      key: 'scope',
      ...scope,
      deviceId: crypto.randomUUID(),
      catalogVersion: null,
      lastCatalogSyncAt: null,
      lastSuccessfulSyncAt: null,
    };
    await this.database.syncMeta.put(meta);
    return meta;
  }

  async replaceCatalog(snapshot: CatalogSnapshot): Promise<void> {
    const db = this.requireDatabase();
    const scope = this.requireScope();
    if (snapshot.id_sucursal !== scope.branchId) {
      throw new Error('El catálogo recibido pertenece a otra sucursal.');
    }
    await db.transaction('rw', db.catalogItems, db.syncMeta, async () => {
      await db.catalogItems.clear();
      if (snapshot.items.length) await db.catalogItems.bulkPut(snapshot.items);
      await db.syncMeta.update('scope', {
        catalogVersion: snapshot.version,
        lastCatalogSyncAt: snapshot.generado_at,
      });
    });
  }

  async listCatalog(): Promise<OfflineCatalogItem[]> {
    return this.requireDatabase().catalogItems.orderBy('producto').toArray();
  }

  async queueOperation(
    tipo: OfflineOperationType,
    payload: Record<string, unknown>,
  ): Promise<PendingOfflineOperation> {
    const db = this.requireDatabase();
    const scope = this.requireScope();
    const now = new Date().toISOString();
    const operation: PendingOfflineOperation = {
      ...scope,
      id_operacion: crypto.randomUUID(),
      tipo,
      fecha_cliente: now,
      payload,
      estado: 'PENDIENTE',
      intentos: 0,
      codigo_error: null,
      mensaje_error: null,
      id_lote: null,
      created_at: now,
      updated_at: now,
    };
    await db.pendingOperations.add(operation);
    return operation;
  }

  async pendingOperations(limit = 100): Promise<PendingOfflineOperation[]> {
    return this.requireDatabase()
      .pendingOperations.where('estado')
      .equals('PENDIENTE')
      .limit(limit)
      .sortBy('created_at');
  }

  async markBatchSending(idLote: string, operationIds: string[]): Promise<void> {
    const db = this.requireDatabase();
    const now = new Date().toISOString();
    await db.transaction('rw', db.pendingOperations, async () => {
      await Promise.all(
        operationIds.map((id) =>
          db.pendingOperations.update(id, {
            estado: 'ENVIANDO',
            id_lote: idLote,
            updated_at: now,
          }),
        ),
      );
    });
  }

  async applyBatchResponse(response: SyncBatchResponse): Promise<void> {
    const db = this.requireDatabase();
    const scope = this.requireScope();
    const now = new Date().toISOString();
    await db.transaction('rw', db.pendingOperations, db.syncBatches, db.syncMeta, async () => {
      for (const result of response.operaciones) {
        await db.pendingOperations.update(result.id_operacion, {
          estado: result.estado,
          codigo_error: result.codigo_error,
          mensaje_error: result.mensaje_error,
          updated_at: now,
        });
      }
      await db.syncBatches.put({
        ...scope,
        id_lote: response.id_lote,
        deviceId: response.id_dispositivo,
        estado: response.estado,
        total_operaciones: response.total_operaciones,
        total_aplicadas: response.total_aplicadas,
        total_conflictos: response.total_conflictos,
        total_rechazadas: response.total_rechazadas,
        created_at: response.recibido_at,
        confirmed_at: response.confirmado_at,
      });
      if (response.confirmado_at) {
        await db.syncMeta.update('scope', { lastSuccessfulSyncAt: response.confirmado_at });
      }
    });
  }

  async releaseBatch(idLote: string, message: string): Promise<void> {
    const db = this.requireDatabase();
    const now = new Date().toISOString();
    const operations = await db.pendingOperations.where('id_lote').equals(idLote).toArray();
    await db.transaction('rw', db.pendingOperations, async () => {
      await Promise.all(
        operations.map((operation) =>
          db.pendingOperations.update(operation.id_operacion, {
            estado: 'PENDIENTE',
            id_lote: null,
            intentos: operation.intentos + 1,
            mensaje_error: message,
            updated_at: now,
          }),
        ),
      );
    });
  }

  async clearCurrentScope(): Promise<void> {
    if (!this.database) return;
    const name = this.database.name;
    this.database.close();
    this.database = null;
    this.scopeState.set(null);
    await Dexie.delete(name);
  }

  close(): void {
    this.database?.close();
    this.database = null;
    this.scopeState.set(null);
  }

  private databaseName(scope: OfflineScope): string {
    return `zentry_offline_${scope.tenantId}_${scope.userId}_${scope.branchId}`;
  }

  private requireDatabase(): ZentryOfflineDatabase {
    if (!this.database) throw new Error('La base offline todavía no tiene un contexto abierto.');
    return this.database;
  }

  private requireScope(): OfflineScope {
    const scope = this.scopeState();
    if (!scope) throw new Error('No existe un contexto offline activo.');
    return scope;
  }

  private assertPositiveScope(scope: OfflineScope): void {
    if (scope.tenantId <= 0 || scope.userId <= 0 || scope.branchId <= 0) {
      throw new Error('Tenant, usuario y sucursal son obligatorios para operar sin conexión.');
    }
  }
}
