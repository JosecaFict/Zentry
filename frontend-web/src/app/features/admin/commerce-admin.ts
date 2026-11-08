import { CommonModule, DatePipe } from '@angular/common';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, firstValueFrom, forkJoin } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { ExportService, PurchasesFilterInfo, SalesFilterInfo } from '../../core/services/export.service';
import { Branch, Product, ProductVariant } from '../../core/models/catalog.model';
import {
  CustomerAdminSummary,
  Order,
  Reservation,
  ReturnRequest,
  Sale,
  SaleReturnInspectionResponse,
  SaleReturnLineInspection,
  ReturnStatusUpdatePayload,
  ReturnChecklist,
  ReturnQuote,
  ReturnSettlementPayload,
  ReturnVariantOption,
} from '../../core/models/commerce.model';
import { ApiErrorService } from '../../core/services/api-error.service';
import { CatalogService } from '../../core/services/catalog.service';
import { CommerceService } from '../../core/services/commerce.service';
import { StatusPanel } from '../../shared/components/status-panel/status-panel';
import { BolivianosPipe } from '../../shared/pipes/bolivianos.pipe';
import { formatBranchName } from '../commerce/commerce-pages';
import { AdminApiService, Entity } from './admin-api.service';

interface SaleLine {
  variant: ProductVariant;
  product: Product;
  quantity: number;
}

@Component({
  selector: 'app-pos-sales-admin',
  imports: [ReactiveFormsModule, FormsModule, BolivianosPipe, DatePipe],
  template: `
    <section class="pos-sales-page">
      <header class="admin-page-heading">
        <div>
          <p class="eyebrow">Punto de Venta</p>
          <h1>Venta Presencial (POS)</h1>
          <p>Registra ventas en mostrador con deducción automática de inventario físico y costeo FIFO.</p>
        </div>
      </header>

      @if (error()) {
        <div class="admin-notice admin-notice--error" role="alert">
          <span>{{ error() }}</span>
          <button type="button" class="pos-notice-close" (click)="error.set('')" aria-label="Cerrar">✕</button>
        </div>
      }

      @if (completed(); as sale) {
        <div class="admin-panel pos-success-panel">
          <div class="pos-success-badge">✓ Cobro Exitoso</div>
          <h2>Venta #{{ sale.id_venta }} Completada</h2>
          <p class="pos-success-lead">
            Total cobrado en efectivo: <strong>{{ sale.total | bolivianos }}</strong> en <strong>{{ sale.sucursal }}</strong>.
          </p>
          <div class="pos-success-details">
            <div class="pos-success-metric">
              <span>Cliente Facturado</span>
              <strong>{{ sale.cliente_nombre || 'Consumidor Final' }}</strong>
            </div>
            @if (sale.cliente_correo) {
              <div class="pos-success-metric">
                <span>Factura Digital</span>
                <strong style="color: #059669;">✉️ Enviada a {{ sale.cliente_correo }}</strong>
              </div>
            }
            <div class="pos-success-metric">
              <span>Modalidad de entrega</span>
              <strong>Directa / Mostrador</strong>
            </div>
            <div class="pos-success-metric">
              <span>Prendas vendidas</span>
              <strong>{{ sale.items.length }} ítem(s)</strong>
            </div>
            <div class="pos-success-metric">
              <span>Fecha y hora</span>
              <strong>{{ sale.fecha_venta | date: 'short' }}</strong>
            </div>
          </div>
          <div class="pos-success-actions">
            <button
              type="button"
              class="button button--secondary"
              [disabled]="downloadingInvoice()"
              (click)="downloadSaleInvoice(sale.id_venta)"
            >
              {{ downloadingInvoice() ? 'Generando PDF…' : '📄 Descargar Factura PDF' }}
            </button>
            <button type="button" class="button button--secondary" (click)="printTicket()">
              🖨️ Imprimir comprobante
            </button>
            <button type="button" class="button button--primary" (click)="resetPos()">
              + Iniciar nueva venta
            </button>
          </div>
        </div>
      }

      <!-- Control de Sucursal: Basado en rol (Cajero fijo vs Admin selector) -->
      <div class="pos-branch-card admin-panel">
        @if (!canSelectBranch()) {
          <div class="pos-branch-assigned-banner">
            <div class="pos-branch-assigned-icon">📍</div>
            <div class="pos-branch-assigned-text">
              <span class="pos-branch-assigned-label">Sucursal asignada a tu usuario</span>
              <strong class="pos-branch-assigned-name">{{ assignedBranchName() }}</strong>
            </div>
            <span class="pos-status-badge pos-status-badge--locked">
              <span class="pos-dot-pulse"></span>
              Caja Asignada (Fija)
            </span>
          </div>
        } @else {
          <div class="pos-branch-admin-banner">
            <label class="field pos-branch-select-field">
              <span>📍 Sucursal de atención (Administración general)</span>
              <select [value]="selectedBranchId() ?? ''" (change)="onBranchChange($any($event.target).value)">
                <option value="">-- Selecciona sucursal para la venta --</option>
                @for (branch of branches(); track branch.id_sucursal) {
                  <option [value]="branch.id_sucursal">{{ branch.nombre }}</option>
                }
              </select>
            </label>
            @if (selectedBranchId()) {
              <span class="pos-status-badge pos-status-badge--active">
                <span class="pos-dot-pulse"></span>
                Sucursal activa
              </span>
            }
          </div>
        }
      </div>

      <!-- Selector Cascada de Prendas: Marca -> Modelo -> Talla -> Color -> Cantidad -->
      <div class="admin-panel pos-cascade-panel">
        <div class="pos-cascade-header">
          <div>
            <h2>Selección guiada de prenda</h2>
            <p>Selecciona ordenadamente para consultar existencias físicas de la sucursal.</p>
          </div>
          @if (selectedBrandId() || selectedProductId()) {
            <button type="button" class="text-button" (click)="clearSelection()">
              Limpiar selección
            </button>
          }
        </div>

        <div class="pos-cascade-grid">
          <!-- 1. Marca -->
          <label class="field pos-cascade-field">
            <span class="pos-step-num">1. Marca</span>
            <select [value]="selectedBrandId() ?? ''" (change)="onBrandChange($any($event.target).value)">
              <option value="">-- Seleccionar Marca --</option>
              @for (b of brands(); track b.id) {
                <option [value]="b.id">{{ b.nombre }}</option>
              }
            </select>
          </label>

          <!-- 2. Modelo / Prenda -->
          <label class="field pos-cascade-field">
            <span class="pos-step-num">2. Modelo / Prenda</span>
            <select
              [disabled]="!selectedBrandId()"
              [value]="selectedProductId() ?? ''"
              (change)="onProductChange($any($event.target).value)"
            >
              <option value="">{{ selectedBrandId() ? '-- Seleccionar Prenda --' : 'Primero elige marca' }}</option>
              @for (p of productsForBrand(); track p.id_producto) {
                <option [value]="p.id_producto">{{ p.nombre }} ({{ p.precio_actual | bolivianos }})</option>
              }
            </select>
          </label>

          <!-- 3. Talla -->
          <label class="field pos-cascade-field">
            <span class="pos-step-num">3. Talla</span>
            <select
              [disabled]="!selectedProductId()"
              [value]="selectedSize()"
              (change)="onSizeChange($any($event.target).value)"
            >
              <option value="">{{ selectedProductId() ? '-- Talla --' : 'Elige prenda' }}</option>
              @for (t of availableSizes(); track t) {
                <option [value]="t">Talla {{ t }}</option>
              }
            </select>
          </label>

          <!-- 4. Color y Stock -->
          <label class="field pos-cascade-field">
            <span class="pos-step-num">4. Color y Existencias</span>
            <select
              [disabled]="!selectedSize()"
              [value]="selectedVariantId() ?? ''"
              (change)="onVariantChange($any($event.target).value)"
            >
              <option value="">{{ selectedSize() ? '-- Color --' : 'Elige talla' }}</option>
              @for (v of availableVariantsForSize(); track v.id_variante) {
                <option [value]="v.id_variante" [disabled]="(v.stock_disponible ?? 0) <= 0">
                  {{ v.color }} — {{ (v.stock_disponible ?? 0) > 0 ? (v.stock_disponible + ' disponibles') : 'AGOTADO' }}
                </option>
              }
            </select>
          </label>
        </div>

        <!-- Previsualización de Prenda Seleccionada y Cantidad -->
        @if (selectedVariant(); as v) {
          <div class="pos-selection-preview">
            <div class="pos-preview-media">
              @if (selectedProduct()?.imagen_principal?.secure_url) {
                <img [src]="selectedProduct()?.imagen_principal?.secure_url" [alt]="selectedProduct()?.nombre" class="pos-preview-img" />
              } @else {
                <div class="pos-preview-placeholder">👗</div>
              }
              <div class="pos-preview-meta">
                <strong>{{ selectedProduct()?.nombre }}</strong>
                <span class="pos-preview-sub">
                  Marca: <em>{{ selectedProduct()?.marca }}</em> · Talla: <strong>{{ v.talla }}</strong> · Color: <strong>{{ v.color }}</strong>
                </span>
                <div class="pos-preview-badges">
                  <span class="pos-sku-badge">{{ v.sku }}</span>
                  @if ((v.stock_disponible ?? 0) > 0) {
                    <span class="pos-stock-badge pos-stock-badge--ok">
                      ✓ {{ v.stock_disponible }} unidad(es) disponible(s) en sucursal
                    </span>
                  } @else {
                    <span class="pos-stock-badge pos-stock-badge--empty">
                      ✕ Sin existencias en esta sucursal
                    </span>
                  }
                </div>
              </div>
            </div>

            <div class="pos-preview-action">
              <div class="pos-stepper-box">
                <span class="pos-stepper-label">5. Cantidad</span>
                <div class="pos-stepper">
                  <button type="button" class="pos-stepper-btn" (click)="decrementQty()" [disabled]="quantity() <= 1">−</button>
                  <input
                    type="number"
                    min="1"
                    [max]="selectedStock() || 1"
                    [value]="quantity()"
                    (input)="onQuantityInput($any($event.target).value)"
                  />
                  <button
                    type="button"
                    class="pos-stepper-btn"
                    (click)="incrementQty()"
                    [disabled]="quantity() >= selectedStock()"
                  >+</button>
                </div>
              </div>

              <div class="pos-subtotal-box">
                <span class="pos-subtotal-label">Subtotal prenda</span>
                <strong class="pos-subtotal-val">{{ currentItemSubtotal() | bolivianos }}</strong>
              </div>

              <button
                type="button"
                class="button button--primary pos-add-btn"
                [disabled]="!canAddCurrentVariant()"
                (click)="addLine()"
              >
                + Agregar a venta
              </button>
            </div>
          </div>
        }
      </div>

      <!-- Ticket de Venta / Carrito POS -->
      @if (lines().length) {
        <div class="admin-panel pos-ticket-panel">
          <div class="pos-ticket-header">
            <div class="pos-ticket-title-wrap">
              <h2>🧾 Comprobante / Ticket de Venta</h2>
              <span class="pos-ticket-badge">{{ lines().length }} ítem(s) agregado(s)</span>
            </div>
            <button type="button" class="text-button text-button--danger" (click)="clearTicket()">
              Vaciar ticket
            </button>
          </div>

          <div class="pos-ticket-table-wrap">
            <table class="pos-ticket-table">
              <thead>
                <tr>
                  <th>Prenda</th>
                  <th>Talla & Color</th>
                  <th>SKU</th>
                  <th>Precio Unitario</th>
                  <th>Cantidad</th>
                  <th>Subtotal</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                @for (line of lines(); track line.variant.id_variante) {
                  <tr>
                    <td class="pos-col-product">
                      <div class="pos-table-product">
                        @if (line.product.imagen_principal?.secure_url) {
                          <img [src]="line.product.imagen_principal?.secure_url" [alt]="line.product.nombre" class="pos-table-thumb" />
                        } @else {
                          <div class="pos-table-thumb-empty">👗</div>
                        }
                        <div>
                          <strong>{{ line.product.nombre }}</strong>
                          <small class="pos-table-brand">{{ line.product.marca }}</small>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div class="pos-variant-tags">
                        <span class="pos-pill pos-pill--size">Talla {{ line.variant.talla }}</span>
                        <span class="pos-pill pos-pill--color">
                          @if (line.variant.codigo_hex) {
                            <span class="pos-color-dot" [style.background-color]="line.variant.codigo_hex"></span>
                          }
                          {{ line.variant.color }}
                        </span>
                      </div>
                    </td>
                    <td>
                      <code class="pos-table-sku">{{ line.variant.sku }}</code>
                    </td>
                    <td class="pos-col-price">
                      {{ line.product.precio_actual | bolivianos }}
                    </td>
                    <td class="pos-col-qty">
                      <div class="pos-table-stepper">
                        <button type="button" (click)="updateLineQty(line.variant.id_variante, -1)">−</button>
                        <span>{{ line.quantity }}</span>
                        <button
                          type="button"
                          (click)="updateLineQty(line.variant.id_variante, 1)"
                          [disabled]="line.quantity >= (line.variant.stock_disponible ?? 999)"
                        >+</button>
                      </div>
                    </td>
                    <td class="pos-col-subtotal">
                      <strong>{{ lineSubtotal(line) | bolivianos }}</strong>
                    </td>
                    <td class="pos-col-remove">
                      <button
                        class="pos-remove-btn"
                        type="button"
                        title="Quitar prenda del ticket"
                        (click)="removeLine(line.variant.id_variante)"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>

          <!-- Sección de Datos del Cliente / Facturación -->
          <div class="pos-customer-section" style="padding: 1rem 1.25rem; border-top: 1px solid var(--line-subtle, #e2e8f0); background: #fafaf9; border-radius: 8px; margin: 1rem 1.25rem 0.5rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
              <span style="font-weight: 800; font-size: 0.95rem; color: #1e293b;">
                👤 Datos del Cliente para la Factura / Comprobante
              </span>
              <div class="pos-customer-modes" style="display: flex; gap: 0.35rem; background: #e2e8f0; padding: 0.2rem; border-radius: 6px;">
                <button
                  type="button"
                  class="button button--small"
                  [class.button--primary]="customerMode() === 'ANON'"
                  [class.button--ghost]="customerMode() !== 'ANON'"
                  style="font-size: 0.8rem; padding: 0.25rem 0.6rem; min-height: 28px;"
                  (click)="setCustomerMode('ANON')"
                >
                  Consumidor Final
                </button>
                <button
                  type="button"
                  class="button button--small"
                  [class.button--primary]="customerMode() === 'SEARCH'"
                  [class.button--ghost]="customerMode() !== 'SEARCH'"
                  style="font-size: 0.8rem; padding: 0.25rem 0.6rem; min-height: 28px;"
                  (click)="setCustomerMode('SEARCH')"
                >
                  🔍 Buscar Registrado
                </button>
                <button
                  type="button"
                  class="button button--small"
                  [class.button--primary]="customerMode() === 'NEW'"
                  [class.button--ghost]="customerMode() !== 'NEW'"
                  style="font-size: 0.8rem; padding: 0.25rem 0.6rem; min-height: 28px;"
                  (click)="setCustomerMode('NEW')"
                >
                  + Nuevo Cliente
                </button>
              </div>
            </div>

            <!-- Modo 1: Consumidor Final -->
            @if (customerMode() === 'ANON') {
              <div style="font-size: 0.85rem; color: #64748b; display: flex; align-items: center; gap: 0.5rem;">
                <span>ℹ️ La venta y factura se emitirán a <strong>Consumidor Final (NIT/CI: S/N)</strong>.</span>
              </div>
            }

            <!-- Modo 2: Buscar Cliente Registrado -->
            @if (customerMode() === 'SEARCH') {
              @if (selectedCustomer(); as c) {
                <div style="display: flex; justify-content: space-between; align-items: center; background: #ffffff; padding: 0.6rem 0.85rem; border: 1px solid #cbd5e1; border-radius: 6px;">
                  <div>
                    <strong style="color: #0f172a; font-size: 0.95rem;">✓ {{ c.nombre_completo }}</strong>
                    <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.15rem;">
                      <span>CI/NIT: <strong>{{ c.ci || 'Sin CI' }}</strong></span> ·
                      <span>Correo: <strong>{{ c.correo }}</strong></span>
                      @if (c.telefono) {
                        · <span>Tel: <strong>{{ c.telefono }}</strong></span>
                      }
                    </div>
                  </div>
                  <button type="button" class="text-button text-button--danger" style="font-size: 0.8rem;" (click)="clearSelectedCustomer()">
                    Cambiar cliente
                  </button>
                </div>
              } @else {
                <div style="position: relative;">
                  <input
                    type="text"
                    [value]="customerSearchQuery()"
                    (input)="onCustomerSearchInput($any($event.target).value)"
                    placeholder="Buscar por CI/NIT, Nombre o Correo..."
                    style="width: 100%; padding: 0.5rem 0.75rem; font-size: 0.88rem; border-radius: 6px; border: 1px solid #cbd5e1;"
                  />
                  @if (searchingCustomers()) {
                    <small style="position: absolute; right: 10px; top: 10px; color: #64748b;">Buscando…</small>
                  }
                  @if (customerSearchResults().length > 0) {
                    <div style="position: absolute; z-index: 50; top: 100%; left: 0; right: 0; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; max-height: 200px; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-top: 4px;">
                      @for (item of customerSearchResults(); track item.id_cliente) {
                        <div
                          (click)="selectCustomer(item)"
                          style="padding: 0.5rem 0.75rem; cursor: pointer; border-bottom: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center;"
                          onmouseover="this.style.background='#f8fafc'"
                          onmouseout="this.style.background='#ffffff'"
                        >
                          <div>
                            <strong style="color: #1e293b; font-size: 0.9rem;">{{ item.nombre_completo }}</strong>
                            <div style="font-size: 0.78rem; color: #64748b;">
                              CI: {{ item.ci || 'S/N' }} · {{ item.correo }}
                            </div>
                          </div>
                          <span class="button button--small button--secondary" style="font-size: 0.75rem; padding: 0.2rem 0.5rem; min-height: 24px;">Seleccionar</span>
                        </div>
                      }
                    </div>
                  } @else if (customerSearchQuery().length >= 2 && !searchingCustomers() && customerSearchResults().length === 0) {
                    <div style="font-size: 0.82rem; color: #64748b; margin-top: 0.4rem;">
                      No se encontraron clientes registrados con ese criterio.
                    </div>
                  }
                </div>
              }
            }

            <!-- Modo 3: Registrar Nuevo Cliente Rápido -->
            @if (customerMode() === 'NEW') {
              @if (selectedCustomer(); as c) {
                <div style="display: flex; justify-content: space-between; align-items: center; background: #ffffff; padding: 0.6rem 0.85rem; border: 1px solid #cbd5e1; border-radius: 6px;">
                  <div>
                    <strong style="color: #059669; font-size: 0.95rem;">✓ Cliente registrado: {{ c.nombre_completo }}</strong>
                    <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.15rem;">
                      <span>CI/NIT: <strong>{{ c.ci || 'Sin CI' }}</strong></span> ·
                      <span>Correo: <strong>{{ c.correo }}</strong></span>
                    </div>
                  </div>
                  <button type="button" class="text-button text-button--danger" style="font-size: 0.8rem;" (click)="clearSelectedCustomer()">
                    Editar datos
                  </button>
                </div>
              } @else {
                <form [formGroup]="quickCustomerForm" (ngSubmit)="saveQuickCustomer()" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.6rem; align-items: end;">
                  <label class="field" style="margin-bottom: 0;">
                    <span style="font-size: 0.8rem;">Nombre / Razón Social *</span>
                    <input formControlName="nombres" placeholder="Ej. Juan Carlos o Empresa SRL" style="padding: 0.4rem 0.6rem; font-size: 0.85rem;" />
                  </label>
                  <label class="field" style="margin-bottom: 0;">
                    <span style="font-size: 0.8rem;">Apellidos</span>
                    <input formControlName="apellidos" placeholder="Ej. Pérez" style="padding: 0.4rem 0.6rem; font-size: 0.85rem;" />
                  </label>
                  <label class="field" style="margin-bottom: 0;">
                    <span style="font-size: 0.8rem;">CI o NIT (para factura)</span>
                    <input formControlName="ci" placeholder="Ej. 6829401 o 102938475" style="padding: 0.4rem 0.6rem; font-size: 0.85rem;" />
                  </label>
                  <label class="field" style="margin-bottom: 0;">
                    <span style="font-size: 0.8rem;">Correo (envío de PDF)</span>
                    <input formControlName="correo" type="email" placeholder="cliente@correo.com" style="padding: 0.4rem 0.6rem; font-size: 0.85rem;" />
                  </label>
                  <label class="field" style="margin-bottom: 0;">
                    <span style="font-size: 0.8rem;">Teléfono</span>
                    <input formControlName="telefono" placeholder="Ej. 78012345" style="padding: 0.4rem 0.6rem; font-size: 0.85rem;" />
                  </label>
                  <div>
                    <button
                      type="submit"
                      class="button button--secondary"
                      style="min-height: 38px; width: 100%; font-size: 0.85rem;"
                      [disabled]="savingQuickCustomer() || quickCustomerForm.invalid"
                    >
                      {{ savingQuickCustomer() ? 'Guardando…' : '✓ Fijar para Factura' }}
                    </button>
                  </div>
                </form>
              }
            }
          </div>

          <footer class="pos-ticket-footer">
            <div class="pos-ticket-total-wrap">
              <span class="pos-ticket-total-label">Total a cobrar en efectivo:</span>
              <strong class="pos-ticket-total-value">{{ estimatedTotal() | bolivianos }}</strong>
            </div>
            <div class="pos-ticket-action-wrap">
              <button
                class="button button--primary button--lg pos-checkout-btn"
                type="button"
                [disabled]="saving() || !selectedBranchId()"
                (click)="confirm()"
              >
                @if (saving()) {
                  Procesando cobro…
                } @else {
                  💵 Cobrar {{ estimatedTotal() | bolivianos }} en Efectivo
                }
              </button>
            </div>
          </footer>
        </div>
      }
    </section>
  `,
})
export class PosSalesAdmin {
  private readonly fb = inject(FormBuilder);
  private readonly commerce = inject(CommerceService);
  private readonly catalog = inject(CatalogService);
  private readonly auth = inject(AuthService);
  private readonly errors = inject(ApiErrorService);

