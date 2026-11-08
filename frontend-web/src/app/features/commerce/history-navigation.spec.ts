import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of } from 'rxjs';
import { vi } from 'vitest';
import { Sale } from '../../core/models/commerce.model';
import { CommerceService } from '../../core/services/commerce.service';
import { ApiErrorService } from '../../core/services/api-error.service';
import { HistoryPage } from './commerce-pages';

describe('Customer returns navigation', () => {
  it('saves the exact requested variant and displays the original color and size', async () => {
    const original = { id_detalle: 5, id_variante: 101, producto: 'Polo clásico', talla: 'S', color: 'Azul marino', cantidad: 1 };
    const sale = { id_venta: 10, id_sucursal: 1, items: [original] } as Sale;
    const commerce = {
      purchaseHistory: () => of([]), reservations: () => of([]), returns: () => of([]),
      customerReturnOptions: vi.fn(() => of([{ id_variante: 202, id_producto: 20, producto: 'Polo clásico', talla: 'M', color: 'Azul marino', stock_disponible: 4 }])),
      createReturn: vi.fn(() => of({ id_devolucion: 3, id_venta: 10, tipo_solicitud: 'CAMBIO_TALLA', estado: 'PENDIENTE', items: [] })),
    };
    TestBed.configureTestingModule({ providers: [
      provideRouter([{ path: 'historial', component: HistoryPage }]),
      { provide: CommerceService, useValue: commerce },
      { provide: ApiErrorService, useValue: { message: (_error: unknown, fallback: string) => fallback } },
    ] });
    const harness = await RouterTestingHarness.create();
    const page = await harness.navigateByUrl('/historial', HistoryPage);
    page.startReturn(sale);
    expect(commerce.customerReturnOptions).toHaveBeenCalledWith(10, 5, 'CAMBIO_TALLA');
    expect(page.returnForm.valid).toBe(false);
    page.returnForm.patchValue({ id_variante_solicitada: '202', motivo: 'Talla pequeña', requisitos_aceptados: true });
    page.submitReturn();
    expect(commerce.createReturn).toHaveBeenCalledWith(expect.objectContaining({ items: [{ id_detalle_venta: 5, cantidad: 1, id_variante_solicitada: 202 }] }));
  });
  it('opens returns from the account shortcut and lets the customer choose a purchase', async () => {
    TestBed.configureTestingModule({ providers: [
      provideRouter([{ path: 'historial', component: HistoryPage }]),
      { provide: CommerceService, useValue: { purchaseHistory: () => of([]), reservations: () => of([]), returns: () => of([]) } },
      { provide: ApiErrorService, useValue: { message: (_error: unknown, fallback: string) => fallback } },
    ] });
    const harness = await RouterTestingHarness.create();
    const page = await harness.navigateByUrl('/historial?seccion=devoluciones', HistoryPage);
    expect(page.tab()).toBe('devoluciones');
    expect(harness.routeNativeElement?.querySelector('h1')?.textContent).toBe('Cambios y devoluciones');
    const requestButton = harness.routeNativeElement?.querySelector('.history-return-actions button') as HTMLButtonElement;
    expect(requestButton.textContent).toContain('Solicitar cambio o devolución');
    requestButton.click();
    harness.detectChanges();
    expect(page.tab()).toBe('compras');
    expect(harness.routeNativeElement?.textContent).toContain('Sin compras');
    await harness.navigateByUrl('/historial?seccion=no-valida', HistoryPage);
    expect(page.tab()).toBe('compras');
  });
});
