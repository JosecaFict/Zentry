import { DatePipe, DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { catchError, combineLatest, finalize, forkJoin, of, startWith, switchMap } from 'rxjs';
import { Branch } from '../../core/models/catalog.model';
import {
  Address,
  Cart,
  OperationalNotification,
  Order,
  Reservation,
  ReturnRequest,
  ReturnVariantOption,
  Sale,
  ShippingQuote,
  StripeCheckoutStatus,
} from '../../core/models/commerce.model';
import { ApiErrorService } from '../../core/services/api-error.service';
import { CatalogService } from '../../core/services/catalog.service';
import { CommerceService } from '../../core/services/commerce.service';
import { AddressMapPickerComponent } from '../../shared/components/address-map-picker/address-map-picker.component';
import { StatusPanel } from '../../shared/components/status-panel/status-panel';
import { BolivianosPipe } from '../../shared/pipes/bolivianos.pipe';

export function formatBranchName(rawName?: string | null, id?: number | null): string {
  if (!rawName) return id ? `Sucursal #${id}` : 'Sucursal asignada';
  let name = rawName.trim();
  name = name.replace(/^capricho\s+store\s*[-–]?\s*/i, '');
  if (name === name.toUpperCase()) {
    name = name
      .split(' ')
      .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : ''))
      .join(' ');
  }
  return name;
}

@Component({
  selector: 'app-cart-page',
  imports: [RouterLink, BolivianosPipe, StatusPanel],
  template: `
    <section class="commerce-page page-shell">
      <header class="commerce-heading">
        <div>
          <h1>Tu carrito</h1>
          <p>Revisa variantes y cantidades antes de continuar.</p>
        </div>
        @if (cart()?.items?.length) {
          <button
            class="button button--quiet"
            type="button"
            [disabled]="saving()"
            (click)="clear()"
          >
            Vaciar carrito
          </button>
        }
      </header>
      @if (loading()) {
        <div class="commerce-skeleton" aria-label="Cargando carrito">
          <span></span><span></span>
        </div>
      } @else if (error()) {
        <app-status-panel
          kind="error"
          title="No pudimos cargar tu carrito"
          [message]="error()"
          (retry)="load()"
        />
      } @else if (!cart()?.items?.length) {
        <app-status-panel
          title="Tu carrito está vacío"
          message="Explora el catálogo y elige una talla y color disponibles."
        />
        <div class="commerce-empty-action">
          <a class="button button--primary" routerLink="/catalogo">Ver catálogo</a>
        </div>
      } @else if (cart(); as current) {
        @if (current.sucursal) {
          <div class="notice notice--info" style="margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
            <span>Prendas preparadas en: <strong>{{ formatBranchName(current.sucursal, current.id_sucursal) }}</strong></span>
            <button class="text-button" type="button" [disabled]="saving()" (click)="clear()">Vaciar carrito</button>
          </div>
        }
        <div class="commerce-layout">
          <div class="commerce-lines" aria-live="polite">
            @for (item of current.items; track item.id_detalle) {
              <article
                class="commerce-line"
                [class.is-unavailable]="!item.activo || item.stock_disponible < item.cantidad"
              >
                <img
                  [src]="item.imagen_url || '/images/catalogo-prendas-oficiales.jpg'"
                  [alt]="item.producto"
                />
                <div class="commerce-line__body">
                  <h2>{{ item.producto }}</h2>
                  <p>{{ item.color }} / Talla {{ item.talla }}</p>
                  @if (!item.activo) {
                    <strong class="field-error">Variante inactiva</strong>
                  } @else if (item.stock_disponible < item.cantidad) {
                    <strong class="field-error"
                      >Solo quedan {{ item.stock_disponible }} unidades</strong
                    >
                  }
                </div>
                <label class="field commerce-quantity">
                  <span>Cantidad</span>
                  <input
                    type="number"
                    min="1"
                    [max]="item.stock_disponible"
                    [value]="item.cantidad"
                    [disabled]="saving()"
                    (change)="changeQuantity(item.id_detalle, $event)"
                  />
                </label>
                <div class="commerce-line__price">
                  <strong>{{ item.subtotal | bolivianos }}</strong>
                  <button
                    class="text-button"
                    type="button"
                    [disabled]="saving()"
                    (click)="remove(item.id_detalle)"
                  >
                    Quitar
                  </button>
                </div>
              </article>
            }
          </div>
          <aside class="commerce-summary" aria-label="Resumen del carrito">
            <h2>Resumen</h2>
            <div>
              <span>Productos</span><strong>{{ current.items.length }}</strong>
            </div>
            <div class="commerce-summary__total">
              <span>Total</span><strong>{{ current.total | bolivianos }}</strong>
            </div>
            <a class="button button--primary button--full" routerLink="/checkout"
              >Continuar compra</a
            >
            <a class="button button--secondary button--full" routerLink="/reservas"
              >Reservar para probar</a
            >
            <p>La reserva aparta stock sin registrar una compra.</p>
          </aside>
        </div>
      }
    </section>
  `,
})
export class CartPage {
  private readonly commerce = inject(CommerceService);
  private readonly errors = inject(ApiErrorService);
  readonly cart = signal<Cart | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly formatBranchName = formatBranchName;

  constructor() {
    this.load();
  }
  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.commerce
      .cart()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (cart) => this.cart.set(cart),
        error: (error) => this.error.set(this.errors.message(error, 'Intenta nuevamente.')),
      });
  }
  changeQuantity(id: number, event: Event): void {
    const quantity = Number((event.target as HTMLInputElement).value);
    if (!Number.isInteger(quantity) || quantity < 1) return;
    this.mutate(this.commerce.updateCartItem(id, quantity));
  }
  remove(id: number): void {
    this.mutate(this.commerce.removeCartItem(id));
  }
  clear(): void {
    this.mutate(this.commerce.clearCart());
  }
  private mutate(request: ReturnType<CommerceService['clearCart']>): void {
    this.saving.set(true);
    this.error.set('');
    request.pipe(finalize(() => this.saving.set(false))).subscribe({
      next: (cart) => this.cart.set(cart),
      error: (error) =>
        this.error.set(this.errors.message(error, 'No pudimos actualizar el carrito.')),
    });
  }
}