  readonly branches = signal<Branch[]>([]);
  readonly products = signal<Product[]>([]);
  readonly lines = signal<SaleLine[]>([]);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly completed = signal<Sale | null>(null);

  // Customer signals for POS invoicing
  readonly customerMode = signal<'ANON' | 'SEARCH' | 'NEW'>('ANON');
  readonly selectedCustomer = signal<CustomerAdminSummary | null>(null);
  readonly customerSearchQuery = signal<string>('');
  readonly customerSearchResults = signal<CustomerAdminSummary[]>([]);
  readonly searchingCustomers = signal<boolean>(false);
  readonly savingQuickCustomer = signal<boolean>(false);
  readonly downloadingInvoice = signal<boolean>(false);

  readonly quickCustomerForm = this.fb.nonNullable.group({
    nombres: ['', [Validators.required, Validators.minLength(2)]],
    apellidos: [''],
    ci: [''],
    correo: ['', [Validators.email]],
    telefono: [''],
  });

  // Branch signals
  readonly selectedBranchId = signal<number | null>(null);

  // Cascading selector signals
  readonly selectedBrandId = signal<number | null>(null);
  readonly selectedProductId = signal<number | null>(null);
  readonly selectedSize = signal<string>('');
  readonly selectedVariantId = signal<number | null>(null);
  readonly quantity = signal<number>(1);

  readonly currentUser = this.auth.currentUser;

  readonly canSelectBranch = computed(() => {
    const u = this.currentUser();
    if (!u) return false;
    return u.roles.includes('ADMIN') || !u.id_sucursal;
  });

  readonly assignedBranchName = computed(() => {
    const u = this.currentUser();
    if (u?.sucursal) return u.sucursal;
    if (u?.id_sucursal) {
      const b = this.branches().find((br) => br.id_sucursal === u.id_sucursal);
      return b ? b.nombre : `Sucursal #${u.id_sucursal}`;
    }
    return 'Sucursal asignada';
  });

  readonly brands = computed(() => {
    const map = new Map<number, string>();
    for (const p of this.products()) {
      if (p.id_marca && p.marca) {
        map.set(p.id_marca, p.marca);
      }
    }
    return Array.from(map.entries())
      .map(([id, nombre]) => ({ id, nombre }))
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
  });

  readonly productsForBrand = computed(() => {
    const brandId = this.selectedBrandId();
    if (!brandId) return [];
    return this.products().filter((p) => p.id_marca === brandId);
  });

  readonly selectedProduct = computed(() => {
    const prodId = this.selectedProductId();
    if (!prodId) return null;
    return this.products().find((p) => p.id_producto === prodId) ?? null;
  });

  readonly availableSizes = computed(() => {
    const prod = this.selectedProduct();
    if (!prod) return [];
    const sizeOrder = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];
    const unique = Array.from(
      new Set(prod.variantes.filter((v) => v.activo).map((v) => v.talla)),
    );
    return unique.sort((a, b) => {
      const ia = sizeOrder.indexOf(a);
      const ib = sizeOrder.indexOf(b);
      if (ia !== -1 && ib !== -1) return ia - ib;
      return a.localeCompare(b);
    });
  });

  readonly availableVariantsForSize = computed(() => {
    const prod = this.selectedProduct();
    const size = this.selectedSize();
    if (!prod || !size) return [];
    return prod.variantes.filter((v) => v.activo && v.talla === size);
  });

  readonly selectedVariant = computed(() => {
    const variantId = this.selectedVariantId();
    if (!variantId) return null;
    const prod = this.selectedProduct();
    if (prod) {
      const found = prod.variantes.find((v) => v.id_variante === variantId);
      if (found) return found;
    }
    for (const p of this.products()) {
      const found = p.variantes.find((v) => v.id_variante === variantId);
      if (found) return found;
    }
    return null;
  });

  readonly selectedStock = computed(() => {
    const v = this.selectedVariant();
    if (!v) return 0;
    return v.stock_disponible ?? 0;
  });

  readonly canAddCurrentVariant = computed(() => {
    const v = this.selectedVariant();
    if (!v) return false;
    const stock = v.stock_disponible ?? 0;
    const qty = this.quantity();
    return stock > 0 && qty > 0 && qty <= stock;
  });

  readonly currentItemSubtotal = computed(() => {
    const p = this.selectedProduct();
    if (!p || !this.selectedVariantId()) return 0;
    return Number(p.precio_actual || 0) * this.quantity();
  });

  readonly estimatedTotal = computed(() =>
    this.lines().reduce(
      (total, item) => total + Number(item.product.precio_actual || 0) * item.quantity,
      0,
    ),
  );

  constructor() {
    this.catalog.branches().subscribe({
      next: (branches) => {
        this.branches.set(branches);
        this.initBranchContext();
      },
      error: (error) => this.error.set(this.errors.message(error, 'No pudimos preparar la venta.')),
    });

    effect(() => {
      const user = this.auth.currentUser();
      if (user && this.branches().length && !this.selectedBranchId()) {
        this.initBranchContext();
      }
    });
  }

  private initBranchContext(): void {
    const user = this.currentUser();
    const branches = this.branches();
    if (!branches.length) return;

    const canSelect = !user?.id_sucursal || user.roles.includes('ADMIN');

    if (!canSelect && user?.id_sucursal) {
      this.selectedBranchId.set(user.id_sucursal);
      this.loadProducts(user.id_sucursal);
    } else {
      const defaultBranchId = this.selectedBranchId() || user?.id_sucursal || branches[0]?.id_sucursal || null;
      if (defaultBranchId) {
        this.selectedBranchId.set(defaultBranchId);
        this.loadProducts(defaultBranchId);
      } else {
        this.loadProducts();
      }
    }
  }

  private loadProducts(branchId?: number): void {
    const filters: { page_size: number; activo: boolean; sucursal?: number } = {
      page_size: 100,
      activo: true,
    };
    if (branchId) {
      filters.sucursal = branchId;
    }
    this.catalog.products(filters).subscribe({
      next: (data) => {
        this.products.set(data.items);
      },
      error: (error) => this.error.set(this.errors.message(error, 'No pudimos cargar las existencias.')),
    });
  }

  onBranchChange(branchIdStr: string): void {
    const branchId = branchIdStr ? Number(branchIdStr) : null;
    this.selectedBranchId.set(branchId);
    if (this.lines().length > 0) {
      this.lines.set([]);
      this.error.set('La sucursal cambió. El ticket fue reiniciado para reflejar el stock correspondiente.');
    }
    this.clearSelection();
    if (branchId) {
      this.loadProducts(branchId);
    }
  }

  onBrandChange(brandIdStr: string): void {
    const brandId = brandIdStr ? Number(brandIdStr) : null;
    this.selectedBrandId.set(brandId);
    this.selectedProductId.set(null);
    this.selectedSize.set('');
    this.selectedVariantId.set(null);
    this.quantity.set(1);
  }

  onProductChange(productIdStr: string): void {
    const prodId = productIdStr ? Number(productIdStr) : null;
    this.selectedProductId.set(prodId);
    this.selectedSize.set('');
    this.selectedVariantId.set(null);
    this.quantity.set(1);

    if (prodId) {
      const prod = this.products().find((p) => p.id_producto === prodId);
      if (prod) {
        const uniqueSizes = Array.from(
          new Set(prod.variantes.filter((v) => v.activo).map((v) => v.talla)),
        );
        if (uniqueSizes.length === 1) {
          this.onSizeChange(uniqueSizes[0]);
        }
      }
    }
  }

  onSizeChange(size: string): void {
    this.selectedSize.set(size);
    this.selectedVariantId.set(null);
    this.quantity.set(1);

    const prod = this.selectedProduct();
    if (prod) {
      const matchingVariants = prod.variantes.filter((v) => v.activo && v.talla === size);
      if (matchingVariants.length === 1) {
        this.onVariantChange(String(matchingVariants[0].id_variante));
      }
    }
  }

  onVariantChange(variantIdStr: string): void {
    const variantId = variantIdStr ? Number(variantIdStr) : null;
    this.selectedVariantId.set(variantId);
    this.quantity.set(1);
  }

  onQuantityInput(val: string): void {
    const parsed = parseInt(val, 10);
    const max = this.selectedStock();
    if (isNaN(parsed) || parsed < 1) {
      this.quantity.set(1);
    } else if (max > 0 && parsed > max) {
      this.quantity.set(max);
    } else {
      this.quantity.set(parsed);
    }
  }

  incrementQty(): void {
    const max = this.selectedStock();
    if (max > 0 && this.quantity() < max) {
      this.quantity.update((q) => q + 1);
    }
  }

  decrementQty(): void {
    if (this.quantity() > 1) {
      this.quantity.update((q) => q - 1);
    }
  }

  clearSelection(): void {
    this.selectedBrandId.set(null);
    this.selectedProductId.set(null);
    this.selectedSize.set('');
    this.selectedVariantId.set(null);
    this.quantity.set(1);
  }

  addLine(): void {
    const prod = this.selectedProduct();
    const variant = this.selectedVariant();
    const qty = this.quantity();
    if (!prod || !variant || qty <= 0) return;

    const available = variant.stock_disponible ?? 0;
    const currentLine = this.lines().find((item) => item.variant.id_variante === variant.id_variante);
    const currentQty = currentLine ? currentLine.quantity : 0;

    if (currentQty + qty > available && available > 0) {
      this.error.set(
        `Stock insuficiente: solo quedan ${available} unidad(es) en esta sucursal (tienes ${currentQty} en el ticket).`,
      );
      return;
    }

    this.lines.update((items) => {
      const existing = items.find((item) => item.variant.id_variante === variant.id_variante);
      return existing
        ? items.map((item) =>
            item.variant.id_variante === variant.id_variante
              ? { ...item, quantity: item.quantity + qty }
              : item,
          )
        : [...items, { product: prod, variant, quantity: qty }];
    });

    this.selectedVariantId.set(null);
    this.quantity.set(1);
    this.error.set('');
  }

  removeLine(id: number): void {
    this.lines.update((items) => items.filter((item) => item.variant.id_variante !== id));
  }

  updateLineQty(variantId: number, delta: number): void {
    this.lines.update((items) =>
      items
        .map((item) => {
          if (item.variant.id_variante === variantId) {
            const newQty = item.quantity + delta;
            const max = item.variant.stock_disponible ?? 999;
            if (newQty > max && max > 0) {
              this.error.set(`Stock máximo disponible alcanzado (${max} unidades).`);
              return item;
            }
            return newQty > 0 ? { ...item, quantity: newQty } : null;
          }
          return item;
        })
        .filter((item): item is SaleLine => item !== null),
    );
  }

  clearTicket(): void {
    this.lines.set([]);
    this.error.set('');
  }

  lineSubtotal(line: SaleLine): number {
    return Number(line.product.precio_actual || 0) * line.quantity;
  }

  confirm(): void {
    const branchId = this.selectedBranchId();
    if (!this.lines().length || !branchId) {
      this.error.set('Debes seleccionar una sucursal y agregar prendas al ticket.');
      return;
    }
    this.saving.set(true);
    this.error.set('');
    const customerId = this.selectedCustomer()?.id_cliente ?? null;
    this.commerce
      .createPosSale({
        id_sucursal: branchId,
        id_cliente: customerId,
        modalidad_entrega: 'ENTREGA_DIRECTA',
        registrar_efectivo: true,
        items: this.lines().map((item) => ({
          id_variante: item.variant.id_variante,
          cantidad: item.quantity,
        })),
      })
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (sale) => {
          this.completed.set(sale);
          this.lines.set([]);
          this.clearSelection();
          this.loadProducts(branchId);
        },
        error: (error) => {
          this.error.set(this.errors.message(error, 'No pudimos registrar la venta en caja.'));
        },
      });
  }

  setCustomerMode(mode: 'ANON' | 'SEARCH' | 'NEW'): void {
    this.customerMode.set(mode);
    if (mode === 'ANON') {
      this.selectedCustomer.set(null);
    }
  }

  onCustomerSearchInput(q: string): void {
    this.customerSearchQuery.set(q);
    if (!q || q.trim().length < 2) {
      this.customerSearchResults.set([]);
      return;
    }
    this.searchingCustomers.set(true);
    this.commerce.adminCustomers({ q: q.trim(), limit: 8 }).subscribe({
      next: (results) => {
        this.customerSearchResults.set(results);
        this.searchingCustomers.set(false);
      },
      error: () => {
        this.customerSearchResults.set([]);
        this.searchingCustomers.set(false);
      },
    });
  }

  selectCustomer(customer: CustomerAdminSummary): void {
    this.selectedCustomer.set(customer);
    this.customerSearchResults.set([]);
    this.customerSearchQuery.set('');
  }

  clearSelectedCustomer(): void {
    this.selectedCustomer.set(null);
  }

  saveQuickCustomer(): void {
    if (this.quickCustomerForm.invalid) return;
    this.savingQuickCustomer.set(true);
    this.error.set('');
    const val = this.quickCustomerForm.getRawValue();
    this.commerce
      .quickCreateCustomer({
        nombres: val.nombres.trim(),
        apellidos: val.apellidos.trim() || undefined,
        ci: val.ci.trim() || undefined,
        correo: val.correo.trim() || undefined,
        telefono: val.telefono.trim() || undefined,
      })
      .pipe(finalize(() => this.savingQuickCustomer.set(false)))
      .subscribe({
        next: (created) => {
          this.selectedCustomer.set(created);
          this.quickCustomerForm.reset();
        },
        error: (err) => {
          this.error.set(this.errors.message(err, 'No pudimos registrar los datos del cliente.'));
        },
      });
  }

  downloadSaleInvoice(saleId: number): void {
    this.downloadingInvoice.set(true);
    this.commerce
      .saleInvoice(saleId)
      .pipe(finalize(() => this.downloadingInvoice.set(false)))
      .subscribe({
        next: (blob) => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `factura_venta_${saleId}.pdf`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          a.remove();
        },
        error: (err) => {
          this.error.set(this.errors.message(err, 'No pudimos descargar la factura.'));
        },
      });
  }

  printTicket(): void {
    window.print();
  }

  resetPos(): void {
    this.completed.set(null);
    this.lines.set([]);
    this.clearSelection();
    this.selectedCustomer.set(null);
    this.customerMode.set('ANON');
    this.customerSearchQuery.set('');
    this.customerSearchResults.set([]);
    this.error.set('');
    const branchId = this.selectedBranchId();
    if (branchId) {
      this.loadProducts(branchId);
    }
  }
}

type ReservationTab =
  | 'TODOS'
  | 'PENDIENTE'
  | 'CONFIRMADA'
  | 'PREPARANDO'
  | 'LISTA'
  | 'CLIENTE_PRESENTE'
  | 'CONVERTIDA'
  | 'CANCELADA';

