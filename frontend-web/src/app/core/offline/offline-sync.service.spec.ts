import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { expect, it, vi } from 'vitest';
import { ConnectivityService } from './connectivity.service';
import { OfflineDatabaseService } from './offline-database.service';
import { OfflineSyncService } from './offline-sync.service';
import { SyncApiService } from './sync-api.service';
import { CommerceService } from '../services/commerce.service';

it('keeps an unconfirmed batch intact and resubmits its original UUID', async () => {
  const scope = { tenantId: 1, userId: 2, branchId: 3 };
  const operations = [{ id_operacion: 'venta-1' }, { id_operacion: 'reserva-1' }];
  const confirmed = { id_lote: 'lote-original', confirmado_at: '2026-11-08T12:00:00Z' };
  const database = {
    scope: () => scope,
    currentMeta: vi.fn().mockResolvedValue({ deviceId: 'device-1' }),
    claimSyncBatch: vi.fn().mockResolvedValue({ id: 'lote-original', operations }),
    applyBatchResponse: vi.fn().mockResolvedValue(undefined),
  };
  const api = {
    submitBatch: vi.fn(() => of({})),
    confirmBatch: vi.fn()
      .mockReturnValueOnce(throwError(() => new Error('Conexión interrumpida')))
      .mockReturnValueOnce(of(confirmed)),
  };
  TestBed.configureTestingModule({
    providers: [
      { provide: OfflineDatabaseService, useValue: database },
      { provide: ConnectivityService, useValue: { online: () => true } },
      { provide: SyncApiService, useValue: api },
      { provide: CommerceService, useValue: {} },
    ],
  });
  const service = TestBed.inject(OfflineSyncService);
  await expect(service.synchronizePending()).rejects.toThrow('Conexión interrumpida');
  expect(database.applyBatchResponse).not.toHaveBeenCalled();
  await expect(service.synchronizePending()).resolves.toEqual(confirmed);
  expect(api.submitBatch.mock.calls).toEqual([
    ['lote-original', 'device-1', operations],
    ['lote-original', 'device-1', operations],
  ]);
  expect(database.applyBatchResponse).toHaveBeenCalledExactlyOnceWith(confirmed);
});