@Component({
  selector: 'app-checkout-page',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    BolivianosPipe,
    StatusPanel,
    AddressMapPickerComponent,
  ],
  template: `
    <section class="commerce-page page-shell">
      <a class="back-link" routerLink="/carrito">Volver al carrito</a>
      <header class="commerce-heading">
        <div>
          <h1>Confirmar pedido</h1>
          <p>Elige cómo recibirás tus prendas y completa el pago seguro.</p>
        </div>
      </header>
      @if (loading()) {
        <div class="commerce-skeleton"><span></span><span></span></div>
      } @else if (error()) {
        <app-status-panel
          kind="error"
          title="No pudimos preparar el checkout"
          [message]="error()"
          (retry)="retry()"
        />
      } @else if (completed(); as order) {
        <app-status-panel
          title="Compra confirmada"
          [message]="
            'Stripe aprobó el pago. Tu número de pedido es #' +
            order.id_pedido +
            '. Enviamos el comprobante oficial de Stripe directamente a tu correo electrónico y puedes seguir el pedido desde tu cuenta.'
          "
        />
        @if (isMobileSource()) {
          <div style="text-align: center; margin: 1rem 0;">
            <a class="button button--primary" [href]="mobileReturnUrl()" (click)="closeWindowSoon()" style="background: #10b981; border-color: #10b981; color: #fff; font-weight: 600;">
              📱 Regresar a la tienda
            </a>
          </div>
        }
        <p class="stripe-checkout-note" style="text-align: center; margin-top: 0.75rem; font-weight: 500;">
          ¿Realizaste esta compra desde la app móvil? Ya puedes cerrar esta ventana y regresar a la aplicación.
        </p>
        <div class="commerce-empty-action" style="display: flex; gap: 0.75rem; justify-content: center; flex-wrap: wrap;">
          <button
            class="button button--secondary"
            type="button"
            [disabled]="downloadingInvoice()"
            (click)="downloadOrderInvoice(order.id_pedido)"
          >
            {{ downloadingInvoice() ? 'Generando Factura…' : '📄 Descargar Factura PDF' }}
          </button>
          @if (order.receipt_url) {
            <a
              class="button button--secondary"
              [href]="order.receipt_url"
              target="_blank"
              rel="noopener noreferrer"
            >
              Ver comprobante de Stripe ↗
            </a>
          }
          <a class="button button--primary" routerLink="/pedidos">Ver mis pedidos</a>
        </div>
      } @else if (paymentStatus(); as result) {
        <app-status-panel title="Pago en verificación" [message]="result.message" />
        <div class="commerce-empty-action">
          <button class="button button--primary" type="button" (click)="verifyPayment()">
            Consultar nuevamente
          </button>
          <a class="button button--quiet" routerLink="/pedidos">Ver mis pedidos</a>
        </div>
      } @else if (cart(); as current) {
        @if (cancelled()) {
          <p class="notice notice--warning" role="status">
            El pago fue cancelado. No se realizó ningún cobro y las prendas volvieron a tu carrito.
            @if (isMobileSource()) {
              <br><br>
              <a class="button button--secondary" href="zentry://checkout-complete?status=CANCELADO" style="margin-top: 0.5rem; display: inline-block;">
                📱 Volver a la tienda
              </a>
            }
          </p>
        }
        <form class="commerce-layout" [formGroup]="form" (ngSubmit)="submit()">
          <div class="checkout-form">
            <fieldset class="delivery-choice">
              <legend>Modalidad de entrega</legend>
              <label
                ><input
                  type="radio"
                  formControlName="modalidad_entrega"
                  value="RETIRO_SUCURSAL"
                  (change)="onDeliveryModeChange()"
                /><span
                  ><strong>Retiro en sucursal</strong
                  ><small>Te avisaremos cuando esté listo.</small></span
                ></label
              >
              <label
                ><input
                  type="radio"
                  formControlName="modalidad_entrega"
                  value="DELIVERY"
                  (change)="onDeliveryModeChange()"
                /><span
                  ><strong>Delivery</strong><small>Envío con OpenRouteService a tu ubicación.</small></span
                ></label
              >
            </fieldset>

            @if (cart()?.id_sucursal) {
              <div class="field">
                <span>Sucursal que prepara el pedido</span>
                <input
                  type="text"
                  [value]="cart()?.sucursal || ('Sucursal #' + cart()?.id_sucursal)"
                  readonly
                  disabled
                />
                <small>Fijada según los productos seleccionados en tu carrito.</small>
              </div>
            } @else {
              <label class="field"
                ><span>Sucursal que prepara el pedido</span
                ><select formControlName="id_sucursal" (change)="onBranchChange()">
                  <option value="">Selecciona una sucursal</option>
                  @for (branch of branches(); track branch.id_sucursal) {
                    <option [value]="branch.id_sucursal">
                      {{ branch.nombre }} / {{ branch.direccion }}
                    </option>
                  }
                </select></label
              >
            }

            @if (form.controls.modalidad_entrega.value === 'DELIVERY') {
              <div class="field" style="margin-bottom: 0.25rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                  <span>Dirección de entrega</span>
                  <button
                    type="button"
                    class="text-button"
                    style="font-size: 0.85rem; padding: 0; min-height: auto;"
                    (click)="openAddressModal()"
                  >
                    + Agregar nueva dirección
                  </button>
                </div>
                <div style="display: flex; gap: 0.5rem; align-items: stretch;">
                  <select
                    formControlName="id_direccion"
                    (change)="onAddressChange()"
                    style="flex: 1;"
                  >
                    <option value="">Selecciona una dirección guardada</option>
                    @for (address of addresses(); track address.id_direccion) {
                      <option [value]="address.id_direccion">
                        {{ address.alias ? (address.alias + ' – ') : '' }}{{ address.direccion }} ({{ address.ciudad }})
                      </option>
                    }
                  </select>
                  <button
                    type="button"
                    class="button button--secondary"
                    style="padding: 0.5rem 0.85rem; font-size: 0.85rem; min-height: 48px;"
                    (click)="openAddressModal()"
                    title="Registrar nueva dirección con mapa y GPS"
                  >
                    📍 Nueva
                  </button>
                </div>
              </div>

              @if (!addresses().length) {
                <div
                  class="notice notice--warning"
                  style="display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; flex-wrap: wrap;"
                >
                  <span>No tienes direcciones guardadas para delivery.</span>
                  <button
                    type="button"
                    class="button button--primary"
                    style="min-height: 38px; padding: 0.4rem 0.85rem; font-size: 0.85rem;"
                    (click)="openAddressModal()"
                  >
                    📍 Ubicar mi casa en el mapa
                  </button>
                </div>
              }

              @if (addresses().length && form.controls.id_direccion.value) {
                <button
                  class="button button--secondary"
                  type="button"
                  [disabled]="quoting() || !canQuote()"
                  (click)="requestQuote()"
                >
                  {{ quoting() ? 'Calculando tarifa OpenRouteService…' : 'Recalcular costo de envío' }}
                </button>
              }

              @if (quote(); as currentQuote) {
                <div
                  class="shipping-quote"
                  style="display: flex; flex-direction: column; gap: 0.35rem; background: rgba(37, 99, 235, 0.04); border: 1px solid rgba(37, 99, 235, 0.25); border-radius: 8px; padding: 0.85rem; margin-top: 0.5rem;"
                >
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; color: #1e40af;">
                      🚚 Envío por Delivery (OpenRouteService)
                    </span>
                    <strong style="font-size: 1.15rem; color: #0f172a;">
                      {{ currentQuote.costo_estimado | bolivianos }}
                    </strong>
                  </div>
                  <div style="font-size: 0.84rem; color: #475569; display: flex; flex-wrap: wrap; gap: 0.85rem;">
                    <span>Distancia en ruta: <strong>{{ currentQuote.distancia_km }} km</strong></span>
                    @if (currentQuote.duracion_estimada_min) {
                      <span>Tiempo estimado: <strong>~{{ currentQuote.duracion_estimada_min }} min</strong></span>
                    }
                  </div>
                  <small style="color: #64748b; font-size: 0.76rem; margin-top: 0.2rem;">
                    Tarifa aplicada: Bs 5,00 base (hasta 1 km) + Bs 2,50 por cada km adicional.
                  </small>
                </div>
              }
            }
          </div>

          <aside class="commerce-summary">
            <h2>Tu pedido</h2>
            @for (item of current.items; track item.id_detalle) {
              <div>
                <span>{{ item.producto }} × {{ item.cantidad }}</span
                ><strong>{{ item.subtotal | bolivianos }}</strong>
              </div>
            }
            <div class="commerce-summary__total">
              <span>Subtotal prendas</span><strong>{{ current.total | bolivianos }}</strong>
            </div>
            @if (quote(); as currentQuote) {
              <div>
                <span>Envío delivery ({{ currentQuote.distancia_km }} km)</span
                ><strong>{{ currentQuote.costo_estimado | bolivianos }}</strong>
              </div>
              <div
                class="commerce-summary__total"
                style="border-top: 2px solid var(--line-subtle, #cbd5e1); padding-top: 0.5rem; margin-top: 0.25rem;"
              >
                <span style="font-weight: 700; font-size: 1.1rem;">Total a pagar</span>
                <strong style="color: #2563eb; font-size: 1.3rem;">
                  {{ calculateTotal(current.total, currentQuote.costo_estimado) | bolivianos }}
                </strong>
              </div>
            }
            <button
              class="button button--primary button--full"
              type="submit"
              [disabled]="submitting() || form.invalid || needsQuote()"
            >
              {{ submitting() ? 'Preparando pago…' : 'Ir al pago seguro' }}
            </button>
            <p class="stripe-checkout-note">
              Stripe procesará los datos de tu tarjeta. La tienda no almacena esos datos.
            </p>
          </aside>
        </form>

        @if (showAddressModal()) {
          <div class="admin-modal-backdrop" (click)="closeAddressModal()">
            <div
              class="admin-modal-card"
              (click)="$event.stopPropagation()"
              style="max-width: 640px; width: 95%; max-height: 90vh;"
            >
              <header class="admin-modal-header">
                <div>
                  <span class="admin-modal-kicker">Entrega a domicilio</span>
                  <h2 class="admin-modal-title">📍 Nueva dirección de entrega</h2>
                  <p class="admin-modal-subtitle">
                    Ubica tu casa o negocio en el mapa con el PIN o el GPS para calcular la ruta exacta.
                  </p>
                </div>
                <button
                  type="button"
                  class="admin-modal-close"
                  (click)="closeAddressModal()"
                  aria-label="Cerrar modal"
                >
                  ✕
                </button>
              </header>
              <div class="admin-modal-body" style="padding: 1.25rem; overflow-y: auto;">
                @if (addressModalError()) {
                  <p class="notice notice--error" style="margin-top: 0;">{{ addressModalError() }}</p>
                }
                <form [formGroup]="newAddressForm" (ngSubmit)="saveNewAddress()">
                  <div class="form-grid" style="grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-top: 0; margin-bottom: 0.75rem;">
                    <label class="field" style="margin-bottom: 0;">
                      <label>Nombre / Alias <span>(ej. Casa, Trabajo)</span></label>
                      <input formControlName="alias" placeholder="Casa" />
                    </label>
                    <label class="field" style="margin-bottom: 0;">
                      <label>Ciudad</label>
                      <select formControlName="id_ciudad">
                        <option value="">Selecciona ciudad</option>
                        @for (city of cities(); track city.id_ciudad) {
                          <option [value]="city.id_ciudad">{{ city.nombre }}</option>
                        }
                      </select>
                    </label>
                  </div>

                  <label class="field" style="margin-bottom: 0.75rem;">
                    <label>Dirección escrita <span>(Calle / Avenida y Nro.)</span></label>
                    <input
                      formControlName="direccion"
                      placeholder="Ej: Av. San Martín #450, Barrio Equipetrol"
                    />
                  </label>

                  <label class="field" style="margin-bottom: 0.75rem;">
                    <label>Referencia de llegada <span>(opcional)</span></label>
                    <input
                      formControlName="referencia"
                      placeholder="Ej: Portón blanco frente a farmacia, timbre 2B"
                    />
                  </label>

                  <div class="field" style="margin-bottom: 0.75rem;">
                    <label>
                      Ubicación exacta en el mapa <span>(arrastra el PIN 📍 o usa GPS)</span>
                    </label>
                    <app-address-map-picker
                      [lat]="modalLatNum()"
                      [lng]="modalLngNum()"
                      (locationSelected)="onModalLocationSelected($event)"
                    />
                  </div>

                  <div
                    class="admin-modal-footer"
                    style="display: flex; justify-content: flex-end; gap: 0.75rem; padding-top: 1rem; border-top: 1px solid var(--line, #e2e8f0); margin-top: 0.5rem;"
                  >
                    <button
                      type="button"
                      class="button button--secondary"
                      (click)="closeAddressModal()"
                      [disabled]="savingAddress()"
                    >
                      Cancelar
                    </button>
                    <button
                      type="submit"
                      class="button button--primary"
                      [disabled]="savingAddress() || newAddressForm.invalid"
                    >
                      {{ savingAddress() ? 'Guardando…' : 'Guardar dirección' }}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        }
      }
    </section>
  `,
})
export class CheckoutPage {
  private readonly fb = inject(FormBuilder);
  private readonly commerce = inject(CommerceService);
  private readonly catalog = inject(CatalogService);
  private readonly errors = inject(ApiErrorService);
  private readonly route = inject(ActivatedRoute);