@Component({
  selector: 'app-reservations-admin',
  imports: [DatePipe, BolivianosPipe, StatusPanel, FormsModule],
  template: `
    <section class="orders-admin-surface">
      <header class="admin-page-heading">
        <div>
          <h1>Gestión de Reservas</h1>
          <p>Supervisa citas en sucursal, apartado de prendas en probador y conversión a ventas.</p>
        </div>
      </header>

      @if (error()) {
        <p class="admin-notice admin-notice--error">{{ error() }}</p>
      }
      @if (successMessage()) {
        <div class="admin-notice admin-notice--success" style="display: flex; justify-content: space-between; align-items: center;">
          <span>{{ successMessage() }}</span>
          <button type="button" (click)="successMessage.set('')" style="background: none; border: none; cursor: pointer; font-size: 1.1rem; color: inherit;" aria-label="Cerrar notificación">✕</button>
        </div>
      }

      <!-- Barra de pestañas por etapa de reserva -->
      <nav class="orders-tabs" aria-label="Etapas de reservas">
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'TODOS'"
          (click)="activeTab.set('TODOS')"
        >
          Todas
          <span class="orders-tab-badge">{{ counts().TODOS }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'PENDIENTE'"
          (click)="activeTab.set('PENDIENTE')"
        >
          Por confirmar
          <span class="orders-tab-badge orders-tab-badge--pending">{{ counts().PENDIENTE }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'CONFIRMADA'"
          (click)="activeTab.set('CONFIRMADA')"
        >
          Confirmadas
          <span class="orders-tab-badge orders-tab-badge--ready">{{ counts().CONFIRMADA }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'PREPARANDO'"
          (click)="activeTab.set('PREPARANDO')"
        >
          Apartando
          <span class="orders-tab-badge orders-tab-badge--preparing">{{ counts().PREPARANDO }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'LISTA'"
          (click)="activeTab.set('LISTA')"
        >
          En probador
          <span class="orders-tab-badge orders-tab-badge--completed">{{ counts().LISTA }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'CLIENTE_PRESENTE'"
          (click)="activeTab.set('CLIENTE_PRESENTE')"
        >
          Cliente en tienda
          <span class="orders-tab-badge orders-tab-badge--ready">{{ counts().CLIENTE_PRESENTE }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'CONVERTIDA'"
          (click)="activeTab.set('CONVERTIDA')"
        >
          Concretadas
          <span class="orders-tab-badge orders-tab-badge--completed">{{ counts().CONVERTIDA }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'CANCELADA'"
          (click)="activeTab.set('CANCELADA')"
        >
          Canceladas
          <span class="orders-tab-badge">{{ counts().CANCELADA }}</span>
        </button>
      </nav>

      <!-- Barra de filtros y búsqueda -->
      <div class="orders-filterbar">
        <div class="orders-filter-field">
          <label for="reservation-search">Buscar reserva o prenda</label>
          <input
            id="reservation-search"
            type="search"
            placeholder="Ej: #1, Ralph Lauren, S, Central..."
            [ngModel]="searchTerm()"
            (ngModelChange)="searchTerm.set($event)"
          />
        </div>
        <div class="orders-filter-field">
          <label for="reservation-branch">Sucursal</label>
          <select
            id="reservation-branch"
            [ngModel]="selectedBranch()"
            (ngModelChange)="selectedBranch.set($event)"
          >
            <option value="">Todas las sucursales</option>
            @for (b of branches(); track b.id_sucursal) {
              <option [value]="b.id_sucursal">{{ b.nombre }}</option>
            }
          </select>
        </div>
        <div class="orders-filter-field">
          <label for="reservation-date-filter">Horario de visita</label>
          <select
            id="reservation-date-filter"
            [ngModel]="selectedDateFilter()"
            (ngModelChange)="selectedDateFilter.set($event)"
          >
            <option value="TODAS">Todas las fechas</option>
            <option value="HOY">Citas de HOY</option>
            <option value="PROXIMAS">Próximas citas</option>
            <option value="SIN_CITA">Sin horario específico</option>
          </select>
        </div>
        <button
          type="button"
          class="orders-refresh-btn"
          [disabled]="loading() || saving()"
          (click)="load()"
          title="Actualizar reservas"
        >
          ↻ Actualizar
        </button>
      </div>

      <!-- Contenido de la tabla -->
      @if (loading()) {
        <div class="admin-skeleton-grid"><span></span></div>
      } @else if (!filteredItems().length) {
        <app-status-panel
          title="Sin reservas encontradas"
          message="No hay reservas que coincidan con los filtros o la pestaña seleccionada."
        />
      } @else {
        <div class="admin-table-wrap">
          <table class="orders-table">
            <thead>
              <tr>
                <th>Reserva</th>
                <th>Cita / Visita</th>
                <th>Sucursal</th>
                <th>Prendas Apartadas</th>
                <th>Total Estimado</th>
                <th>Estado</th>
                <th style="text-align: right;">Acción Siguiente</th>
              </tr>
            </thead>
            <tbody>
              @for (item of filteredItems(); track item.id_reserva) {
                <tr>
                  <!-- Reserva & Creación & Cliente -->
                  <td>
                    <div class="order-id-cell">
                      <span class="order-id-title">Reserva #{{ item.id_reserva }}</span>
                      <span class="order-date-text">{{ item.fecha_reserva | date: 'short' }}</span>
                      @if (item.cliente_nombre) {
                        <div class="order-customer-info">
                          <span class="order-customer-name">👤 {{ item.cliente_nombre }}</span>
                          @if (item.cliente_telefono) {
                            <small class="order-customer-contact">📞 {{ item.cliente_telefono }}</small>
                          } @else if (item.cliente_correo) {
                            <small class="order-customer-contact">✉️ {{ item.cliente_correo }}</small>
                          }
                        </div>
                      }
                    </div>
                  </td>

                  <!-- Cita / Visita -->
                  <td>
                    @if (isToday(item.fecha_cita)) {
                      <span class="order-mode-pill order-mode-pill--appointment-today">
                        🔥 CITA HOY
                      </span>
                      <strong class="order-location-text" style="color: #b45309; font-size: 0.85rem;">
                        {{ item.fecha_cita | date: 'HH:mm' }}
                      </strong>
                    } @else if (item.fecha_cita) {
                      <span class="order-mode-pill order-mode-pill--appointment">
                        📅 Visita programada
                      </span>
                      <small class="order-location-text">
                        {{ item.fecha_cita | date: 'dd/MM/yyyy HH:mm' }}
                      </small>
                    } @else {
                      <span class="order-mode-pill" style="background: var(--surface-muted); color: var(--ink-soft);">
                        Sin horario
                      </span>
                    }
                  </td>

                  <!-- Sucursal -->
                  <td>
                    <div class="order-id-cell">
                      <span class="orders-item-name" style="font-weight: 700;">
                        {{ formatBranchName(item.sucursal, item.id_sucursal) }}
                      </span>
                      @if (item.direccion_sucursal) {
                        <small class="order-location-text">{{ item.direccion_sucursal }}</small>
                      }
                    </div>
                  </td>

                  <!-- Prendas apartadas -->
                  <td>
                    <div class="orders-items-list">
                      @for (line of item.items; track line.id_detalle) {
                        <div class="orders-item-line">
                          @if (line.imagen_url) {
                            <img [src]="line.imagen_url" [alt]="line.producto" class="orders-item-thumb" />
                          } @else {
                            <span class="orders-item-thumb orders-item-thumb--placeholder">👕</span>
                          }
                          <div class="orders-item-info">
                            <span class="orders-item-name" [title]="line.producto">{{ line.producto }}</span>
                            <small class="orders-item-meta">
                              {{ line.color }} · Talla {{ line.talla }} <strong>×{{ line.cantidad }}</strong>
                            </small>
                          </div>
                        </div>
                      }
                    </div>
                  </td>

                  <!-- Total estimado -->
                  <td>
                    <div class="orders-price-cell">
                      <span class="orders-total-amount">{{ totalEstimated(item) | bolivianos }}</span>
                      <small style="color: var(--ink-soft); font-size: 0.72rem;">Pago en tienda</small>
                    </div>
                  </td>

                  <!-- Estado actual -->
                  <td>
                    <span class="order-badge" [class]="statusBadgeClass(item.estado)">
                      {{ statusLabel(item.estado) }}
                    </span>
                  </td>

                  <!-- Acción operativa -->
                  <td style="text-align: right;">
                    <div class="orders-action-cell" style="align-items: flex-end;">
                      @if (canQuickCharge(item)) {
                        <button
                          class="order-quick-pay-btn"
                          type="button"
                          [disabled]="saving()"
                          (click)="openPaymentModal(item)"
                          title="Cobrar en caja y formalizar venta"
                        >
                          💳 Cobrar en caja
                        </button>
                      }
                      @if (primaryAction(item); as act) {
                        <button
                          class="order-primary-btn"
                          type="button"
                          [disabled]="saving()"
                          (click)="handleAction(item, act)"
                        >
                          {{ act.label }}
                        </button>
                      }
                      @if (canCancel(item)) {
                        <button
                          class="order-cancel-btn"
                          type="button"
                          [disabled]="saving()"
                          (click)="confirmCancel(item)"
                        >
                          Cancelar reserva
                        </button>
                      }
                    </div>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }

      <!-- Modal de Cobro en Caja / Concretar Venta -->
      @if (checkoutReservation(); as res) {
        <div class="admin-modal-backdrop" (click)="closePaymentModal()">
          <div
            class="admin-modal-card"
            (click)="$event.stopPropagation()"
            role="dialog"
            aria-modal="true"
            aria-labelledby="checkout-modal-title"
          >
            <header class="admin-modal-header">
              <div>
                <span class="admin-modal-kicker">Caja y Facturación Presencial</span>
                <h2 id="checkout-modal-title" class="admin-modal-title">
                  Concretar Venta · Reserva #{{ res.id_reserva }}
                </h2>
                <p class="admin-modal-subtitle">
                  {{ formatBranchName(res.sucursal, res.id_sucursal) }} · {{ res.items.length }} prenda(s) reservada(s)
                </p>
              </div>
              <button
                type="button"
                class="admin-modal-close"
                (click)="closePaymentModal()"
                [disabled]="saving()"
                aria-label="Cerrar modal"
              >
                ✕
              </button>
            </header>

            <div class="admin-modal-body">
              <!-- Resumen de prendas reservadas -->
              <div class="checkout-summary-section">
                <span class="checkout-section-label">Prendas a facturar y retirar</span>
                <div class="checkout-items-list">
                  @for (line of res.items; track line.id_detalle) {
                    <div class="checkout-item-row">
                      @if (line.imagen_url) {
                        <img [src]="line.imagen_url" [alt]="line.producto" class="checkout-item-thumb" />
                      } @else {
                        <span class="checkout-item-thumb checkout-item-thumb--placeholder">👕</span>
                      }
                      <div class="checkout-item-details">
                        <span class="checkout-item-name">{{ line.producto }}</span>
                        <div class="checkout-item-badges">
                          <span class="checkout-badge-prop">{{ line.color }}</span>
                          <span class="checkout-badge-prop">Talla {{ line.talla }}</span>
                          <span class="checkout-badge-qty">×{{ line.cantidad }}</span>
                        </div>
                      </div>
                      <div class="checkout-item-price">
                        <span class="checkout-subtotal">{{ line.subtotal | bolivianos }}</span>
                        <small class="checkout-unit-price">{{ line.precio_unitario | bolivianos }} c/u</small>
                      </div>
                    </div>
                  }
                </div>
              </div>

              <!-- Banner de Total a Cobrar -->
              <div class="checkout-total-banner">
                <div class="checkout-total-banner__label">
                  <span>TOTAL A COBRAR</span>
                  <small>Prendas reservadas en tienda</small>
                </div>
                <div class="checkout-total-banner__amount">
                  {{ totalEstimated(res) | bolivianos }}
                </div>
              </div>

              <!-- Selector de Método de Pago -->
              <div class="checkout-method-section">
                <span class="checkout-section-label">Método de cobro</span>
                <div class="payment-method-grid">
                  <button
                    type="button"
                    class="payment-method-card"
                    [class.is-selected]="paymentMethod() === 'EFECTIVO'"
                    (click)="paymentMethod.set('EFECTIVO')"
                  >
                    <span class="payment-method-icon">💵</span>
                    <strong class="payment-method-title">Efectivo</strong>
                    <span class="payment-method-desc">Cálculo de cambio</span>
                  </button>
                  <button
                    type="button"
                    class="payment-method-card"
                    [class.is-selected]="paymentMethod() === 'TARJETA'"
                    (click)="paymentMethod.set('TARJETA')"
                  >
                    <span class="payment-method-icon">💳</span>
                    <strong class="payment-method-title">Tarjeta (POS)</strong>
                    <span class="payment-method-desc">Débito / Crédito</span>
                  </button>
                </div>
              </div>

              <!-- Configuración / Dinámica según Método -->
              @if (paymentMethod() === 'EFECTIVO') {
                <div class="checkout-method-detail cash-detail-box">
                  <div class="cash-input-group">
                    <label for="cash-received-input">Efectivo recibido del cliente (Bs.)</label>
                    <div class="cash-input-wrap">
                      <span class="cash-currency-symbol">Bs.</span>
                      <input
                        id="cash-received-input"
                        type="number"
                        step="1"
                        min="0"
                        class="cash-input"
                        [ngModel]="amountReceived()"
                        (ngModelChange)="amountReceived.set($event)"
                        placeholder="0.00"
                      />
                    </div>
                  </div>

                  <!-- Botones de billetes rápidos -->
                  <div class="cash-quick-buttons">
                    <span class="cash-quick-label">Atajos:</span>
                    <button type="button" class="cash-chip-btn" (click)="setExactCash()">
                      Exacto ({{ totalEstimated(res) | bolivianos }})
                    </button>
                    <button type="button" class="cash-chip-btn" (click)="addCash(10)">+10</button>
                    <button type="button" class="cash-chip-btn" (click)="addCash(20)">+20</button>
                    <button type="button" class="cash-chip-btn" (click)="addCash(50)">+50</button>
                    <button type="button" class="cash-chip-btn" (click)="addCash(100)">+100</button>
                  </div>

                  <!-- Cálculo de vuelto o faltante -->
                  @if (cashShortage() > 0) {
                    <div class="cash-alert cash-alert--shortage">
                      <span class="cash-alert-icon">⚠️</span>
                      <div>
                        <strong>Monto insuficiente</strong>
                        <p>Faltan {{ cashShortage() | bolivianos }} para cubrir el total de la reserva.</p>
                      </div>
                    </div>
                  } @else {
                    <div class="cash-change-display">
                      <span class="cash-change-label">CAMBIO / VUELTO A ENTREGAR:</span>
                      <strong class="cash-change-amount">{{ changeAmount() | bolivianos }}</strong>
                    </div>
                  }
                </div>
              } @else if (paymentMethod() === 'TARJETA') {
                <div class="checkout-method-detail card-detail-box">
                  <div class="pos-info-banner">
                    <span class="pos-icon">💳</span>
                    <p>
                      Pase la tarjeta del cliente por el dispositivo POS físico de la tienda. Una vez aprobada la transacción en el POS, ingrese el número de autorización para auditoría.
                    </p>
                  </div>
                  <div class="ref-input-group">
                    <label for="pos-reference-input">N° de Autorización o Referencia del POS (Opcional)</label>
                    <input
                      id="pos-reference-input"
                      type="text"
                      class="ref-input"
                      placeholder="Ej: POS-94821 o N° de voucher"
                      [ngModel]="cardReference()"
                      (ngModelChange)="cardReference.set($event)"
                    />
                  </div>
                </div>
              }
            </div>

            <footer class="admin-modal-footer">
              <button
                type="button"
                class="admin-modal-btn admin-modal-btn--secondary"
                (click)="closePaymentModal()"
                [disabled]="saving()"
              >
                Cancelar
              </button>
              <button
                type="button"
                class="admin-modal-btn admin-modal-btn--primary"
                (click)="submitPosSale()"
                [disabled]="saving() || (paymentMethod() === 'EFECTIVO' && cashShortage() > 0)"
              >
                @if (saving()) {
                  <span>Registrando venta...</span>
                } @else {
                  <span>✓ Registrar Pago y Concretar ({{ totalEstimated(res) | bolivianos }})</span>
                }
              </button>
            </footer>
          </div>
        </div>
      }
    </section>
  `,
})
export class ReservationsAdmin {
  private readonly commerce = inject(CommerceService);
  private readonly catalog = inject(CatalogService);
  private readonly errors = inject(ApiErrorService);

  readonly items = signal<Reservation[]>([]);
  readonly branches = signal<Branch[]>([]);
  readonly activeTab = signal<ReservationTab>('TODOS');
  readonly searchTerm = signal<string>('');
  readonly selectedBranch = signal<string>('');
  readonly selectedDateFilter = signal<'TODAS' | 'HOY' | 'PROXIMAS' | 'SIN_CITA'>('TODAS');
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly successMessage = signal<string>('');
  readonly formatBranchName = formatBranchName;

  readonly checkoutReservation = signal<Reservation | null>(null);
  readonly paymentMethod = signal<'EFECTIVO' | 'TARJETA'>('EFECTIVO');
  readonly amountReceived = signal<number>(0);
  readonly cardReference = signal<string>('');

  readonly changeAmount = computed(() => {
    const res = this.checkoutReservation();
    if (!res) return 0;
    const total = this.totalEstimated(res);
    const received = Number(this.amountReceived()) || 0;
    return Math.max(0, received - total);
  });

  readonly cashShortage = computed(() => {
    const res = this.checkoutReservation();
    if (!res) return 0;
    const total = this.totalEstimated(res);
    const received = Number(this.amountReceived()) || 0;
    return Math.max(0, total - received);
  });

  readonly counts = computed(() => {
    const all = this.items();
    return {
      TODOS: all.length,
      PENDIENTE: all.filter((r) => r.estado === 'PENDIENTE').length,
      CONFIRMADA: all.filter((r) => r.estado === 'CONFIRMADA').length,
      PREPARANDO: all.filter((r) => r.estado === 'PREPARANDO').length,
      LISTA: all.filter((r) => r.estado === 'LISTA').length,
      CLIENTE_PRESENTE: all.filter((r) => r.estado === 'CLIENTE_PRESENTE').length,
      CONVERTIDA: all.filter((r) => r.estado === 'CONVERTIDA').length,
      CANCELADA: all.filter((r) => r.estado === 'CANCELADA' || r.estado === 'EXPIRADA').length,
    };
  });

  readonly filteredItems = computed(() => {
    let result = this.items();
    const tab = this.activeTab();
    if (tab === 'PENDIENTE') {
      result = result.filter((r) => r.estado === 'PENDIENTE');
    } else if (tab === 'CONFIRMADA') {
      result = result.filter((r) => r.estado === 'CONFIRMADA');
    } else if (tab === 'PREPARANDO') {
      result = result.filter((r) => r.estado === 'PREPARANDO');
    } else if (tab === 'LISTA') {
      result = result.filter((r) => r.estado === 'LISTA');
    } else if (tab === 'CLIENTE_PRESENTE') {
      result = result.filter((r) => r.estado === 'CLIENTE_PRESENTE');
    } else if (tab === 'CONVERTIDA') {
      result = result.filter((r) => r.estado === 'CONVERTIDA');
    } else if (tab === 'CANCELADA') {
      result = result.filter((r) => r.estado === 'CANCELADA' || r.estado === 'EXPIRADA');
    }

    const branch = this.selectedBranch();
    if (branch) {
      result = result.filter((r) => r.id_sucursal === Number(branch));
    }

    const dateFilter = this.selectedDateFilter();
    if (dateFilter === 'HOY') {
      result = result.filter((r) => this.isToday(r.fecha_cita));
    } else if (dateFilter === 'PROXIMAS') {
      const now = new Date();
      result = result.filter((r) => r.fecha_cita && new Date(r.fecha_cita) >= now);
    } else if (dateFilter === 'SIN_CITA') {
      result = result.filter((r) => !r.fecha_cita);
    }

    const search = this.searchTerm().trim().toLowerCase();
    if (search) {
      result = result.filter((r) => {
        const idMatch = String(r.id_reserva).includes(search) || `#${r.id_reserva}`.includes(search);
        const branchMatch = r.sucursal.toLowerCase().includes(search);
        const itemsMatch = r.items.some(
          (i) =>
            i.producto.toLowerCase().includes(search) ||
            i.color.toLowerCase().includes(search) ||
            i.talla.toLowerCase().includes(search) ||
            i.sku.toLowerCase().includes(search),
        );
        const addressMatch = (r.direccion_sucursal || '').toLowerCase().includes(search);
        const customerMatch =
          (r.cliente_nombre || '').toLowerCase().includes(search) ||
          (r.cliente_correo || '').toLowerCase().includes(search) ||
          (r.cliente_telefono || '').toLowerCase().includes(search);
        return idMatch || branchMatch || itemsMatch || addressMatch || customerMatch;
      });
    }

    return result;
  });

  constructor() {
    this.load();
    this.catalog.branches().subscribe({
      next: (branches) => this.branches.set(branches),
      error: () => {},
    });
  }

