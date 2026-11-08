import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { API_BASE_URL } from '../config/api.config';
import {
  ActivePromotionItem,
  Address,
  AdminDashboardSummary,
  AdminNotificationPage,
  AdminOperationalNotification,
  Campaign,
  CampaignCreate,
  CampaignLaunchResponse,
  CampaignUpdate,
  Cart,
  ManualNotificationPayload,
  OperationalNotification,
  Order,
  Promotion,
  PromotionCreate,
  PromotionUpdate,
  Reservation,
  ReturnRequest,
  Sale,
  ShippingQuote,
  StripeCheckoutSession,
  StripeCheckoutStatus,
  SupplierPurchaseHistoryPage,
  CustomerAdminDetail,
  CustomerAdminSummary,
  CustomerAdminUpdateRequest,
  AdminReturnCreate,
  SaleReturnInspectionResponse,
  ReturnStatusUpdatePayload,
  ReturnQuote,
  ReturnSettlementPayload,
  ReturnVariantOption,
} from '../models/commerce.model';

type Params = Record<string, string | number | boolean | null | undefined>;

@Injectable({ providedIn: 'root' })
export class CommerceService {
  private readonly http = inject(HttpClient);
  private readonly cartCountState = signal(0);
  readonly cartCount = this.cartCountState.asReadonly();
  private cartOwner = '';
  private cartRevision = 0;

  setCartOwner(owner: string): void {
    if (owner === this.cartOwner) return;
    this.cartOwner = owner;
    this.cartRevision++;
    this.cartCountState.set(0);
  }

  private trackCart(request: Observable<Cart>, mutation = false): Observable<Cart> {
    const owner = this.cartOwner;
    const revision = mutation ? ++this.cartRevision : this.cartRevision;
    return request.pipe(tap((cart) => {
      if (owner !== this.cartOwner || revision !== this.cartRevision) return;
      this.cartCountState.set((cart.items ?? []).reduce((total, item) => total + item.cantidad, 0));
    }));
  }

  private refreshCartAfterCheckout(owner: string): void {
    if (owner === this.cartOwner) this.cart().subscribe({ error: () => {} });
  }

  private params(values?: Params): HttpParams {
    let params = new HttpParams();
    Object.entries(values ?? {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    });
    return params;
  }

