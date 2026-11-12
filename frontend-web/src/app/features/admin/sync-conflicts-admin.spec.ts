import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { expect, it, vi } from 'vitest';

import { AuthService } from '../../core/auth/auth.service';
import { SyncConflict } from '../../core/offline/offline.models';
import { OfflineAutoSyncService } from '../../core/offline/offline-auto-sync.service';
import { SyncApiService } from '../../core/offline/sync-api.service';
import { SyncConflictsAdmin } from './sync-conflicts-admin';

function conflict(overrides: Partial<SyncConflict> = {}): SyncConflict {
  return {
    id_conflicto: 11,
    id_operacion: '7c9e6679-7425-40de-944b-e07fc1f90ae7',
    tipo_operacion: 'VENTA',
    codigo: 'STOCK_INSUFICIENTE',
    mensaje: 'Stock insuficiente para completar la venta',
    estado: 'PENDIENTE',
    id_sucursal: 1,
    id_vendedor: 9,
    vendedor: 'Ana Vendedora',
    items: [{ id_variante: 2, cantidad: 1, descripcion: 'Polo básico M Negro' }],
    total_cobrado_centavos: 9990,
    fecha_cliente: '2026-11-11T14:30:00Z',
    created_at: '2026-11-11T15:00:00Z',
    puede_reaplicar: true,
    accion: null,
    resolucion: null,
    resuelto_por: null,
    resuelto_at: null,
    ...overrides,
  };
}

function setup(roles = ['ENCARGADO_SUCURSAL'], items = [conflict()]) {
  const conflicts = vi.fn(() => of(items));
  const resolveConflict = vi.fn();
  TestBed.configureTestingModule({
    imports: [SyncConflictsAdmin],
    providers: [
      { provide: AuthService, useValue: {
        currentUser: () => ({ roles, permisos: ['inventario.ver'], id_sucursal: 1 }),
      } },
      { provide: SyncApiService, useValue: { conflicts, resolveConflict } },
      { provide: OfflineAutoSyncService, useValue: { refreshPendingConflicts: vi.fn() } },
    ],
  });
  const fixture = TestBed.createComponent(SyncConflictsAdmin);
  fixture.detectChanges();
  return { fixture, component: fixture.componentInstance, conflicts, resolveConflict };
}

it('shows seller, garments, amount, reason and actions of a pending conflict', async () => {
  const { fixture, conflicts } = setup();
  await fixture.whenStable();
  fixture.detectChanges();
  const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

  expect(conflicts).toHaveBeenCalledExactlyOnceWith('TODOS');
  expect(text).toContain('Pendientes (1)');
  expect(text).toContain('Venta de Ana Vendedora');
  expect(text).toContain('1 × Polo básico M Negro');
  expect(text).toContain('99.90');
  expect(text).toContain('No había stock');
  expect(text).toContain('Reaplicar');
});

it('does not call the server for a cashier', () => {
  const { fixture, conflicts } = setup(['CAJERO']);
  expect(conflicts).not.toHaveBeenCalled();
  expect((fixture.nativeElement as HTMLElement).textContent).toContain('Solo para encargados');
});

it('cancelling requires a note and moves the conflict to history', async () => {
  const { fixture, component, resolveConflict } = setup();
  await fixture.whenStable();
  const pending = component.pending()[0];
  resolveConflict.mockReturnValue(of(conflict({
    estado: 'DESCARTADO', accion: 'ANULADA', resolucion: 'Se devolvió el dinero',
    resuelto_por: 'Luis Encargado', resuelto_at: '2026-11-11T16:00:00Z', puede_reaplicar: false,
  })));

  component.startCancel(pending);
  await component.resolve(pending, 'ANULAR');
  expect(resolveConflict).not.toHaveBeenCalled();

  component.note.set('  Se devolvió el dinero ');
  await component.resolve(pending, 'ANULAR');

  expect(resolveConflict).toHaveBeenCalledExactlyOnceWith(11, 'ANULAR', 'Se devolvió el dinero');
  expect(component.pending()).toHaveLength(0);
  component.tab.set('history');
  expect(component.visible()[0].resolucion).toBe('Se devolvió el dinero');
});

it('keeps the conflict pending and explains why when reapplying still fails', async () => {
  const { fixture, component, resolveConflict } = setup();
  await fixture.whenStable();
  resolveConflict.mockReturnValue(throwError(() => new HttpErrorResponse({
    status: 409,
    error: { detail: 'Todavía no se puede registrar: sin stock.' },
  })));

  await component.resolve(component.pending()[0], 'REAPLICAR');

  expect(component.pending()).toHaveLength(1);
  expect(component.isError()).toBe(true);
  expect(component.message()).toContain('Todavía no se puede registrar');
});