  readonly cart = signal<Cart | null>(null);
  readonly branches = signal<Branch[]>([]);
  readonly addresses = signal<Address[]>([]);
  readonly cities = signal<Array<{ id_ciudad: number; nombre: string }>>([]);
  readonly quote = signal<ShippingQuote | null>(null);
  readonly completed = signal<Order | null>(null);
  readonly paymentStatus = signal<StripeCheckoutStatus | null>(null);
  readonly paymentSessionId = signal('');
  readonly cancelled = signal(false);
  readonly loading = signal(true);
  readonly submitting = signal(false);
  readonly quoting = signal(false);
  readonly downloadingInvoice = signal(false);
  readonly error = signal('');
  readonly isMobileSource = computed(
    () => this.route.snapshot.queryParamMap.get('source') === 'mobile',
  );
  readonly mobileReturnUrl = computed(() => {
    const sessionId = this.paymentSessionId();
    return `zentry://checkout-complete?session_id=${encodeURIComponent(sessionId)}&status=PAGADO`;
  });

  // Inline address creation modal state
  readonly showAddressModal = signal(false);
  readonly savingAddress = signal(false);
  readonly addressModalError = signal('');

  readonly form = this.fb.nonNullable.group({
    modalidad_entrega: ['RETIRO_SUCURSAL', Validators.required],
    id_sucursal: ['', Validators.required],
    id_direccion: [''],
  });

  readonly newAddressForm = this.fb.nonNullable.group({
    alias: ['Casa'],
    id_ciudad: ['', Validators.required],
    direccion: ['', [Validators.required, Validators.minLength(3)]],
    referencia: [''],
    latitud: ['-17.7833', Validators.required],
    longitud: ['-63.1821', Validators.required],
    es_principal: [true],
  });

  constructor() {
    const sessionId = this.route.snapshot.queryParamMap.get('session_id') ?? '';
    if (sessionId) {
      this.paymentSessionId.set(sessionId);
      this.verifyPayment();
      return;
    }
    if (this.route.snapshot.queryParamMap.get('pago_cancelado') === '1') {
      if (this.isMobileSource()) {
        try {
          window.location.href = 'zentry://checkout-complete?status=CANCELADO';
        } catch {
          // ignore navigation errors
        }
      }
      this.cancelPendingPayment();
      return;
    }
    this.load();
  }

  closeWindowSoon(): void {
    setTimeout(() => {
      try {
        window.close();
      } catch {
        // ignore
      }
    }, 500);
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    forkJoin({
      cart: this.commerce.cart(),
      branches: this.catalog.branches(),
      addresses: this.commerce.addresses(),
      cities: this.catalog.cities().pipe(catchError(() => of([]))),
    })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: ({ cart, branches, addresses, cities }) => {
          this.cart.set(cart);
          this.branches.set(branches);
          this.addresses.set(addresses);
          this.cities.set(cities);
          if (cart.id_sucursal) {
            this.form.controls.id_sucursal.setValue(String(cart.id_sucursal));
          }
          if (
            this.form.controls.modalidad_entrega.value === 'DELIVERY' &&
            !this.form.controls.id_direccion.value &&
            addresses.length > 0
          ) {
            const preferred = addresses.find((a) => a.es_principal) || addresses[0];
            this.form.controls.id_direccion.setValue(String(preferred.id_direccion));
            if (this.canQuote()) {
              this.requestQuote();
            }
          }
        },
        error: (error) => this.error.set(this.errors.message(error, 'Intenta nuevamente.')),
      });
  }

  retry(): void {
    if (this.paymentSessionId()) {
      this.verifyPayment();
    } else {
      this.load();
    }
  }

  canQuote(): boolean {
    return !!this.form.controls.id_sucursal.value && !!this.form.controls.id_direccion.value;
  }

  needsQuote(): boolean {
    return this.form.controls.modalidad_entrega.value === 'DELIVERY' && !this.quote();
  }

  onDeliveryModeChange(): void {
    this.quote.set(null);
    if (this.form.controls.modalidad_entrega.value === 'DELIVERY') {
      if (!this.form.controls.id_direccion.value && this.addresses().length > 0) {
        const preferred = this.addresses().find((a) => a.es_principal) || this.addresses()[0];
        this.form.controls.id_direccion.setValue(String(preferred.id_direccion));
      }
      if (this.canQuote()) {
        this.requestQuote();
      }
    }
  }

  onBranchChange(): void {
    this.quote.set(null);
    if (this.form.controls.modalidad_entrega.value === 'DELIVERY' && this.canQuote()) {
      this.requestQuote();
    }
  }

  onAddressChange(): void {
    this.quote.set(null);
    if (this.canQuote()) {
      this.requestQuote();
    }
  }

  calculateTotal(itemsTotal: string | number, shippingCost: string | number): number {
    return Number(itemsTotal || 0) + Number(shippingCost || 0);
  }

  requestQuote(): void {
    if (!this.canQuote()) return;
    this.quoting.set(true);
    this.error.set('');
    this.commerce
      .quoteShipping(
        Number(this.form.controls.id_sucursal.value),
        Number(this.form.controls.id_direccion.value),
      )
      .pipe(finalize(() => this.quoting.set(false)))
      .subscribe({
        next: (quote) => this.quote.set(quote),
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos calcular el envío.')),
      });
  }

  openAddressModal(): void {
    this.addressModalError.set('');
    const defaultCityId = this.cities()[0]?.id_ciudad;
    this.newAddressForm.reset({
      alias: 'Casa',
      id_ciudad: defaultCityId ? String(defaultCityId) : '',
      direccion: '',
      referencia: '',
      latitud: '-17.7833',
      longitud: '-63.1821',
      es_principal: true,
    });
    this.showAddressModal.set(true);
  }

  closeAddressModal(): void {
    this.showAddressModal.set(false);
  }

  modalLatNum(): number | null {
    const val = parseFloat(this.newAddressForm.controls.latitud.value);
    return isNaN(val) ? null : val;
  }

  modalLngNum(): number | null {
    const val = parseFloat(this.newAddressForm.controls.longitud.value);
    return isNaN(val) ? null : val;
  }

  onModalLocationSelected(evt: { lat: number; lng: number; addressText?: string }): void {
    this.newAddressForm.controls.latitud.setValue(String(evt.lat));
    this.newAddressForm.controls.longitud.setValue(String(evt.lng));
    if (evt.addressText && !this.newAddressForm.controls.direccion.value.trim()) {
      this.newAddressForm.controls.direccion.setValue(evt.addressText);
    }
  }

  saveNewAddress(): void {
    if (this.newAddressForm.invalid) return;
    this.savingAddress.set(true);
    this.addressModalError.set('');

    const raw = this.newAddressForm.getRawValue();
    const payload = {
      alias: raw.alias || 'Dirección',
      id_ciudad: Number(raw.id_ciudad),
      direccion: raw.direccion,
      referencia: raw.referencia || null,
      latitud: Number(raw.latitud),
      longitud: Number(raw.longitud),
      es_principal: raw.es_principal,
    };

    this.commerce
      .createAddress(payload)
      .pipe(finalize(() => this.savingAddress.set(false)))
      .subscribe({
        next: (savedAddress) => {
          this.addresses.update((items) => [savedAddress, ...items]);
          this.form.controls.id_direccion.setValue(String(savedAddress.id_direccion));
          this.showAddressModal.set(false);
          if (this.canQuote()) {
            this.requestQuote();
          }
        },
        error: (err) => {
          this.addressModalError.set(
            this.errors.message(err, 'No pudimos guardar la dirección. Revisa los datos.'),
          );
        },
      });
  }

  submit(): void {
    if (this.form.invalid || this.needsQuote()) return;
    this.submitting.set(true);
    this.error.set('');
    const value = this.form.getRawValue();
    this.commerce
      .checkout({
        id_sucursal: Number(value.id_sucursal),
        modalidad_entrega: value.modalidad_entrega,
        id_direccion: value.modalidad_entrega === 'DELIVERY' ? Number(value.id_direccion) : null,
        id_cotizacion: this.quote()?.id_cotizacion ?? null,
        return_url: window.location.origin,
      })
      .pipe(finalize(() => this.submitting.set(false)))
      .subscribe({
        next: (session) => {
          this.rememberSession(session.session_id);
          window.location.assign(session.checkout_url);
        },
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos iniciar el pago con Stripe.')),
      });
  }

  verifyPayment(): void {
    const sessionId = this.paymentSessionId();
    if (!sessionId) return;
    this.loading.set(true);
    this.error.set('');
    this.commerce
      .checkoutStatus(sessionId)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (result) => {
          if (result.status === 'PAGADO' && result.order) {
            const order: Order = {
              ...result.order,
              receipt_url: result.receipt_url || result.order.receipt_url,
            };
            this.completed.set(order);
            this.paymentStatus.set(null);
            this.forgetSession();
            if (this.isMobileSource()) {
              setTimeout(() => {
                try {
                  window.location.href = this.mobileReturnUrl();
                } catch {
                  // ignore navigation errors
                }
                setTimeout(() => {
                  try {
                    window.close();
                  } catch {
                    // ignore
                  }
                }, 600);
              }, 400);
            }
          } else {
            this.paymentStatus.set(result);
          }
        },
        error: (error) =>
          this.error.set(
            this.errors.message(error, 'No pudimos confirmar el estado del pago con Stripe.'),
          ),
      });
  }

  downloadOrderInvoice(orderId: number): void {
    this.downloadingInvoice.set(true);
    this.commerce
      .orderInvoice(orderId)
      .pipe(finalize(() => this.downloadingInvoice.set(false)))
      .subscribe({
        next: (blob) => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `factura_pedido_${orderId}.pdf`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          a.remove();
        },
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos descargar la factura.')),
      });
  }

  private cancelPendingPayment(): void {
    const sessionId = this.recalledSession();
    this.cancelled.set(true);
    if (!sessionId) {
      this.load();
      return;
    }
    this.loading.set(true);
    this.commerce.cancelCheckout(sessionId).subscribe({
      next: () => {
        this.forgetSession();
        this.load();
      },
      error: (error) => {
        this.loading.set(false);
        this.error.set(
          this.errors.message(error, 'No pudimos recuperar el carrito después de cancelar.'),
        );
      },
    });
  }

  private rememberSession(sessionId: string): void {
    try {
      sessionStorage.setItem('capricho_stripe_session', sessionId);
    } catch {
      // Stripe still redirects back with the session id after a successful payment.
    }
  }

  private recalledSession(): string {
    try {
      return sessionStorage.getItem('capricho_stripe_session') ?? '';
    } catch {
      return '';
    }
  }

  private forgetSession(): void {
    try {
      sessionStorage.removeItem('capricho_stripe_session');
    } catch {
      // Storage can be unavailable in privacy modes; there is nothing else to clear.
    }
  }
}

