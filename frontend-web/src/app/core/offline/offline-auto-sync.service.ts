import { effect, inject, Injectable, Injector, signal, untracked } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { AuthService } from '../auth/auth.service';
import { TenantContextService } from '../tenant/tenant-context.service';
import { ConnectivityService } from './connectivity.service';
import { OfflineDatabaseService } from './offline-database.service';
import { OfflineSyncService } from './offline-sync.service';
import {
  canReviewSyncConflicts,
  canUseOffline,
  OfflineScope,
  PendingOfflineOperation,
} from './offline.models';
import { SyncApiService } from './sync-api.service';

/** Máximo de lotes por ejecución, para no quedar en un bucle si algo falla. */
const MAX_BATCHES_PER_RUN = 20;
/** Cada cuánto se vuelve a contar los conflictos pendientes del encargado. */
const CONFLICTS_REFRESH_MS = 2 * 60_000;

/**
 * Sincronización automática de ventas offline en toda la app (no solo con la
 * pantalla Operación offline abierta). En cada chequeo de conexión con
 * internet: envía la cola, actualiza el stock local, consulta si el
 * encargado ya resolvió las operaciones no registradas y recalcula las
 * alertas que muestra el panel.
 */
@Injectable({ providedIn: 'root' })
export class OfflineAutoSyncService {
  private readonly auth = inject(AuthService);
  private readonly tenant = inject(TenantContextService);
  private readonly connectivity = inject(ConnectivityService);
  private readonly database = inject(OfflineDatabaseService);
  private readonly synchronization = inject(OfflineSyncService);
  private readonly api = inject(SyncApiService);
  private readonly injector = inject(Injector);
  private running: Promise<void> | null = null;
  private started = false;
  private conflictsCheckedAt = 0;

  private readonly failuresState = signal<PendingOfflineOperation[]>([]);
  private readonly pendingConflictsState = signal(0);
  private readonly revisionState = signal(0);
  private readonly syncingState = signal(false);

  /** Ventas o reservas de este equipo que no se registraron y nadie revisó. */
  readonly failures = this.failuresState.asReadonly();
  /** Conflictos por resolver (solo encargados y administradores). */
  readonly pendingConflicts = this.pendingConflictsState.asReadonly();
  /** Aumenta cuando cambió la cola local (para que la pantalla se recargue). */
  readonly revision = this.revisionState.asReadonly();
  readonly syncing = this.syncingState.asReadonly();

  /** Se llama una vez al arrancar la app. */
  start(): void {
    if (this.started) return;
    this.started = true;
    this.connectivity.start();
    // Cada chequeo terminado (30 s, cambio de red, volver a la pestaña).
    effect(() => {
      this.connectivity.checkedAt();
      this.auth.currentUser();
      untracked(() => void this.syncNow());
    }, { injector: this.injector });
  }

  /** Ejecuta ahora; si ya hay una ejecución en curso, devuelve esa. */
  syncNow(): Promise<void> {
    return (this.running ??= this.run().finally(() => (this.running = null)));
  }

  /** Recalcula las alertas (tras marcar como revisada, cargar de nuevo o quitar). */
  async refreshAlerts(): Promise<void> {
    try {
      this.failuresState.set(this.ownScope() ? await this.database.unreviewedFailures() : []);
    } catch {
      this.failuresState.set([]);
    }
  }

  /** Vuelve a contar los conflictos pendientes (tras resolver uno). */
  async refreshPendingConflicts(): Promise<void> {
    if (!canReviewSyncConflicts(this.auth.currentUser()) || !this.connectivity.online()) {
      if (!canReviewSyncConflicts(this.auth.currentUser())) this.pendingConflictsState.set(0);
      return;
    }
    this.conflictsCheckedAt = Date.now();
    try {
      const conflicts = await firstValueFrom(this.api.conflicts('PENDIENTE'));
      this.pendingConflictsState.set(conflicts.length);
    } catch {
      // Se reintenta en el próximo chequeo.
    }
  }

