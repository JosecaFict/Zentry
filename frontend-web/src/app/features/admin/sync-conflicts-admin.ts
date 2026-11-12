import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import {
  canReviewSyncConflicts,
  offlineFailureReason,
  SyncConflict,
  syncConflictAdvice,
} from '../../core/offline/offline.models';
import { OfflineAutoSyncService } from '../../core/offline/offline-auto-sync.service';
import { SyncApiService } from '../../core/offline/sync-api.service';
import { ApiErrorService } from '../../core/services/api-error.service';

/**
 * Ventas y reservas offline que el servidor no registró (sin stock, conflicto
 * o datos inválidos). Un encargado o administrador decide: REAPLICAR (p. ej.
 * tras ajustar el inventario) o ANULAR con una nota de cómo se resolvió.
 */
@Component({
  selector: 'app-sync-conflicts-admin',
  imports: [CommonModule],
  template: `<div class="admin-page conflicts-page">
    <header class="admin-page-heading">
      <div>
        <h1>Conflictos offline</h1>
        <p>Ventas y reservas hechas sin conexión que no se pudieron registrar al sincronizar.</p>
      </div>
      @if (allowed()) {
        <button class="button button--secondary" type="button" [disabled]="loading()" (click)="load()">
          Actualizar
        </button>
      }
    </header>

    @if (!allowed()) {
      <section class="admin-state admin-state--inline" role="alert">
        <h2>Solo para encargados y administradores</h2>
        <p>Los conflictos los revisa el encargado de la sucursal o un administrador.</p>
      </section>
    } @else {
      @if (message()) {
        <div class="notice" [class.notice--error]="isError()" [attr.role]="isError() ? 'alert' : 'status'">
          {{ message() }}
        </div>
      }

      <div class="admin-tabs" role="tablist">
        <button type="button" role="tab" [class.active]="tab() === 'pending'"
          [attr.aria-selected]="tab() === 'pending'" (click)="tab.set('pending')">
          Pendientes ({{ pending().length }})
        </button>
        <button type="button" role="tab" [class.active]="tab() === 'history'"
          [attr.aria-selected]="tab() === 'history'" (click)="tab.set('history')">
          Historial
        </button>
      </div>

      @if (loading() && !conflicts().length) {
        <div class="admin-skeleton" aria-hidden="true"></div>
      } @else if (!visible().length) {
        <p class="admin-empty">
          {{ tab() === 'pending' ? 'Sin conflictos pendientes. Todas las ventas offline se registraron.' : 'Todavía no hay conflictos resueltos.' }}
        </p>
      } @else {
        <div class="conflict-list">
          @for (conflict of visible(); track conflict.id_conflicto) {
            <article class="conflict-card" [class.is-pending]="conflict.estado === 'PENDIENTE'">
              <header>
                <div>
                  <h2>{{ label(conflict) }} de {{ conflict.vendedor ?? 'Vendedor #' + conflict.id_vendedor }}</h2>
                  <span>Hecha el {{ conflict.fecha_cliente | date: 'dd/MM/yyyy, HH:mm' }}</span>
                </div>
                @if (conflict.total_cobrado_centavos !== null) {
                  <strong class="conflict-total">Bs {{ conflict.total_cobrado_centavos / 100 | number: '1.2-2' }}</strong>
                }
              </header>

              <ul class="conflict-items">
                @for (item of conflict.items; track item.id_variante) {
                  <li>{{ item.cantidad }} × {{ item.descripcion }}</li>
                }
              </ul>

              <p class="conflict-reason">
                <strong>{{ reason(conflict) }}</strong>
                @if (conflict.mensaje) { <br /><small>Detalle: {{ conflict.mensaje }}</small> }
              </p>

              @if (conflict.estado === 'PENDIENTE') {
                <p class="conflict-advice">{{ advice(conflict) }}</p>
                @if (cancellingId() === conflict.id_conflicto) {
                  <label class="field">
                    <span>¿Cómo se resolvió con el cliente?</span>
                    <textarea rows="2" maxlength="500" [value]="note()"
                      placeholder="Ej.: se devolvió el dinero al cliente"
                      (input)="note.set($any($event.target).value)"></textarea>
                  </label>
                  <div class="conflict-actions">
                    <button class="button button--quiet" type="button" (click)="cancellingId.set(null)">Volver</button>
                    <button class="button button--danger" type="button"
                      [disabled]="!noteValid() || busyId() === conflict.id_conflicto"
                      (click)="resolve(conflict, 'ANULAR')">Anular</button>
                  </div>
                } @else {
                  <div class="conflict-actions">
                    <button class="button button--primary" type="button"
                      [disabled]="!conflict.puede_reaplicar || busyId() !== null"
                      [title]="conflict.puede_reaplicar ? '' : 'Con datos inválidos no se puede reaplicar'"
                      (click)="resolve(conflict, 'REAPLICAR')">
                      {{ busyId() === conflict.id_conflicto ? 'Reaplicando…' : 'Reaplicar' }}
                    </button>
                    <button class="button button--secondary" type="button" [disabled]="busyId() !== null"
                      (click)="startCancel(conflict)">Anular</button>
                  </div>
                }
              } @else {
                <p class="conflict-resolution">
                  <strong>{{ conflict.accion === 'REAPLICADA' ? 'Reaplicada' : 'Anulada' }}</strong>
                  @if (conflict.resuelto_por) { por {{ conflict.resuelto_por }} }
                  @if (conflict.resuelto_at) { · {{ conflict.resuelto_at | date: 'dd/MM/yyyy, HH:mm' }} }
                  @if (conflict.resolucion) { <br />{{ conflict.resolucion }} }
                </p>
              }
            </article>
          }
        </div>
      }
    }
  </div>`,
  styles: `
    .conflict-list { display: grid; gap: 14px; }
    .conflict-card {
      padding: 18px 20px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
    }
    .conflict-card.is-pending { border-left: 4px solid var(--danger); }
    .conflict-card header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
    .conflict-card h2 { margin: 0; font-size: 1.05rem; }
    .conflict-card header span { color: var(--ink-soft); font-size: 0.85rem; }
    .conflict-total { white-space: nowrap; }
    .conflict-items { margin: 12px 0; padding-left: 18px; }
    .conflict-reason { margin: 0 0 6px; color: var(--danger); }
    .conflict-reason small { color: var(--ink-soft); }
    .conflict-advice, .conflict-resolution { margin: 0 0 12px; color: var(--ink-soft); }
    .conflict-resolution strong { color: var(--ink); }
    .conflict-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
    .field { display: grid; gap: 6px; margin-bottom: 10px; }
  `,
})
export class SyncConflictsAdmin implements OnInit {
  private readonly api = inject(SyncApiService);
  private readonly auth = inject(AuthService);
  private readonly errors = inject(ApiErrorService);
  private readonly autoSync = inject(OfflineAutoSyncService);

