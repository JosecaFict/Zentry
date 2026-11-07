import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { API_BASE_URL } from '../config/api.config';
import { CommerceService } from './commerce.service';

describe('CommerceService', () => {
  let service: CommerceService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CommerceService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('adds a selected variant to the customer cart', () => {
    service.addCartItem(42, 2).subscribe();

    const request = http.expectOne(`${API_BASE_URL}/cart/items`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ id_variante: 42, cantidad: 2 });
    request.flush({ id_carrito: 1, estado: 'ACTIVO', items: [], total: 0 });
  });

  it('requests a backend shipping quote with branch and address', () => {
    service.quoteShipping(3, 9).subscribe();

    const request = http.expectOne(`${API_BASE_URL}/shipping-quotes`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ id_sucursal: 3, id_direccion: 9 });
    request.flush({});
  });

  it('starts and verifies a Stripe Checkout session through FastAPI', () => {
    service.checkout({ id_sucursal: 1, modalidad_entrega: 'RETIRO_SUCURSAL' }).subscribe();

    const checkout = http.expectOne(`${API_BASE_URL}/checkout`);
    expect(checkout.request.method).toBe('POST');
    checkout.flush({
      session_id: 'cs_test_capricho',
      checkout_url: 'https://checkout.stripe.com/test',
      expires_at: '2026-09-10T15:00:00Z',
    });

    service.checkoutStatus('cs_test_capricho').subscribe();
    const status = http.expectOne(`${API_BASE_URL}/checkout/cs_test_capricho/status`);
    expect(status.request.method).toBe('GET');
    status.flush({ status: 'PAGADO', message: 'Confirmado', order: null });
    http.expectOne(`${API_BASE_URL}/cart`).flush({ items: [], total: '0' });
  });

  it('keeps the total quantity in sync when adding, changing, removing and clearing', () => {
    service.setCartOwner('7:1');
    service.cart().subscribe();
    http.expectOne(`${API_BASE_URL}/cart`).flush({ items: [{ cantidad: 2 }, { cantidad: 3 }] });
    expect(service.cartCount()).toBe(5);
    service.addCartItem(42).subscribe();
    http.expectOne(`${API_BASE_URL}/cart/items`).flush({ items: [{ cantidad: 3 }, { cantidad: 3 }] });
    expect(service.cartCount()).toBe(6);
    service.updateCartItem(1, 1).subscribe();
    http.expectOne(`${API_BASE_URL}/cart/items/1`).flush({ items: [{ cantidad: 1 }, { cantidad: 3 }] });
    expect(service.cartCount()).toBe(4);
    service.removeCartItem(1).subscribe();
    http.expectOne(`${API_BASE_URL}/cart/items/1/remove`).flush({ items: [{ cantidad: 3 }] });
    expect(service.cartCount()).toBe(3);
    service.clearCart().subscribe();
    http.expectOne(`${API_BASE_URL}/cart/clear`).flush({ items: [] });
    expect(service.cartCount()).toBe(0);
  });

  it('ignores late responses from another user or tenant and stale initial loads', () => {
    service.setCartOwner('7:1');
    service.cart().subscribe();
    const oldLoad = http.expectOne(`${API_BASE_URL}/cart`);
    service.addCartItem(42).subscribe();
    http.expectOne(`${API_BASE_URL}/cart/items`).flush({ items: [{ cantidad: 2 }] });
    oldLoad.flush({ items: [{ cantidad: 1 }] });
    expect(service.cartCount()).toBe(2);
    service.addCartItem(43).subscribe();
    const oldMutation = http.expectOne(`${API_BASE_URL}/cart/items`);
    service.setCartOwner('8:2');
    expect(service.cartCount()).toBe(0);
    oldMutation.flush({ items: [{ cantidad: 3 }] });
    expect(service.cartCount()).toBe(0);
  });

  it('updates an existing delivery address through FastAPI', () => {
    service.updateAddress(9, { direccion: 'Av. Principal 50' }).subscribe();

    const request = http.expectOne(`${API_BASE_URL}/addresses/9`);
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ direccion: 'Av. Principal 50' });
    request.flush({});
  });

  it('uses supplier history filters and pagination', () => {
    service.supplierPurchaseHistory({ proveedor: 8, page: 2, page_size: 25 }).subscribe();

    const request = http.expectOne(
      (candidate) => candidate.url === `${API_BASE_URL}/supplier-purchase-history`,
    );
    expect(request.request.params.get('proveedor')).toBe('8');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('25');
    request.flush({ items: [], total: 0, page: 2, page_size: 25 });
  });

  it('downloads the official PDF invoice for an order', () => {
    let receivedBlob: Blob | null = null;
    service.orderInvoice(12).subscribe((blob) => {
      receivedBlob = blob;
    });

    const request = http.expectOne(`${API_BASE_URL}/orders/12/invoice`);
    expect(request.request.method).toBe('GET');
    expect(request.request.responseType).toBe('blob');
    const mockBlob = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
    request.flush(mockBlob);

    expect(receivedBlob).toBeTruthy();
  });

  it('downloads the official PDF invoice for a direct POS sale', () => {
    let receivedBlob: Blob | null = null;
    service.saleInvoice(45).subscribe((blob) => {
      receivedBlob = blob;
    });

    const request = http.expectOne(`${API_BASE_URL}/sales/45/invoice`);
    expect(request.request.method).toBe('GET');
    expect(request.request.responseType).toBe('blob');
    const mockBlob = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
    request.flush(mockBlob);

    expect(receivedBlob).toBeTruthy();
  });

  it('quick creates a customer at POS counter', () => {
    service
      .quickCreateCustomer({
        nombres: 'Ana',
        apellidos: 'Silva',
        ci: '778899',
        correo: 'ana@example.com',
      })
      .subscribe();

    const request = http.expectOne(`${API_BASE_URL}/customers/quick`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      nombres: 'Ana',
      apellidos: 'Silva',
      ci: '778899',
      correo: 'ana@example.com',
    });
    request.flush({ id_cliente: 7, nombre_completo: 'Ana Silva' });
  });

  it('posts confirm delivery for an order', () => {
    let result: any = null;
    service.confirmDelivery(22).subscribe((res) => {
      result = res;
    });

    const request = http.expectOne(`${API_BASE_URL}/orders/22/confirm-delivery`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({});
    request.flush({ id_pedido: 22, estado: 'ENTREGADO' });

    expect(result).toEqual({ id_pedido: 22, estado: 'ENTREGADO' });
  });

  it('updates return status with string state', () => {
    service.updateReturn(5, 'APROBADA').subscribe();

    const request = http.expectOne(`${API_BASE_URL}/admin/returns/5/status`);
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ estado: 'APROBADA' });
    request.flush({ id_devolucion: 5, estado: 'APROBADA' });
  });

  it('updates return status with full ReturnStatusUpdatePayload', () => {
    service
      .updateReturn(5, {
        estado: 'COMPLETADA',
        items: [{ id_detalle_devolucion: 10, estado_prenda: 'NO_APTA' }],
        observaciones: 'Prenda con mancha',
      })
      .subscribe();

    const request = http.expectOne(`${API_BASE_URL}/admin/returns/5/status`);
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({
      estado: 'COMPLETADA',
      items: [{ id_detalle_devolucion: 10, estado_prenda: 'NO_APTA' }],
      observaciones: 'Prenda con mancha',
    });
    request.flush({ id_devolucion: 5, estado: 'COMPLETADA' });
  });
});