  private async run(): Promise<void> {
    const user = this.auth.currentUser();
    if (this.connectivity.online() &&
        Date.now() - this.conflictsCheckedAt >= CONFLICTS_REFRESH_MS) {
      await this.refreshPendingConflicts();
    }
    // Mismas reglas que el backend: vender o reservar offline (no exige inventario).
    if (!canUseOffline(user)) {
      this.failuresState.set([]);
      return;
    }
    const scope = await this.ensureScope();
    if (!scope) {
      this.failuresState.set([]);
      return;
    }
    let changed = false;
    if (this.connectivity.online()) {
      this.syncingState.set(true);
      try {
        changed = await this.sendQueue(scope);
        changed = (await this.fetchResolutions()) || changed;
      } finally {
        this.syncingState.set(false);
      }
    }
    await this.refreshAlerts();
    if (changed) this.revisionState.update((value) => value + 1);
  }

  /** Envía todos los lotes pendientes; true si se envió alguno. */
  private async sendQueue(scope: OfflineScope): Promise<boolean> {
    let batches = 0;
    try {
      for (let i = 0; i < MAX_BATCHES_PER_RUN; i++) {
        const response = await this.synchronization.synchronizePending(scope);
        if (!response) break;
        batches++;
      }
    } catch {
      // Sin red o servidor caído: se reintenta en el próximo chequeo (30 s).
    }
    if (batches) {
      // El stock del servidor cambió: se refresca el catálogo local.
      try {
        await this.synchronization.prepare(scope);
      } catch {
        // Se sigue vendiendo con el catálogo guardado.
      }
    }
    return batches > 0;
  }

  /** Consulta si el encargado ya reaplicó o anuló las operaciones fallidas. */
  private async fetchResolutions(): Promise<boolean> {
    let resolved = 0;
    try {
      const ids = await this.database.unresolvedFailedIds();
      for (let start = 0; start < ids.length; start += 100) {
        const statuses = await firstValueFrom(
          this.api.operationStatus(ids.slice(start, start + 100)),
        );
        for (const status of statuses) {
          if (!status.accion) continue;
          await this.database.applyServerResolution(
            status.id_operacion,
            status.accion,
            status.resolucion,
          );
          resolved++;
        }
      }
    } catch {
      // Se vuelve a consultar en el próximo chequeo.
    }
    return resolved > 0;
  }

  /**
   * Sucursal abierta en la base local. Si no hay ninguna (p. ej. se recargó la
   * página), se abre la última usada por este usuario en este equipo.
   */
  private async ensureScope(): Promise<OfflineScope | null> {
    if (this.database.scope()) return this.ownScope();
    const tenantId = this.tenant.tenant()?.id_tenant;
    const userId = this.auth.currentUser()?.id_usuario;
    if (!tenantId || !userId) return null;
    try {
      const saved = await this.database.savedBranchIds(tenantId, userId);
      const last = this.lastBranch(tenantId, userId);
      const branchId = saved.includes(last ?? -1) ? last : saved.length === 1 ? saved[0] : null;
      if (!branchId || this.database.scope()) return this.ownScope();
      await this.database.openScope({ tenantId, userId, branchId });
      return this.ownScope();
    } catch {
      return null;
    }
  }

  /** La sucursal abierta, solo si pertenece a la empresa y sesión actuales. */
  private ownScope(): OfflineScope | null {
    const scope = this.database.scope();
    if (!scope) return null;
    const sameTenant = scope.tenantId === this.tenant.tenant()?.id_tenant;
    const sameUser = scope.userId === this.auth.currentUser()?.id_usuario;
    return sameTenant && sameUser ? scope : null;
  }

  private lastBranch(tenantId: number, userId: number): number | null {
    try {
      const raw = localStorage.getItem(`zentry_offline_branches_${tenantId}_${userId}`);
      const selected = raw ? JSON.parse(raw)?.selected : null;
      return typeof selected === 'number' ? selected : null;
    } catch {
      return null;
    }
  }
}