  readonly conflicts = signal<SyncConflict[]>([]);
  readonly loading = signal(false);
  readonly tab = signal<'pending' | 'history'>('pending');
  readonly message = signal('');
  readonly isError = signal(false);
  readonly busyId = signal<number | null>(null);
  readonly cancellingId = signal<number | null>(null);
  readonly note = signal('');
  readonly noteValid = computed(() => this.note().trim().length >= 3);

  readonly allowed = computed(() => canReviewSyncConflicts(this.auth.currentUser()));

  readonly pending = computed(() => this.conflicts().filter((item) => item.estado === 'PENDIENTE'));
  readonly visible = computed(() => {
    if (this.tab() === 'pending') return this.pending();
    return this.conflicts()
      .filter((item) => item.estado !== 'PENDIENTE')
      .sort((a, b) => (b.resuelto_at ?? b.created_at).localeCompare(a.resuelto_at ?? a.created_at));
  });

  ngOnInit(): void {
    if (this.allowed()) void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      this.conflicts.set(await firstValueFrom(this.api.conflicts('TODOS')));
    } catch (error) {
      this.show(this.errors.message(error, 'No se pudieron cargar los conflictos.'), true);
    } finally {
      this.loading.set(false);
    }
  }

  label(conflict: SyncConflict): string {
    return conflict.tipo_operacion === 'VENTA' ? 'Venta' : 'Reserva';
  }

  reason(conflict: SyncConflict): string {
    return offlineFailureReason(conflict.codigo);
  }

  advice(conflict: SyncConflict): string {
    return syncConflictAdvice(conflict.codigo);
  }

  startCancel(conflict: SyncConflict): void {
    this.note.set('');
    this.cancellingId.set(conflict.id_conflicto);
  }

  async resolve(conflict: SyncConflict, accion: 'REAPLICAR' | 'ANULAR'): Promise<void> {
    if (this.busyId() !== null) return;
    if (accion === 'ANULAR' && !this.noteValid()) return;
    this.busyId.set(conflict.id_conflicto);
    this.message.set('');
    try {
      const updated = await firstValueFrom(
        this.api.resolveConflict(
          conflict.id_conflicto,
          accion,
          accion === 'ANULAR' ? this.note().trim() : null,
        ),
      );
      this.conflicts.update((items) =>
        items.map((item) => (item.id_conflicto === updated.id_conflicto ? updated : item)),
      );
      this.cancellingId.set(null);
      void this.autoSync.refreshPendingConflicts();
      this.show(
        accion === 'REAPLICAR'
          ? `${this.label(conflict)} reaplicada: ya quedó registrada y se avisó al vendedor.`
          : `${this.label(conflict)} anulada. Se avisó al vendedor.`,
        false,
      );
    } catch (error) {
      // Si al reaplicar sigue sin stock, el backend lo explica en el detalle.
      this.show(this.errors.message(error, 'No se pudo resolver el conflicto.'), true);
    } finally {
      this.busyId.set(null);
    }
  }

  private show(text: string, error: boolean): void {
    this.message.set(text);
    this.isError.set(error);
  }
}
