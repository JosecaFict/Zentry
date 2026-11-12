import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { expect, it, vi } from 'vitest';
import { AuthService } from '../../core/auth/auth.service';
import { ConnectivityService } from '../../core/offline/connectivity.service';
import { OfflineDatabaseService } from '../../core/offline/offline-database.service';
import { PendingOfflineOperation } from '../../core/offline/offline.models';
import { OfflineAutoSyncService } from '../../core/offline/offline-auto-sync.service';
import { OfflineSyncService } from '../../core/offline/offline-sync.service';
import { CatalogService } from '../../core/services/catalog.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';
import { OfflineOperationsAdmin } from './offline-operations-admin';

function setup(restoredBranchIds?: number[]) {
  const online = signal(false);
  const synchronize = vi.fn().mockResolvedValue(null);
  const saved: PendingOfflineOperation[] = [];
  const branches = vi.fn(() => of([]));
  const openScope = vi.fn();
  const autoSync = { revision: signal(0), syncNow: vi.fn().mockResolvedValue(undefined), refreshAlerts: vi.fn() };
  const customers = [{ id_cliente: 8, nombre_completo: 'Cliente de prueba', correo: '', telefono: null }];
  const queueOperation = vi.fn(async (_type: string, payload: Record<string, unknown>) => {
    const operation = { id_operacion: 'venta-1', tipo: 'VENTA', estado: 'PENDIENTE', payload } as PendingOfflineOperation;
    saved.push(operation);
    return operation;
  });
  TestBed.configureTestingModule({
    imports: [OfflineOperationsAdmin],
    providers: [
      { provide: AuthService, useValue: { currentUser: () => ({ id_usuario: 2 }) } },
      { provide: OfflineAutoSyncService, useValue: autoSync },
      { provide: TenantContextService, useValue: { tenant: () => ({ id_tenant: 1 }) } },
      { provide: CatalogService, useValue: { branches } },
      { provide: ConnectivityService, useValue: { online } },
      { provide: OfflineSyncService, useValue: { synchronizePending: synchronize } },
      { provide: OfflineDatabaseService, useValue: {
        listCatalog: async () => [],
        currentMeta: async () => null,
        operationSummary: async () => ({ pending: 0, conflicts: 0, rejected: 0 }),
        queuedQuantities: async () => ({}),
        recentOperations: async () => saved,
        listCustomers: async () => customers,
        queueOperation,
        openScope,
        savedBranchIds: vi.fn().mockResolvedValue(restoredBranchIds ?? []),
      } },
    ],
  }).overrideComponent(OfflineOperationsAdmin, { set: { template: '' } });

  const fixture = TestBed.createComponent(OfflineOperationsAdmin);
  const component = fixture.componentInstance;
  fixture.detectChanges();
  if (!restoredBranchIds) component.selectedBranchId.set(3);
  return { fixture, component, online, synchronize, queueOperation, customers, branches, openScope, autoSync };
}

it('recovers the last saved branch without requesting the network', async () => {
  const key = 'zentry_offline_branches_1_2';
  localStorage.setItem(key, JSON.stringify({
    selected: 4,
    branches: [{ id_sucursal: 4, nombre: 'Central', direccion: '' }],
  }));
  try {
    const { component, branches, openScope } = setup([3, 4]);
    await vi.waitFor(() => expect(component.loadingBranches()).toBe(false));
    expect(branches).not.toHaveBeenCalled();
    expect(openScope).toHaveBeenCalledExactlyOnceWith({ tenantId: 1, userId: 2, branchId: 4 });
    expect(component.selectedBranch()?.nombre).toBe('Central');
  } finally {
    localStorage.removeItem(key);
  }
});

it('opens a previously downloaded branch without a saved display name', async () => {
  const { component, branches, openScope } = setup([3]);
  await vi.waitFor(() => expect(component.loadingBranches()).toBe(false));
  expect(branches).not.toHaveBeenCalled();
  expect(openScope).toHaveBeenCalledExactlyOnceWith({ tenantId: 1, userId: 2, branchId: 3 });
  expect(component.selectedBranch()?.nombre).toBe('Sucursal #3');
});