@Component({
  selector: 'app-reservations-page',
  imports: [ReactiveFormsModule, DatePipe, RouterLink, StatusPanel, BolivianosPipe],
  template: `
    <section class="commerce-page page-shell">
      <header class="commerce-heading">
        <div>
          <h1>Reservas</h1>
          <p>Aparta las prendas de tu carrito para visitarnos y probártelas en tienda.</p>
        </div>
      </header>
      @if (error()) {
        <p class="notice notice--error" role="alert">{{ error() }}</p>
      }
      @if (cart()?.items?.length) {
        <div class="reservation-workspace">
          <!-- Left Column: Booking Form Card -->
          <div class="reservation-form-card">
            <div class="reservation-card-header">
              <span class="reservation-badge">Apartado sin pago</span>
              <h2>Nueva reserva</h2>
              <p>Programa tu visita para apartar las prendas y probártelas en tienda.</p>
            </div>

            <form class="reservation-fields" [formGroup]="form" (ngSubmit)="create()">
              @if (cart()?.id_sucursal) {
                <div class="reservation-branch-box">
                  <div class="branch-box-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                      <polyline points="9 22 9 12 15 12 15 22"/>
                    </svg>
                  </div>
                  <div class="branch-box-content">
                    <span class="branch-box-label">Sucursal asignada</span>
                    <strong class="branch-box-name">{{ formatBranchName(cart()?.sucursal, cart()?.id_sucursal) }}</strong>
                    @if (selectedBranch()?.direccion) {
                      <span class="branch-box-address">{{ selectedBranch()?.direccion }}</span>
                    }
                    <span class="branch-box-hint">Fijada según el stock de las prendas en tu carrito.</span>
                  </div>
                </div>
              } @else {
                <label class="field">
                  <span>Sucursal</span>
                  <select formControlName="id_sucursal">
                    <option value="">Selecciona una sucursal</option>
                    @for (branch of branches(); track branch.id_sucursal) {
                      <option [value]="branch.id_sucursal">{{ branch.nombre }}</option>
                    }
                  </select>
                </label>
              }

              <label class="field">
                <span class="field-title-with-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                    <line x1="16" y1="2" x2="16" y2="6"/>
                    <line x1="8" y1="2" x2="8" y2="6"/>
                    <line x1="3" y1="10" x2="21" y2="10"/>
                  </svg>
                  Fecha y hora de visita
                </span>
                <input
                  type="datetime-local"
                  formControlName="fecha_cita"
                  [min]="minDateTime"
                  class="reservation-date-input"
                />
                <small class="field-help">Selecciona el día y horario en que pasarás por la tienda.</small>
              </label>

              <div class="reservation-policy-note">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                <span>Tus prendas se apartarán por 48 horas tras la fecha de tu visita. No necesitas pagar nada por adelantado.</span>
              </div>

              <button
                class="button button--primary reservation-submit-btn"
                type="submit"
                [disabled]="saving() || form.invalid"
              >
                {{ saving() ? 'Apartando prendas…' : 'Confirmar reserva' }}
              </button>
            </form>
          </div>

          <!-- Right Column: Reserved Items Preview Summary -->
          <aside class="reservation-summary-card">
            <div class="summary-card-header">
              <h3>Prendas a reservar</h3>
              <span class="items-count-chip">
                {{ cart()!.items.length }} {{ cart()!.items.length === 1 ? 'variante' : 'variantes' }}
              </span>
            </div>

            <div class="reservation-items-list">
              @for (item of cart()!.items; track item.id_detalle) {
                <div class="reservation-item-row">
                  <img
                    [src]="item.imagen_url || '/images/catalogo-prendas-oficiales.jpg'"
                    [alt]="item.producto"
                    class="reservation-item-thumb"
                  />
                  <div class="reservation-item-info">
                    <h4>{{ item.producto }}</h4>
                    <div class="item-variants-tags">
                      <span class="tag-variant">Talla {{ item.talla }}</span>
                      <span class="tag-variant">{{ item.color }}</span>
                      <span class="tag-qty">Cant: {{ item.cantidad }}</span>
                    </div>
                    <span class="item-price">{{ item.subtotal | bolivianos }}</span>
                  </div>
                </div>
              }
            </div>

            <div class="summary-card-footer">
              <div class="summary-total-row">
                <span>Total prendas</span>
                <strong>{{ cart()!.total | bolivianos }}</strong>
              </div>
              <p class="summary-disclaimer">Pago presencial al momento de retirar en sucursal.</p>
            </div>
          </aside>
        </div>
      } @else if (!loading()) {
        <p class="notice notice--warning">
          Tu carrito está vacío. <a routerLink="/catalogo">Elige prendas del catálogo</a> para reservar.
        </p>
      }

      <section class="history-section">
        <div class="section-title-bar">
          <h2>Tus reservas</h2>
          @if (reservations().length) {
            <span class="badge">{{ reservations().length }}</span>
          }
        </div>
        @if (loading()) {
          <div class="commerce-skeleton"><span></span></div>
        } @else if (!reservations().length) {
          <app-status-panel
            title="Aún no tienes reservas"
            message="Cuando apartes prendas, podrás consultar su preparación y horario de visita aquí."
          />
        } @else {
          <div class="reservations-grid">
            @for (reservation of reservations(); track reservation.id_reserva) {
              <article class="reservation-card">
                <header class="reservation-card__header">
                  <div>
                    <span class="res-num-tag">Reserva #{{ reservation.id_reserva }}</span>
                    <p class="res-branch">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                        <circle cx="12" cy="10" r="3"/>
                      </svg>
                      {{ formatBranchName(reservation.sucursal, reservation.id_sucursal) }}
                    </p>
                  </div>
                  <span class="status-chip">{{ reservation.estado }}</span>
                </header>

                <div class="reservation-card__body">
                  <div class="res-appointment-info">
                    <span class="label">Cita programada:</span>
                    <strong class="value">
                      {{
                        reservation.fecha_cita
                          ? (reservation.fecha_cita | date: 'dd/MM/yyyy HH:mm')
                          : 'Sin horario registrado'
                      }}
                    </strong>
                  </div>
                  @if (reservation.direccion_sucursal) {
                    <div class="res-address-info">
                      <span class="label">Ubicación:</span>
                      <span>{{ reservation.direccion_sucursal }}</span>
                    </div>
                  }
                  <div class="res-items-summary">
                    <span class="label">Prendas reservadas:</span>
                    <ul class="res-items-chips">
                      @for (item of reservation.items; track item.id_detalle) {
                        <li>
                          {{ item.producto }} ({{ item.color }}, {{ item.talla }}) × {{ item.cantidad }}
                        </li>
                      }
                    </ul>
                  </div>
                </div>

                @if (canCancel(reservation)) {
                  <footer class="reservation-card__footer">
                    <button
                      class="button button--quiet res-cancel-btn"
                      type="button"
                      [disabled]="saving()"
                      (click)="cancel(reservation.id_reserva)"
                    >
                      Cancelar reserva
                    </button>
                  </footer>
                }
              </article>
            }
          </div>
        }
      </section>
    </section>
  `,
})
export class ReservationsPage {
  private readonly fb = inject(FormBuilder);
  private readonly commerce = inject(CommerceService);
  private readonly catalog = inject(CatalogService);
  private readonly errors = inject(ApiErrorService);
  readonly cart = signal<Cart | null>(null);
  readonly branches = signal<Branch[]>([]);
  readonly reservations = signal<Reservation[]>([]);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly formatBranchName = formatBranchName;

