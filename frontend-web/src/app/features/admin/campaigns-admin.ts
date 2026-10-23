import { CommonModule, DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize } from 'rxjs';
import {
  Campaign,
  CampaignCreate,
  CampaignLaunchResponse,
} from '../../core/models/commerce.model';
import { ApiErrorService } from '../../core/services/api-error.service';
import { CommerceService } from '../../core/services/commerce.service';

@Component({
  selector: 'app-campaigns-admin',
  imports: [CommonModule, ReactiveFormsModule, DatePipe],
  template: `
    <div class="admin-page">
      <header class="admin-page-heading">
        <div>
          <p class="eyebrow">Marketing y promociones</p>
          <h1>Campañas y Difusión Masiva</h1>
          <p>
            Crea comunicados promocionales y difúndelos a los clientes para que aparezcan en su campana de notificaciones y móvil.
          </p>
        </div>
        <div class="admin-page-heading__actions">
          <button class="button button--primary" (click)="openCreateModal()">
            <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16" aria-hidden="true">
              <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
            </svg>
            Nueva campaña
          </button>
        </div>
      </header>

      @if (successMessage()) {
        <div class="admin-notice admin-notice--success">
          <span>{{ successMessage() }}</span>
          <button type="button" class="button button--ghost button--small" (click)="successMessage.set(null)" style="margin-left: auto;">✕</button>
        </div>
      }

      @if (errorMessage()) {
        <div class="admin-notice admin-notice--error">
          <span>{{ errorMessage() }}</span>
          <button type="button" class="button button--ghost button--small" (click)="errorMessage.set(null)" style="margin-left: auto;">✕</button>
        </div>
      }

      <!-- KPI Grid -->
      <section class="notification-kpi-grid">
        <div class="notification-kpi-card">
          <span class="notification-kpi-card__label">Total Campañas</span>
          <strong class="notification-kpi-card__value">{{ kpis().total }}</strong>
          <span class="notification-kpi-card__sub">Registradas en el sistema</span>
        </div>
        <div class="notification-kpi-card notification-kpi-card--success">
          <span class="notification-kpi-card__label">Difundidas / Finalizadas</span>
          <strong class="notification-kpi-card__value">{{ kpis().finalizadas }}</strong>
          <span class="notification-kpi-card__sub">Enviadas a clientes</span>
        </div>
        <div class="notification-kpi-card notification-kpi-card--warning">
          <span class="notification-kpi-card__label">En Borrador</span>
          <strong class="notification-kpi-card__value">{{ kpis().borradores }}</strong>
          <span class="notification-kpi-card__sub">Listas para configurar y enviar</span>
        </div>
        <div class="notification-kpi-card">
          <span class="notification-kpi-card__label">Avisos Emitidos</span>
          <strong class="notification-kpi-card__value">{{ kpis().impactoTotal }}</strong>
          <span class="notification-kpi-card__sub">Notificaciones entregadas</span>
        </div>
      </section>

      <!-- Filtros -->
      <section class="table-card" style="margin-top: 1.5rem;">
        <div class="table-card__toolbar" style="display: flex; gap: 1rem; align-items: center; justify-content: space-between; flex-wrap: wrap;">
          <div class="search-wrap" style="flex: 1; min-width: 260px;">
            <input
              type="search"
              class="input-search"
              placeholder="Buscar por nombre o mensaje..."
              [value]="searchQuery()"
              (input)="onSearchInput($event)"
            />
          </div>
          <div style="display: flex; gap: 0.75rem; align-items: center;">
            <select class="input-select" [value]="statusFilter()" (change)="onStatusFilterChange($event)">
              <option value="">Todos los estados</option>
              <option value="BORRADOR">En borrador</option>
              <option value="FINALIZADA">Finalizadas / Difundidas</option>
              <option value="CANCELADA">Canceladas</option>
            </select>
            <button class="button button--secondary button--small" (click)="loadCampaigns()" [disabled]="loading()">
              🔄 Actualizar
            </button>
          </div>
        </div>

        @if (loading()) {
          <div class="table-card__empty" style="padding: 3rem; text-align: center;">
            <p>Cargando campañas...</p>
          </div>
        } @else if (filteredCampaigns().length === 0) {
          <div class="table-card__empty" style="padding: 3rem; text-align: center;">
            <h3>No se encontraron campañas</h3>
            <p>Puedes redactar una nueva campaña promocional pulsando en "Nueva campaña".</p>
          </div>
        } @else {
          <div class="table-responsive">
            <table class="returns-table" aria-label="Listado de campañas promocionales">
              <thead>
                <tr>
                  <th scope="col">Campaña</th>
                  <th scope="col">Segmento</th>
                  <th scope="col">Estado</th>
                  <th scope="col">Impacto</th>
                  <th scope="col">Fecha creación</th>
                  <th scope="col" style="text-align: right;">Acciones</th>
                </tr>
              </thead>
              <tbody>
                @for (c of filteredCampaigns(); track c.id_campania) {
                  <tr>
                    <td>
                      <div>
                        <strong>{{ c.nombre }}</strong>
                        <p style="margin: 2px 0 0; font-size: 0.8rem; color: var(--ink-soft); line-height: 1.3;">
                          {{ c.descripcion }}
                        </p>
                        @if (c.asunto_email) {
                          <small style="color: var(--accent); font-weight: 600;">Asunto: {{ c.asunto_email }}</small>
                        }
                      </div>
                    </td>
                    <td>
                      <span class="badge" style="background: var(--canvas); color: var(--ink); border: 1px solid var(--line);">
                        {{ c.segmento_objetivo || 'TODOS' }}
                      </span>
                    </td>
                    <td>
                      <span class="badge" [class.badge--success]="c.estado === 'FINALIZADA'" [class.badge--warning]="c.estado === 'BORRADOR'" [class.badge--danger]="c.estado === 'CANCELADA'">
                        {{ c.estado }}
                      </span>
                    </td>
                    <td>
                      <strong>{{ c.total_notificaciones }}</strong>
                      <small style="display: block; color: var(--ink-soft); font-size: 0.72rem;">clientes notificados</small>
                    </td>
                    <td>
                      <span style="font-size: 0.82rem;">{{ c.created_at | date: 'mediumDate' }}</span>
                      <small style="display: block; color: var(--ink-soft); font-size: 0.72rem;">{{ c.created_at | date: 'shortTime' }}</small>
                    </td>
                    <td style="text-align: right; white-space: nowrap;">
                      @if (c.estado === 'BORRADOR') {
                        <button
                          class="button button--primary button--small"
                          (click)="openLaunchConfirm(c)"
                          style="margin-left: 6px;"
                          title="Lanzar difusión a clientes"
                        >
                          🚀 Lanzar difusión
                        </button>
                      } @else if (c.estado === 'FINALIZADA') {
                        <span class="badge badge--success" style="font-size: 0.75rem;">✓ Difundida</span>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>

      <!-- Modal: Crear Campaña -->
      @if (showCreateModal()) {
        <div class="admin-modal-backdrop" (click)="closeCreateModal()">
          <div class="admin-modal" (click)="$event.stopPropagation()" role="dialog" aria-modal="true">
            <header class="admin-modal__header">
              <h2>Nueva Campaña Promocional</h2>
              <button class="admin-modal__close" (click)="closeCreateModal()" aria-label="Cerrar">✕</button>
            </header>
            <form [formGroup]="createForm" (ngSubmit)="submitCreate()">
              <div class="admin-modal__body">
                <div class="form-group" style="margin-bottom: 1rem;">
                  <label for="c-nombre"><strong>Nombre de la campaña *</strong></label>
                  <input
                    id="c-nombre"
                    type="text"
                    class="input-text"
                    formControlName="nombre"
                    placeholder="Ej. Liquidación de Primavera 2026"
                  />
                  @if (createForm.get('nombre')?.touched && createForm.get('nombre')?.invalid) {
                    <small style="color: var(--danger, #dc2626);">El nombre es requerido (mín. 3 caracteres).</small>
                  }
                </div>

                <div class="form-group" style="margin-bottom: 1rem;">
                  <label for="c-desc"><strong>Mensaje para los clientes *</strong></label>
                  <textarea
                    id="c-desc"
                    class="input-textarea"
                    rows="3"
                    formControlName="descripcion"
                    placeholder="Ej. ¡Aprovecha un 20% de descuento en todas nuestras camisas y poleras este fin de semana!"
                  ></textarea>
                  @if (createForm.get('descripcion')?.touched && createForm.get('descripcion')?.invalid) {
                    <small style="color: var(--danger, #dc2626);">El mensaje es requerido (mín. 5 caracteres).</small>
                  }
                </div>

                <div class="form-group" style="margin-bottom: 1rem;">
                  <label for="c-asunto"><strong>Asunto de correo (opcional)</strong></label>
                  <input
                    id="c-asunto"
                    type="text"
                    class="input-text"
                    formControlName="asunto_email"
                    placeholder="Ej. ¡Descubre nuestras ofertas exclusivas!"
                  />
                </div>

                <div class="form-group" style="margin-bottom: 1rem;">
                  <label for="c-segmento"><strong>Segmento objetivo</strong></label>
                  <select id="c-segmento" class="input-select" formControlName="segmento_objetivo">
                    <option value="TODOS">Todos los clientes registrados</option>
                    <option value="CON_COMPRAS">Clientes con compras anteriores</option>
                    <option value="CON_RESERVAS">Clientes con reservas en tienda</option>
                  </select>
                </div>
              </div>

              <footer class="admin-modal__footer" style="display: flex; justify-content: flex-end; gap: 0.75rem;">
                <button type="button" class="button button--secondary" (click)="closeCreateModal()" [disabled]="submitting()">
                  Cancelar
                </button>
                <button type="submit" class="button button--primary" [disabled]="createForm.invalid || submitting()">
                  {{ submitting() ? 'Guardando...' : 'Crear campaña' }}
                </button>
              </footer>
            </form>
          </div>
        </div>
      }

      <!-- Modal: Confirmar Lanzamiento de Difusión -->
      @if (campaignToLaunch()) {
        <div class="admin-modal-backdrop" (click)="closeLaunchConfirm()">
          <div class="admin-modal" (click)="$event.stopPropagation()" role="dialog" aria-modal="true" style="max-width: 480px;">
            <header class="admin-modal__header">
              <h2>Confirmar Difusión Masiva</h2>
              <button class="admin-modal__close" (click)="closeLaunchConfirm()" aria-label="Cerrar">✕</button>
            </header>
            <div class="admin-modal__body">
              <p>¿Estás seguro de que deseas lanzar la campaña <strong>"{{ campaignToLaunch()?.nombre }}"</strong>?</p>
              <div style="background: color-mix(in srgb, var(--accent) 8%, var(--canvas)); border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent); border-radius: 8px; padding: 12px; margin: 12px 0;">
                <p style="margin: 0 0 6px; font-weight: 700; color: var(--accent);">Efectos del lanzamiento:</p>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.85rem; line-height: 1.4; color: var(--ink);">
                  <li>Se emitirá una notificación a todos los clientes del segmento <strong>{{ campaignToLaunch()?.segmento_objetivo || 'TODOS' }}</strong>.</li>
                  <li>Aparecerá en la <strong>Campana 🔔</strong> de la tienda web de cada usuario.</li>
                  <li>Se enviará notificación Push a sus dispositivos móviles registrados.</li>
                  <li>La campaña pasará a estado <strong>FINALIZADA</strong> y quedará registrada.</li>
                </ul>
              </div>
            </div>
            <footer class="admin-modal__footer" style="display: flex; justify-content: flex-end; gap: 0.75rem;">
              <button type="button" class="button button--secondary" (click)="closeLaunchConfirm()" [disabled]="submitting()">
                Cancelar
              </button>
              <button type="button" class="button button--primary" (click)="executeLaunch()" [disabled]="submitting()">
                {{ submitting() ? 'Difundiendo...' : '🚀 Sí, difundir ahora' }}
              </button>
            </footer>
          </div>
        </div>
      }
    </div>
  `,
})
export class CampaignsAdmin implements OnInit {
  private readonly commerce = inject(CommerceService);
  private readonly fb = inject(FormBuilder);
  private readonly errorService = inject(ApiErrorService);