  load(): void {
    this.loading.set(true);
    this.commerce
      .adminReservations()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (items) => this.items.set(items),
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos cargar las reservas.')),
      });
  }

  primaryAction(item: Reservation): { targetState: string; label: string } | null {
    switch (item.estado) {
      case 'PENDIENTE':
        return { targetState: 'CONFIRMADA', label: 'Confirmar cita ✓' };
      case 'CONFIRMADA':
        return { targetState: 'PREPARANDO', label: 'Apartar prendas 👕' };
      case 'PREPARANDO':
        return { targetState: 'LISTA', label: 'Lista en probador 🛍️' };
      case 'LISTA':
        return { targetState: 'CLIENTE_PRESENTE', label: 'Cliente en tienda 👤' };
      case 'CLIENTE_PRESENTE':
        return { targetState: 'CONVERTIDA', label: 'Concretar venta 💳' };
      default:
        return null;
    }
  }

  canCancel(item: Reservation): boolean {
    return ['PENDIENTE', 'CONFIRMADA', 'PREPARANDO', 'LISTA', 'CLIENTE_PRESENTE'].includes(
      item.estado,
    );
  }

  confirmCancel(item: Reservation): void {
    if (
      confirm(
        `¿Estás seguro de cancelar la Reserva #${item.id_reserva}? Las prendas reservadas volverán al stock disponible.`,
      )
    ) {
      this.update(item.id_reserva, 'CANCELADA');
    }
  }

  totalEstimated(item: Reservation): number {
    return item.items.reduce((acc, line) => acc + Number(line.subtotal || 0), 0);
  }

  isToday(dateStr: string | null): boolean {
    if (!dateStr) return false;
    const d = new Date(dateStr);
    const today = new Date();
    return (
      d.getDate() === today.getDate() &&
      d.getMonth() === today.getMonth() &&
      d.getFullYear() === today.getFullYear()
    );
  }

  statusLabel(state: string): string {
    switch (state) {
      case 'PENDIENTE':
        return 'Por confirmar';
      case 'CONFIRMADA':
        return 'Confirmada';
      case 'PREPARANDO':
        return 'Apartando';
      case 'LISTA':
        return 'Lista en probador';
      case 'CLIENTE_PRESENTE':
        return 'Cliente en tienda';
      case 'CONVERTIDA':
        return 'Venta concretada';
      case 'CANCELADA':
        return 'Cancelada';
      case 'EXPIRADA':
        return 'Expirada';
      default:
        return state;
    }
  }

  statusBadgeClass(state: string): string {
    switch (state) {
      case 'PENDIENTE':
        return 'order-badge--pending';
      case 'CONFIRMADA':
        return 'order-badge--ready';
      case 'PREPARANDO':
        return 'order-badge--preparing';
      case 'LISTA':
        return 'order-badge--completed';
      case 'CLIENTE_PRESENTE':
        return 'order-badge--ready';
      case 'CONVERTIDA':
        return 'order-badge--completed';
      case 'CANCELADA':
      case 'EXPIRADA':
        return 'order-badge--cancelled';
      default:
        return 'order-badge--default';
    }
  }

  update(id: number, state: string): void {
    this.saving.set(true);
    this.commerce
      .updateReservation(id, state)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (updated) =>
          this.items.update((items) =>
            items.map((item) => (item.id_reserva === id ? updated : item)),
          ),
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos actualizar la reserva.')),
      });
  }

  canQuickCharge(item: Reservation): boolean {
    return ['PREPARANDO', 'LISTA'].includes(item.estado);
  }

  handleAction(item: Reservation, act: { targetState: string; label: string }): void {
    if (act.targetState === 'CONVERTIDA') {
      this.openPaymentModal(item);
    } else {
      this.update(item.id_reserva, act.targetState);
    }
  }

  openPaymentModal(res: Reservation): void {
    this.checkoutReservation.set(res);
    this.paymentMethod.set('EFECTIVO');
    const total = this.totalEstimated(res);
    this.amountReceived.set(total);
    this.cardReference.set('');
    this.error.set('');
  }

  closePaymentModal(): void {
    if (this.saving()) return;
    this.checkoutReservation.set(null);
  }

  setExactCash(): void {
    const res = this.checkoutReservation();
    if (!res) return;
    this.amountReceived.set(this.totalEstimated(res));
  }

  addCash(extra: number): void {
    const current = Number(this.amountReceived()) || 0;
    this.amountReceived.set(current + extra);
  }

  paymentMethodLabel(m: 'EFECTIVO' | 'TARJETA'): string {
    switch (m) {
      case 'EFECTIVO':
        return 'Efectivo';
      case 'TARJETA':
        return 'Tarjeta (POS)';
    }
  }

  submitPosSale(): void {
    const res = this.checkoutReservation();
    if (!res) return;

    const method = this.paymentMethod();
    const total = this.totalEstimated(res);
    const received = Number(this.amountReceived()) || 0;

    if (method === 'EFECTIVO' && received < total) {
      this.error.set(
        `El monto recibido (Bs. ${received.toFixed(2)}) es insuficiente para cubrir el total (Bs. ${total.toFixed(2)}).`,
      );
      return;
    }

    let ref: string | null = null;
    if (method === 'TARJETA') {
      ref = this.cardReference().trim() || null;
    }

    const payload = {
      id_sucursal: res.id_sucursal,
      id_reserva: res.id_reserva,
      modalidad_entrega: 'ENTREGA_DIRECTA',
      items: res.items.map((line) => ({
        id_variante: line.id_variante,
        cantidad: line.cantidad,
      })),
      registrar_efectivo: true,
      metodo_pago: method,
      referencia_pago: ref,
    };

    this.saving.set(true);
    this.error.set('');

    this.commerce
      .createPosSale(payload)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (sale) => {
          this.checkoutReservation.set(null);
          const saleId = sale.id_venta ? ` #${sale.id_venta}` : '';
          this.successMessage.set(
            `¡Venta${saleId} registrada con éxito mediante ${this.paymentMethodLabel(method)}! Stock consumido y reserva finalizada.`,
          );
          this.items.update((items) =>
            items.map((item) =>
              item.id_reserva === res.id_reserva ? { ...item, estado: 'CONVERTIDA' } : item,
            ),
          );
          setTimeout(() => {
            if (this.successMessage().includes(saleId)) {
              this.successMessage.set('');
            }
          }, 8000);
        },
        error: (err) => {
          this.error.set(this.errors.message(err, 'No pudimos registrar la venta en caja.'));
        },
      });
  }
}

type OrderTab = 'TODOS' | 'PENDIENTE' | 'PREPARANDO' | 'LISTO' | 'COMPLETADO' | 'CANCELADO';

@Component({
  selector: 'app-orders-admin',
  imports: [DatePipe, BolivianosPipe, StatusPanel, FormsModule],
  template: `
    <section class="orders-admin-surface">
      <header class="admin-page-heading">
        <div>
          <h1>Gestión de Pedidos</h1>
          <p>Controla el pipeline de despacho: preparación, entrega en tienda y envíos delivery.</p>
        </div>
      </header>

      @if (error()) {
        <p class="admin-notice admin-notice--error">{{ error() }}</p>
      }

      <!-- Barra de pestañas por etapa -->
      <nav class="orders-tabs" aria-label="Etapas de pedidos">
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'TODOS'"
          (click)="activeTab.set('TODOS')"
        >
          Todos
          <span class="orders-tab-badge">{{ counts().TODOS }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'PENDIENTE'"
          (click)="activeTab.set('PENDIENTE')"
        >
          Por preparar
          <span class="orders-tab-badge orders-tab-badge--pending">{{ counts().PENDIENTE }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'PREPARANDO'"
          (click)="activeTab.set('PREPARANDO')"
        >
          En preparación
          <span class="orders-tab-badge orders-tab-badge--preparing">{{ counts().PREPARANDO }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'LISTO'"
          (click)="activeTab.set('LISTO')"
        >
          Listos para entrega
          <span class="orders-tab-badge orders-tab-badge--ready">{{ counts().LISTO }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'COMPLETADO'"
          (click)="activeTab.set('COMPLETADO')"
        >
          Completados
          <span class="orders-tab-badge orders-tab-badge--completed">{{ counts().COMPLETADO }}</span>
        </button>
        <button
          type="button"
          class="orders-tab"
          [class.is-active]="activeTab() === 'CANCELADO'"
          (click)="activeTab.set('CANCELADO')"
        >
          Cancelados
          <span class="orders-tab-badge">{{ counts().CANCELADO }}</span>
        </button>
      </nav>

      <!-- Barra de filtros y búsqueda -->
      <div class="orders-filterbar">
        <div class="orders-filter-field">
          <label for="order-search">Buscar pedido, prenda o cliente</label>
          <input
            id="order-search"
            type="search"
            placeholder="Ej: #12, Cliente, Polo, Verde, Central..."
            [ngModel]="searchTerm()"
            (ngModelChange)="searchTerm.set($event)"
          />
        </div>
        <div class="orders-filter-field">
          <label for="order-branch">Sucursal</label>
          <select
            id="order-branch"
            [ngModel]="selectedBranch()"
            (ngModelChange)="selectedBranch.set($event)"
          >
            <option value="">Todas las sucursales</option>
            @for (b of branches(); track b.id_sucursal) {
              <option [value]="b.id_sucursal">{{ b.nombre }}</option>
            }
          </select>
        </div>
        <div class="orders-filter-field">
          <label for="order-mode">Modalidad</label>
          <select
            id="order-mode"
            [ngModel]="selectedMode()"
            (ngModelChange)="selectedMode.set($event)"
          >
            <option value="">Todas las modalidades</option>
            <option value="RETIRO_SUCURSAL">Retiro en tienda</option>
            <option value="DELIVERY">Delivery a domicilio</option>
          </select>
        </div>
        <button
          type="button"
          class="orders-refresh-btn"
          [disabled]="loading() || saving()"
          (click)="load()"
          title="Actualizar pedidos"
        >
          ↻ Actualizar
        </button>
      </div>

      <!-- Contenido de la tabla -->
      @if (loading()) {
        <div class="admin-skeleton-grid"><span></span></div>
      } @else if (!filteredItems().length) {
        <app-status-panel
          title="Sin pedidos encontrados"
          message="No hay pedidos que coincidan con el filtro o la pestaña seleccionada."
        />
      } @else {
        <div class="admin-table-wrap">
          <table class="orders-table">
            <thead>
              <tr>
                <th>Pedido</th>
                <th>Modalidad & Destino</th>
                <th>Prendas a Entregar</th>
                <th>Total & Pago</th>
                <th>Estado</th>
                <th style="text-align: right;">Acción Siguiente</th>
              </tr>
            </thead>
            <tbody>
              @for (item of filteredItems(); track item.id_pedido) {
                <tr>
                  <!-- Pedido & Fecha & Cliente -->
                  <td>
                    <div class="order-id-cell">
                      <span class="order-id-title">Pedido #{{ item.id_pedido }}</span>
                      <span class="order-date-text">{{ item.fecha_creacion | date: 'short' }}</span>
                      @if (item.cliente_nombre) {
                        <div class="order-customer-info">
                          <span class="order-customer-name">👤 {{ item.cliente_nombre }}</span>
                          @if (item.cliente_telefono) {
                            <small class="order-customer-contact">📞 {{ item.cliente_telefono }}</small>
                          } @else if (item.cliente_correo) {
                            <small class="order-customer-contact">✉️ {{ item.cliente_correo }}</small>
                          }
                        </div>
                      }
                    </div>
                  </td>

                  <!-- Modalidad & Destino -->
                  <td>
                    @if (item.modalidad_entrega === 'DELIVERY') {
                      <span class="order-mode-pill order-mode-pill--delivery">
                        🚚 Delivery
                      </span>
                      <small class="order-location-text">
                        {{ item.direccion_entrega || 'Dirección del cliente' }}
                      </small>
                    } @else {
                      <span class="order-mode-pill order-mode-pill--pickup">
                        🏬 Retiro en tienda
                      </span>
                      <small class="order-location-text">
                        {{ item.sucursal }} · {{ item.direccion_sucursal }}
                      </small>
                    }
                  </td>

                  <!-- Prendas a entregar -->
                  <td>
                    <div class="orders-items-list">
                      @for (line of item.items; track line.id_detalle) {
                        <div class="orders-item-line">
                          @if (line.imagen_url) {
                            <img [src]="line.imagen_url" [alt]="line.producto" class="orders-item-thumb" />
                          } @else {
                            <span class="orders-item-thumb orders-item-thumb--placeholder">👕</span>
                          }
                          <div class="orders-item-info">
                            <span class="orders-item-name" [title]="line.producto">{{ line.producto }}</span>
                            <small class="orders-item-meta">
                              {{ line.color }} · Talla {{ line.talla }} <strong>×{{ line.cantidad }}</strong>
                            </small>
                          </div>
                        </div>
                      }
                    </div>
                  </td>

                  <!-- Total y comprobante -->
                  <td>
                    <div class="orders-price-cell">
                      <span class="orders-total-amount">{{ item.total | bolivianos }}</span>
                      @if (item.receipt_url) {
                        <a
                          [href]="item.receipt_url"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="orders-receipt-link"
                        >
                          Recibo Stripe ↗
                        </a>
                      } @else {
                        <span class="orders-paid-chip">✓ Pagado</span>
                      }
                    </div>
                  </td>

                  <!-- Estado actual -->
                  <td>
                    <span class="order-badge" [class]="statusBadgeClass(item.estado)">
                      {{ statusLabel(item.estado) }}
                    </span>
                  </td>

                  <!-- Acción principal y secundaria -->
                  <td style="text-align: right;">
                    <div class="orders-action-cell" style="align-items: flex-end;">
                      @if (primaryAction(item); as act) {
                        <button
                          class="order-primary-btn"
                          type="button"
                          [disabled]="saving()"
                          (click)="update(item.id_pedido, act.targetState)"
                        >
                          {{ act.label }}
                        </button>
                      }
                      @if (canCancel(item)) {
                        <button
                          class="order-cancel-btn"
                          type="button"
                          [disabled]="saving()"
                          (click)="confirmCancel(item)"
                        >
                          Cancelar pedido
                        </button>
                      }
                    </div>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }
    </section>
  `,
})
export class OrdersAdmin {
  private readonly commerce = inject(CommerceService);
  private readonly catalog = inject(CatalogService);
  private readonly errors = inject(ApiErrorService);

  readonly items = signal<Order[]>([]);
  readonly branches = signal<Branch[]>([]);
  readonly activeTab = signal<OrderTab>('TODOS');
  readonly searchTerm = signal<string>('');
  readonly selectedBranch = signal<string>('');
  readonly selectedMode = signal<string>('');
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal('');

  readonly counts = computed(() => {
    const all = this.items();
    return {
      TODOS: all.length,
      PENDIENTE: all.filter((o) => o.estado === 'PENDIENTE').length,
      PREPARANDO: all.filter((o) => o.estado === 'PREPARANDO').length,
      LISTO: all.filter(
        (o) => o.estado === 'LISTO_PARA_RETIRO' || o.estado === 'LISTO_PARA_ENVIO',
      ).length,
      COMPLETADO: all.filter((o) => o.estado === 'RETIRADO' || o.estado === 'ENTREGADO').length,
      CANCELADO: all.filter((o) => o.estado === 'CANCELADO').length,
    };
  });

  readonly filteredItems = computed(() => {
    let result = this.items();
    const tab = this.activeTab();
    if (tab === 'PENDIENTE') {
      result = result.filter((o) => o.estado === 'PENDIENTE');
    } else if (tab === 'PREPARANDO') {
      result = result.filter((o) => o.estado === 'PREPARANDO');
    } else if (tab === 'LISTO') {
      result = result.filter(
        (o) => o.estado === 'LISTO_PARA_RETIRO' || o.estado === 'LISTO_PARA_ENVIO',
      );
    } else if (tab === 'COMPLETADO') {
      result = result.filter((o) => o.estado === 'RETIRADO' || o.estado === 'ENTREGADO');
    } else if (tab === 'CANCELADO') {
      result = result.filter((o) => o.estado === 'CANCELADO');
    }

    const branch = this.selectedBranch();
    if (branch) {
      result = result.filter((o) => o.id_sucursal === Number(branch));
    }

    const mode = this.selectedMode();
    if (mode) {
      result = result.filter((o) => o.modalidad_entrega === mode);
    }

    const search = this.searchTerm().trim().toLowerCase();
    if (search) {
      result = result.filter((o) => {
        const idMatch = String(o.id_pedido).includes(search) || `#${o.id_pedido}`.includes(search);
        const branchMatch = o.sucursal.toLowerCase().includes(search);
        const itemsMatch = o.items.some(
          (i) =>
            i.producto.toLowerCase().includes(search) ||
            i.color.toLowerCase().includes(search) ||
            i.sku.toLowerCase().includes(search),
        );
        const addressMatch = (o.direccion_entrega || o.direccion_sucursal || '')
          .toLowerCase()
          .includes(search);
        const customerMatch =
          (o.cliente_nombre || '').toLowerCase().includes(search) ||
          (o.cliente_correo || '').toLowerCase().includes(search) ||
          (o.cliente_telefono || '').toLowerCase().includes(search);
        return idMatch || branchMatch || itemsMatch || addressMatch || customerMatch;
      });
    }

    return result;
  });

  constructor() {
    this.load();
    this.catalog.branches().subscribe({
      next: (branches) => this.branches.set(branches),
      error: () => {},
    });
  }

  load(): void {
    this.loading.set(true);
    this.commerce
      .adminOrders()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (items) => this.items.set(items),
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos cargar los pedidos.')),
      });
  }

  primaryAction(item: Order): { targetState: string; label: string } | null {
    switch (item.estado) {
      case 'PENDIENTE':
        return { targetState: 'PREPARANDO', label: 'Comenzar preparación' };
      case 'PREPARANDO':
        return item.modalidad_entrega === 'DELIVERY'
          ? { targetState: 'LISTO_PARA_ENVIO', label: 'Listo para envío' }
          : { targetState: 'LISTO_PARA_RETIRO', label: 'Listo para retiro' };
      case 'LISTO_PARA_RETIRO':
        return { targetState: 'RETIRADO', label: 'Entregar (Retirado) ✓' };
      case 'LISTO_PARA_ENVIO':
        return { targetState: 'EN_CAMINO', label: 'Despachar (En camino)' };
      case 'RECOGIDO':
        return { targetState: 'EN_CAMINO', label: 'En camino' };
      case 'EN_CAMINO':
        return { targetState: 'ENTREGADO', label: 'Confirmar entrega ✓' };
      default:
        return null;
    }
  }

  canCancel(item: Order): boolean {
    return ['PENDIENTE', 'PREPARANDO', 'LISTO_PARA_RETIRO', 'LISTO_PARA_ENVIO'].includes(item.estado);
  }

  confirmCancel(item: Order): void {
    if (confirm(`¿Confirmas que deseas cancelar el Pedido #${item.id_pedido}? Las prendas retornarán al stock.`)) {
      this.update(item.id_pedido, 'CANCELADO');
    }
  }

  statusLabel(state: string): string {
    const map: Record<string, string> = {
      PENDIENTE: 'Por preparar',
      PREPARANDO: 'En preparación',
      LISTO_PARA_RETIRO: 'Listo para retiro',
      LISTO_PARA_ENVIO: 'Listo para envío',
      RECOGIDO: 'Recogido',
      EN_CAMINO: 'En camino',
      RETIRADO: 'Retirado en tienda',
      ENTREGADO: 'Entregado a cliente',
      CANCELADO: 'Cancelado',
    };
    return map[state] || state.replaceAll('_', ' ');
  }

  statusBadgeClass(state: string): string {
    switch (state) {
      case 'PENDIENTE':
        return 'order-badge--pending';
      case 'PREPARANDO':
        return 'order-badge--preparing';
      case 'LISTO_PARA_RETIRO':
      case 'LISTO_PARA_ENVIO':
        return 'order-badge--ready';
      case 'RETIRADO':
      case 'ENTREGADO':
        return 'order-badge--completed';
      case 'CANCELADO':
        return 'order-badge--cancelled';
      default:
        return 'order-badge--default';
    }
  }

  update(id: number, state: string): void {
    this.saving.set(true);
    this.commerce
      .updateOrder(id, state)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (updated) =>
          this.items.update((items) =>
            items.map((item) => (item.id_pedido === id ? updated : item)),
          ),
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos actualizar el pedido.')),
      });
  }
}

