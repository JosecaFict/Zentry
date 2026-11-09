import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, DestroyRef, effect, inject, OnInit, signal, untracked } from '@angular/core';
import { firstValueFrom, TimeoutError } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { Branch } from '../../core/models/catalog.model';
import { ConnectivityService } from '../../core/offline/connectivity.service';
import { OfflineDatabaseService } from '../../core/offline/offline-database.service';
import {
  OfflineCatalogItem,
  OfflineCustomerItem,
  OfflineOperationSummary,
  OfflineScope,
  OfflineSyncMeta,
  PendingOfflineOperation,
} from '../../core/offline/offline.models';
import { OfflineSyncService } from '../../core/offline/offline-sync.service';
import { ApiErrorService } from '../../core/services/api-error.service';
import { CatalogService } from '../../core/services/catalog.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';

interface OfflineCatalogGroup {
  name: string;
  variants: OfflineCatalogItem[];
  availableUnits: number;
  minPrice: number;
  maxPrice: number;
}

interface OfflineCartLine {
  item: OfflineCatalogItem;
  quantity: number;
  subtotal: number;
}

@Component({
  selector: 'app-offline-operations-admin',
  imports: [CommonModule],
  templateUrl: './offline-operations-admin.html',
  styleUrl: './offline-operations-admin.scss',
})
export class OfflineOperationsAdmin implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly tenant = inject(TenantContextService);
  private readonly catalogService = inject(CatalogService);
  private readonly database = inject(OfflineDatabaseService);
  private readonly synchronization = inject(OfflineSyncService);
  private readonly errors = inject(ApiErrorService);
  private readonly destroyRef = inject(DestroyRef);
  private retryTimer?: ReturnType<typeof setTimeout>;
  private retryCount = 0;

  readonly connectivity = inject(ConnectivityService);
  readonly branches = signal<Branch[]>([]);
  readonly selectedBranchId = signal<number | null>(null);
  readonly catalog = signal<OfflineCatalogItem[]>([]);
  readonly meta = signal<OfflineSyncMeta | null>(null);
  readonly operationSummary = signal<OfflineOperationSummary>({
    pending: 0,
    conflicts: 0,
    rejected: 0,
  });
  readonly loadingBranches = signal(true);
  readonly preparing = signal(false);
  readonly synchronizing = signal(false);
  readonly message = signal('');
  readonly error = signal('');
  readonly search = signal('');
  readonly cartQuantities = signal<Record<number, number>>({});
  readonly queuedQuantities = signal<Record<number, number>>({});
  readonly recentOperations = signal<PendingOfflineOperation[]>([]);
  readonly latestOperation = computed(() => this.recentOperations()[0]);
  readonly queuingSale = signal(false);
  readonly customers = signal<OfflineCustomerItem[]>([]);
  readonly operationMode = signal<'VENTA' | 'RESERVA'>('VENTA');
  readonly selectedCustomerId = signal<number | null>(null);
  readonly resolvingOperationId = signal<string | null>(null);
  readonly discardConfirmationId = signal<string | null>(null);

  readonly assignedBranch = computed(() => this.auth.currentUser()?.id_sucursal ?? null);
  readonly selectedBranch = computed(() =>
    this.branches().find((branch) => branch.id_sucursal === this.selectedBranchId()),
  );
  readonly filteredCatalog = computed(() => {
    const query = this.search().trim().toLocaleLowerCase('es');
    if (!query) return this.catalog();
    return this.catalog().filter((item) =>
      [item.producto, item.sku, item.talla, item.color]
        .join(' ')
        .toLocaleLowerCase('es')
        .includes(query),
    );
  });
  readonly groupedCatalog = computed<OfflineCatalogGroup[]>(() => {
    const groups = new Map<string, OfflineCatalogItem[]>();
    for (const item of this.filteredCatalog()) {
      const variants = groups.get(item.producto) ?? [];
      variants.push(item);
      groups.set(item.producto, variants);
    }
    return [...groups.entries()].map(([name, variants]) => {
      const prices = variants.map((item) => Number(item.precio));
      return {
        name,
        variants,
        availableUnits: variants.reduce((total, item) => total + this.availableFor(item), 0),
        minPrice: Math.min(...prices),
        maxPrice: Math.max(...prices),
      };
    });
  });
  readonly productCount = computed(() => new Set(this.catalog().map((item) => item.producto)).size);
  readonly availableUnits = computed(() =>
    this.catalog().reduce((total, item) => total + this.availableFor(item), 0),
  );
  readonly cartLines = computed<OfflineCartLine[]>(() => {
    const quantities = this.cartQuantities();
    return this.catalog()
      .filter((item) => (quantities[item.id_variante] ?? 0) > 0)
      .map((item) => {
        const quantity = quantities[item.id_variante];
        return { item, quantity, subtotal: quantity * Number(item.precio) };
      });
  });
  readonly cartUnits = computed(() =>
    this.cartLines().reduce((total, line) => total + line.quantity, 0),
  );
  readonly cartTotal = computed(() =>
    this.cartLines().reduce((total, line) => total + line.subtotal, 0),
  );
  readonly selectedCustomer = computed(() =>
    this.customers().find((customer) => customer.id_cliente === this.selectedCustomerId()),
  );

  constructor() {
    effect(() => {
      const online = this.connectivity.online();
      untracked(() => {
        this.resetAutoSync();
        if (online) this.scheduleAutoSync();
      });
    });
    this.destroyRef.onDestroy(() => this.resetAutoSync());
  }

  private resetAutoSync(): void {
    clearTimeout(this.retryTimer);
    this.retryCount = 0;
  }

  private scheduleAutoSync(delay = 0): void {
    clearTimeout(this.retryTimer);
    if (this.destroyRef.destroyed || !this.connectivity.online() || !this.operationSummary().pending) return;
    this.retryTimer = setTimeout(() => void this.synchronizeNow(true), delay);
  }

  async ngOnInit(): Promise<void> {
    try {
      const branches = await firstValueFrom(this.catalogService.branches());
      this.branches.set(branches);
      const assigned = this.assignedBranch();
      if (assigned && branches.some((branch) => branch.id_sucursal === assigned)) {
        this.selectedBranchId.set(assigned);
        await this.inspectLocalData();
      }
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudieron cargar las sucursales.'));
    } finally {
      this.loadingBranches.set(false);
    }
  }

  async selectBranch(rawValue: string): Promise<void> {
    if (this.synchronizing() || this.preparing() || this.queuingSale()) return;
    this.resetAutoSync();
    this.selectedBranchId.set(rawValue ? Number(rawValue) : null);
    this.resetLocalView();
    if (!this.selectedBranchId()) return;
    this.preparing.set(true);
    try {
      await this.inspectLocalData();
    } finally {
      this.preparing.set(false);
    }
  }

  availableFor(item: OfflineCatalogItem): number {
    return Math.max(0, item.stock_disponible - (this.queuedQuantities()[item.id_variante] ?? 0));
  }

  addToCart(item: OfflineCatalogItem): void {
    const current = this.cartQuantities()[item.id_variante] ?? 0;
    this.setCartQuantity(item, current + 1);
  }

  decreaseCartLine(item: OfflineCatalogItem): void {
    const current = this.cartQuantities()[item.id_variante] ?? 0;
    this.setCartQuantity(item, current - 1);
  }

  setCartQuantity(item: OfflineCatalogItem, rawValue: number | string): void {
    const requested = Math.max(0, Math.floor(Number(rawValue) || 0));
    const quantity = Math.min(requested, this.availableFor(item));
    const next = { ...this.cartQuantities() };
    if (quantity > 0) next[item.id_variante] = quantity;
    else delete next[item.id_variante];
    this.cartQuantities.set(next);
  }

  clearCart(): void {
    this.cartQuantities.set({});
  }

  selectOperationMode(mode: 'VENTA' | 'RESERVA'): void {
    this.operationMode.set(mode);
    this.message.set('');
    this.error.set('');
  }

  async queueOfflineSale(): Promise<void> {
    if (this.queuingSale()) return;
    const scope = this.scope();
    const lines = this.cartLines();
    if (!scope || !lines.length) return;
    const wasOnline = this.connectivity.online();
    this.queuingSale.set(true);
    this.error.set('');
    this.message.set('');
    try {
      const operation = await this.database.queueOperation('VENTA', {
        id_sucursal: scope.branchId,
        id_cliente: this.selectedCustomer()?.id_cliente ?? null,
        id_reserva: null,
        modalidad_entrega: 'ENTREGA_DIRECTA',
        items: lines.map((line) => ({
          id_variante: line.item.id_variante,
          cantidad: line.quantity,
        })),
        registrar_efectivo: true,
        metodo_pago: 'EFECTIVO',
        referencia_pago: null,
      });
      this.clearCart();
      this.selectedCustomerId.set(null);
      this.recentOperations.update((operations) => [operation, ...operations]);
      await this.refreshLocalView();
      this.message.set(
        'Venta guardada en este dispositivo. Puedes sincronizarla cuando exista conexión.',
      );
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo guardar la venta offline.'));
    } finally {
      this.queuingSale.set(false);
      if (!wasOnline && this.connectivity.online()) this.scheduleAutoSync();
    }
  }

  async queueOfflineReservation(): Promise<void> {
    if (this.queuingSale()) return;
    const scope = this.scope();
    const lines = this.cartLines();
    const customerId = this.selectedCustomerId();
    if (!scope || !lines.length) return;
    if (!customerId) {
      this.error.set('Selecciona el cliente para guardar la reserva.');
      return;
    }
    const wasOnline = this.connectivity.online();
    this.queuingSale.set(true);
    this.error.set('');
    this.message.set('');
    try {
      await this.database.queueOperation('RESERVA', {
        id_sucursal: scope.branchId,
        id_cliente: customerId,
        fecha_cita: null,
        observacion: 'Reserva registrada desde operación offline',
        items: lines.map((line) => ({
          id_variante: line.item.id_variante,
          cantidad: line.quantity,
        })),
      });
      this.clearCart();
      this.selectedCustomerId.set(null);
      await this.refreshLocalView();
      this.message.set(
        'Reserva guardada en este dispositivo. Se validará el stock al sincronizar.',
      );
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo guardar la reserva offline.'));
    } finally {
      this.queuingSale.set(false);
      if (!wasOnline && this.connectivity.online()) this.scheduleAutoSync();
    }
  }

  async prepareDevice(): Promise<void> {
    if (this.preparing() || this.synchronizing()) return;
    const scope = this.scope();
    if (!scope) return;
    this.preparing.set(true);
    this.error.set('');
    this.message.set('');
    try {
      await this.synchronization.prepare(scope);
      await this.refreshLocalView();
      if (this.catalog().length) {
        this.message.set(
          `Catálogo de ${this.selectedBranch()?.nombre ?? 'la sucursal'} disponible en este dispositivo.`,
        );
      } else if (!this.connectivity.online()) {
        this.error.set('Conéctate a internet una vez para descargar el catálogo de esta sucursal.');
      }
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo preparar este dispositivo.'));
    } finally {
      this.preparing.set(false);
      this.scheduleAutoSync();
    }
  }

  async synchronizeNow(automatic = false): Promise<void> {
    if (this.destroyRef.destroyed || !this.connectivity.online() || !this.selectedBranchId() ||
        this.synchronizing() || this.preparing()) return;
    if (!automatic) this.resetAutoSync();
    const scope = this.scope();
    if (!scope) return;
    this.synchronizing.set(true);
    this.error.set('');
    this.message.set('');
    let delay: number | null = null;
    try {
      const response = await this.synchronization.synchronizePending(scope);
      if (this.destroyRef.destroyed) return;
      await this.refreshLocalView();
      if (this.destroyRef.destroyed) return;
      this.retryCount = 0;
      this.message.set(
        response
          ? `Sincronización completada: ${response.total_aplicadas} operaciones aplicadas.`
          : 'No existen operaciones pendientes por sincronizar.',
      );
      if (response) {
        if (this.operationSummary().pending) delay = 0;
        try {
          await this.synchronization.prepare(scope);
          await this.refreshLocalView();
        } catch {
          this.error.set('Se enviaron las operaciones, pero no se pudo actualizar el catálogo.');
        }
      }
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo completar la sincronización.'));
      if ((error instanceof TimeoutError || (error instanceof HttpErrorResponse &&
          (error.status === 0 || error.status === 408 || error.status === 429 || error.status >= 500))) &&
          this.retryCount < 5) {
        delay = 2000 * 2 ** this.retryCount++;
      }
    } finally {
      this.synchronizing.set(false);
      if (delay !== null) this.scheduleAutoSync(delay);
    }
  }

  async retryOperation(operation: PendingOfflineOperation): Promise<void> {
    this.resolvingOperationId.set(operation.id_operacion);
    this.error.set('');
    try {
      await this.database.retryOperation(operation.id_operacion);
      await this.refreshLocalView();
      this.message.set('La operación volvió a la cola. Actualiza el catálogo y sincroniza nuevamente.');
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo reintentar la operación.'));
    } finally {
      this.resolvingOperationId.set(null);
    }
  }

  async discardOperation(operation: PendingOfflineOperation): Promise<void> {
    if (this.discardConfirmationId() !== operation.id_operacion) {
      this.discardConfirmationId.set(operation.id_operacion);
      return;
    }
    this.resolvingOperationId.set(operation.id_operacion);
    this.error.set('');
    try {
      await this.database.discardOperation(operation.id_operacion);
      this.discardConfirmationId.set(null);
      await this.refreshLocalView();
      this.message.set('La operación local fue descartada y el stock local quedó liberado.');
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo descartar la operación.'));
    } finally {
      this.resolvingOperationId.set(null);
    }
  }

  operationStatusLabel(operation: PendingOfflineOperation): string {
    return ({
      PENDIENTE: 'Pendiente', ENVIANDO: 'Enviando', CONFIRMADA: 'Confirmada',
      CONFLICTO: 'Conflicto', RECHAZADA: 'Rechazada', APLICADA: 'Aplicada',
    } as Record<string, string>)[operation.estado] ?? operation.estado;
  }

  operationCustomerLabel(operation: PendingOfflineOperation): string {
    const id = operation.payload['id_cliente'];
    if (typeof id !== 'number') return 'Sin cliente registrado';
    return this.customers().find((customer) => customer.id_cliente === id)?.nombre_completo ??
      `Cliente #${id}`;
  }

  operationUnits(operation: PendingOfflineOperation): number {
    const items = operation.payload['items'];
    if (!Array.isArray(items)) return 0;
    return items.reduce((total, item) => total + Number((item as Record<string, unknown>)['cantidad'] ?? 0), 0);
  }

  private async inspectLocalData(): Promise<void> {
    const scope = this.scope();
    if (!scope) return;
    try {
      await this.database.openScope(scope);
      await this.refreshLocalView();
      this.scheduleAutoSync();
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo abrir el almacenamiento local.'));
    }
  }

  private async refreshLocalView(): Promise<void> {
    const [catalog, meta, summary, queued, operations, customers] = await Promise.all([
      this.database.listCatalog(),
      this.database.currentMeta(),
      this.database.operationSummary(),
      this.database.queuedQuantities(),
      this.database.recentOperations(),
      this.database.listCustomers(),
    ]);
    this.catalog.set(catalog);
    this.meta.set(meta);
    this.operationSummary.set(summary);
    this.queuedQuantities.set(queued);
    this.recentOperations.set(operations);
    this.customers.set(customers);
  }

  private scope(): OfflineScope | null {
    const tenantId = this.tenant.tenant()?.id_tenant;
    const userId = this.auth.currentUser()?.id_usuario;
    const branchId = this.selectedBranchId();
    if (!tenantId || !userId || !branchId) {
      this.error.set('Selecciona una sucursal para preparar la operación offline.');
      return null;
    }
    return { tenantId, userId, branchId };
  }

  private resetLocalView(): void {
    this.catalog.set([]);
    this.meta.set(null);
    this.operationSummary.set({ pending: 0, conflicts: 0, rejected: 0 });
    this.message.set('');
    this.error.set('');
    this.search.set('');
    this.cartQuantities.set({});
    this.queuedQuantities.set({});
    this.recentOperations.set([]);
    this.customers.set([]);
    this.selectedCustomerId.set(null);
    this.operationMode.set('VENTA');
  }
}