  readonly campaigns = signal<Campaign[]>([]);
  readonly loading = signal(false);
  readonly submitting = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);

  readonly searchQuery = signal('');
  readonly statusFilter = signal('');

  readonly showCreateModal = signal(false);
  readonly campaignToLaunch = signal<Campaign | null>(null);

  readonly createForm = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(150)]],
    descripcion: ['', [Validators.required, Validators.minLength(5), Validators.maxLength(250)]],
    asunto_email: [''],
    segmento_objetivo: ['TODOS'],
  });

  readonly filteredCampaigns = computed(() => {
    const q = this.searchQuery().toLowerCase().trim();
    const st = this.statusFilter();
    return this.campaigns().filter((c) => {
      const matchQuery =
        !q ||
        c.nombre.toLowerCase().includes(q) ||
        (c.descripcion && c.descripcion.toLowerCase().includes(q));
      const matchStatus = !st || c.estado === st;
      return matchQuery && matchStatus;
    });
  });

  readonly kpis = computed(() => {
    const all = this.campaigns();
    return {
      total: all.length,
      finalizadas: all.filter((c) => c.estado === 'FINALIZADA').length,
      borradores: all.filter((c) => c.estado === 'BORRADOR').length,
      impactoTotal: all.reduce((sum, c) => sum + (c.total_notificaciones || 0), 0),
    };
  });

  ngOnInit(): void {
    this.loadCampaigns();
  }

  loadCampaigns(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.commerce
      .adminCampaigns()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (items) => this.campaigns.set(items || []),
        error: (err) => this.errorMessage.set(this.errorService.message(err, 'No pudimos cargar las campañas.')),
      });
  }

  onSearchInput(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }

  onStatusFilterChange(event: Event): void {
    this.statusFilter.set((event.target as HTMLSelectElement).value);
  }

  openCreateModal(): void {
    this.createForm.reset({
      nombre: '',
      descripcion: '',
      asunto_email: '',
      segmento_objetivo: 'TODOS',
    });
    this.showCreateModal.set(true);
  }

  closeCreateModal(): void {
    this.showCreateModal.set(false);
  }

  submitCreate(): void {
    if (this.createForm.invalid) return;
    this.submitting.set(true);
    this.errorMessage.set(null);

    const val = this.createForm.value;
    const payload: CampaignCreate = {
      nombre: val.nombre!,
      descripcion: val.descripcion!,
      asunto_email: val.asunto_email || null,
      segmento_objetivo: val.segmento_objetivo || 'TODOS',
    };

    this.commerce
      .createCampaign(payload)
      .pipe(finalize(() => this.submitting.set(false)))
      .subscribe({
        next: (created) => {
          this.closeCreateModal();
          this.successMessage.set(`Campaña "${created.nombre}" creada en borrador.`);
          this.loadCampaigns();
        },
        error: (err) => this.errorMessage.set(this.errorService.message(err, 'Error al crear la campaña.')),
      });
  }

  openLaunchConfirm(campaign: Campaign): void {
    this.campaignToLaunch.set(campaign);
  }

  closeLaunchConfirm(): void {
    this.campaignToLaunch.set(null);
  }

  executeLaunch(): void {
    const c = this.campaignToLaunch();
    if (!c) return;
    this.submitting.set(true);
    this.errorMessage.set(null);

    this.commerce
      .launchCampaign(c.id_campania)
      .pipe(finalize(() => this.submitting.set(false)))
      .subscribe({
        next: (res: CampaignLaunchResponse) => {
          this.closeLaunchConfirm();
          this.successMessage.set(res.mensaje);
          this.loadCampaigns();
        },
        error: (err) => this.errorMessage.set(this.errorService.message(err, 'Error al difundir la campaña.')),
      });
  }
}