@Component({
  selector: 'app-returns-admin',
  imports: [CommonModule, FormsModule, DatePipe, BolivianosPipe, StatusPanel],
  template: `
    <section class="returns-admin-view">
      <header class="admin-page-heading">
        <div>
          <p class="eyebrow">Gestión Posventa</p>
          <h1>Devoluciones</h1>
          <p>Revisa solicitudes online y gestiona devoluciones en mostrador bajo la política de máximo 5 días hábiles.</p>
        </div>
        <button class="button button--primary" type="button" (click)="openCounterReturnModal()">
          + Registrar Devolución en Mostrador
        </button>
      </header>

      @if (successMessage()) {
        <div class="admin-notice admin-notice--success" role="status">
          <span>{{ successMessage() }}</span>
          <button type="button" class="pos-notice-close" (click)="successMessage.set('')" aria-label="Cerrar">✕</button>
        </div>
      }

      @if (error()) {
        <div class="admin-notice admin-notice--error" role="alert">
          <span>{{ error() }}</span>
          <button type="button" class="pos-notice-close" (click)="error.set('')" aria-label="Cerrar">✕</button>
        </div>
      }

      <!-- Métricas KPIs -->
      <div class="sales-kpi-grid">
        <div class="sales-kpi-card sales-kpi-card--total">
          <span class="kpi-icon">📦</span>
          <div class="kpi-info">
            <span class="kpi-label">Total Devoluciones</span>
            <strong class="kpi-value">{{ kpis().total }}</strong>
            <span class="kpi-sub">Histórico acumulado</span>
          </div>
        </div>

        <div class="sales-kpi-card returns-kpi-card--pending">
          <span class="kpi-icon">⏳</span>
          <div class="kpi-info">
            <span class="kpi-label">Pendientes</span>
            <strong class="kpi-value" style="color: #d97706;">{{ kpis().pending }}</strong>
            <span class="kpi-sub">Por revisar o inspeccionar</span>
          </div>
        </div>

        <div class="sales-kpi-card returns-kpi-card--approved">
          <span class="kpi-icon">📋</span>
          <div class="kpi-info">
            <span class="kpi-label">Aprobadas</span>
            <strong class="kpi-value" style="color: #2563eb;">{{ kpis().approved }}</strong>
            <span class="kpi-sub">Esperando recepción física</span>
          </div>
        </div>

        <div class="sales-kpi-card returns-kpi-card--completed">
          <span class="kpi-icon">✅</span>
          <div class="kpi-info">
            <span class="kpi-label">Completadas</span>
            <strong class="kpi-value" style="color: #059669;">{{ kpis().completed }}</strong>
            <span class="kpi-sub">Recepción inspeccionada</span>
          </div>
        </div>

        <div class="sales-kpi-card returns-kpi-card--rejected">
          <span class="kpi-icon">✕</span>
          <div class="kpi-info">
            <span class="kpi-label">Rechazadas</span>
            <strong class="kpi-value" style="color: #dc2626;">{{ kpis().rejected }}</strong>
            <span class="kpi-sub">Fuera de plazo / condición</span>
          </div>
        </div>
      </div>

      <!-- Barra de Filtros y Búsqueda -->
      <div class="sales-filterbar">
        <div class="sales-tabs">
          <button
            type="button"
            class="sales-tab"
            [class.sales-tab--active]="statusTab() === 'TODAS'"
            (click)="statusTab.set('TODAS')"
          >
            Todas <span class="sales-tab-badge">{{ kpis().total }}</span>
          </button>
          <button
            type="button"
            class="sales-tab"
            [class.sales-tab--active]="statusTab() === 'PENDIENTE'"
            (click)="statusTab.set('PENDIENTE')"
          >
            Pendientes <span class="sales-tab-badge">{{ kpis().pending }}</span>
          </button>
          <button
            type="button"
            class="sales-tab"
            [class.sales-tab--active]="statusTab() === 'APROBADA'"
            (click)="statusTab.set('APROBADA')"
          >
            Aprobadas <span class="sales-tab-badge">{{ kpis().approved }}</span>
          </button>
          <button
            type="button"
            class="sales-tab"
            [class.sales-tab--active]="statusTab() === 'COMPLETADA'"
            (click)="statusTab.set('COMPLETADA')"
          >
            Completadas <span class="sales-tab-badge">{{ kpis().completed }}</span>
          </button>
          <button
            type="button"
            class="sales-tab"
            [class.sales-tab--active]="statusTab() === 'RECHAZADA'"
            (click)="statusTab.set('RECHAZADA')"
          >
            Rechazadas <span class="sales-tab-badge">{{ kpis().rejected }}</span>
          </button>
        </div>

        <div class="sales-search-box">
          <span>🔍</span>
          <input
            type="text"
            placeholder="Buscar por Nº devolución, Nº venta, cliente, motivo..."
            [value]="searchQuery()"
            (input)="searchQuery.set($any($event.target).value)"
          />
          @if (searchQuery()) {
            <button type="button" class="sales-search-clear" (click)="searchQuery.set('')">✕</button>
          }
        </div>
      </div>

      @if (loading()) {
        <div class="admin-skeleton-table"><span></span><span></span></div>
      } @else if (!filteredItems().length) {
        <app-status-panel
          title="Sin devoluciones encontradas"
          message="No existen registros de devolución para los criterios seleccionados."
        />
      } @else {
        <div class="admin-table-wrap returns-table-wrap">
          <table class="returns-table">
            <thead>
              <tr>
                <th style="width: 130px;">N° Devolución</th>
                <th style="width: 180px;">Solicitante</th>
                <th style="min-width: 220px;">Motivo</th>
                <th style="min-width: 280px;">Prendas Devueltas</th>
                <th style="width: 210px;">Acción</th>
                <th style="width: 170px;">Fecha</th>
              </tr>
            </thead>
            <tbody>
              @for (item of filteredItems(); track item.id_devolucion) {
                <tr>
                  <!-- 1. N° Devolución -->
                  <td>
                    <div style="display: flex; flex-direction: column; gap: 2px;">
                      <strong style="font-size: 1.05rem; color: var(--ink);">#{{ item.id_devolucion }}</strong>
                      <span style="font-size: 0.76rem; color: var(--ink-soft); font-weight: 600;">Venta #{{ item.id_venta }}</span>
                    </div>
                  </td>

                  <!-- 2. Solicitante -->
                  <td>
                    <div style="display: flex; flex-direction: column; gap: 4px;">
                      <strong style="font-size: 0.88rem; color: var(--ink);">
                        {{ item.cliente_nombre || 'Consumidor Final' }}
                      </strong>
                      <span
                        class="status-chip"
                        style="width: fit-content; font-size: 0.7rem; padding: 2px 7px;"
                        [style.background]="item.cliente_nombre ? '#eff6ff' : '#f1f5f9'"
                        [style.color]="item.cliente_nombre ? '#1d4ed8' : '#64748b'"
                        [style.border]="item.cliente_nombre ? '1px solid #bfdbfe' : '1px solid #e2e8f0'"
                      >
                        {{ item.cliente_nombre ? '👤 Registrado' : '🏪 Mostrador' }}
                      </span>
                    </div>
                  </td>

                  <!-- 3. Motivo -->
                  <td>
                    <div style="font-size: 0.85rem; color: var(--ink); line-height: 1.4; font-style: italic;">
                      <strong>{{ item.tipo_solicitud.replaceAll('_', ' ') }}</strong><br />"{{ item.motivo }}"
                    </div>
                  </td>

                  <!-- 4. Prendas Devueltas -->
                  <td>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                      @for (line of item.items; track line.id_detalle_devolucion) {
                        <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 0.82rem; background: var(--surface-muted); padding: 5px 10px; border-radius: 6px; border: 1px solid var(--line);">
                          <div>
                            <strong>{{ line.producto }}</strong>
                            <span style="color: var(--ink-soft); font-size: 0.76rem;"> ({{ line.color }} / {{ line.talla }})</span>
                          </div>
                          <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                            <strong style="font-variant-numeric: tabular-nums;">{{ line.cantidad }} u.</strong>
                            <span
                              class="condition-badge"
                              [class.condition-badge--apta]="line.estado_prenda === 'APTA_REINGRESO'"
                              [class.condition-badge--no-apta]="line.estado_prenda === 'NO_APTA'"
                            >
                              {{ line.estado_prenda === 'APTA_REINGRESO' ? '✓ Apta' : line.estado_prenda === 'NO_APTA' ? '⚠️ No Apta' : 'Pendiente de inspección' }}
                            </span>
                          </div>
                        </div>
                      }
                    </div>
                  </td>

                  <!-- 5. Acción (si fue aprobado o no + botones de transición) -->
                  <td>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                      <div>
                        <span class="status-chip" [class]="badgeClass(item.estado)">
                          @if (item.estado === 'COMPLETADA') {
                            ✓ Aprobada / Completada
                          } @else if (item.estado === 'APROBADA') {
                            📋 Aprobada
                          } @else if (item.estado === 'RECHAZADA') {
                            ✕ No Aprobada (Rechazada)
                          } @else {
                            ⏳ Pendiente
                          }
                        </span>
                      </div>

                      <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                        <button
                          class="button button--quiet"
                          type="button"
                          (click)="openInspectionModal(item)"
                          style="font-size: 0.75rem; padding: 4px 8px;"
                          title="Inspeccionar prendas y ver resolución"
                        >
                          🔍 Inspeccionar
                        </button>

                        @for (state of nextStates(item.estado); track state) {
                          <button
                            class="button"
                            [class.button--primary]="state === 'COMPLETADA'"
                            [class.button--secondary]="state === 'APROBADA'"
                            [class.button--danger]="state === 'RECHAZADA'"
                            type="button"
                            [disabled]="saving()"
                            (click)="state === 'COMPLETADA' ? openInspectionModal(item) : update(item.id_devolucion, state)"
                            style="font-size: 0.75rem; padding: 4px 8px;"
                          >
                            @if (state === 'COMPLETADA') {
                              ✓ Completar
                            } @else if (state === 'APROBADA') {
                              📋 Aprobar
                            } @else if (state === 'RECHAZADA') {
                              ✕ Rechazar
                            } @else {
                              {{ state }}
                            }
                          </button>
                        }
                      </div>
                    </div>
                  </td>

                  <!-- 6. Fecha (cuándo fue) -->
                  <td>
                    <div style="display: flex; flex-direction: column; gap: 3px; font-size: 0.8rem;">
                      <div>
                        <span style="color: var(--ink-soft); font-size: 0.7rem; text-transform: uppercase; font-weight: 700;">Solicitado:</span>
                        <div style="font-weight: 600;">{{ item.fecha_solicitud | date: 'short' }}</div>
                      </div>
                      @if (item.fecha_resolucion) {
                        <div style="margin-top: 4px; border-top: 1px dashed var(--line); padding-top: 3px;">
                          <span style="color: var(--ink-soft); font-size: 0.7rem; text-transform: uppercase; font-weight: 700;">Resuelto:</span>
                          <div style="color: #059669; font-weight: 700;">{{ item.fecha_resolucion | date: 'short' }}</div>
                        </div>
                      }
                    </div>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }

      <!-- Modal de Registro de Devolución en Mostrador -->
      @if (showModal()) {
        <div class="admin-modal-backdrop" (click)="closeCounterReturnModal()">
          <div
            class="admin-modal-card"
            style="max-width: 720px;"
            (click)="$event.stopPropagation()"
            role="dialog"
            aria-modal="true"
            aria-labelledby="counter-return-modal-title"
          >
            <header class="admin-modal-header">
              <div>
                <span class="admin-modal-kicker">Atención al Cliente · Mostrador</span>
                <h2 id="counter-return-modal-title" class="admin-modal-title">
                  Registrar Devolución en Mostrador
                </h2>
                <p class="admin-modal-subtitle">
                  Política oficial: plazo máximo de 5 días hábiles a partir de la fecha de venta.
                </p>
              </div>
              <button
                type="button"
                class="admin-modal-close"
                (click)="closeCounterReturnModal()"
                [disabled]="saving()"
                aria-label="Cerrar modal"
              >
                ✕
              </button>
            </header>

            <div style="padding: 1.25rem 1.5rem; display: flex; flex-direction: column; gap: 1.25rem; overflow-y: auto;">
              <!-- Búsqueda de Venta -->
              <div style="display: flex; gap: 10px; align-items: flex-end;">
                <label class="field" style="flex: 1;">
                  <span>Número de Venta o Factura (ID)</span>
                  <input
                    type="number"
                    min="1"
                    placeholder="Ej. 6"
                    [value]="searchSaleId() ?? ''"
                    (input)="searchSaleId.set($any($event.target).value ? Number($any($event.target).value) : null)"
                    (keyup.enter)="searchSale()"
                  />
                </label>
                <button
                  type="button"
                  class="button button--primary"
                  [disabled]="!searchSaleId() || searchingSale()"
                  (click)="searchSale()"
                >
                  {{ searchingSale() ? 'Buscando...' : '🔍 Buscar Venta' }}
                </button>
              </div>

              @if (searchError()) {
                <div class="admin-notice admin-notice--error">
                  <span>{{ searchError() }}</span>
                </div>
              }

              <!-- Detalle de Venta Inspeccionada -->
              @if (inspectedSale(); as sale) {
                <!-- Resumen de Venta -->
                <div class="counter-sale-grid">
                  <div class="metric-item">
                    <span>Venta</span>
                    <strong>#{{ sale.id_venta }}</strong>
                  </div>
                  <div class="metric-item">
                    <span>Sucursal</span>
                    <strong>{{ sale.sucursal }}</strong>
                  </div>
                  <div class="metric-item">
                    <span>Cliente</span>
                    <strong>{{ sale.cliente_nombre || 'Consumidor Final' }}</strong>
                  </div>
                  <div class="metric-item">
                    <span>Fecha Emisión</span>
                    <strong>{{ sale.fecha_venta | date: 'short' }}</strong>
                  </div>
                  <div class="metric-item">
                    <span>Total Pagado</span>
                    <strong style="color: #059669;">{{ sale.total | bolivianos }}</strong>
                  </div>
                </div>

                <!-- Banner de 5 Días Hábiles -->
                @if (sale.es_retornable) {
                  <div class="policy-banner policy-banner--valid">
                    <span class="policy-banner__icon">✓</span>
                    <div class="policy-banner__text">
                      <strong>Válida para Devolución en Plazo Legal</strong>
                      <span>
                        Quedan {{ sale.dias_habiles_limite - sale.dias_habiles_transcurridos }} día(s) hábil(es)
                        (Límite: {{ sale.fecha_limite_devolucion | date: 'mediumDate' }}).
                      </span>
                    </div>
                  </div>
                } @else {
                  <div class="policy-banner policy-banner--expired">
                    <span class="policy-banner__icon">✕</span>
                    <div class="policy-banner__text">
                      <strong>No Elegible para Devolución</strong>
                      <span>{{ sale.motivo_invalidez || 'La venta no admite devolución o ha superado los 5 días hábiles.' }}</span>
                    </div>
                  </div>
                }

                <!-- Tabla de Selección de Prendas -->
                <div>
                  <label style="font-weight: 700; font-size: 0.85rem; display: block; margin-bottom: 6px;">
                    Seleccionar Prendas a Devolver:
                  </label>
                  <div class="modal-table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th style="width: 36px;">Sel.</th>
                          <th>Prenda / Talla / Color</th>
                          <th>Comprado</th>
                          <th>Disponible</th>
                          <th style="width: 110px;">Cant. Devolver</th>
                          <th>Condición de Prenda</th>
                        </tr>
                      </thead>
                      <tbody>
                        @for (item of sale.items; track item.id_detalle_venta) {
                          <tr>
                            <td>
                              <input
                                type="checkbox"
                                [disabled]="item.cantidad_disponible <= 0 || !sale.es_retornable"
                                [checked]="isLineSelected(item.id_detalle_venta)"
                                (change)="toggleLineSelection(item.id_detalle_venta, $any($event.target).checked, item.cantidad_disponible)"
                              />
                            </td>
                            <td>
                              <strong>{{ item.producto }}</strong>
                              <span style="color: var(--ink-soft); font-size: 0.75rem;"> ({{ item.color }} / {{ item.talla }})</span>
                            </td>
                            <td>{{ item.cantidad_vendida }}</td>
                            <td>
                              <strong [style.color]="item.cantidad_disponible > 0 ? '#059669' : '#dc2626'">
                                {{ item.cantidad_disponible }}
                              </strong>
                            </td>
                            <td>
                              <input
                                type="number"
                                min="1"
                                [max]="item.cantidad_disponible"
                                [disabled]="!isLineSelected(item.id_detalle_venta)"
                                [value]="getLineQuantity(item.id_detalle_venta)"
                                (input)="updateLineQuantity(item.id_detalle_venta, Number($any($event.target).value), item.cantidad_disponible)"
                                style="width: 70px; padding: 4px 8px; border: 1px solid var(--line); border-radius: 6px;"
                              />
                            </td>
                            <td>
                              <select
                                [disabled]="!isLineSelected(item.id_detalle_venta)"
                                [value]="getLineCondition(item.id_detalle_venta)"
                                (change)="updateLineCondition(item.id_detalle_venta, $any($event.target).value)"
                                style="padding: 4px 8px; border: 1px solid var(--line); border-radius: 6px; font-size: 0.78rem;"
                              >
                                <option value="APTA_REINGRESO">✓ Apta (Reintegra stock)</option>
                                <option value="NO_APTA">⚠️ No Apta (Defecto / Merma)</option>
                              </select>
                            </td>
                          </tr>
                        }
                      </tbody>
                    </table>
                  </div>
                </div>

                <!-- Motivo -->
                <label class="field"><span>Solicitud del cliente</span>
                  <select [value]="modalTipoSolicitud()" (change)="modalTipoSolicitud.set($any($event.target).value)">
                    <option value="CAMBIO_TALLA">Cambio de talla</option>
                    <option value="CAMBIO_COLOR">Cambio de color</option>
                    <option value="CAMBIO_PRENDA">Cambio de prenda</option>
                    <option value="REEMBOLSO">Reembolso</option>
                  </select>
                </label>
                <label class="field">
                  <span>Motivo de la Devolución *</span>
                  <input
                    type="text"
                    placeholder="Ej: Cambio de talla solicitado en tienda, prenda con defecto en costura..."
                    [value]="modalMotivo()"
                    (input)="modalMotivo.set($any($event.target).value)"
                  />
                </label>

                <p>La solicitud se registrará pendiente. Luego podrás inspeccionar las prendas y cerrar el cambio o reembolso desde su detalle.</p>
              }
            </div>

            <footer style="padding: 1rem 1.5rem; border-top: 1px solid var(--line); display: flex; justify-content: flex-end; gap: 10px; background: var(--surface-muted);">
              <button
                type="button"
                class="button button--quiet"
                (click)="closeCounterReturnModal()"
                [disabled]="saving()"
              >
                Cancelar
              </button>
              <button
                type="button"
                class="button button--primary"
                [disabled]="!canSubmitCounterReturn() || saving()"
                (click)="submitCounterReturn()"
              >
                {{ saving() ? 'Registrando...' : 'Confirmar Devolución' }}
              </button>
            </footer>
          </div>
        </div>
      }

      <!-- Modal de Inspección y Resolución de Devolución -->
      @if (inspectingReturn(); as item) {
        <div class="admin-modal-backdrop" (click)="closeInspectionModal()">
          <div
            class="admin-modal-card"
            style="max-width: 680px;"
            (click)="$event.stopPropagation()"
            role="dialog"
            aria-modal="true"
            aria-labelledby="inspection-modal-title"
          >
            <header class="admin-modal-header">
              <div>
                <span class="admin-modal-kicker">Inspección Física y Kardex</span>
                <h2 id="inspection-modal-title" class="admin-modal-title">
                  Devolución #{{ item.id_devolucion }} · {{ item.tipo_solicitud.replaceAll('_', ' ') }}
                </h2>
                <p class="admin-modal-subtitle">
                  Venta original #{{ item.id_venta }} · Solicitado el {{ item.fecha_solicitud | date: 'short' }}
                </p>
              </div>
              <button
                type="button"
                class="admin-modal-close"
                (click)="closeInspectionModal()"
                [disabled]="saving()"
                aria-label="Cerrar modal"
              >
                ✕
              </button>
            </header>

            <div style="padding: 1.25rem 1.5rem; display: flex; flex-direction: column; gap: 1.25rem; overflow-y: auto; max-height: 70vh;">
              @if (error()) { <p class="notice notice--error" role="alert">{{ error() }}</p> }
              <!-- Resumen de Cliente y Estado -->
              <div class="counter-sale-grid">
                <div class="metric-item">
                  <span>Cliente</span>
                  <strong>{{ item.cliente_nombre || 'Consumidor Final' }}</strong>
                </div>
                <div class="metric-item">
                  <span>Estado Actual</span>
                  <strong [style.color]="item.estado === 'COMPLETADA' ? '#059669' : (item.estado === 'RECHAZADA' ? '#dc2626' : '#2563eb')">
                    {{ item.estado }}
                  </strong>
                </div>
                <div class="metric-item">
                  <span>Venta Relacionada</span>
                  <strong>#{{ item.id_venta }}</strong>
                </div>
                <div class="metric-item">
                  <span>Fecha Solicitud</span>
                  <strong>{{ item.fecha_solicitud | date: 'short' }}</strong>
                </div>
              </div>

              <!-- Motivo del Cliente -->
              <div style="background: var(--surface-muted); padding: 10px 14px; border-radius: 8px; border: 1px solid var(--line);">
                <span style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: var(--ink-soft); display: block; margin-bottom: 2px;">
                  Motivo indicado por el cliente:
                </span>
                <p style="margin: 0; font-size: 0.88rem; font-style: italic; color: var(--ink);">
                  "{{ item.motivo }}"
                </p>
              </div>

              <!-- Tabla de Inspección de Prendas -->
              <div>
                <label style="font-weight: 700; font-size: 0.85rem; display: block; margin-bottom: 6px;">
                  Prendas a Inspeccionar:
                </label>
                <div class="modal-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Prenda / Talla / Color</th>
                        <th style="width: 80px; text-align: center;">Cantidad</th>
                        <th style="width: 260px;">Condición Física (Inspección)</th>
                      </tr>
                    </thead>
                    <tbody>
                      @for (line of item.items; track line.id_detalle_devolucion) {
                        <tr>
                          <td>
                            <strong>{{ line.producto }}</strong>
                            <span style="color: var(--ink-soft); font-size: 0.75rem;"> ({{ line.color }} / {{ line.talla }})</span>
                          </td>
                          <td style="text-align: center; font-weight: 700;">
                            {{ line.cantidad }} u.
                          </td>
                          <td>
                            @if (item.estado === 'COMPLETADA' || item.estado === 'RECHAZADA') {
                              <span
                                class="condition-badge"
                                [class.condition-badge--apta]="line.estado_prenda === 'APTA_REINGRESO'"
                                [class.condition-badge--no-apta]="line.estado_prenda === 'NO_APTA'"
                              >
                                {{ line.estado_prenda === 'APTA_REINGRESO' ? '✓ Apta para Reingreso' : line.estado_prenda === 'NO_APTA' ? '⚠️ No Apta (Merma/Defecto)' : 'Pendiente de inspección' }}
                              </span>
                            } @else {
                              <select
                                [value]="inspectionConditions()[line.id_detalle_devolucion] || 'PENDIENTE_INSPECCION'"
                                (change)="updateInspectionCondition(line.id_detalle_devolucion, $any($event.target).value)"
                                style="width: 100%; padding: 6px 10px; border: 1px solid var(--line); border-radius: 6px; font-size: 0.8rem;"
                              >
                                <option value="PENDIENTE_INSPECCION">Pendiente de inspección</option>
                                <option value="APTA_REINGRESO">✓ Apta para Reingreso (Suma stock a tienda)</option>
                                <option value="NO_APTA">⚠️ No Apta (Daño/Uso - no suma stock)</option>
                              </select>
                            }
                          </td>
                        </tr>
                      }
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Banner de Impacto en Inventario -->
              @if (item.estado === 'APROBADA') {
                <fieldset>
                  <legend>Requisitos de recepción</legend>
                  @for (requirement of returnRequirements; track requirement.key) {
                    <label style="display: flex; align-items: center; gap: 10px; padding: 8px 0;">
                      <input type="checkbox" [checked]="receiptChecklist()[requirement.key]"
                        (change)="setReceiptRequirement(requirement.key, $any($event.target).checked)" />
                      {{ requirement.label }}
                    </label>
                  }
                </fieldset>
                <label class="field"><span>Resolución</span>
                  <select [value]="settlementType()" (change)="setSettlementType($any($event.target).value)">
                    <option value="CAMBIO">Entregar otra talla, color o prenda</option>
                    <option value="REEMBOLSO">Registrar reembolso</option>
                  </select>
                </label>
                @if (settlementType() === 'CAMBIO') {
                  <p>La misma prenda conserva el importe pagado. Otra prenda usa su precio vigente, con la promoción aplicable. Solo se muestran variantes con stock en esta sucursal.</p>
                  @if (specificExchange()) {
                    <p>{{ item.tipo_solicitud === 'CAMBIO_TALLA' ? 'Cambio de talla: se conserva la prenda y su color original.' : 'Cambio de color: se conserva la prenda y su talla original.' }}</p>
                  } @else {
                  <label class="field"><span>Filtrar prendas de esta página</span>
                    <input type="search" [value]="replacementSearch()" (input)="replacementSearch.set($any($event.target).value)" />
                  </label>
                  <div style="display: flex; gap: 12px; align-items: center;">
                    <button type="button" class="button button--quiet" [disabled]="replacementPage() <= 1 || replacementLoading()" (click)="loadReplacementProducts(replacementPage() - 1)">Anterior</button>
                    <span>Página {{ replacementPage() }} de {{ replacementPages() }}</span>
                    <button type="button" class="button button--quiet" [disabled]="replacementPage() >= replacementPages() || replacementLoading()" (click)="loadReplacementProducts(replacementPage() + 1)">Siguiente</button>
                  </div>
                  }
                  @if (replacementLoading()) { <p role="status">Cargando existencias…</p> }
                  @for (line of item.items; track line.id_detalle_devolucion) {
                    <label class="field"><span>Devolver: {{ line.producto }} · Talla {{ line.talla }} · Color {{ line.color }} · {{ line.cantidad }} u.</span>
                      <span>{{ line.id_variante_solicitada ? 'Variante solicitada: talla ' + line.talla_solicitada + ' · color ' + line.color_solicitado : 'Selecciona la variante que se entregará al cliente' }}</span>
                      <select [ngModel]="replacementSelections()[line.id_detalle_devolucion] || null"
                        [ngModelOptions]="{ standalone: true }" [disabled]="replacementLoading()"
                        (ngModelChange)="selectReplacement(line.id_detalle_devolucion, $event)">
                        <option [ngValue]="null">{{ replacementLoading() ? 'Cargando variantes…' : 'Seleccionar variante de reemplazo' }}</option>
                        @if (selectedReplacementLabelOutsidePage(line); as selectedLabel) {
                          <option [ngValue]="replacementSelections()[line.id_detalle_devolucion]">{{ selectedLabel }}</option>
                        }
                        @for (option of replacementOptionsFor(line); track option.id) {
                          <option [ngValue]="option.id" [disabled]="option.stock < line.cantidad">{{ option.label }}</option>
                        }
                      </select>
                    </label>
                    @if (!replacementLoading() && !replacementOptionsFor(line).length) {
                      <p role="status">No se encontraron variantes compatibles en esta sucursal. No se puede completar el cambio sin un reemplazo disponible.</p>
                    } @else if (!replacementLoading() && !hasReplacementStock(line)) {
                      <p role="status">Las variantes compatibles no tienen stock suficiente en esta sucursal. Puedes coordinar una reposición o acordar un reembolso.</p>
                    }
                  }
                }
                <button type="button" class="button button--secondary" [disabled]="saving() || quoting()" (click)="quoteSettlement()">{{ quoting() ? 'Calculando…' : 'Calcular diferencia' }}</button>
                @if (settlementQuote(); as quote) {
                  <div role="status">
                    <p>Importe reconocido: <strong>{{ quote.importe_devuelto | bolivianos }}</strong></p>
                    <p>Reemplazos: <strong>{{ quote.importe_reemplazos | bolivianos }}</strong></p>
                    <p><strong>{{ quote.accion === 'COBRAR' ? 'Cobrar al cliente' : quote.accion === 'REEMBOLSAR' ? 'Devolver al cliente' : 'Sin diferencia de precio' }}: {{ quote.monto | bolivianos }}</strong></p>
                  </div>
                  @if (Number(quote.monto) > 0) {
                    <p>Registra el movimiento después de realizar el cobro o reembolso. Esta pantalla no ejecuta transferencias ni devoluciones automáticas de tarjeta.</p>
                    <label class="field"><span>Medio utilizado</span>
                      <select [value]="settlementMedium()" (change)="settlementMedium.set($any($event.target).value); settlementConfirmed.set(false)">
                        <option value="EFECTIVO">Efectivo</option><option value="TRANSFERENCIA">Transferencia</option>
                        <option value="QR">QR</option><option value="TARJETA">Tarjeta / pasarela</option>
                      </select>
                    </label>
                    <label class="field"><span>Referencia del comprobante (obligatoria salvo efectivo)</span>
                      <input maxlength="120" [value]="settlementReference()" (input)="settlementReference.set($any($event.target).value); settlementConfirmed.set(false)" />
                    </label>
                  }
                  <label style="display: flex; gap: 10px; align-items: center; padding: 12px 0;">
                    <input type="checkbox" [checked]="settlementConfirmed()" (change)="settlementConfirmed.set($any($event.target).checked)" />
                    Confirmo la entrega del reemplazo y/o la liquidación de la diferencia indicada.
                  </label>
                }
              }
              @if (item.cierre; as receipt) {
                <div>
                  <h3>Comprobante {{ receipt.comprobante }}</h3>
                  <p>{{ receipt.tipo }} · {{ receipt.accion }} · {{ receipt.monto | bolivianos }}</p>
                  @for (line of receipt.items; track line.id_detalle_devolucion) {
                    @if (line.producto) { <p>Entregado: {{ line.producto }} · {{ line.talla }} / {{ line.color }} × {{ line.cantidad }}</p> }
                  }
                  <p>Notas de entrada: {{ receipt.notas_entrada.join(', ') || 'Sin reingreso apto' }} · Notas de salida: {{ receipt.notas_salida.join(', ') || 'No corresponde' }}</p>
                  <button type="button" class="button button--secondary" (click)="downloadReturnReceipt(item.id_devolucion)">Descargar comprobante PDF</button>
                </div>
              }
              @if (item.estado !== 'COMPLETADA' && item.estado !== 'RECHAZADA') {
                <div class="policy-banner policy-banner--valid">
                  <span class="policy-banner__icon">ℹ️</span>
                  <div class="policy-banner__text">
                    <strong>Control de Inventario y Kardex FIFO</strong>
                    <span>
                      Al marcar una prenda como <strong>Apta</strong>, el sistema restablece automáticamente su stock en la sucursal y repone las capas FIFO originales.
                    </span>
                  </div>
                </div>

                <!-- Observaciones opcionales del personal -->
                <label class="field">
                  <span>Observaciones del Encargado (Opcional)</span>
                  <input
                    type="text"
                    placeholder="Ej: Prenda recibida en perfecto estado con etiqueta original..."
                    [value]="inspectionObservations()"
                    (input)="inspectionObservations.set($any($event.target).value)"
                  />
                </label>
              } @else if (item.fecha_resolucion) {
                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; padding: 10px 14px; border-radius: 8px; font-size: 0.82rem; color: #166534;">
                  ✓ Devolución finalizada el <strong>{{ item.fecha_resolucion | date: 'medium' }}</strong>.
                </div>
              }
            </div>

            <footer style="padding: 1rem 1.5rem; border-top: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; background: var(--surface-muted);">
              <button
                type="button"
                class="button button--quiet"
                (click)="closeInspectionModal()"
                [disabled]="saving()"
              >
                Cerrar
              </button>

              <div style="display: flex; gap: 8px;">
                @if (item.estado === 'PENDIENTE') {
                  <button
                    type="button"
                    class="button button--danger"
                    [disabled]="saving()"
                    (click)="resolveInspection('RECHAZADA')"
                  >
                    ✕ Rechazar Solicitud
                  </button>
                  <button
                    type="button"
                    class="button button--primary"
                    [disabled]="saving()"
                    (click)="resolveInspection('APROBADA')"
                  >
                    {{ saving() ? 'Guardando...' : '📋 Aprobar Solicitud' }}
                  </button>
                } @else if (item.estado === 'APROBADA') {
                  <button
                    type="button"
                    class="button button--danger"
                    [disabled]="saving()"
                    (click)="resolveInspection('RECHAZADA')"
                  >
                    ✕ Rechazar
                  </button>
                  <button
                    type="button"
                    class="button button--primary"
                    [disabled]="saving() || !settlementQuote() || !settlementConfirmed()"
                    (click)="resolveInspection('COMPLETADA')"
                  >
                    {{ saving() ? 'Procesando...' : 'Cerrar cambio o reembolso' }}
                  </button>
                }
              </div>
            </footer>
          </div>
        </div>
      }
    </section>
  `,
})
export class ReturnsAdmin {
  private readonly commerce = inject(CommerceService);
  private readonly catalog = inject(CatalogService);
  private readonly errors = inject(ApiErrorService);