it('asks the global auto-sync to send the queue on reconnection', async () => {
  const { fixture, component, online, autoSync } = setup();
  component.operationSummary.set({ pending: 2, conflicts: 0, rejected: 0 });
  expect(autoSync.syncNow).not.toHaveBeenCalled();

  online.set(true);
  fixture.detectChanges();
  await vi.waitFor(() => expect(autoSync.syncNow).toHaveBeenCalledOnce());
});

it('ignores a second manual sync while one is sending', async () => {
  const { component, online, synchronize } = setup();
  online.set(true);
  let finish!: (value: null) => void;
  synchronize.mockReturnValueOnce(new Promise<null>((resolve) => { finish = resolve; }));

  const first = component.synchronizeNow();
  await component.synchronizeNow();
  expect(synchronize).toHaveBeenCalledExactlyOnceWith({ tenantId: 1, userId: 2, branchId: 3 });
  finish(null);
  await first;
  expect(component.synchronizing()).toBe(false);
});

it.each([8, null])('keeps the cash sale visible after saving with customer %s', async (customerId) => {
  const { component, queueOperation, customers } = setup();
  component.customers.set(customers);
  component.catalog.set([{
    id_variante: 4, sku: 'DEMO', producto: 'Polo', talla: 'M', color: 'Azul',
    precio: '100.00', stock_fisico: 2, stock_reservado: 0, stock_disponible: 2, updated_at: null,
  }]);
  component.cartQuantities.set({ 4: 1 });
  component.selectedCustomerId.set(customerId);

  await component.queueOfflineSale();

  expect(queueOperation).toHaveBeenCalledExactlyOnceWith('VENTA', expect.objectContaining({
    id_cliente: customerId, registrar_efectivo: true, metodo_pago: 'EFECTIVO',
    precios_cobrados: { 4: 10000 }, total_cobrado_centavos: 10000,
  }));
  expect(component.cartLines()).toHaveLength(0);
  const sale = component.latestOperation();
  expect(sale.estado).toBe('PENDIENTE');
  expect(component.operationCustomerLabel(sale)).toBe(customerId ? 'Cliente de prueba' : 'Sin cliente registrado');
});

function rejected(code: string): PendingOfflineOperation {
  return {
    id_operacion: 'venta-rechazada', tipo: 'VENTA', estado: 'RECHAZADA', codigo_error: code,
    mensaje_error: 'Precio inválido', payload: { id_cliente: 8, items: [
      { id_variante: 4, cantidad: 3 }, { id_variante: 99, cantidad: 1 },
    ] },
  } as unknown as PendingOfflineOperation;
}

it('reloads a sale rejected for invalid data into the cart as a new operation', async () => {
  const { component } = setup();
  const markReviewed = vi.fn().mockResolvedValue(undefined);
  Object.assign(TestBed.inject(OfflineDatabaseService), { markReviewed });
  component.catalog.set([{
    id_variante: 4, sku: 'DEMO', producto: 'Polo', talla: 'M', color: 'Azul',
    precio: '100.00', stock_fisico: 2, stock_reservado: 0, stock_disponible: 2, updated_at: null,
  }]);

  await component.reloadIntoCart(rejected('DATOS_INVALIDOS'));

  expect(markReviewed).toHaveBeenCalledExactlyOnceWith('venta-rechazada');
  // Se limita al stock disponible y la variante que ya no existe se omite.
  expect(component.cartQuantities()).toEqual({ 4: 2 });
  expect(component.selectedCustomerId()).toBe(8);
  expect(component.message()).toContain('1 ya no están disponibles');
});

it('does not reload operations that a manager must resolve', async () => {
  const { component } = setup();
  const markReviewed = vi.fn();
  Object.assign(TestBed.inject(OfflineDatabaseService), { markReviewed });
  const conflict = rejected('STOCK_INSUFICIENTE');

  expect(component.canReload(conflict)).toBe(false);
  await component.reloadIntoCart(conflict);

  expect(markReviewed).not.toHaveBeenCalled();
  expect(component.cartQuantities()).toEqual({});
  expect(component.failureReason(conflict)).toContain('No había stock');
});
