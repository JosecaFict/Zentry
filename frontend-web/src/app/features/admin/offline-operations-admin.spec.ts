import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { expect, it, vi } from 'vitest';
import { AuthService } from '../../core/auth/auth.service';
import { ConnectivityService } from '../../core/offline/connectivity.service';
import { OfflineDatabaseService } from '../../core/offline/offline-database.service';
import { OfflineSyncService } from '../../core/offline/offline-sync.service';
import { CatalogService } from '../../core/services/catalog.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';
import { OfflineOperationsAdmin } from './offline-operations-admin';

it('starts sending on reconnection and ignores a second request while sending', async () => {
  const online = signal(false);
  const synchronize = vi.fn().mockResolvedValue(null);
  TestBed.configureTestingModule({
    imports: [OfflineOperationsAdmin],
    providers: [
      { provide: AuthService, useValue: { currentUser: () => ({ id_usuario: 2 }) } },
      { provide: TenantContextService, useValue: { tenant: () => ({ id_tenant: 1 }) } },
      { provide: CatalogService, useValue: { branches: () => of([]) } },
      { provide: ConnectivityService, useValue: { online } },
      { provide: OfflineSyncService, useValue: { synchronizePending: synchronize } },
      { provide: OfflineDatabaseService, useValue: {
        listCatalog: async () => [],
        currentMeta: async () => null,
        operationSummary: async () => ({ pending: 0, conflicts: 0, rejected: 0 }),
        queuedQuantities: async () => ({}),
        recentOperations: async () => [],
        listCustomers: async () => [],
      } },
    ],
  }).overrideComponent(OfflineOperationsAdmin, { set: { template: '' } });

  const fixture = TestBed.createComponent(OfflineOperationsAdmin);
  const component = fixture.componentInstance;
  fixture.detectChanges();
  component.selectedBranchId.set(3);
  component.operationSummary.set({ pending: 2, conflicts: 0, rejected: 0 });
  expect(synchronize).not.toHaveBeenCalled();

  let finish!: (value: null) => void;
  synchronize.mockReturnValueOnce(new Promise<null>((resolve) => { finish = resolve; }));
  online.set(true);
  fixture.detectChanges();
  await vi.waitFor(() => expect(synchronize).toHaveBeenCalledOnce());
  await component.synchronizeNow();
  expect(synchronize).toHaveBeenCalledExactlyOnceWith({ tenantId: 1, userId: 2, branchId: 3 });
  finish(null);
  await vi.waitFor(() => expect(component.synchronizing()).toBe(false));
});