  readonly items = signal<ReturnRequest[]>([]);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly successMessage = signal('');

  readonly statusTab = signal<'TODAS' | 'PENDIENTE' | 'APROBADA' | 'COMPLETADA' | 'RECHAZADA'>('TODAS');
  readonly searchQuery = signal('');

  // Inspection & Resolution modal state
  readonly inspectingReturn = signal<ReturnRequest | null>(null);
  readonly inspectionConditions = signal<Record<number, 'PENDIENTE_INSPECCION' | 'APTA_REINGRESO' | 'NO_APTA'>>({});
  readonly inspectionObservations = signal('');
  readonly returnRequirements: Array<{ key: keyof ReturnChecklist; label: string }> = [
    { key: 'comprobante_verificado', label: 'Comprobante de compra verificado' },
    { key: 'sin_uso', label: 'Prenda sin uso' },
    { key: 'sin_lavado', label: 'Prenda sin lavar' },
    { key: 'etiquetas_conservadas', label: 'Etiquetas conservadas' },
    { key: 'sin_danos_cliente', label: 'Sin daños atribuibles al cliente' },
  ];
  readonly receiptChecklist = signal<ReturnChecklist>({ comprobante_verificado: false, sin_uso: false, sin_lavado: false, etiquetas_conservadas: false, sin_danos_cliente: false });
  readonly settlementType = signal<'CAMBIO' | 'REEMBOLSO'>('CAMBIO');
  readonly replacementProducts = signal<Product[]>([]);
  readonly replacementLoading = signal(false);
  readonly replacementPage = signal(1);
  readonly replacementPages = signal(1);
  readonly replacementSearch = signal('');
  readonly replacementSelections = signal<Record<number, number>>({});
  readonly specificOptions = signal<Record<number, ReturnVariantOption[]>>({});
  readonly specificExchange = computed(() => ['CAMBIO_TALLA', 'CAMBIO_COLOR'].includes(this.inspectingReturn()?.tipo_solicitud ?? ''));
  readonly selectedReplacementLabels = signal<Record<number, string>>({});
  readonly settlementQuote = signal<ReturnQuote | null>(null);
  readonly quoting = signal(false);
  readonly settlementMedium = signal<'EFECTIVO' | 'TRANSFERENCIA' | 'QR' | 'TARJETA'>('EFECTIVO');
  readonly settlementReference = signal('');
  readonly settlementConfirmed = signal(false);
  private quoteVersion = 0;
  readonly replacementOptions = computed(() => this.replacementProducts()
    .filter((product) => product.nombre.toLocaleLowerCase().includes(this.replacementSearch().trim().toLocaleLowerCase()))
    .flatMap((product) => product.variantes.filter((variant) => variant.activo && Number(variant.stock_disponible) > 0).map((variant) => ({
      id: variant.id_variante, stock: Number(variant.stock_disponible),
      label: `${product.nombre} · ${variant.talla} / ${variant.color} · Stock ${variant.stock_disponible} · Bs ${product.precio_promocional ?? product.precio_actual}`,
    }))));

  setReceiptRequirement(key: keyof ReturnChecklist, checked: boolean): void {
    this.receiptChecklist.update((value) => ({ ...value, [key]: checked }));
  }
  setSettlementType(value: 'CAMBIO' | 'REEMBOLSO'): void {
    this.settlementType.set(value);
    this.invalidateQuote();
    if (value === 'CAMBIO') this.loadReplacementProducts();
  }
  private invalidateQuote(): void {
    this.quoteVersion++;
    this.settlementQuote.set(null);
    this.settlementConfirmed.set(false);
  }
  replacementOptionsFor(line: ReturnRequest['items'][number]): Array<{ id: number; stock: number; label: string }> {
    if (this.specificExchange()) return (this.specificOptions()[line.id_detalle_devolucion] ?? [])
      .filter((option) => !line.id_variante_solicitada || option.id_variante === line.id_variante_solicitada)
      .map((option) => ({ id: option.id_variante, stock: option.stock_disponible,
        label: `Talla ${option.talla} · Color ${option.color} · ${option.stock_disponible > 0 ? 'Stock ' + option.stock_disponible : 'Sin stock'}` }));
    return this.replacementOptions().filter((option) => option.id !== line.id_variante);
  }
  selectedReplacementLabelOutsidePage(line: ReturnRequest['items'][number]): string {
    const selected = this.replacementSelections()[line.id_detalle_devolucion];
    return !this.specificExchange() && selected && !this.replacementOptionsFor(line).some((option) => option.id === selected)
      ? this.selectedReplacementLabels()[line.id_detalle_devolucion] || '' : '';
  }
  hasReplacementStock(line: ReturnRequest['items'][number]): boolean {
    return this.replacementOptionsFor(line).some((option) => option.stock >= line.cantidad);
  }
  loadReplacementProducts(page = 1): void {
    const item = this.inspectingReturn();
    if (!item?.id_sucursal) return;
    this.replacementLoading.set(true);
    if (this.specificExchange()) {
      this.commerce.returnReplacementOptions(item.id_devolucion).pipe(finalize(() => this.replacementLoading.set(false))).subscribe({
        next: (result) => {
          if (this.inspectingReturn()?.id_devolucion !== item.id_devolucion) return;
          this.specificOptions.set(Object.fromEntries(result.items.map((entry) => [entry.id_detalle_devolucion, entry.opciones])));
          for (const line of item.items) {
            const requested = this.replacementOptionsFor(line).find((option) => option.id === line.id_variante_solicitada && option.stock >= line.cantidad);
            if (requested) this.selectReplacement(line.id_detalle_devolucion, requested.id);
          }
        },
        error: (error) => this.error.set(this.errors.message(error, 'No pudimos cargar las tallas o colores disponibles.')),
      });
      return;
    }
    this.catalog.products({ sucursal: item.id_sucursal, activo: true, page, page_size: 100 })
      .pipe(finalize(() => this.replacementLoading.set(false))).subscribe({
        next: (result) => {
          if (this.inspectingReturn()?.id_devolucion !== item.id_devolucion) return;
          this.replacementProducts.set(result.items);
          this.replacementPage.set(result.page);
          this.replacementPages.set(result.pages);
        },
        error: (error) => this.error.set(this.errors.message(error, 'No pudimos cargar los reemplazos.')),
      });
  }
  selectReplacement(detailId: number, value: string | number | null): void {
    const id = Number(value);
    this.replacementSelections.update((current) => ({ ...current, [detailId]: id }));
    const line = this.inspectingReturn()?.items.find((item) => item.id_detalle_devolucion === detailId);
    const label = line ? this.replacementOptionsFor(line).find((option) => option.id === id)?.label ?? '' : '';
    this.selectedReplacementLabels.update((current) => ({ ...current, [detailId]: label }));
    this.invalidateQuote();
  }
  private settlementPayload(): ReturnSettlementPayload {
    const item = this.inspectingReturn();
    return {
      tipo: this.settlementType(),
      reemplazos: this.settlementType() === 'CAMBIO' ? (item?.items ?? []).map((line) => ({
        id_detalle_devolucion: line.id_detalle_devolucion,
        id_variante: this.replacementSelections()[line.id_detalle_devolucion] || 0,
      })) : [],
    };
  }
  quoteSettlement(): void {
    const item = this.inspectingReturn();
    if (!item) return;
    const payload = this.settlementPayload();
    if (payload.reemplazos.some((line) => !line.id_variante)) {
      this.error.set('Selecciona un reemplazo para cada prenda.');
      return;
    }
    this.invalidateQuote();
    const version = this.quoteVersion;
    this.error.set('');
    this.quoting.set(true);
    this.commerce.quoteReturn(item.id_devolucion, payload).pipe(finalize(() => this.quoting.set(false))).subscribe({
      next: (quote) => { if (version === this.quoteVersion) this.settlementQuote.set(quote); },
      error: (error) => this.error.set(this.errors.message(error, 'No pudimos calcular la diferencia.')),
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

  // Counter return modal state
  readonly showModal = signal(false);
  readonly searchSaleId = signal<number | null>(null);
  readonly searchingSale = signal(false);
  readonly searchError = signal('');
  readonly inspectedSale = signal<SaleReturnInspectionResponse | null>(null);
  readonly lineSelections = signal<Record<number, { selected: boolean; quantity: number; condition: 'APTA_REINGRESO' | 'NO_APTA' }>>({});
  readonly modalMotivo = signal('');
  readonly modalTipoSolicitud = signal<ReturnRequest['tipo_solicitud']>('CAMBIO_TALLA');
  readonly modalCompletarInmediato = signal(false);

  readonly kpis = computed(() => {
    const list = this.items();
    return {
      total: list.length,
      pending: list.filter((i) => i.estado === 'PENDIENTE').length,
      approved: list.filter((i) => i.estado === 'APROBADA').length,
      completed: list.filter((i) => i.estado === 'COMPLETADA').length,
      rejected: list.filter((i) => i.estado === 'RECHAZADA').length,
    };
  });

  readonly filteredItems = computed(() => {
    let list = this.items();
    const tab = this.statusTab();
    if (tab !== 'TODAS') {
      list = list.filter((i) => i.estado === tab);
    }
    const q = this.searchQuery().trim().toLowerCase();
    if (q) {
      list = list.filter(
        (i) =>
          String(i.id_devolucion).includes(q) ||
          String(i.id_venta).includes(q) ||
          (i.cliente_nombre && i.cliente_nombre.toLowerCase().includes(q)) ||
          i.motivo.toLowerCase().includes(q),
      );
    }
    return list;
  });

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.commerce
      .adminReturns()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (items) => this.items.set(items),
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos cargar las devoluciones.')),
      });
  }

