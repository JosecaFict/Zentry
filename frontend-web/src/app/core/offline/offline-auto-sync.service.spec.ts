import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { expect, it, vi } from 'vitest';

import { AuthService } from '../auth/auth.service';
import { TenantContextService } from '../tenant/tenant-context.service';
import { ConnectivityService } from './connectivity.service';
import { OfflineAutoSyncService } from './offline-auto-sync.service';
import { OfflineDatabaseService } from './offline-database.service';
import { OfflineSyncService } from './offline-sync.service';
import { PendingOfflineOperation } from './offline.models';
import { SyncApiService } from './sync-api.service';

const scope = { tenantId: 1, userId: 2, branchId: 3 };

function setup(options: { permisos?: string[]; online?: boolean; roles?: string[] } = {}) {
  const failed = { id_operacion: 'venta-2', estado: 'CONFLICTO' } as PendingOfflineOperation;
  const database = {
    scope: signal(scope),
    savedBranchIds: vi.fn().mockResolvedValue([3]),
    openScope: vi.fn(),
    unresolvedFailedIds: vi.fn().mockResolvedValue(['venta-2', 'venta-3']),
    applyServerResolution: vi.fn().mockResolvedValue(undefined),
    unreviewedFailures: vi.fn().mockResolvedValue([failed]),
  };
  const synchronization = {
    synchronizePending: vi.fn()
      .mockResolvedValueOnce({ id_lote: 'l1' })
      .mockResolvedValueOnce({ id_lote: 'l2' })
      .mockResolvedValue(null),
    prepare: vi.fn().mockResolvedValue(undefined),
  };
  const api = {
    conflicts: vi.fn(() => of([{}, {}])),
    operationStatus: vi.fn(() => of([
      { id_operacion: 'venta-2', accion: null, resolucion: null },
      { id_operacion: 'venta-3', accion: 'ANULADA', resolucion: 'Se devolvió el dinero' },
    ])),
  };
  TestBed.configureTestingModule({
    providers: [
      { provide: AuthService, useValue: { currentUser: signal({
        id_usuario: 2,
        roles: options.roles ?? ['CAJERO'],
        permisos: options.permisos ?? ['inventario.ver'],
        id_sucursal: 3,
      }) } },
      { provide: TenantContextService, useValue: { tenant: () => ({ id_tenant: 1 }) } },
      { provide: ConnectivityService, useValue: {
        online: () => options.online ?? true, start: vi.fn(), checkedAt: signal(null),
      } },
      { provide: OfflineDatabaseService, useValue: database },
      { provide: OfflineSyncService, useValue: synchronization },
      { provide: SyncApiService, useValue: api },
    ],
  });
  return { service: TestBed.inject(OfflineAutoSyncService), database, synchronization, api, failed };
}

it('sends every pending batch, refreshes stock and reads the manager decision', async () => {
  const { service, database, synchronization, failed } = setup();

  await service.syncNow();

  expect(synchronization.synchronizePending).toHaveBeenCalledTimes(3);
  expect(synchronization.prepare).toHaveBeenCalledExactlyOnceWith(scope);
  expect(database.applyServerResolution).toHaveBeenCalledExactlyOnceWith(
    'venta-3', 'ANULADA', 'Se devolvió el dinero',
  );
  expect(service.failures()).toEqual([failed]);
  expect(service.revision()).toBe(1);
});

it('counts pending conflicts only for branch managers', async () => {
  const manager = setup({ roles: ['ENCARGADO_SUCURSAL'] });
  await manager.service.syncNow();
  expect(manager.service.pendingConflicts()).toBe(2);
});

it('offline only recalculates alerts, without calling the server', async () => {
  const { service, synchronization, api } = setup({ online: false });

  await service.syncNow();

  expect(synchronization.synchronizePending).not.toHaveBeenCalled();
  expect(api.operationStatus).not.toHaveBeenCalled();
  expect(service.failures()).toHaveLength(1);
  expect(service.revision()).toBe(0);
});

it('does nothing for users without offline access', async () => {
  const { service, synchronization } = setup({ permisos: [] });
  await service.syncNow();
  expect(synchronization.synchronizePending).not.toHaveBeenCalled();
  expect(service.failures()).toEqual([]);
});
