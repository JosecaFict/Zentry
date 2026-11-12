import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, DestroyRef, effect, inject, OnInit, signal, untracked } from '@angular/core';
import { firstValueFrom, timeout, TimeoutError } from 'rxjs';

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
  canReloadOfflineOperation,
  canReserveOffline,
  canSellOffline,
  offlineFailureReason,
  serverResolutionLabel,
} from '../../core/offline/offline.models';
import { OfflineAutoSyncService } from '../../core/offline/offline-auto-sync.service';
import { OfflineSyncService } from '../../core/offline/offline-sync.service';
import { ApiErrorService } from '../../core/services/api-error.service';
import { CatalogService } from '../../core/services/catalog.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';

/** Con internet, el catálogo local se vuelve a descargar si tiene más de esto. */
const CATALOG_REFRESH_MS = 5 * 60_000;

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
  private readonly autoSync = inject(OfflineAutoSyncService);

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
  /** Actualización del catálogo en segundo plano: no bloquea la venta. */
  readonly refreshing = signal(false);
  private preparedAt = 0;
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
  readonly canSell = computed(() => canSellOffline(this.auth.currentUser()));
  readonly canReserve = computed(() => canReserveOffline(this.auth.currentUser()));
  readonly operationMode = signal<'VENTA' | 'RESERVA'>(this.allowedMode('VENTA'));
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
    // El envío automático es global (OfflineAutoSyncService, cada chequeo de
    // conexión); esta pantalla solo se recarga cuando cambia la cola.
    effect(() => {
      this.autoSync.revision();
      untracked(() => {
        if (this.selectedBranchId() && this.database.scope()) {
          void this.refreshLocalView().catch(() => undefined);
        }
      });
    });
    effect(() => {
      if (!this.connectivity.online()) return;
      untracked(() => {
        this.scheduleAutoSync();
        // Volvió la red: descarga el catálogo si falta o está viejo.
        void this.autoPrepare();
      });
    });
  }

  /** Con conexión y ventas en cola, las envía ya sin esperar al próximo chequeo. */
  private scheduleAutoSync(): void {
    if (this.destroyRef.destroyed || !this.connectivity.online() || !this.operationSummary().pending) return;
    void this.autoSync.syncNow();
  }

  async ngOnInit(): Promise<void> {
    try {
      if (!this.connectivity.online()) {
        await this.restoreLocalBranches();
        return;
      }
      const branches = await firstValueFrom(this.catalogService.branches().pipe(timeout(8000)));
      this.branches.set(branches);
      const preferred = this.assignedBranch() ?? this.readBranchCache()?.selected;
      if (preferred && branches.some((branch) => branch.id_sucursal === preferred)) {
        this.selectedBranchId.set(preferred);
        await this.inspectLocalData();
      }
      this.writeBranchCache();
    } catch (error) {
      if (error instanceof TimeoutError || (error instanceof HttpErrorResponse && error.status === 0)) {
        try {
          await this.restoreLocalBranches();
        } catch {
          this.error.set('No se pudo recuperar el catálogo local.');
        }
      } else {
        this.error.set(this.errors.message(error, 'No se pudieron cargar las sucursales.'));
      }
    } finally {
      this.loadingBranches.set(false);
    }
    await this.autoPrepare();
  }

  private async restoreLocalBranches(): Promise<void> {
    const tenantId = this.tenant.tenant()?.id_tenant;
    const userId = this.auth.currentUser()?.id_usuario;
    if (!tenantId || !userId) return;
    const ids = await this.database.savedBranchIds(tenantId, userId);
    if (this.destroyRef.destroyed || this.tenant.tenant()?.id_tenant !== tenantId ||
        this.auth.currentUser()?.id_usuario !== userId) return;
    const assigned = this.assignedBranch();
    const cached = this.readBranchCache();
    const branches = ids.filter((id) => assigned === null || id === assigned).map((id) =>
      cached?.branches.find((branch) => branch.id_sucursal === id) ??
        { id_sucursal: id, nombre: `Sucursal #${id}`, direccion: '' },
    );
    this.branches.set(branches);
    const preferred = assigned ?? cached?.selected;
    const selected = branches.find((branch) => branch.id_sucursal === preferred) ??
      (branches.length === 1 ? branches[0] : undefined);
    if (selected) {
      this.selectedBranchId.set(selected.id_sucursal);
      await this.inspectLocalData();
    } else if (!branches.length) {
      this.message.set('Conéctate a internet una vez y elige tu sucursal: el catálogo se descargará solo para usarlo sin internet.');
    }
  }

  private branchCacheKey(): string | null {
    const tenantId = this.tenant.tenant()?.id_tenant;
    const userId = this.auth.currentUser()?.id_usuario;
    return tenantId && userId ? `zentry_offline_branches_${tenantId}_${userId}` : null;
  }

  private readBranchCache(): { branches: Branch[]; selected: number | null } | null {
    try {
      const key = this.branchCacheKey();
      const value = key ? JSON.parse(localStorage.getItem(key) ?? 'null') : null;
      return Array.isArray(value?.branches) ? value : null;
    } catch {
      return null;
    }
  }

  private writeBranchCache(): void {
    try {
      const key = this.branchCacheKey();
      if (!key) return;
      const branches = this.readBranchCache()?.branches ?? [];
      const known = new Map(branches.map((branch) => [branch.id_sucursal, branch]));
      for (const branch of this.branches()) known.set(branch.id_sucursal, branch);
      localStorage.setItem(key, JSON.stringify({
        branches: [...known.values()],
        selected: this.selectedBranchId(),
      }));
    } catch {
      // IndexedDB can still recover saved branches if localStorage is unavailable.
    }
  }

  async selectBranch(rawValue: string): Promise<void> {
    if (this.synchronizing() || this.preparing() || this.queuingSale()) return;
    this.selectedBranchId.set(rawValue ? Number(rawValue) : null);
    this.resetLocalView();
    if (!this.selectedBranchId()) return;
    this.preparing.set(true);
    try {
      await this.inspectLocalData();
      this.writeBranchCache();
    } finally {
      this.preparing.set(false);
    }
    this.preparedAt = 0;
    await this.autoPrepare();
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
    this.operationMode.set(this.allowedMode(mode));
    this.message.set('');
    this.error.set('');
  }

  /**
   * El modo pedido si el usuario puede usarlo; si no, el otro. Así quien solo
   * reserva no queda en "Venta" (el backend la rechazaría al sincronizar).
   */
  private allowedMode(wanted: 'VENTA' | 'RESERVA'): 'VENTA' | 'RESERVA' {
    const user = this.auth.currentUser();
    if (wanted === 'VENTA' && !canSellOffline(user) && canReserveOffline(user)) return 'RESERVA';
    if (wanted === 'RESERVA' && !canReserveOffline(user) && canSellOffline(user)) return 'VENTA';
    return wanted;
  }

  async queueOfflineSale(): Promise<void> {
    if (this.queuingSale()) return;
    const scope = this.scope();
    const lines = this.cartLines();
    if (!scope || !lines.length) return;
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
        precios_cobrados: Object.fromEntries(lines.map((line) => [
          line.item.id_variante, Math.round(Number(line.item.precio) * 100),
        ])),
        total_cobrado_centavos: lines.reduce(
          (total, line) => total + Math.round(Number(line.item.precio) * 100) * line.quantity, 0,
        ),
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
      // Con conexión se envía enseguida, sin esperar al próximo chequeo.
      this.scheduleAutoSync();
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
      // Con conexión se envía enseguida, sin esperar al próximo chequeo.
      this.scheduleAutoSync();
    }
  }

  /**
   * Descarga el catálogo y los clientes de la sucursal. Con `automatic` y un
   * catálogo ya guardado, actualiza en segundo plano: no bloquea la venta ni
   * muestra errores (se sigue vendiendo con lo guardado).
   */
  async prepareDevice(automatic = false): Promise<void> {
    if (this.preparing() || this.refreshing() || this.synchronizing()) return;
    const scope = this.scope();
    if (!scope) return;
    const background = automatic && this.catalog().length > 0;
    (background ? this.refreshing : this.preparing).set(true);
    if (!background) {
      this.error.set('');
      this.message.set('');
    }
    try {
      await this.synchronization.prepare(scope);
      this.preparedAt = Date.now();
      await this.refreshLocalView();
      if (background) return;
      if (this.catalog().length) {
        this.message.set(
          `Catálogo de ${this.selectedBranch()?.nombre ?? 'la sucursal'} listo para vender, con o sin conexión.`,
        );
      } else if (!this.connectivity.online()) {
        this.error.set('Conéctate a internet una vez para descargar el catálogo de esta sucursal.');
      }
    } catch (error) {
      if (!background) {
        this.error.set(this.errors.message(error, 'No se pudo descargar el catálogo de la sucursal.'));
      }
    } finally {
      this.preparing.set(false);
      this.refreshing.set(false);
      this.scheduleAutoSync();
    }
  }

  /**
   * Sin pasos manuales: con internet descarga el catálogo si falta o tiene más
   * de 5 minutos (al abrir la pantalla, al elegir sucursal y al volver la red).
   */
  private async autoPrepare(): Promise<void> {
    if (this.destroyRef.destroyed || !this.connectivity.online() || !this.selectedBranchId() ||
        this.loadingBranches() || this.preparing() || this.refreshing() || this.synchronizing()) return;
    if (this.catalog().length && Date.now() - this.preparedAt < CATALOG_REFRESH_MS) return;
    await this.prepareDevice(true);
  }

  /** Botón "Sincronizar": envía ya (si falla, el envío automático reintenta cada 30 s). */
  async synchronizeNow(): Promise<void> {
    if (this.destroyRef.destroyed || !this.connectivity.online() || !this.selectedBranchId() ||
        this.synchronizing() || this.preparing()) return;
    const scope = this.scope();
    if (!scope) return;
    this.synchronizing.set(true);
    this.error.set('');
    this.message.set('');
    try {
      const response = await this.synchronization.synchronizePending(scope);
      if (this.destroyRef.destroyed) return;
      await this.refreshLocalView();
      if (this.destroyRef.destroyed) return;
      this.message.set(
        response
          ? `Sincronización completada: ${response.total_aplicadas} operaciones aplicadas.`
          : 'No existen operaciones pendientes por sincronizar.',
      );
      if (response) {
        // Quedan más lotes: los envía el servicio automático.
        this.scheduleAutoSync();
        try {
          await this.synchronization.prepare(scope);
          await this.refreshLocalView();
        } catch {
          this.error.set('Se enviaron las operaciones, pero no se pudo actualizar el catálogo.');
        }
      }
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo completar la sincronización.'));
    } finally {
      this.synchronizing.set(false);
      void this.autoSync.refreshAlerts();
    }
  }

  readonly canReload = canReloadOfflineOperation;
  readonly serverResolution = serverResolutionLabel;
  readonly failureReason = (operation: PendingOfflineOperation) =>
    offlineFailureReason(operation.codigo_error);

  /**
   * Venta rechazada por datos inválidos: carga sus prendas en el carrito para
   * registrarla corregida como operación nueva. La original queda revisada
   * (el servidor no acepta reenviarla con el mismo id).
   */
  async reloadIntoCart(operation: PendingOfflineOperation): Promise<void> {
    if (!this.canReload(operation) || this.resolvingOperationId()) return;
    const quantities: Record<number, number> = {};
    let missing = 0;
    const items = Array.isArray(operation.payload['items']) ? operation.payload['items'] : [];
    for (const raw of items) {
      const line = (raw ?? {}) as Record<string, unknown>;
      const variantId = Number(line['id_variante']);
      const requested = Math.floor(Number(line['cantidad']) || 0);
      const item = this.catalog().find((entry) => entry.id_variante === variantId);
      const available = item ? this.availableFor(item) : 0;
      if (!item || available <= 0 || requested <= 0) {
        missing++;
        continue;
      }
      quantities[variantId] = Math.min(requested, available);
    }
    if (!Object.keys(quantities).length) {
      this.error.set('Ninguna prenda de esa operación está disponible en el catálogo local.');
      return;
    }
    this.resolvingOperationId.set(operation.id_operacion);
    this.error.set('');
    try {
      await this.database.markReviewed(operation.id_operacion);
      this.cartQuantities.set(quantities);
      this.operationMode.set(this.allowedMode(operation.tipo));
      const customerId = operation.payload['id_cliente'];
      this.selectedCustomerId.set(typeof customerId === 'number' ? customerId : null);
      await this.refreshLocalView();
      this.message.set(missing
        ? `Prendas cargadas (${missing} ya no están disponibles): revisa y vuelve a guardar.`
        : 'Prendas cargadas en el carrito: revisa los datos y vuelve a guardar.');
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo cargar la operación.'));
    } finally {
      this.resolvingOperationId.set(null);
    }
  }

  /** Deja de alertar sobre la operación; no la reenvía ni la borra. */
  async markReviewed(operation: PendingOfflineOperation): Promise<void> {
    this.resolvingOperationId.set(operation.id_operacion);
    this.error.set('');
    try {
      await this.database.markReviewed(operation.id_operacion);
      await this.refreshLocalView();
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo marcar la operación.'));
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
    // Alertas del panel (banner y contador) al día con la cola local.
    void this.autoSync.refreshAlerts();
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
    this.operationMode.set(this.allowedMode('VENTA'));
  }
}