  badgeClass(state: string): string {
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

  nextStates(state: string): string[] {
    return (
      (
        { PENDIENTE: ['APROBADA', 'RECHAZADA'], APROBADA: ['COMPLETADA', 'RECHAZADA'] } as Record<
          string,
          string[]
        >
      )[state] ?? []
    );
  }

  update(id: number, state: string): void {
    this.saving.set(true);
    this.error.set('');
    this.successMessage.set('');
    this.commerce
      .updateReturn(id, state)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (updated) => {
          this.items.update((items) =>
            items.map((item) => (item.id_devolucion === id ? updated : item)),
          );
          this.successMessage.set(`Devolución #${id} actualizada a ${state}.`);
        },
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos actualizar la devolución.')),
      });
  }

  openInspectionModal(item: ReturnRequest): void {
    this.inspectingReturn.set(item);
    const condMap: Record<number, 'PENDIENTE_INSPECCION' | 'APTA_REINGRESO' | 'NO_APTA'> = {};
    (item.items || []).forEach((line) => {
      condMap[line.id_detalle_devolucion] =
        (line.estado_prenda as 'PENDIENTE_INSPECCION' | 'APTA_REINGRESO' | 'NO_APTA') || 'PENDIENTE_INSPECCION';
    });
    this.inspectionConditions.set(condMap);
    this.inspectionObservations.set('');
    this.error.set('');
    this.receiptChecklist.set({ comprobante_verificado: false, sin_uso: false, sin_lavado: false, etiquetas_conservadas: false, sin_danos_cliente: false });
    this.settlementType.set(item.tipo_solicitud.startsWith('CAMBIO') ? 'CAMBIO' : 'REEMBOLSO');
    this.replacementSelections.set({});
    this.specificOptions.set({});
    this.selectedReplacementLabels.set({});
    this.replacementProducts.set([]);
    this.replacementSearch.set('');
    this.settlementReference.set('');
    this.settlementMedium.set('EFECTIVO');
    this.invalidateQuote();
    if (item.estado === 'APROBADA' && this.settlementType() === 'CAMBIO') this.loadReplacementProducts();
  }

  closeInspectionModal(): void {
    this.inspectingReturn.set(null);
    this.invalidateQuote();
  }

  updateInspectionCondition(detailId: number, condition: 'PENDIENTE_INSPECCION' | 'APTA_REINGRESO' | 'NO_APTA'): void {
    this.inspectionConditions.update((map) => ({
      ...map,
      [detailId]: condition,
    }));
  }

  resolveInspection(newState: 'APROBADA' | 'COMPLETADA' | 'RECHAZADA'): void {
    const item = this.inspectingReturn();
    if (!item) return;
    if (newState === 'COMPLETADA' && (!this.settlementQuote() || !this.settlementConfirmed() || !Object.values(this.receiptChecklist()).every(Boolean))) {
      this.error.set('Confirma los requisitos, calcula la diferencia y registra la entrega o liquidación.');
      return;
    }

    if (newState === 'COMPLETADA' && item.items.some((line) =>
      (this.inspectionConditions()[line.id_detalle_devolucion] || 'PENDIENTE_INSPECCION') === 'PENDIENTE_INSPECCION'
    )) {
      this.error.set('Inspecciona todas las prendas antes de completar la devolución.');
      return;
    }

    const payload: ReturnStatusUpdatePayload = {
      estado: newState,
      items: newState === 'COMPLETADA' ? item.items.map((line) => ({
        id_detalle_devolucion: line.id_detalle_devolucion,
        estado_prenda: this.inspectionConditions()[line.id_detalle_devolucion] as 'APTA_REINGRESO' | 'NO_APTA',
      })) : undefined,
      observaciones: this.inspectionObservations().trim() || null,
      ...(newState === 'COMPLETADA' ? {
        checklist: this.receiptChecklist(),
        resolucion: { ...this.settlementPayload(), monto_confirmado: this.settlementQuote()!.monto,
          medio: this.settlementMedium(), referencia: this.settlementReference().trim() || null },
      } : {}),
    };

    this.saving.set(true);
    this.error.set('');
    this.successMessage.set('');

    this.commerce
      .updateReturn(item.id_devolucion, payload)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (updated) => {
          this.items.update((list) =>
            list.map((r) => (r.id_devolucion === updated.id_devolucion ? updated : r)),
          );
          this.successMessage.set(
            `Devolución #${updated.id_devolucion} actualizada a ${updated.estado}.` +
              (updated.estado === 'COMPLETADA' ? ' Se reintegraron las prendas aptas al inventario.' : ''),
          );
          this.closeInspectionModal();
        },
        error: (err) => {
          this.error.set(this.errors.message(err, 'No fue posible actualizar la devolución.'));
        },
      });
  }

  openCounterReturnModal(): void {
    this.showModal.set(true);
    this.searchSaleId.set(null);
    this.searchingSale.set(false);
    this.searchError.set('');
    this.inspectedSale.set(null);
    this.lineSelections.set({});
    this.modalMotivo.set('');
    this.modalCompletarInmediato.set(false);
    this.modalTipoSolicitud.set('CAMBIO_TALLA');
  }

  closeCounterReturnModal(): void {
    this.showModal.set(false);
  }

  searchSale(): void {
    const id = this.searchSaleId();
    if (!id || id <= 0) return;
    this.searchingSale.set(true);
    this.searchError.set('');
    this.inspectedSale.set(null);
    this.lineSelections.set({});

    this.commerce
      .inspectSaleForReturn(id)
      .pipe(finalize(() => this.searchingSale.set(false)))
      .subscribe({
        next: (sale) => {
          this.inspectedSale.set(sale);
          const initialSelections: Record<number, { selected: boolean; quantity: number; condition: 'APTA_REINGRESO' | 'NO_APTA' }> = {};
          sale.items.forEach((item) => {
            initialSelections[item.id_detalle_venta] = {
              selected: item.cantidad_disponible > 0 && sale.es_retornable,
              quantity: Math.min(1, item.cantidad_disponible),
              condition: 'APTA_REINGRESO',
            };
          });
          this.lineSelections.set(initialSelections);
        },
        error: (err) => {
          this.searchError.set(this.errors.message(err, 'No fue posible encontrar la venta solicitada.'));
        },
      });
  }

  isLineSelected(detailId: number): boolean {
    return !!this.lineSelections()[detailId]?.selected;
  }

  getLineQuantity(detailId: number): number {
    return this.lineSelections()[detailId]?.quantity ?? 1;
  }

  getLineCondition(detailId: number): 'APTA_REINGRESO' | 'NO_APTA' {
    return this.lineSelections()[detailId]?.condition ?? 'APTA_REINGRESO';
  }

  toggleLineSelection(detailId: number, checked: boolean, available: number): void {
    this.lineSelections.update((map) => {
      const current = map[detailId] ?? { quantity: 1, condition: 'APTA_REINGRESO' };
      return {
        ...map,
        [detailId]: {
          ...current,
          selected: checked,
          quantity: Math.min(Math.max(1, current.quantity), Math.max(1, available)),
        },
      };
    });
  }

  updateLineQuantity(detailId: number, qty: number, available: number): void {
    const validQty = Math.min(Math.max(1, qty), Math.max(1, available));
    this.lineSelections.update((map) => {
      const current = map[detailId] ?? { selected: true, condition: 'APTA_REINGRESO' };
      return {
        ...map,
        [detailId]: {
          ...current,
          quantity: validQty,
        },
      };
    });
  }

  updateLineCondition(detailId: number, cond: string): void {
    const condition = cond === 'NO_APTA' ? 'NO_APTA' : 'APTA_REINGRESO';
    this.lineSelections.update((map) => {
      const current = map[detailId] ?? { selected: true, quantity: 1 };
      return {
        ...map,
        [detailId]: {
          ...current,
          condition,
        },
      };
    });
  }

  canSubmitCounterReturn(): boolean {
    const sale = this.inspectedSale();
    if (!sale || !sale.es_retornable) return false;
    if (!this.modalMotivo().trim() || this.modalMotivo().trim().length < 3) return false;

    const selections = this.lineSelections();
    const hasSelected = Object.values(selections).some((s) => s.selected && s.quantity > 0);
    return hasSelected;
  }

  submitCounterReturn(): void {
    const sale = this.inspectedSale();
    if (!sale || !this.canSubmitCounterReturn()) return;

    const selections = this.lineSelections();
    const items = Object.entries(selections)
      .filter(([_, s]) => s.selected && s.quantity > 0)
      .map(([detailId, s]) => ({
        id_detalle_venta: Number(detailId),
        cantidad: s.quantity,
        estado_prenda: s.condition,
      }));

    this.saving.set(true);
    this.searchError.set('');

    this.commerce
      .createAdminReturn({
        id_venta: sale.id_venta,
        tipo_solicitud: this.modalTipoSolicitud(),
        motivo: this.modalMotivo().trim(),
        items,
        completar_inmediato: this.modalCompletarInmediato(),
      })
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (newReturn) => {
          this.items.update((prev) => [newReturn, ...prev]);
          this.successMessage.set(
            `Devolución #${newReturn.id_devolucion} para la venta #${sale.id_venta} registrada con éxito (${newReturn.estado}).`,
          );
          this.closeCounterReturnModal();
        },
        error: (err) => {
          this.searchError.set(this.errors.message(err, 'No fue posible registrar la devolución en mostrador.'));
        },
      });
  }

  protected readonly Number = Number;
}

@Component({
  selector: 'app-supplier-history-admin',
  imports: [ReactiveFormsModule, DatePipe, BolivianosPipe, StatusPanel],
  template: `<section>
    <header class="admin-page-heading">
      <div>
        <p class="eyebrow">Historiales</p>
        <h1>Compras a proveedores</h1>
        <p>Costos históricos por recepción y lote, sin recalcular precios pasados.</p>
      </div>
      <div class="sales-history-top-actions">
        <strong>{{ total() }} registros</strong>
        <button
          type="button"
          class="button button--secondary button--export-pdf"
          (click)="exportPdf()"
          [disabled]="loading() || items().length === 0"
          title="Exportar reporte de compras en PDF con logo oficial"
        >
          📄 PDF
        </button>
        <button
          type="button"
          class="button button--secondary button--export-excel"
          (click)="exportExcel()"
          [disabled]="loading() || items().length === 0"
          title="Descargar compras filtradas en Excel (.xlsx) con logo"
        >
          📊 Excel
        </button>
      </div>
    </header>
    <form class="admin-filterbar supplier-history-filters" [formGroup]="form" (ngSubmit)="load(1)">
      <div class="sales-date-presets supplier-date-presets">
        <button
          type="button"
          class="date-preset-btn"
          [class.date-preset-btn--active]="datePreset() === 'TODOS'"
          (click)="applyPreset('TODOS')"
        >
          Todo
        </button>
        <button
          type="button"
          class="date-preset-btn"
          [class.date-preset-btn--active]="datePreset() === 'HOY'"
          (click)="applyPreset('HOY')"
        >
          Hoy
        </button>
        <button
          type="button"
          class="date-preset-btn"
          [class.date-preset-btn--active]="datePreset() === 'SEMANA'"
          (click)="applyPreset('SEMANA')"
        >
          Esta semana
        </button>
        <button
          type="button"
          class="date-preset-btn"
          [class.date-preset-btn--active]="datePreset() === 'MES'"
          (click)="applyPreset('MES')"
        >
          Este mes
        </button>
      </div>
      <label class="field"
        ><span>Proveedor</span
        ><select formControlName="proveedor">
          <option value="">Todos</option>
          @for (supplier of suppliers(); track supplier['id_proveedor']) {
            <option [value]="supplier['id_proveedor']">{{ supplier['razon_social'] }}</option>
          }
        </select></label
      ><label class="field"
        ><span>Sucursal</span
        ><select formControlName="sucursal">
          <option value="">Todas</option>
          @for (branch of branches(); track branch.id_sucursal) {
            <option [value]="branch.id_sucursal">{{ branch.nombre }}</option>
          }
        </select></label
      ><label class="field"
        ><span>Desde</span><input type="date" formControlName="fecha_desde" (change)="onDateInputChange()" /></label
      ><label class="field"
        ><span>Hasta</span><input type="date" formControlName="fecha_hasta" (change)="onDateInputChange()" /></label
      ><button class="button button--primary" type="submit">Filtrar</button>
    </form>
    @if (error()) {
      <p class="admin-notice admin-notice--error">{{ error() }}</p>
    }
    @if (loading()) {
      <div class="admin-skeleton-table"><span></span><span></span></div>
    } @else if (!items().length) {
      <app-status-panel title="Sin compras" message="No existen recepciones para estos filtros." />
    } @else {
      <div class="admin-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Proveedor</th>
              <th>Orden / recepción</th>
              <th>Producto</th>
              <th>Variante</th>
              <th>Cantidad</th>
              <th>Costo</th>
              <th>Subtotal</th>
              <th>Total recepción</th>
              <th>Sucursal</th>
              <th>Responsable</th>
            </tr>
          </thead>
          <tbody>
            @for (item of items(); track item['id_recepcion'] + '-' + item['id_variante']) {
              <tr>
                <td>{{ item['fecha_recepcion'] | date: 'short' }}</td>
                <td>{{ item['proveedor'] || 'Sin proveedor' }}</td>
                <td>#{{ item['id_orden_compra'] || 'N/D' }} / #{{ item['id_recepcion'] }}</td>
                <td>{{ item['producto'] }}</td>
                <td>{{ item['color'] }} / {{ item['talla'] }}</td>
                <td>{{ item['cantidad'] }}</td>
                <td>{{ item['precio_unitario'] | bolivianos }}</td>
                <td>{{ item['subtotal'] | bolivianos }}</td>
                <td>{{ item['total_compra'] | bolivianos }}</td>
                <td>{{ item['sucursal'] }}</td>
                <td>{{ item['usuario_responsable'] || 'No disponible' }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <nav class="audit-pagination" aria-label="Paginación">
        <button
          class="button button--quiet"
          type="button"
          [disabled]="page() === 1"
          (click)="load(page() - 1)"
        >
          Anterior</button
        ><span>Página {{ page() }}</span
        ><button
          class="button button--quiet"
          type="button"
          [disabled]="page() * 25 >= total()"
          (click)="load(page() + 1)"
        >
          Siguiente
        </button>
      </nav>
    }
  </section>`,
})
export class SupplierHistoryAdmin {
  private readonly fb = inject(FormBuilder);
  private readonly commerce = inject(CommerceService);
  private readonly catalog = inject(CatalogService);
  private readonly admin = inject(AdminApiService);
  private readonly errors = inject(ApiErrorService);
  private readonly exportService = inject(ExportService);

  readonly suppliers = signal<Entity[]>([]);
  readonly branches = signal<Branch[]>([]);
  readonly items = signal<Array<Record<string, string | number | null>>>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly datePreset = signal<'TODOS' | 'HOY' | 'SEMANA' | 'MES'>('TODOS');

  readonly form = this.fb.nonNullable.group({
    proveedor: [''],
    sucursal: [''],
    fecha_desde: [''],
    fecha_hasta: [''],
  });

  constructor() {
    forkJoin({
      suppliers: this.admin.list('suppliers'),
      branches: this.catalog.branches(),
    }).subscribe({
      next: (data) => {
        this.suppliers.set(data.suppliers);
        this.branches.set(data.branches);
        this.load();
      },
      error: (error) =>
        this.error.set(this.errors.message(error, 'No pudimos cargar los filtros.')),
    });
  }

  applyPreset(preset: 'TODOS' | 'HOY' | 'SEMANA' | 'MES'): void {
    this.datePreset.set(preset);
    if (preset === 'TODOS') {
      this.form.patchValue({ fecha_desde: '', fecha_hasta: '' });
    } else if (preset === 'HOY') {
      const today = new Date().toISOString().slice(0, 10);
      this.form.patchValue({ fecha_desde: today, fecha_hasta: today });
    } else if (preset === 'SEMANA') {
      const now = new Date();
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      this.form.patchValue({
        fecha_desde: weekAgo.toISOString().slice(0, 10),
        fecha_hasta: now.toISOString().slice(0, 10),
      });
    } else if (preset === 'MES') {
      const now = new Date();
      const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      this.form.patchValue({
        fecha_desde: monthAgo.toISOString().slice(0, 10),
        fecha_hasta: now.toISOString().slice(0, 10),
      });
    }
    this.load(1);
  }

  onDateInputChange(): void {
    this.datePreset.set('TODOS');
  }

  load(page = 1): void {
    this.loading.set(true);
    const value = this.form.getRawValue();
    this.commerce
      .supplierPurchaseHistory({ page, page_size: 25, ...value })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (result) => {
          this.items.set(result.items);
          this.total.set(result.total);
          this.page.set(result.page);
        },
        error: (error) =>
          this.error.set(this.errors.message(error, 'No pudimos cargar el historial.')),
      });
  }

  async getPurchasesForExport(): Promise<Array<Record<string, string | number | null>>> {
    if (this.total() <= this.items().length) {
      return this.items();
    }
    try {
      const value = this.form.getRawValue();
      const res = await firstValueFrom(
        this.commerce.supplierPurchaseHistory({
          page: 1,
          page_size: Math.min(this.total(), 100),
          ...value,
        })
      );
      return res.items.length ? res.items : this.items();
    } catch {
      return this.items();
    }
  }

  private getPurchasesFilterInfo(): PurchasesFilterInfo {
    const value = this.form.getRawValue();
    const preset = this.datePreset();
    let periodLabel = 'Histórico completo';
    if (preset === 'HOY') {
      periodLabel = 'Hoy';
    } else if (preset === 'SEMANA') {
      periodLabel = 'Últimos 7 días';
    } else if (preset === 'MES') {
      periodLabel = 'Últimos 30 días';
    } else if (value.fecha_desde || value.fecha_hasta) {
      periodLabel = `${value.fecha_desde || 'Inicio'} al ${value.fecha_hasta || 'Actual'}`;
    }

    const supplierObj = this.suppliers().find(
      (s) => String(s['id_proveedor']) === String(value.proveedor)
    );
    const branchObj = this.branches().find(
      (b) => String(b.id_sucursal) === String(value.sucursal)
    );

    return {
      period: periodLabel,
      supplier: supplierObj ? String(supplierObj['razon_social']) : 'Todos los proveedores',
      branch: branchObj ? branchObj.nombre : 'Todas las sucursales',
      dateFrom: value.fecha_desde || undefined,
      dateTo: value.fecha_hasta || undefined,
    };
  }

  async exportPdf(): Promise<void> {
    const exportItems = await this.getPurchasesForExport();
    const filters = this.getPurchasesFilterInfo();
    this.exportService.exportPurchasesToPdf(exportItems, filters);
  }

  async exportExcel(): Promise<void> {
    const exportItems = await this.getPurchasesForExport();
    const filters = this.getPurchasesFilterInfo();
    await this.exportService.exportPurchasesToExcel(exportItems, filters);
  }
}