  cart() {
    return this.trackCart(this.http.get<Cart>(`${API_BASE_URL}/cart`));
  }
  addCartItem(id_variante: number, cantidad = 1, id_sucursal?: number | null) {
    const payload: { id_variante: number; cantidad: number; id_sucursal?: number } = {
      id_variante,
      cantidad,
    };
    if (id_sucursal) {
      payload.id_sucursal = id_sucursal;
    }
    return this.trackCart(this.http.post<Cart>(`${API_BASE_URL}/cart/items`, payload), true);
  }
  updateCartItem(id: number, cantidad: number) {
    return this.trackCart(this.http.patch<Cart>(`${API_BASE_URL}/cart/items/${id}`, { cantidad }), true);
  }
  removeCartItem(id: number) {
    return this.trackCart(this.http.post<Cart>(`${API_BASE_URL}/cart/items/${id}/remove`, {}), true);
  }
  clearCart() {
    return this.trackCart(this.http.post<Cart>(`${API_BASE_URL}/cart/clear`, {}), true);
  }
  addresses() {
    return this.http.get<Address[]>(`${API_BASE_URL}/addresses`);
  }
  createAddress(payload: object) {
    return this.http.post<Address>(`${API_BASE_URL}/addresses`, payload);
  }
  updateAddress(id: number, payload: object) {
    return this.http.patch<Address>(`${API_BASE_URL}/addresses/${id}`, payload);
  }
  deleteAddress(id: number) {
    return this.updateAddress(id, { activo: false });
  }
  reservations() {
    return this.http.get<Reservation[]>(`${API_BASE_URL}/reservations`);
  }
  createReservation(payload: object) {
    return this.http.post<Reservation>(`${API_BASE_URL}/reservations`, payload);
  }
  cancelReservation(id: number) {
    return this.http.post<Reservation>(`${API_BASE_URL}/reservations/${id}/cancel`, {});
  }
  checkout(payload: object) {
    return this.http.post<StripeCheckoutSession>(`${API_BASE_URL}/checkout`, payload);
  }
  checkoutStatus(sessionId: string) {
    const owner = this.cartOwner;
    return this.http.get<StripeCheckoutStatus>(
      `${API_BASE_URL}/checkout/${encodeURIComponent(sessionId)}/status`,
    ).pipe(tap((result) => {
      if (['PAGADO', 'CANCELADO', 'RECHAZADO'].includes(result.status)) this.refreshCartAfterCheckout(owner);
    }));
  }
  cancelCheckout(sessionId: string) {
    const owner = this.cartOwner;
    return this.http.post<void>(
      `${API_BASE_URL}/checkout/${encodeURIComponent(sessionId)}/cancel`,
      {},
    ).pipe(tap(() => this.refreshCartAfterCheckout(owner)));
  }
  orders() {
    return this.http.get<Order[]>(`${API_BASE_URL}/orders`);
  }
  orderInvoice(orderId: number) {
    return this.http.get(`${API_BASE_URL}/orders/${orderId}/invoice`, {
      responseType: 'blob',
    });
  }
  confirmDelivery(orderId: number) {
    return this.http.post<Order>(`${API_BASE_URL}/orders/${orderId}/confirm-delivery`, {});
  }
  purchaseHistory() {
    return this.http.get<Sale[]>(`${API_BASE_URL}/history/purchases`);
  }
  quoteShipping(id_sucursal: number, id_direccion: number) {
    return this.http.post<ShippingQuote>(`${API_BASE_URL}/shipping-quotes`, {
      id_sucursal,
      id_direccion,
    });
  }
  returns() {
    return this.http.get<ReturnRequest[]>(`${API_BASE_URL}/returns`);
  }
  createReturn(payload: object) {
    return this.http.post<ReturnRequest>(`${API_BASE_URL}/returns`, payload);
  }
  notifications() {
    return this.http.get<OperationalNotification[]>(`${API_BASE_URL}/notifications`);
  }
  markNotificationAsRead(id: number) {
    return this.http.patch(`${API_BASE_URL}/notifications/${id}/read`, {});
  }
  markAllNotificationsAsRead() {
    return this.http.patch(`${API_BASE_URL}/notifications/read-all`, {});
  }
  adminNotifications(params?: Params) {
    return this.http.get<AdminNotificationPage>(`${API_BASE_URL}/admin/notifications`, {
      params: this.params(params),
    });
  }
  sendManualNotification(payload: ManualNotificationPayload) {
    return this.http.post<AdminOperationalNotification>(
      `${API_BASE_URL}/admin/notifications`,
      payload,
    );
  }
  resendNotification(id: number) {
    return this.http.post<AdminOperationalNotification>(
      `${API_BASE_URL}/admin/notifications/${id}/resend`,
      {},
    );
  }
  adminReservations(params?: Params) {
    return this.http.get<Reservation[]>(`${API_BASE_URL}/admin/reservations`, {
      params: this.params(params),
    });
  }
  updateReservation(id: number, estado: string) {
    return this.http.patch<Reservation>(`${API_BASE_URL}/admin/reservations/${id}/status`, {
      estado,
    });
  }
  createPosSale(payload: object) {
    return this.http.post<Sale>(`${API_BASE_URL}/sales/pos`, payload);
  }
  adminOrders(params?: Params) {
    return this.http.get<Order[]>(`${API_BASE_URL}/admin/orders`, {
      params: this.params(params),
    });
  }
  updateOrder(id: number, estado: string) {
    return this.http.patch<Order>(`${API_BASE_URL}/admin/orders/${id}/status`, { estado });
  }
  adminReturns() {
    return this.http.get<ReturnRequest[]>(`${API_BASE_URL}/admin/returns`);
  }
  updateReturn(id: number, payload: string | ReturnStatusUpdatePayload) {
    const body = typeof payload === 'string' ? { estado: payload } : payload;
    return this.http.patch<ReturnRequest>(`${API_BASE_URL}/admin/returns/${id}/status`, body);
  }
  quoteReturn(id: number, payload: ReturnSettlementPayload) {
    return this.http.post<ReturnQuote>(`${API_BASE_URL}/admin/returns/${id}/quote`, payload);
  }
  returnReplacementOptions(id: number) {
    return this.http.get<{ items: Array<{ id_detalle_devolucion: number; opciones: ReturnVariantOption[] }> }>(`${API_BASE_URL}/admin/returns/${id}/replacement-options`);
  }
  customerReturnOptions(saleId: number, detailId: number, kind: string) {
    return this.http.get<ReturnVariantOption[]>(`${API_BASE_URL}/returns/purchases/${saleId}/items/${detailId}/options`, { params: { tipo_solicitud: kind } });
  }
  returnReceipt(id: number) {
    return this.http.get(`${API_BASE_URL}/returns/${id}/receipt`, { responseType: 'blob' });
  }
  inspectSaleForReturn(saleId: number) {
    return this.http.get<SaleReturnInspectionResponse>(
      `${API_BASE_URL}/admin/returns/inspect-sale/${saleId}`,
    );
  }
  createAdminReturn(payload: AdminReturnCreate) {
    return this.http.post<ReturnRequest>(`${API_BASE_URL}/admin/returns`, payload);
  }
  sale(saleId: number) {
    return this.http.get<Sale>(`${API_BASE_URL}/sales/${saleId}`);
  }
  supplierPurchaseHistory(params?: Params) {
    return this.http.get<SupplierPurchaseHistoryPage>(`${API_BASE_URL}/supplier-purchase-history`, {
      params: this.params(params),
    });
  }
  adminCustomers(params?: Params) {
    return this.http.get<CustomerAdminSummary[]>(`${API_BASE_URL}/customers`, {
      params: this.params(params),
    });
  }
  adminCustomer(id: number) {
    return this.http.get<CustomerAdminDetail>(`${API_BASE_URL}/customers/${id}`);
  }
  updateAdminCustomer(id: number, payload: CustomerAdminUpdateRequest) {
    return this.http.patch<CustomerAdminDetail>(`${API_BASE_URL}/customers/${id}`, payload);
  }
  quickCreateCustomer(payload: {
    nombres: string;
    apellidos?: string;
    ci?: string;
    correo?: string;
    telefono?: string;
  }) {
    return this.http.post<CustomerAdminSummary>(`${API_BASE_URL}/customers/quick`, payload);
  }
  saleInvoice(saleId: number) {
    return this.http.get(`${API_BASE_URL}/sales/${saleId}/invoice`, {
      responseType: 'blob',
    });
  }
  adminSales(params?: Params) {
    return this.http.get<Sale[]>(`${API_BASE_URL}/sales`, {
      params: this.params(params),
    });
  }
  adminCampaigns(params?: Params) {
    return this.http.get<Campaign[]>(`${API_BASE_URL}/admin/campaigns`, {
      params: this.params(params),
    });
  }
  createCampaign(payload: CampaignCreate) {
    return this.http.post<Campaign>(`${API_BASE_URL}/admin/campaigns`, payload);
  }
  getCampaign(id: number) {
    return this.http.get<Campaign>(`${API_BASE_URL}/admin/campaigns/${id}`);
  }
  updateCampaign(id: number, payload: CampaignUpdate) {
    return this.http.patch<Campaign>(`${API_BASE_URL}/admin/campaigns/${id}`, payload);
  }
  launchCampaign(id: number) {
    return this.http.post<CampaignLaunchResponse>(`${API_BASE_URL}/admin/campaigns/${id}/send`, {});
  }
  adminPromotions(params?: Params) {
    return this.http.get<Promotion[]>(`${API_BASE_URL}/admin/promotions`, {
      params: this.params(params),
    });
  }
  createPromotion(payload: PromotionCreate) {
    return this.http.post<Promotion>(`${API_BASE_URL}/admin/promotions`, payload);
  }
  getPromotion(id: number) {
    return this.http.get<Promotion>(`${API_BASE_URL}/admin/promotions/${id}`);
  }
  updatePromotion(id: number, payload: PromotionUpdate) {
    return this.http.patch<Promotion>(`${API_BASE_URL}/admin/promotions/${id}`, payload);
  }
  deletePromotion(id: number) {
    return this.http.delete<{ mensaje: string }>(`${API_BASE_URL}/admin/promotions/${id}`);
  }
  activePromotions() {
    return this.http.get<ActivePromotionItem[]>(`${API_BASE_URL}/promotions/active`);
  }
  adminDashboardSummary(branchId?: number | null) {
    const params: Params = {};
    if (branchId != null) {
      params['id_sucursal'] = branchId;
    }
    return this.http.get<AdminDashboardSummary>(`${API_BASE_URL}/admin/dashboard/summary`, {
      params: this.params(params),
    });
  }
}


