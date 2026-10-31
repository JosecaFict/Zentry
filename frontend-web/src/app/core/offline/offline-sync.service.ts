import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ConnectivityService } from './connectivity.service';
import { OfflineDatabaseService } from './offline-database.service';
import { OfflineScope, SyncBatchResponse } from './offline.models';
import { SyncApiService } from './sync-api.service';
import { CommerceService } from '../services/commerce.service';

export type OfflineSyncState = 'INACTIVO' | 'PREPARANDO' | 'LISTO' | 'SINCRONIZANDO' | 'ERROR';

@Injectable({ providedIn: 'root' })
export class OfflineSyncService {
  private readonly api = inject(SyncApiService);
  private readonly database = inject(OfflineDatabaseService);
  private readonly connectivity = inject(ConnectivityService);
  private readonly commerce = inject(CommerceService);
  private readonly stateSignal = signal<OfflineSyncState>('INACTIVO');
  private readonly errorSignal = signal<string | null>(null);

  readonly state = this.stateSignal.asReadonly();
  readonly error = this.errorSignal.asReadonly();

  async prepare(scope: OfflineScope): Promise<void> {
    this.stateSignal.set('PREPARANDO');
    this.errorSignal.set(null);
    try {
      const meta = await this.database.openScope(scope);
      if (!this.connectivity.online()) {
        this.stateSignal.set('LISTO');
        return;
      }
      await firstValueFrom(
        this.api.registerDevice({
          id_dispositivo: meta.deviceId,
          nombre: this.deviceName(),
          plataforma: 'PWA',
          version_app: '1.0.0',
          id_sucursal: scope.branchId,
        }),
      );
      const catalog = await firstValueFrom(this.api.catalog(scope.branchId));
      await this.database.replaceCatalog(catalog);
      const customers = await firstValueFrom(this.commerce.adminCustomers({ estado: 'ACTIVO' }));
      await this.database.replaceCustomers(
        customers.filter((customer) => customer.estado === 'ACTIVO').map((customer) => ({
          id_cliente: customer.id_cliente,
          nombre_completo: customer.nombre_completo,
          correo: customer.correo,
          telefono: customer.telefono,
        })),
      );
      this.stateSignal.set('LISTO');
    } catch (error) {
      this.fail(error, 'No se pudo preparar el modo sin conexión.');
      throw error;
    }
  }

  async synchronizePending(): Promise<SyncBatchResponse | null> {
    if (!this.connectivity.online()) {
      throw new Error('No hay conexión para sincronizar las operaciones pendientes.');
    }
    const scope = this.database.scope();
    if (!scope) throw new Error('Primero debe seleccionarse una sucursal para sincronizar.');

    const meta = await this.database.openScope(scope);
    const operations = await this.database.pendingOperations();
    if (!operations.length) return null;

    const batchId = crypto.randomUUID();
    this.stateSignal.set('SINCRONIZANDO');
    this.errorSignal.set(null);
    await this.database.markBatchSending(
      batchId,
      operations.map((operation) => operation.id_operacion),
    );
    try {
      const submitted = await firstValueFrom(
        this.api.submitBatch(batchId, meta.deviceId, operations),
      );
      await this.database.applyBatchResponse(submitted);
      const confirmed = await firstValueFrom(this.api.confirmBatch(batchId, meta.deviceId));
      await this.database.applyBatchResponse(confirmed);
      this.stateSignal.set('LISTO');
      return confirmed;
    } catch (error) {
      const message = this.messageFrom(error, 'No se pudo completar la sincronización.');
      await this.database.releaseBatch(batchId, message);
      this.fail(error, message);
      throw error;
    }
  }

  private deviceName(): string {
    const browser = navigator.platform || 'Navegador';
    return `Zentry PWA · ${browser}`;
  }

  private fail(error: unknown, fallback: string): void {
    this.errorSignal.set(this.messageFrom(error, fallback));
    this.stateSignal.set('ERROR');
  }

  private messageFrom(error: unknown, fallback: string): string {
    return error instanceof Error && error.message ? error.message : fallback;
  }
}