  readonly selectedBranch = computed(() => {
    const branchId = this.cart()?.id_sucursal;
    if (!branchId) return null;
    return this.branches().find((b) => b.id_sucursal === branchId) ?? null;
  });

  get minDateTime(): string {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 16);
  }

  readonly form = this.fb.nonNullable.group({
    id_sucursal: ['', Validators.required],
    fecha_cita: ['', Validators.required],
  });
  constructor() {
    this.load();
  }
  load(): void {
    this.loading.set(true);
    forkJoin({
      cart: this.commerce.cart(),
      branches: this.catalog.branches(),
      reservations: this.commerce.reservations(),
    })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (data) => {
          this.cart.set(data.cart);
          this.branches.set(data.branches);
          this.reservations.set(data.reservations);
          if (data.cart.id_sucursal) {
            this.form.controls.id_sucursal.setValue(String(data.cart.id_sucursal));
          }
        },
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos cargar tus reservas.')),
      });
  }
  create(): void {
    if (this.form.invalid || !this.cart()?.items.length) return;
    this.saving.set(true);
    const value = this.form.getRawValue();
    this.commerce
      .createReservation({
        id_sucursal: Number(value.id_sucursal),
        fecha_cita: new Date(value.fecha_cita).toISOString(),
        items: this.cart()!.items.map((item) => ({
          id_variante: item.id_variante,
          cantidad: item.cantidad,
        })),
      })
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (item) => {
          this.reservations.update((items) => [item, ...items]);
          this.cart.set(null);
          this.form.reset();
        },
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos crear la reserva.')),
      });
  }
  canCancel(item: Reservation): boolean {
    return ['PENDIENTE', 'CONFIRMADA', 'PREPARANDO', 'LISTA', 'CLIENTE_PRESENTE'].includes(
      item.estado,
    );
  }
  cancel(id: number): void {
    this.saving.set(true);
    this.commerce
      .cancelReservation(id)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (updated) =>
          this.reservations.update((items) =>
            items.map((item) => (item.id_reserva === id ? updated : item)),
          ),
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos cancelar la reserva.')),
      });
  }
}

@Component({
  selector: 'app-orders-page',
  imports: [DatePipe, BolivianosPipe, StatusPanel],
  template: `<section class="commerce-page page-shell">
    <header class="commerce-heading">
      <div>
        <h1>Pedidos</h1>
        <p>Sigue la preparación, el retiro o la entrega.</p>
      </div>
    </header>
    @if (actionSuccess()) {
      <div class="notice notice--success" style="margin-bottom: 1rem;">
        {{ actionSuccess() }}
      </div>
    }
    @if (actionError()) {
      <div class="notice notice--error" style="margin-bottom: 1rem;">
        {{ actionError() }}
      </div>
    }
    @if (loading()) {
      <div class="commerce-skeleton"><span></span><span></span></div>
    } @else if (error()) {
      <app-status-panel
        kind="error"
        title="No pudimos cargar tus pedidos"
        [message]="error()"
        (retry)="load()"
      />
    } @else if (!orders().length) {
      <app-status-panel
        title="Aún no tienes pedidos"
        message="Tus compras online aparecerán aquí."
      />
    } @else {
      <div class="record-list">
        @for (order of orders(); track order.id_pedido) {
          <article>
            <header>
              <div>
                <h2>Pedido #{{ order.id_pedido }}</h2>
                <p>{{ order.fecha_creacion | date: 'medium' }}</p>
              </div>
              <span class="status-chip">{{ order.estado }}</span>
            </header>
            <dl class="record-facts">
              <div>
                <dt>Modalidad</dt>
                <dd>
                  {{ order.modalidad_entrega === 'DELIVERY' ? 'Delivery' : 'Retiro en sucursal' }}
                </dd>
              </div>
              <div>
                <dt>Lugar</dt>
                <dd>{{ order.direccion_entrega || order.sucursal }}</dd>
              </div>
              <div>
                <dt>Total</dt>
                <dd>{{ order.total | bolivianos }}</dd>
              </div>
            </dl>
            <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--line-subtle, #f0ede8); display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;">
              @if (order.modalidad_entrega === 'DELIVERY' && order.estado === 'EN_CAMINO') {
                <button
                  class="button button--primary button--small btn-confirm-delivery"
                  type="button"
                  [disabled]="confirmingId() === order.id_pedido"
                  (click)="confirmDelivery(order.id_pedido)"
                >
                  {{ confirmingId() === order.id_pedido ? 'Confirmando…' : '✓ Confirmar que recibí mi pedido' }}
                </button>
              }
              <button
                class="button button--small"
                type="button"
                [disabled]="downloadingId() === order.id_pedido"
                (click)="downloadInvoice(order.id_pedido)"
              >
                {{ downloadingId() === order.id_pedido ? 'Generando PDF…' : '📄 Descargar Factura PDF' }}
              </button>
              @if (order.receipt_url) {
                <a
                  class="button button--quiet button--small"
                  [href]="order.receipt_url"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Comprobante Stripe ↗
                </a>
              }
            </div>
          </article>
        }
      </div>
    }
  </section>`,
})
export class OrdersPage {
  private readonly commerce = inject(CommerceService);
  private readonly errors = inject(ApiErrorService);
  readonly orders = signal<Order[]>([]);
  readonly loading = signal(true);
  readonly downloadingId = signal<number | null>(null);
  readonly confirmingId = signal<number | null>(null);
  readonly error = signal('');
  readonly actionError = signal('');
  readonly actionSuccess = signal('');
  constructor() {
    this.load();
  }
  load(): void {
    this.loading.set(true);
    this.commerce
      .orders()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (items) => this.orders.set(items),
        error: (error) => this.error.set(this.errors.message(error, 'Intenta nuevamente.')),
      });
  }

  confirmDelivery(orderId: number): void {
    const confirmed = window.confirm('¿Confirmas que recibiste tu pedido de forma satisfactoria?');
    if (!confirmed) return;

    this.confirmingId.set(orderId);
    this.actionError.set('');
    this.actionSuccess.set('');
    this.commerce
      .confirmDelivery(orderId)
      .pipe(finalize(() => this.confirmingId.set(null)))
      .subscribe({
        next: (updatedOrder) => {
          this.orders.update((list) =>
            list.map((o) => (o.id_pedido === updatedOrder.id_pedido ? updatedOrder : o))
          );
          this.actionSuccess.set(`¡Pedido #${orderId} confirmado como recibido con éxito!`);
        },
        error: (error) =>
          this.actionError.set(this.errors.message(error, 'No pudimos confirmar la entrega.')),
      });
  }

  downloadInvoice(orderId: number): void {
    this.downloadingId.set(orderId);
    this.commerce
      .orderInvoice(orderId)
      .pipe(finalize(() => this.downloadingId.set(null)))
      .subscribe({
        next: (blob) => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `factura_pedido_${orderId}.pdf`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          a.remove();
        },
        error: (error) =>
          this.actionError.set(this.errors.message(error, 'No pudimos descargar la factura.')),
      });
  }
}

