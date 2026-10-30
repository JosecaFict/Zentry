import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { Branch } from '../../core/models/catalog.model';
import { ConnectivityService } from '../../core/offline/connectivity.service';
import { OfflineDatabaseService } from '../../core/offline/offline-database.service';
import {
  OfflineCatalogItem,
  OfflineOperationSummary,
  OfflineScope,
  OfflineSyncMeta,
} from '../../core/offline/offline.models';
import { OfflineSyncService } from '../../core/offline/offline-sync.service';
import { ApiErrorService } from '../../core/services/api-error.service';
import { CatalogService } from '../../core/services/catalog.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';

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
  readonly availableUnits = computed(() =>
    this.catalog().reduce((total, item) => total + item.stock_disponible, 0),
  );

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
    this.selectedBranchId.set(rawValue ? Number(rawValue) : null);
    this.resetLocalView();
    if (this.selectedBranchId()) await this.inspectLocalData();
  }

  async prepareDevice(): Promise<void> {
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
    }
  }

  async synchronizeNow(): Promise<void> {
    if (!this.connectivity.online() || !this.selectedBranchId()) return;
    this.synchronizing.set(true);
    this.error.set('');
    this.message.set('');
    try {
      const response = await this.synchronization.synchronizePending();
      await this.refreshLocalView();
      this.message.set(
        response
          ? `Sincronización completada: ${response.total_aplicadas} operaciones aplicadas.`
          : 'No existen operaciones pendientes por sincronizar.',
      );
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo completar la sincronización.'));
    } finally {
      this.synchronizing.set(false);
    }
  }

  private async inspectLocalData(): Promise<void> {
    const scope = this.scope();
    if (!scope) return;
    try {
      await this.database.openScope(scope);
      await this.refreshLocalView();
    } catch (error) {
      this.error.set(this.errors.message(error, 'No se pudo abrir el almacenamiento local.'));
    }
  }

  private async refreshLocalView(): Promise<void> {
    const [catalog, meta, summary] = await Promise.all([
      this.database.listCatalog(),
      this.database.currentMeta(),
      this.database.operationSummary(),
    ]);
    this.catalog.set(catalog);
    this.meta.set(meta);
    this.operationSummary.set(summary);
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
  }
}
