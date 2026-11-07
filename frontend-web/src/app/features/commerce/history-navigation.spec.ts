import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of } from 'rxjs';
import { CommerceService } from '../../core/services/commerce.service';
import { ApiErrorService } from '../../core/services/api-error.service';
import { HistoryPage } from './commerce-pages';

describe('Customer returns navigation', () => {
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