@Component({
  selector: 'app-sales-history-admin',
  imports: [CommonModule, ReactiveFormsModule, FormsModule, DatePipe, BolivianosPipe, StatusPanel],
  template: `
    <section class="admin-page sales-history-page">
      <header class="admin-page-heading">
        <div>
          <p class="eyebrow">Historiales</p>
          <h1>Historial de ventas</h1>
          <p>Registro consolidado de ventas en mostrador (POS) y ventas de la tienda online (Stripe).</p>
        </div>
        <div class="sales-history-top-actions">
          <button type="button" class="button button--quiet" (click)="loadSales()">
            🔄 Actualizar
          </button>
          <button
            type="button"
            class="button button--secondary button--export-pdf"
            (click)="exportPdf()"
            [disabled]="loading() || filteredSales().length === 0"
            title="Exportar reporte en PDF para imprimir o guardar"
          >
            📄 PDF
          </button>
          <button
            type="button"
            class="button button--secondary button--export-excel"
            (click)="exportExcel()"
            [disabled]="loading() || filteredSales().length === 0"
            title="Descargar datos filtrados en formato Excel (.xlsx)"
          >
            📊 Excel
          </button>
        </div>
      </header>

      @if (error()) {
        <div class="admin-notice admin-notice--error" role="alert">
          <span>{{ error() }}</span>
          <button type="button" class="pos-notice-close" (click)="error.set('')" aria-label="Cerrar">✕</button>
        </div>
      }

      <!-- KPIs de Resumen -->
      <div class="sales-kpi-grid">
        <div class="sales-kpi-card sales-kpi-card--total">
          <div class="kpi-icon">💰</div>
          <div class="kpi-info">
            <span class="kpi-label">Total facturado</span>
            <strong class="kpi-value">{{ kpis().totalAmount | bolivianos }}</strong>
            <small class="kpi-sub">{{ kpis().totalCount }} ventas realizadas</small>
          </div>
        </div>

        <div class="sales-kpi-card sales-kpi-card--pos">
          <div class="kpi-icon">🏢</div>
          <div class="kpi-info">
            <span class="kpi-label">Ventas presenciales (POS)</span>
            <strong class="kpi-value">{{ kpis().posAmount | bolivianos }}</strong>
            <small class="kpi-sub">{{ kpis().posCount }} transacciones en mostrador</small>
          </div>
        </div>

        <div class="sales-kpi-card sales-kpi-card--web">
          <div class="kpi-icon">🌐</div>
          <div class="kpi-info">
            <span class="kpi-label">Ventas online (Web)</span>
            <strong class="kpi-value">{{ kpis().webAmount | bolivianos }}</strong>
            <small class="kpi-sub">{{ kpis().webCount }} pedidos Stripe</small>
          </div>
        </div>

        <div class="sales-kpi-card sales-kpi-card--avg">
          <div class="kpi-icon">📊</div>
          <div class="kpi-info">
            <span class="kpi-label">Ticket promedio</span>
            <strong class="kpi-value">{{ kpis().avgTicket | bolivianos }}</strong>
            <small class="kpi-sub">Por venta concretada</small>
          </div>
        </div>
      </div>

      <!-- Barra de Filtros -->
      <div class="sales-filterbar">
        <div class="sales-tabs" role="tablist">
          <button
            type="button"
            class="sales-tab"
            [class.sales-tab--active]="channelTab() === 'TODAS'"
            (click)="channelTab.set('TODAS')"
          >
            Todas <span class="sales-tab-badge">{{ counts().todas }}</span>
          </button>
          <button
            type="button"
            class="sales-tab"
            [class.sales-tab--active]="channelTab() === 'PRESENCIAL'"
            (click)="channelTab.set('PRESENCIAL')"
          >
            🏢 Presencial <span class="sales-tab-badge">{{ counts().presencial }}</span>
          </button>
          <button
            type="button"
            class="sales-tab"
            [class.sales-tab--active]="channelTab() === 'WEB'"
            (click)="channelTab.set('WEB')"
          >
            🌐 Web <span class="sales-tab-badge">{{ counts().web }}</span>
          </button>
        </div>

        <div class="sales-filter-controls">
          @if (canSelectBranch()) {
            <label class="field sales-field-compact">
              <span>Sucursal</span>
              <select [value]="selectedBranchId() ?? ''" (change)="onBranchChange($any($event.target).value)">
                <option value="">Todas las sucursales</option>
                @for (branch of branches(); track branch.id_sucursal) {
                  <option [value]="branch.id_sucursal">{{ branch.nombre }}</option>
                }
              </select>
            </label>
          }

          <div class="sales-date-presets">
            <button
              type="button"
              class="date-preset-btn"
              [class.date-preset-btn--active]="datePreset() === 'TODOS'"
              (click)="datePreset.set('TODOS')"
            >
              Todo
            </button>
            <button
              type="button"
              class="date-preset-btn"
              [class.date-preset-btn--active]="datePreset() === 'HOY'"
              (click)="datePreset.set('HOY')"
            >
              Hoy
            </button>
            <button
              type="button"
              class="date-preset-btn"
              [class.date-preset-btn--active]="datePreset() === 'SEMANA'"
              (click)="datePreset.set('SEMANA')"
            >
              Esta semana
            </button>
            <button
              type="button"
              class="date-preset-btn"
              [class.date-preset-btn--active]="datePreset() === 'MES'"
              (click)="datePreset.set('MES')"
            >
              Este mes
            </button>
          </div>

          <div class="sales-search-box">
            <span>🔍</span>
            <input
              type="text"
              placeholder="Buscar venta #, cliente, CI, cajero..."
              [value]="searchQuery()"
              (input)="searchQuery.set($any($event.target).value)"
            />
            @if (searchQuery()) {
              <button type="button" class="sales-search-clear" (click)="searchQuery.set('')">✕</button>
            }
          </div>
        </div>
      </div>

      @if (loading()) {
        <div class="admin-skeleton-table"><span></span><span></span></div>
      } @else if (filteredSales().length === 0) {
        <app-status-panel
          title="Sin ventas encontradas"
          message="No existen ventas registradas que coincidan con los filtros o búsqueda seleccionados."
        />
      } @else {
        <div class="admin-table-wrap sales-table-wrap">
          <table class="sales-table">
            <thead>
              <tr>
                <th>Venta / Fecha</th>
                <th>Canal & Entrega</th>
                <th>Cliente / Facturado a</th>
                <th>Sucursal & Atendido por</th>
                <th class="num-col">Prendas</th>
                <th>Método de pago</th>
                <th class="num-col">Total</th>
                <th class="actions-col">Acciones</th>
              </tr>
            </thead>
            <tbody>
              @for (sale of filteredSales(); track sale.id_venta) {
                <tr class="sale-row" [class.sale-row--expanded]="isExpanded(sale.id_venta)">
                  <td>
                    <div class="sale-ident-cell">
                      <strong class="sale-num-badge">#{{ sale.id_venta }}</strong>
                      <small class="sale-date-text">{{ sale.fecha_venta | date: 'medium' }}</small>
                    </div>
                  </td>
                  <td>
                    <div class="sale-channel-cell">
                      <span
                        class="sale-channel-chip"
                        [class.sale-channel-chip--pos]="sale.canal_venta === 'PRESENCIAL'"
                        [class.sale-channel-chip--web]="sale.canal_venta !== 'PRESENCIAL'"
                      >
                        @if (sale.canal_venta === 'PRESENCIAL') {
                          🏢 Presencial
                        } @else {
                          🌐 Web (Online)
                        }
                      </span>
                      <small class="sale-mode-sub">
                        {{ formatDeliveryMode(sale.modalidad_entrega) }}
                      </small>
                    </div>
                  </td>
                  <td>
                    <div class="sale-customer-cell">
                      <strong class="sale-customer-name">
                        {{ sale.cliente_nombre || 'Consumidor Final' }}
                      </strong>
                      @if (sale.cliente_correo || sale.cliente_telefono) {
                        <small class="sale-customer-sub">
                          {{ sale.cliente_correo || sale.cliente_telefono }}
                        </small>
                      }
                    </div>
                  </td>
                  <td>
                    <div class="sale-branch-cell">
                      <span class="sale-branch-name">{{ sale.sucursal }}</span>
                      <small class="sale-cashier-text">
                        {{ sale.empleado_nombre ? 'Por: ' + sale.empleado_nombre : (sale.canal_venta === 'PRESENCIAL' ? 'Cajero' : 'Tienda Online (Stripe)') }}
                      </small>
                    </div>
                  </td>
                  <td class="num-col">
                    <span class="sale-items-count">{{ lineUnits(sale) }}</span>
                  </td>
                  <td>
                    <span class="sale-payment-method">{{ formatPaymentMethod(sale) }}</span>
                  </td>
                  <td class="num-col">
                    <strong class="sale-total-amount">{{ sale.total | bolivianos }}</strong>
                  </td>
                  <td class="actions-col">
                    <div class="sale-actions-wrap">
                      <button
                        type="button"
                        class="button--review"
                        [class.button--review-active]="isExpanded(sale.id_venta)"
                        (click)="toggleExpanded(sale.id_venta)"
                      >
                        @if (isExpanded(sale.id_venta)) {
                          ▲ Ocultar
                        } @else {
                          ▼ Revisar
                        }
                      </button>
                      <button
                        type="button"
                        class="button button--quiet button--invoice"
                        (click)="downloadInvoice(sale.id_venta)"
                        title="Descargar o imprimir Factura PDF"
                      >
                        📄 Factura
                      </button>
                    </div>
                  </td>
                </tr>

                @if (isExpanded(sale.id_venta)) {
                  <tr class="sale-expanded-row">
                    <td colspan="8">
                      <div class="sale-detail-panel">
                        <header class="sale-detail-header">
                          <div class="sale-detail-title">
                            <span class="detail-icon">🧾</span>
                            <div>
                              <h4>Detalle de Venta #{{ sale.id_venta }}</h4>
                              <p>Prendas adquiridas, precios unitarios y desglose contable de la transacción.</p>
                            </div>
                          </div>
                          <div class="sale-detail-actions">
                            <button
                              type="button"
                              class="button button--primary button--small"
                              (click)="downloadInvoice(sale.id_venta)"
                            >
                              🖨️ Imprimir / Descargar Factura PDF
                            </button>
                          </div>
                        </header>

                        <div class="sale-items-table-wrap">
                          <table class="sale-items-table">
                            <thead>
                              <tr>
                                <th>Producto</th>
                                <th>Color</th>
                                <th>Talla</th>
                                <th class="num-col">Cantidad</th>
                                <th class="num-col">Precio Unitario</th>
                                <th class="num-col">Subtotal</th>
                              </tr>
                            </thead>
                            <tbody>
                              @for (line of sale.items; track line.id_detalle) {
                                <tr>
                                  <td>
                                    <strong class="line-prod-title">{{ line.producto }}</strong>
                                  </td>
                                  <td>{{ line.color }}</td>
                                  <td><span class="line-size-badge">{{ line.talla }}</span></td>
                                  <td class="num-col">{{ line.cantidad }}</td>
                                  <td class="num-col">{{ line.precio_unitario | bolivianos }}</td>
                                  <td class="num-col"><strong>{{ line.subtotal | bolivianos }}</strong></td>
                                </tr>
                              }
                            </tbody>
                            <tfoot>
                              <tr>
                                <td colspan="4"></td>
                                <td class="num-col">Subtotal prendas:</td>
                                <td class="num-col">{{ sale.subtotal | bolivianos }}</td>
                              </tr>
                              @if (parseAmount(sale.costo_envio) > 0) {
                                <tr>
                                  <td colspan="4"></td>
                                  <td class="num-col">Costo de envío:</td>
                                  <td class="num-col">+ {{ sale.costo_envio | bolivianos }}</td>
                                </tr>
                              }
                              <tr class="total-row">
                                <td colspan="4"></td>
                                <td class="num-col"><strong>Total Cobrado:</strong></td>
                                <td class="num-col"><strong>{{ sale.total | bolivianos }}</strong></td>
                              </tr>
                            </tfoot>
                          </table>
                        </div>
                      </div>
                    </td>
                  </tr>
                }
              }
            </tbody>
          </table>
        </div>
      }
    </section>
  `,
})
export class SalesHistoryAdmin {
  private readonly commerce = inject(CommerceService);
  private readonly catalog = inject(CatalogService);
  private readonly auth = inject(AuthService);
  private readonly errors = inject(ApiErrorService);
  private readonly exportService = inject(ExportService);

  readonly sales = signal<Sale[]>([]);
  readonly branches = signal<Branch[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');

  readonly channelTab = signal<'TODAS' | 'PRESENCIAL' | 'WEB'>('TODAS');
  readonly selectedBranchId = signal<number | null>(null);
  readonly datePreset = signal<'TODOS' | 'HOY' | 'SEMANA' | 'MES'>('TODOS');
  readonly searchQuery = signal('');
  readonly expandedSaleId = signal<number | null>(null);

  readonly currentUser = this.auth.currentUser;

  readonly canSelectBranch = computed(() => {
    const u = this.currentUser();
    if (!u) return false;
    return u.roles.includes('ADMIN') || !u.id_sucursal;
  });

  readonly counts = computed(() => {
    const all = this.sales();
    return {
      todas: all.length,
      presencial: all.filter((s) => s.canal_venta === 'PRESENCIAL').length,
      web: all.filter((s) => s.canal_venta !== 'PRESENCIAL').length,
    };
  });

  readonly filteredSales = computed(() => {
    let result = this.sales();
    const tab = this.channelTab();
    if (tab === 'PRESENCIAL') {
      result = result.filter((s) => s.canal_venta === 'PRESENCIAL');
    } else if (tab === 'WEB') {
      result = result.filter((s) => s.canal_venta !== 'PRESENCIAL');
    }

    const branchId = this.selectedBranchId();
    if (branchId) {
      result = result.filter((s) => s.id_sucursal === branchId);
    }

    const preset = this.datePreset();
    if (preset !== 'TODOS') {
      const now = new Date();
      if (preset === 'HOY') {
        const todayStr = now.toISOString().slice(0, 10);
        result = result.filter((s) => s.fecha_venta?.slice(0, 10) === todayStr);
      } else if (preset === 'SEMANA') {
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        result = result.filter((s) => new Date(s.fecha_venta) >= weekAgo);
      } else if (preset === 'MES') {
        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        result = result.filter((s) => new Date(s.fecha_venta) >= monthAgo);
      }
    }

    const query = this.searchQuery().trim().toLowerCase();
    if (query) {
      result = result.filter((s) => {
        const idMatch = String(s.id_venta).includes(query) || `#${s.id_venta}`.includes(query);
        const customerMatch =
          (s.cliente_nombre || '').toLowerCase().includes(query) ||
          (s.cliente_correo || '').toLowerCase().includes(query) ||
          (s.cliente_telefono || '').toLowerCase().includes(query);
        const branchMatch = (s.sucursal || '').toLowerCase().includes(query);
        const employeeMatch = (s.empleado_nombre || '').toLowerCase().includes(query);
        const methodMatch = (s.metodo_pago || '').toLowerCase().includes(query);
        return idMatch || customerMatch || branchMatch || employeeMatch || methodMatch;
      });
    }

    return result;
  });

  readonly kpis = computed(() => {
    const list = this.filteredSales();
    const totalAmount = list.reduce((sum, s) => sum + Number(s.total || 0), 0);
    const totalCount = list.length;

    const posList = list.filter((s) => s.canal_venta === 'PRESENCIAL');
    const posCount = posList.length;
    const posAmount = posList.reduce((sum, s) => sum + Number(s.total || 0), 0);

    const webList = list.filter((s) => s.canal_venta !== 'PRESENCIAL');
    const webCount = webList.length;
    const webAmount = webList.reduce((sum, s) => sum + Number(s.total || 0), 0);

    const avgTicket = totalCount > 0 ? totalAmount / totalCount : 0;

    return {
      totalAmount,
      totalCount,
      posCount,
      posAmount,
      webCount,
      webAmount,
      avgTicket,
    };
  });

  constructor() {
    this.loadBranches();
    this.loadSales();
  }

  loadBranches(): void {
    this.catalog.branches().subscribe({
      next: (b) => this.branches.set(b),
      error: () => {},
    });
  }

  loadSales(): void {
    this.loading.set(true);
    this.commerce
      .adminSales()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (data) => this.sales.set(data),
        error: (err) =>
          this.error.set(this.errors.message(err, 'No se pudo cargar el historial de ventas.')),
      });
  }

  onBranchChange(val: string): void {
    this.selectedBranchId.set(val ? Number(val) : null);
  }

  toggleExpanded(saleId: number): void {
    this.expandedSaleId.set(this.expandedSaleId() === saleId ? null : saleId);
  }

  isExpanded(saleId: number): boolean {
    return this.expandedSaleId() === saleId;
  }

  lineUnits(sale: Sale): number {
    return (sale.items ?? []).reduce((acc, item) => acc + (item.cantidad || 0), 0);
  }

  formatDeliveryMode(mode: string): string {
    switch (mode) {
      case 'MOSTRADOR':
      case 'ENTREGA_DIRECTA':
        return 'Venta en mostrador';
      case 'DELIVERY':
        return 'Envío por delivery';
      case 'RETIRO_SUCURSAL':
        return 'Retiro en sucursal';
      default:
        return mode;
    }
  }

  formatPaymentMethod(sale: Sale): string {
    if (sale.metodo_pago) {
      return sale.metodo_pago;
    }
    return sale.canal_venta === 'PRESENCIAL' ? '💵 Efectivo' : '💳 Tarjeta (Stripe)';
  }

  parseAmount(val: string | number | null | undefined): number {
    return Number(val || 0);
  }

  downloadInvoice(saleId: number): void {
    this.commerce.saleInvoice(saleId).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.target = '_blank';
        a.download = `Factura_Venta_${saleId}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => window.URL.revokeObjectURL(url), 1000);
      },
      error: (err) =>
        this.error.set(this.errors.message(err, 'No se pudo descargar la factura.')),
    });
  }

  private getActiveSalesFilters(): SalesFilterInfo {
    const periodMap = {
      TODOS: 'Histórico completo',
      HOY: 'Hoy',
      SEMANA: 'Últimos 7 días',
      MES: 'Últimos 30 días',
    };
    const channelMap = {
      TODAS: 'Todos los canales',
      PRESENCIAL: 'Presencial (POS)',
      WEB: 'Online (Web Stripe)',
    };
    const branchName = this.selectedBranchId()
      ? this.branches().find((b) => b.id_sucursal === this.selectedBranchId())?.nombre || 'Sucursal'
      : 'Todas las sucursales';

    return {
      period: periodMap[this.datePreset()],
      branch: branchName,
      channel: channelMap[this.channelTab()],
      search: this.searchQuery().trim() || undefined,
    };
  }

  exportPdf(): void {
    const sales = this.filteredSales();
    const kpis = this.kpis();
    const filters = this.getActiveSalesFilters();
    this.exportService.exportSalesToPdf(sales, kpis, filters);
  }

  async exportExcel(): Promise<void> {
    const sales = this.filteredSales();
    const kpis = this.kpis();
    const filters = this.getActiveSalesFilters();
    await this.exportService.exportSalesToExcel(sales, kpis, filters);
  }
}