@Component({
  selector: 'app-addresses-page',
  imports: [ReactiveFormsModule, StatusPanel, AddressMapPickerComponent, DecimalPipe],
  template: `<section class="commerce-page page-shell">
    <header class="commerce-heading">
      <div>
        <h1>Direcciones</h1>
        <p>Guarda tus ubicaciones exactas con mapa y GPS para pedidos con delivery.</p>
      </div>
    </header>
    @if (error()) {
      <p class="notice notice--error">{{ error() }}</p>
    }
    @if (editingId()) {
      <div class="notice notice--info" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
        <span>✏️ <strong>Modificando dirección:</strong> Puedes actualizar los datos o arrastrar el PIN 📍 a una nueva ubicación.</span>
        <button class="button button--ghost button--small" type="button" (click)="cancelEdit()">Cancelar edición</button>
      </div>
    }
    <form class="address-form" [formGroup]="form" (ngSubmit)="save()">
      <label class="field"
        ><span>Nombre / Alias</span><input formControlName="alias" placeholder="Casa" /></label
      ><label class="field"
        ><span>Ciudad</span
        ><select formControlName="id_ciudad">
          <option value="">Selecciona</option>
          @for (city of cities(); track city.id_ciudad) {
            <option [value]="city.id_ciudad">{{ city.nombre }}</option>
          }
        </select></label
      ><label class="field field--wide"
        ><span>Dirección escrita (Calle / Avenida y Nro.)</span><input formControlName="direccion" placeholder="Ej: Av. San Martín #450" /></label
      ><div class="field field--wide" style="margin-top: 0.5rem; margin-bottom: 0.5rem;">
        <span style="font-weight: 700; margin-bottom: 0.35rem; display: block;">
          Ubicación en el mapa (PIN arrastrable 📍 y botón GPS)
        </span>
        <app-address-map-picker
          [lat]="currentLatNum()"
          [lng]="currentLngNum()"
          (locationSelected)="onLocationSelected($event)"
        />
      </div>
      <label class="check-field field--wide"
        ><input type="checkbox" formControlName="es_principal" /> Dirección principal</label
      ><button class="button button--primary" type="submit" [disabled]="saving() || form.invalid">
        {{ saving() ? 'Guardando…' : editingId() ? 'Actualizar dirección' : 'Guardar dirección' }}
      </button>
      @if (editingId()) {
        <button class="button button--ghost" type="button" (click)="cancelEdit()">Cancelar</button>
      }
    </form>
    <section class="history-section">
      <h2>Direcciones guardadas</h2>
      @if (!loading() && !addresses().length) {
        <app-status-panel
          title="Sin direcciones"
          message="Agrega una dirección para cotizar delivery."
        />
      } @else {
        <div class="record-list record-list--compact">
          @for (address of addresses(); track address.id_direccion) {
            <article>
              <header>
                <div>
                  <h3>{{ address.alias || 'Dirección' }}</h3>
                  <p>{{ address.direccion }}, {{ address.ciudad }}</p>
                  @if (address.latitud && address.longitud) {
                    <small style="color: #64748b; font-size: 0.75rem;">
                      📍 Coordenadas: {{ address.latitud | number: '1.4-4' }}, {{ address.longitud | number: '1.4-4' }}
                    </small>
                  }
                </div>
                @if (address.es_principal) {
                  <span class="status-chip">Principal</span>
                }
              </header>
              <div style="display: flex; gap: 0.5rem; align-items: center; margin-top: 0.5rem;">
                <button class="button button--ghost button--small" type="button" (click)="edit(address)">
                  Editar
                </button>
                <button
                  class="button button--quiet button--small"
                  type="button"
                  style="color: var(--danger, #dc2626);"
                  (click)="delete(address)"
                  title="Eliminar esta dirección"
                >
                  Eliminar
                </button>
              </div>
            </article>
          }
        </div>
      }
    </section>
  </section>`,
})
export class AddressesPage {
  private readonly fb = inject(FormBuilder);
  private readonly commerce = inject(CommerceService);
  private readonly catalog = inject(CatalogService);
  private readonly errors = inject(ApiErrorService);
  readonly addresses = signal<Address[]>([]);
  readonly cities = signal<Array<{ id_ciudad: number; nombre: string }>>([]);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly editingId = signal<number | null>(null);
  readonly error = signal('');
  readonly form = this.fb.nonNullable.group({
    alias: [''],
    id_ciudad: ['', Validators.required],
    direccion: ['', [Validators.required, Validators.minLength(3)]],
    latitud: ['', Validators.required],
    longitud: ['', Validators.required],
    es_principal: [false],
  });
  constructor() {
    forkJoin({
      addresses: this.commerce.addresses(),
      cities: this.catalog.cities().pipe(catchError(() => of([]))),
    })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (data) => {
          this.addresses.set(data.addresses);
          this.cities.set(data.cities);
          if (data.cities.length > 0 && !this.form.controls.id_ciudad.value) {
            this.form.controls.id_ciudad.setValue(String(data.cities[0].id_ciudad));
          }
        },
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos cargar las direcciones.')),
      });
  }

  currentLatNum(): number | null {
    const val = parseFloat(this.form.controls.latitud.value);
    return isNaN(val) ? null : val;
  }

  currentLngNum(): number | null {
    const val = parseFloat(this.form.controls.longitud.value);
    return isNaN(val) ? null : val;
  }

  onLocationSelected(evt: { lat: number; lng: number; addressText?: string }): void {
    this.form.controls.latitud.setValue(String(evt.lat));
    this.form.controls.longitud.setValue(String(evt.lng));
    if (evt.addressText && !this.form.controls.direccion.value.trim()) {
      this.form.controls.direccion.setValue(evt.addressText);
    }
    if (!this.form.controls.id_ciudad.value && this.cities().length > 0) {
      this.form.controls.id_ciudad.setValue(String(this.cities()[0].id_ciudad));
    }
  }

  save(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    const value = this.form.getRawValue();
    const payload = {
      ...value,
      id_ciudad: Number(value.id_ciudad),
      latitud: Number(value.latitud),
      longitud: Number(value.longitud),
    };
    const editingId = this.editingId();
    const request = editingId
      ? this.commerce.updateAddress(editingId, payload)
      : this.commerce.createAddress(payload);
    request.pipe(finalize(() => this.saving.set(false))).subscribe({
      next: (address) => {
        this.addresses.update((items) =>
          editingId
            ? items.map((item) => (item.id_direccion === editingId ? address : item))
            : [address, ...items],
        );
        this.cancelEdit();
      },
      error: (error) =>
        this.error.set(this.errors.message(error, 'No pudimos guardar la dirección.')),
    });
  }
  edit(address: Address): void {
    this.editingId.set(address.id_direccion);
    this.form.setValue({
      alias: address.alias ?? '',
      id_ciudad: String(address.id_ciudad),
      direccion: address.direccion,
      latitud: address.latitud ?? '',
      longitud: address.longitud ?? '',
      es_principal: address.es_principal,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  delete(address: Address): void {
    if (!confirm(`¿Estás seguro de que deseas eliminar la dirección "${address.alias || address.direccion}"?`)) {
      return;
    }
    this.saving.set(true);
    this.error.set('');
    this.commerce
      .deleteAddress(address.id_direccion)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: () => {
          this.addresses.update((items) =>
            items.filter((item) => item.id_direccion !== address.id_direccion),
          );
          if (this.editingId() === address.id_direccion) {
            this.cancelEdit();
          }
        },
        error: (err) => {
          this.error.set(this.errors.message(err, 'No pudimos eliminar la dirección.'));
        },
      });
  }

  cancelEdit(): void {
    this.editingId.set(null);
    const defaultCity = this.cities()[0]?.id_ciudad;
    this.form.reset({
      alias: '',
      id_ciudad: defaultCity ? String(defaultCity) : '',
      direccion: '',
      latitud: '',
      longitud: '',
      es_principal: false,
    });
  }
}

@Component({
  selector: 'app-history-page',
  imports: [DatePipe, BolivianosPipe, NgTemplateOutlet, ReactiveFormsModule, StatusPanel],
  styleUrl: './history-page.scss',
  template: `<section class="commerce-page page-shell customer-history">
    <header class="history-heading">
      <h1>{{ tab() === 'devoluciones' ? 'Cambios y devoluciones' : 'Mi historial' }}</h1>
    </header>
    <div class="commerce-tabs" role="group" aria-label="Secciones del historial">
      <button type="button" [class.active]="tab() === 'compras'" [attr.aria-pressed]="tab() === 'compras'" (click)="tab.set('compras')">
        Compras</button
      ><button type="button" [class.active]="tab() === 'reservas'" [attr.aria-pressed]="tab() === 'reservas'" (click)="tab.set('reservas')">
        Reservas</button
      ><button
        type="button"
        [class.active]="tab() === 'devoluciones'"
        [attr.aria-pressed]="tab() === 'devoluciones'"
        (click)="tab.set('devoluciones')"
      >
        Cambios y devoluciones
      </button>
    </div>
    @if (tab() === 'devoluciones') {
      <div class="history-return-actions">
        <p>Para iniciar una solicitud, elige la compra y la prenda que quieres cambiar o devolver.</p>
        <button type="button" class="button button--primary" (click)="tab.set('compras')">Solicitar cambio o devolución</button>
      </div>
    }
    @if (error()) {
      <p class="notice notice--error">{{ error() }}</p>
    }
    @if (loading()) {
      <div class="commerce-skeleton"><span></span></div>
    } @else if (tab() === 'compras') {
      <div class="history-list" [class.has-detail]="selectedReturn()"
        [style.--purchase-count]="sales().length">
        @if (sales().length) {
          <div class="history-row history-columns" aria-hidden="true">
            <span>Compra</span><span>Prenda</span><span>Total</span><span>Acciones</span>
          </div>
        }
        @for (sale of sales(); track sale.id_venta) {
          @let availableItems = returnableItems(sale);
          @let requests = returnsBySale().get(sale.id_venta) ?? [];
          @let selected = selectedReturn();
          <article class="history-purchase" [class.is-selected]="selected?.id_venta === sale.id_venta">
            <div class="history-row">
              <div>
                <h2>#{{ sale.id_venta }}</h2>
                <p>{{ sale.fecha_venta | date: 'dd/MM/yyyy' }}</p>
                <p>{{ sale.sucursal }}</p>
              </div>
              <ul class="history-products">
                @for (item of sale.items; track item.id_detalle) {
                  <li>
                    @if (item.imagen_url) {
                      <img [src]="item.imagen_url" alt="" width="42" height="46" loading="lazy" />
                    }
                    <div><strong>{{ item.producto }}</strong>
                      <p>{{ item.color }} · {{ item.talla }} · {{ item.cantidad }} u.</p>
                    </div>
                  </li>
                }
              </ul>
              <strong class="history-total">{{ sale.total | bolivianos }}</strong>
              <div class="history-actions">
                <button class="history-link" type="button"
                  [disabled]="downloadingSaleId() === sale.id_venta"
                  (click)="downloadSaleInvoice(sale.id_venta)">
                  {{ downloadingSaleId() === sale.id_venta ? 'Generando PDF…' : 'Factura PDF' }}
                </button>
                @for (request of requests; track request.id_devolucion) {
                  <div class="history-request">
                    <button class="history-link" type="button"
                      [attr.aria-expanded]="selected?.id_devolucion === request.id_devolucion"
                      [attr.aria-controls]="'history-return-' + request.id_devolucion"
                      (click)="toggleReturnDetail(request)">
                      {{ request.tipo_solicitud.startsWith('CAMBIO_') ? 'Ver cambio' : 'Ver solicitud' }}
                      @if (requests.length > 1) { #{{ request.id_devolucion }} }
                    </button>
                    <span class="history-status" [class]="returnBadgeClass(request.estado)">
                      {{ returnStateLabel(request.estado) }}
                    </span>
                  </div>
                }
                @if (sale.devolucion_habilitada && availableItems.length) {
                  <button class="history-link" type="button" (click)="startReturn(sale)">
                    Solicitar cambio o devolución
                  </button>
                  @if (sale.fecha_limite_devolucion) {
                    <p>Hasta el {{ sale.fecha_limite_devolucion | date: 'dd/MM/yyyy HH:mm' }}</p>
                  }
                } @else if (availableItems.length) {
                  <p>{{ !sale.fecha_inicio_devolucion ? 'Disponible después de la entrega o retiro' : 'Compra fuera del plazo o estado habilitado' }}</p>
                }
              </div>
            </div>
            @if (returnSale()?.id_venta === sale.id_venta) {
              <form class="return-form" [formGroup]="returnForm" (ngSubmit)="submitReturn()">
                <label class="field"
                  ><span>Artículo</span
                  ><select formControlName="id_detalle_venta">
                    @for (item of availableItems; track item.id_detalle) {
                      <option [value]="item.id_detalle">
                        {{ item.producto }} · Talla {{ item.talla }} · Color {{ item.color }} · Disponibles: {{ item.available }}
                      </option>
                    }
                  </select></label
                ><label class="field"
                  ><span>Cantidad</span
                  ><input type="number" min="1" [max]="maxReturnQuantity()" formControlName="cantidad" /></label
                ><label class="field"
                  ><span>¿Qué necesitas?</span><select formControlName="tipo_solicitud">
                    <option value="CAMBIO_TALLA">Cambiar talla</option>
                    <option value="CAMBIO_COLOR">Cambiar color</option>
                    <option value="CAMBIO_PRENDA">Cambiar prenda</option>
                    <option value="REEMBOLSO">Solicitar reembolso</option>
                  </select></label
                >
                @if (returnForm.controls.tipo_solicitud.value === 'CAMBIO_TALLA' || returnForm.controls.tipo_solicitud.value === 'CAMBIO_COLOR') {
                  <label class="field field--wide"><span>{{ returnForm.controls.tipo_solicitud.value === 'CAMBIO_TALLA' ? 'Talla solicitada (se conserva el color original)' : 'Color solicitado (se conserva la talla original)' }}</span>
                    <select formControlName="id_variante_solicitada">
                      <option value="">{{ returnOptionsLoading() ? 'Cargando variantes…' : 'Seleccionar talla o color' }}</option>
                      @for (option of returnOptions(); track option.id_variante) {
                        <option [value]="option.id_variante" [disabled]="option.stock_disponible < returnForm.controls.cantidad.value">Talla {{ option.talla }} · Color {{ option.color }} · {{ option.stock_disponible > 0 ? 'Stock ' + option.stock_disponible : 'Sin stock' }}</option>
                      }
                    </select>
                  </label>
                  @if (!returnOptionsLoading() && !returnOptions().length) { <p>No hay variantes compatibles para este cambio en la sucursal de la compra.</p> }
                  <p>La disponibilidad se volverá a comprobar al recibir la prenda. Esta solicitud no reserva stock.</p>
                }
                <label class="field field--wide"
                  ><span>Motivo y talla/color deseado, si corresponde</span><input maxlength="255" formControlName="motivo" /></label
                ><label class="field field--wide">
                  <span>Requisitos: sin uso, sin lavado, etiquetas conservadas y sin daños atribuibles al cliente. Presenta tu comprobante; la tienda verificará la prenda.</span>
                  <span><input type="checkbox" formControlName="requisitos_aceptados" /> Leí los requisitos de devolución.</span>
                </label
                ><button
                  class="button button--primary"
                  type="submit"
                  [disabled]="saving() || returnForm.invalid || !validReturnQuantity()"
                >
                  Enviar solicitud
                </button>
              </form>
            }
          </article>
          @if (selected && selected.id_venta === sale.id_venta) {
            <aside class="history-detail" [id]="'history-return-' + selected.id_devolucion"
              [attr.aria-label]="returnKindLabel(selected.tipo_solicitud)">
              <ng-container *ngTemplateOutlet="returnDetail; context: { $implicit: selected }" />
            </aside>
          }
        } @empty {
          <app-status-panel title="Sin compras" message="Todavía no registraste compras." />
        }
      </div>
    } @else if (tab() === 'reservas') {
      <div class="record-list">
        @for (item of reservations(); track item.id_reserva) {
          <article>
            <header>
              <div>
                <h2>Reserva #{{ item.id_reserva }}</h2>
                <p>{{ item.fecha_reserva | date: 'medium' }} / {{ item.sucursal }}</p>
              </div>
              <span class="status-chip">{{ item.estado }}</span>
            </header>
          </article>
        } @empty {
          <app-status-panel title="Sin reservas" message="Todavía no registraste reservas." />
        }
      </div>
    } @else {
      @if (returns().length) {
        <div class="history-list history-returns">
          @for (request of returns(); track request.id_devolucion) {
            <article class="history-detail">
              <ng-container *ngTemplateOutlet="returnDetail; context: { $implicit: request }" />
            </article>
          }
        </div>
      } @else {
        <app-status-panel title="Sin devoluciones" message="No tienes solicitudes de devolución." />
      }
    }

    <ng-template #returnDetail let-request>
      <header class="history-detail-heading">
        <div>
          <h2>{{ returnKindLabel(request.tipo_solicitud) }}</h2>
          <p>Solicitud #{{ request.id_devolucion }} · Compra #{{ request.id_venta }}</p>
          <p>Solicitada el {{ request.fecha_solicitud | date: 'dd/MM/yyyy HH:mm' }}</p>
        </div>
        <span class="history-status" [class]="returnBadgeClass(request.estado)">
          {{ returnStateLabel(request.estado) }}
        </span>
      </header>

      @switch (request.estado) {
        @case ('APROBADA') {
          <p class="history-detail-note">Presenta la prenda y tu comprobante en la tienda para la inspección.</p>
        }
        @case ('PENDIENTE') {
          <p class="history-detail-note">La tienda está revisando tu solicitud.</p>
        }
        @case ('RECHAZADA') {
          <p class="history-detail-note">La tienda rechazó la solicitud.</p>
        }
      }

      @if (request.items.length || request.cierre?.tipo === 'CAMBIO') {
        <div class="history-comparison" [class.has-replacement]="request.cierre?.tipo === 'CAMBIO'">
          <div>
            <h3>{{ request.estado === 'COMPLETADA' ? 'Devolviste' : 'Prendas de la solicitud' }}</h3>
            @for (line of request.items; track line.id_detalle_devolucion) {
              <div class="history-variant">
                <strong>{{ line.producto }}</strong>
                <p>Talla {{ line.talla }} · {{ line.color }} · {{ line.cantidad }} u.</p>
                @if (line.id_variante_solicitada && !request.cierre) {
                  <p>Solicitaste talla {{ line.talla_solicitada }} · {{ line.color_solicitado }}</p>
                }
              </div>
            }
          </div>
          @if (request.cierre?.tipo === 'CAMBIO') {
            <div>
              <h3>Recibiste</h3>
              @for (line of request.cierre.items; track line.id_detalle_devolucion) {
                @if (line.producto) {
                  <div class="history-variant">
                    <strong>{{ line.producto }}</strong>
                    <p>Talla {{ line.talla }} · {{ line.color }} · {{ line.cantidad }} u.</p>
                  </div>
                }
              }
            </div>
          }
        </div>
      }
      @if (request.fecha_resolucion) {
        <p class="history-detail-note">Resuelta el {{ request.fecha_resolucion | date: 'dd/MM/yyyy HH:mm' }}</p>
      }
      @if (request.cierre; as receipt) {
        <div class="history-receipt">
          <div class="history-receipt-row">
            <span>{{ receipt.accion === 'COBRAR' ? 'Adicional pagado' : receipt.accion === 'REEMBOLSAR' ? 'Importe reembolsado' : 'Sin diferencia' }}</span>
            <strong>{{ receipt.monto | bolivianos }}</strong>
          </div>
          <div class="history-receipt-row">
            <span>{{ receipt.comprobante }}</span>
            <button type="button" class="history-link history-document" (click)="downloadReturnReceipt(request.id_devolucion)">
              Comprobante PDF
            </button>
          </div>
        </div>
      }
      @if (request.motivo) {
        <details class="history-reason">
          <summary>Ver motivo de la solicitud</summary>
          <p>{{ request.motivo }}</p>
        </details>
      }
    </ng-template>
  </section>`,
})
export class HistoryPage {
  private readonly fb = inject(FormBuilder);
  private readonly commerce = inject(CommerceService);
  private readonly errors = inject(ApiErrorService);
  private readonly route = inject(ActivatedRoute);
  readonly tab = signal<'compras' | 'reservas' | 'devoluciones'>('compras');
  readonly sales = signal<Sale[]>([]);
  readonly reservations = signal<Reservation[]>([]);
  readonly returns = signal<ReturnRequest[]>([]);
  readonly selectedReturn = signal<ReturnRequest | null>(null);
  readonly returnsBySale = computed(() => {
    const grouped = new Map<number, ReturnRequest[]>();
    for (const request of this.returns()) {
      if (!['PENDIENTE', 'APROBADA', 'COMPLETADA'].includes(request.estado)) continue;
      const requests = grouped.get(request.id_venta) ?? [];
      requests.push(request);
      grouped.set(request.id_venta, requests);
    }
    return grouped;
  });
  readonly returnSale = signal<Sale | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly downloadingSaleId = signal<number | null>(null);
  readonly returnOptions = signal<ReturnVariantOption[]>([]);
  readonly returnOptionsLoading = signal(false);
  readonly returnForm = this.fb.nonNullable.group({
    id_detalle_venta: ['', Validators.required],
    cantidad: [1, [Validators.required, Validators.min(1)]],
    tipo_solicitud: ['CAMBIO_TALLA', Validators.required],
    id_variante_solicitada: [''],
    motivo: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(255)]],
    requisitos_aceptados: [false, Validators.requiredTrue],
  });
  constructor() {
    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const section = params.get('seccion');
      this.tab.set(section === 'reservas' || section === 'devoluciones' ? section : 'compras');
    });
    combineLatest([
      this.returnForm.controls.id_detalle_venta.valueChanges.pipe(startWith('')),
      this.returnForm.controls.tipo_solicitud.valueChanges.pipe(startWith('CAMBIO_TALLA')),
    ]).pipe(takeUntilDestroyed(), switchMap(([detail, kind]) => {
      const sale = this.returnSale();
      this.returnOptions.set([]);
      const requested = this.returnForm.controls.id_variante_solicitada;
      requested.reset('', { emitEvent: false });
      if (!sale || !detail || !['CAMBIO_TALLA', 'CAMBIO_COLOR'].includes(kind)) {
        requested.clearValidators(); requested.updateValueAndValidity({ emitEvent: false });
        return of([] as ReturnVariantOption[]);
      }
      requested.setValidators(Validators.required); requested.updateValueAndValidity({ emitEvent: false });
      this.returnOptionsLoading.set(true);
      return this.commerce.customerReturnOptions(sale.id_venta, Number(detail), kind).pipe(
        catchError((error) => { this.error.set(this.errors.message(error, 'No pudimos cargar las tallas o colores disponibles.')); return of([]); }),
        finalize(() => this.returnOptionsLoading.set(false)),
      );
    })).subscribe((options) => this.returnOptions.set(options));
    forkJoin({
      sales: this.commerce.purchaseHistory(),
      reservations: this.commerce.reservations(),
      returns: this.commerce.returns(),
    })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (data) => {
          this.sales.set(data.sales);
          this.reservations.set(data.reservations);
          this.returns.set(data.returns);
        },
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos cargar el historial.')),
      });
  }
  returnableItems(sale: Sale) {
    const used = new Map<number, number>();
    for (const request of this.returnsBySale().get(sale.id_venta) ?? []) {
      for (const item of request.items) {
        used.set(item.id_detalle_venta, (used.get(item.id_detalle_venta) ?? 0) + item.cantidad);
      }
    }
    return sale.items
      .map((item) => ({ ...item, available: item.cantidad - (used.get(item.id_detalle) ?? 0) }))
      .filter((item) => item.available > 0);
  }
  toggleReturnDetail(request: ReturnRequest): void {
    this.selectedReturn.update((selected) =>
      selected?.id_devolucion === request.id_devolucion ? null : request,
    );
  }
  maxReturnQuantity(): number {
    const sale = this.returnSale();
    if (!sale) return 0;
    const detailId = Number(this.returnForm.controls.id_detalle_venta.value);
    return this.returnableItems(sale).find((item) => item.id_detalle === detailId)?.available ?? 0;
  }
  validReturnQuantity(): boolean {
    const quantity = this.returnForm.controls.cantidad.value;
    return Number.isInteger(quantity) && quantity >= 1 && quantity <= this.maxReturnQuantity();
  }
  startReturn(sale: Sale): void {
    const firstItem = this.returnableItems(sale)[0];
    if (!sale.devolucion_habilitada || !firstItem) return;
    this.returnSale.set(sale);
    this.returnForm.reset({
      id_detalle_venta: String(firstItem.id_detalle),
      cantidad: 1,
      tipo_solicitud: 'CAMBIO_TALLA',
      id_variante_solicitada: '',
      motivo: '',
      requisitos_aceptados: false,
    });
  }
  submitReturn(): void {
    const sale = this.returnSale();
    if (!sale?.devolucion_habilitada || this.saving() || this.returnForm.invalid || !this.validReturnQuantity()) return;
    const value = this.returnForm.getRawValue();
    if (['CAMBIO_TALLA', 'CAMBIO_COLOR'].includes(value.tipo_solicitud) && !this.returnOptions().some((option) => option.id_variante === Number(value.id_variante_solicitada) && option.stock_disponible >= value.cantidad)) {
      this.error.set('Selecciona una talla o color disponible para la cantidad solicitada.');
      return;
    }
    this.saving.set(true);
    this.commerce
      .createReturn({
        id_venta: sale.id_venta,
        tipo_solicitud: value.tipo_solicitud,
        motivo: value.motivo,
        items: [
          {
            id_detalle_venta: Number(value.id_detalle_venta),
            cantidad: value.cantidad,
            id_variante_solicitada: value.id_variante_solicitada ? Number(value.id_variante_solicitada) : null,
          },
        ],
      })
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (item) => {
          this.returns.update((items) => [item, ...items]);
          this.tab.set('devoluciones');
          this.returnSale.set(null);
        },
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos crear la devolución.')),
      });
  }

  downloadReturnReceipt(id: number): void {
    this.commerce.returnReceipt(id).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a'); link.href = url; link.download = `devolucion-${id}.pdf`; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      },
      error: (error) => this.error.set(this.errors.message(error, 'No pudimos descargar el comprobante.')),
    });
  }

  downloadSaleInvoice(saleId: number): void {
    this.downloadingSaleId.set(saleId);
    this.commerce
      .saleInvoice(saleId)
      .pipe(finalize(() => this.downloadingSaleId.set(null)))
      .subscribe({
        next: (blob) => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `factura_compra_${saleId}.pdf`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          a.remove();
        },
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos descargar la factura.')),
      });
  }

  isReturnEligible(saleDateStr: string): { eligible: boolean; remaining: number } {
    const saleDate = new Date(saleDateStr);
    let cur = new Date(saleDate);
    let added = 0;
    while (added < 5) {
      cur.setDate(cur.getDate() + 1);
      const day = cur.getDay();
      if (day !== 0 && day !== 6) {
        added++;
      }
    }
    cur.setHours(23, 59, 59, 999);
    const now = new Date();
    const eligible = now <= cur;

    let elapsed = 0;
    const scan = new Date(saleDate);
    scan.setDate(scan.getDate() + 1);
    while (scan <= now) {
      const day = scan.getDay();
      if (day !== 0 && day !== 6) {
        elapsed++;
      }
      scan.setDate(scan.getDate() + 1);
    }
    const remaining = Math.max(0, 5 - elapsed);
    return { eligible, remaining };
  }

  returnKindLabel(kind: ReturnRequest['tipo_solicitud']): string {
    return ({
      DEVOLUCION: 'Devolución',
      CAMBIO_TALLA: 'Cambio de talla',
      CAMBIO_COLOR: 'Cambio de color',
      CAMBIO_PRENDA: 'Cambio de prenda',
      REEMBOLSO: 'Reembolso solicitado',
      CREDITO: 'Crédito solicitado',
    })[kind] ?? 'Devolución';
  }

  returnBadgeClass(state: string): string {
    switch (state) {
      case 'PENDIENTE':
        return 'order-badge--pending';
      case 'APROBADA':
        return 'order-badge--confirmed';
      case 'COMPLETADA':
        return 'order-badge--completed';
      case 'RECHAZADA':
        return 'order-badge--cancelled';
      default:
        return 'order-badge--default';
    }
  }

  returnStateLabel(state: string): string {
    switch (state) {
      case 'PENDIENTE':
        return 'En revisión';
      case 'APROBADA':
        return 'Aprobada';
      case 'COMPLETADA':
        return 'Completada';
      case 'RECHAZADA':
        return 'Rechazada';
      default:
        return state;
    }
  }
}

@Component({
  selector: 'app-notifications-page',
  imports: [DatePipe, StatusPanel],
  template: `<section class="commerce-page page-shell">
    <header class="commerce-heading">
      <div>
        <h1>Notificaciones</h1>
        <p>Cambios operativos de tus reservas, pedidos y devoluciones.</p>
      </div>
    </header>
    @if (loading()) {
      <div class="commerce-skeleton"><span></span></div>
    } @else if (!items().length) {
      <app-status-panel
        title="Sin notificaciones"
        message="Los cambios importantes aparecerán aquí."
      />
    } @else {
      <div class="notification-list">
        @for (item of items(); track item.id_notificacion) {
          <article>
            <div>
              <h2>{{ item.titulo || 'Actualización' }}</h2>
              <p>{{ item.contenido }}</p>
            </div>
            <time [attr.datetime]="item.fecha_creacion">{{
              item.fecha_creacion | date: 'short'
            }}</time>
          </article>
        }
      </div>
    }
  </section>`,
})
export class NotificationsPage {
  private readonly commerce = inject(CommerceService);
  readonly items = signal<OperationalNotification[]>([]);
  readonly loading = signal(true);
  constructor() {
    this.commerce
      .notifications()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({ next: (items) => this.items.set(items) });
  }
}
