import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import {
  PlatformOverview,
  PlatformPayment,
  PlatformPlan,
  PlatformTenant,
  PlatformTenantCreate,
  PlatformTenantUpdate,
} from '../../core/models/platform.model';
import { ApiErrorService } from '../../core/services/api-error.service';
import { PlatformService } from '../../core/services/platform.service';

@Component({
  selector: 'app-platform-overview',
  imports: [RouterLink],
  template: `
    <div class="platform-page">
      <header class="platform-heading">
        <div>
          <p class="eyebrow">Vista general</p>
          <h1>Estado de la plataforma</h1>
          <p>Empresas, capacidad y suscripciones de Zentry en una sola lectura.</p>
        </div>
        <a class="platform-primary" routerLink="/platform/empresas">Ver empresas</a>
      </header>
      @if (error()) {
        <div class="platform-alert" role="alert">{{ error() }}</div>
      }
      @if (loading()) {
        <div class="platform-metric-grid" aria-busy="true">
          @for (item of [1, 2, 3, 4]; track item) {
            <div class="platform-skeleton"></div>
          }
        </div>
      } @else if (overview(); as data) {
        <section class="platform-metric-grid" aria-label="Indicadores de plataforma">
          <article class="platform-metric platform-metric--lead">
            <span>Empresas activas</span><strong>{{ data.tenants_activos }}</strong
            ><small>de {{ data.tenants_total }} registradas</small>
          </article>
          <article class="platform-metric">
            <span>Sucursales activas</span><strong>{{ data.sucursales_activas }}</strong
            ><small>capacidad operativa actual</small>
          </article>
          <article class="platform-metric">
            <span>Por vencer</span><strong>{{ data.suscripciones_por_vencer }}</strong
            ><small>renuevan durante los próximos 7 días</small>
          </article>
          <article class="platform-metric">
            <span>En gracia</span><strong>{{ data.suscripciones_en_gracia }}</strong
            ><small>requieren seguimiento de cobro</small>
          </article>
          <article class="platform-metric">
            <span>Suscripciones suspendidas</span
            ><strong>{{ data.suscripciones_suspendidas }}</strong
            ><small>sin acceso por falta de renovación</small>
          </article>
        </section>
        <section class="platform-ledger">
          <header>
            <div>
              <p class="eyebrow">Directorio reciente</p>
              <h2>Empresas conectadas</h2>
            </div>
            <a routerLink="/platform/empresas">Abrir directorio →</a>
          </header>
          @for (tenant of tenants().slice(0, 5); track tenant.id_tenant) {
            <div class="platform-ledger-row">
              <span class="platform-tenant-mark">{{ tenant.nombre.charAt(0) }}</span>
              <div>
                <strong>{{ tenant.nombre }}</strong
                ><small>/t/{{ tenant.slug }}</small>
              </div>
              <span class="platform-plan">{{ tenant.plan_nombre || 'Sin plan' }}</span
              ><span class="platform-status" [class.is-paused]="tenant.estado !== 'ACTIVO'">{{
                tenant.estado
              }}</span>
            </div>
          } @empty {
            <p class="platform-empty">Aún no existen empresas registradas.</p>
          }
        </section>
      }
    </div>
  `,
})
export class PlatformOverviewPage implements OnInit {
  private readonly platform = inject(PlatformService);
  private readonly errors = inject(ApiErrorService);
  readonly overview = signal<PlatformOverview | null>(null);
  readonly tenants = signal<PlatformTenant[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');

  ngOnInit(): void {
    forkJoin({ overview: this.platform.overview(), tenants: this.platform.tenants() }).subscribe({
      next: ({ overview, tenants }) => {
        this.overview.set(overview);
        this.tenants.set(tenants);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(this.errors.message(error, 'No se pudo cargar la plataforma.'));
        this.loading.set(false);
      },
    });
  }
}

@Component({
  selector: 'app-platform-tenants',
  imports: [DatePipe, RouterLink],
  template: `
    <div class="platform-page">
      <header class="platform-heading">
        <div>
          <p class="eyebrow">Directorio</p>
          <h1>Empresas</h1>
          <p>Identidad, plan y capacidad operativa de cada tenant.</p>
        </div>
        <a class="platform-primary" routerLink="/platform/empresas/nueva">Nueva empresa</a>
      </header>
      @if (error()) {
        <div class="platform-alert" role="alert">{{ error() }}</div>
      }
      <div class="platform-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Empresa</th>
              <th>Estado</th>
              <th>Plan</th>
              <th>Sucursales</th>
              <th>Vencimiento</th>
            </tr>
          </thead>
          <tbody>
            @for (tenant of tenants(); track tenant.id_tenant) {
              <tr>
                <td>
                  <strong
                    ><a [routerLink]="['/platform/empresas', tenant.id_tenant]">{{
                      tenant.nombre
                    }}</a></strong
                  ><small>{{ tenant.slug }}</small>
                </td>
                <td>
                  <span class="platform-status" [class.is-paused]="tenant.estado !== 'ACTIVO'">{{
                    tenant.estado
                  }}</span>
                </td>
                <td>{{ tenant.plan_nombre || 'Sin plan' }}</td>
                <td>{{ tenant.sucursales_activas }}</td>
                <td>
                  {{
                    tenant.fecha_fin ? (tenant.fecha_fin | date: 'dd MMM yyyy') : 'Sin vencimiento'
                  }}
                </td>
              </tr>
            } @empty {
              @if (!loading()) {
                <tr>
                  <td colspan="5" class="platform-empty">No hay empresas registradas.</td>
                </tr>
              }
            }
          </tbody>
        </table>
        @if (loading()) {
          <div class="platform-loading-line">Cargando empresas…</div>
        }
      </div>
    </div>
  `,
})
export class PlatformTenantsPage implements OnInit {
  private readonly platform = inject(PlatformService);
  private readonly errors = inject(ApiErrorService);
  readonly tenants = signal<PlatformTenant[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  ngOnInit(): void {
    this.platform.tenants().subscribe({
      next: (value) => {
        this.tenants.set(value);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(this.errors.message(error, 'No se pudieron cargar las empresas.'));
        this.loading.set(false);
      },
    });
  }
}

@Component({
  selector: 'app-platform-tenant-create',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <div class="platform-page platform-page--form">
      <header class="platform-heading">
        <div>
          <p class="eyebrow">Aprovisionamiento</p>
          <h1>Nueva empresa</h1>
          <p>Crea el espacio comercial, su suscripción y el acceso de su administrador.</p>
        </div>
        <a class="platform-secondary" routerLink="/platform/empresas">Cancelar</a>
      </header>

      @if (error()) {
        <div class="platform-alert" role="alert">{{ error() }}</div>
      }

      <form class="platform-form" [formGroup]="form" (ngSubmit)="submit()">
        <section>
          <header>
            <span>01</span>
            <div>
              <h2>Identidad de la empresa</h2>
              <p>Datos visibles y legales del nuevo tenant.</p>
            </div>
          </header>
          <div class="platform-form-grid">
            <label
              >Nombre comercial<input formControlName="nombre" autocomplete="organization"
            /></label>
            <label
              >Identificador URL<input formControlName="slug" placeholder="mi-empresa"
            /></label>
            <label>Razón social<input formControlName="razon_social" /></label>
            <label>NIT<input formControlName="nit" /></label>
            <label
              >Correo de contacto<input type="email" formControlName="correo_contacto"
            /></label>
            <label>Teléfono de contacto<input formControlName="telefono_contacto" /></label>
            <label>URL del logotipo<input type="url" formControlName="logo_url" /></label>
            <label>Color principal<input type="color" formControlName="color_primario" /></label>
            <label
              >Color de interacción<input type="color" formControlName="color_primario_oscuro"
            /></label>
          </div>
        </section>

        <section>
          <header>
            <span>02</span>
            <div>
              <h2>Suscripción</h2>
              <p>Capacidad inicial y vigencia del servicio.</p>
            </div>
          </header>
          <div class="platform-form-grid">
            <label
              >Plan
              <select formControlName="id_plan">
                <option value="" disabled>Selecciona un plan</option>
                @for (plan of plans(); track plan.id_plan) {
                  <option [value]="plan.id_plan">
                    {{ plan.nombre }} · {{ plan.max_sucursales_activas }} sucursales
                  </option>
                }
              </select>
            </label>
            <label>Vencimiento opcional<input type="date" formControlName="fecha_fin" /></label>
            <label
              >Modalidad
              <select formControlName="modalidad">
                <option value="MENSUAL">Mensual</option>
                <option value="ANUAL">Anual</option>
              </select>
            </label>
          </div>
        </section>

        <section formGroupName="administrador">
          <header>
            <span>03</span>
            <div>
              <h2>Administrador principal</h2>
              <p>Primera persona responsable de operar la empresa.</p>
            </div>
          </header>
          <div class="platform-form-grid">
            <label>Nombres<input formControlName="nombres" autocomplete="given-name" /></label>
            <label>Apellidos<input formControlName="apellidos" autocomplete="family-name" /></label>
            <label
              >Correo de acceso<input type="email" formControlName="correo" autocomplete="email"
            /></label>
            <label>Teléfono<input formControlName="telefono" autocomplete="tel" /></label>
            <label>CI<input formControlName="ci" /></label>
            <label
              >Contraseña inicial<input
                type="password"
                formControlName="password"
                autocomplete="new-password"
            /></label>
          </div>
          <p class="platform-form-note">
            Debe incluir mayúscula, minúscula, número y carácter especial.
          </p>
        </section>

        <footer>
          <p>La empresa y todos sus accesos se guardarán juntos.</p>
          <button class="platform-primary" type="submit" [disabled]="form.invalid || submitting()">
            {{ submitting() ? 'Creando empresa…' : 'Crear empresa' }}
          </button>
        </footer>
      </form>
    </div>
  `,
})
export class PlatformTenantCreatePage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly platform = inject(PlatformService);
  private readonly errors = inject(ApiErrorService);
  private readonly router = inject(Router);
  readonly plans = signal<PlatformPlan[]>([]);
  readonly error = signal('');
  readonly submitting = signal(false);
  readonly form = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.minLength(2)]],
    slug: ['', [Validators.required, Validators.pattern(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)]],
    razon_social: [''],
    nit: [''],
    correo_contacto: ['', Validators.email],
    telefono_contacto: [''],
    logo_url: [''],
    color_primario: ['#064FE8', [Validators.required, Validators.pattern(/^#[0-9A-Fa-f]{6}$/)]],
    color_primario_oscuro: [
      '#0039B8',
      [Validators.required, Validators.pattern(/^#[0-9A-Fa-f]{6}$/)],
    ],
    id_plan: ['', Validators.required],
    modalidad: ['MENSUAL' as const, Validators.required],
    fecha_fin: [''],
    administrador: this.fb.nonNullable.group({
      nombres: ['', Validators.required],
      apellidos: ['', Validators.required],
      correo: ['', [Validators.required, Validators.email]],
      telefono: [''],
      ci: [''],
      password: ['', [Validators.required, Validators.minLength(8)]],
    }),
  });

  ngOnInit(): void {
    this.platform.plans().subscribe({
      next: (plans) => this.plans.set(plans.filter((plan) => plan.activo)),
      error: (error) =>
        this.error.set(this.errors.message(error, 'No se pudieron cargar los planes.')),
    });
  }

  submit(): void {
    if (this.form.invalid || this.submitting()) return;
    const value = this.form.getRawValue();
    const optional = (text: string): string | null => text.trim() || null;
    const payload: PlatformTenantCreate = {
      nombre: value.nombre.trim(),
      slug: value.slug.trim().toLowerCase(),
      razon_social: optional(value.razon_social),
      nit: optional(value.nit),
      correo_contacto: optional(value.correo_contacto),
      telefono_contacto: optional(value.telefono_contacto),
      logo_url: optional(value.logo_url),
      color_primario: value.color_primario,
      color_primario_oscuro: value.color_primario_oscuro,
      id_plan: Number(value.id_plan),
      modalidad: value.modalidad,
      fecha_fin: optional(value.fecha_fin),
      administrador: {
        nombres: value.administrador.nombres.trim(),
        apellidos: value.administrador.apellidos.trim(),
        correo: value.administrador.correo.trim(),
        telefono: optional(value.administrador.telefono),
        ci: optional(value.administrador.ci),
        password: value.administrador.password,
      },
    };
    this.error.set('');
    this.submitting.set(true);
    this.platform.createTenant(payload).subscribe({
      next: () => void this.router.navigate(['/platform/empresas']),
      error: (error) => {
        this.error.set(this.errors.message(error, 'No se pudo crear la empresa.'));
        this.submitting.set(false);
      },
    });
  }
}

@Component({
  selector: 'app-platform-tenant-detail',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <div class="platform-page platform-page--form">
      @if (loading()) {
        <div class="platform-loading-line">Cargando empresa…</div>
      } @else if (tenant(); as company) {
        <header class="platform-heading platform-heading--detail">
          <div>
            <a class="platform-back-link" routerLink="/platform/empresas">← Empresas</a>
            <p class="eyebrow">{{ company.slug }}</p>
            <h1>{{ company.nombre }}</h1>
            <p>
              {{ company.plan_nombre || 'Sin plan' }} · {{ company.sucursales_activas }} sucursales
            </p>
          </div>
          <div class="platform-heading-actions">
            <span class="platform-status" [class.is-paused]="company.estado !== 'ACTIVO'">{{
              company.estado
            }}</span>
            <button
              class="platform-danger"
              type="button"
              (click)="confirmingStatus.set(true)"
              [disabled]="changingStatus()"
            >
              {{ company.estado === 'ACTIVO' ? 'Suspender empresa' : 'Reactivar empresa' }}
            </button>
          </div>
        </header>

        @if (error()) {
          <div class="platform-alert" role="alert">{{ error() }}</div>
        }
        @if (success()) {
          <div class="platform-success" role="status">{{ success() }}</div>
        }
        @if (confirmingStatus()) {
          <div class="platform-confirm" role="alertdialog" aria-label="Confirmar cambio de estado">
            <div>
              <strong>Confirma el cambio de estado</strong>
              <p>
                {{
                  company.estado === 'ACTIVO'
                    ? 'Los usuarios de esta empresa perderán el acceso inmediatamente.'
                    : 'Los usuarios podrán volver a ingresar a la empresa.'
                }}
              </p>
            </div>
            <button type="button" class="platform-secondary" (click)="confirmingStatus.set(false)">
              Cancelar
            </button>
            <button type="button" class="platform-danger" (click)="toggleStatus()">
              Confirmar
            </button>
          </div>
        }

        <section class="platform-detail-metrics">
          <div>
            <span>Usuarios</span><strong>{{ company.usuarios || 0 }}</strong>
          </div>
          <div>
            <span>Administradores</span><strong>{{ company.administradores || 0 }}</strong>
          </div>
          <div>
            <span>Sucursales activas</span><strong>{{ company.sucursales_activas }}</strong>
          </div>
          <div>
            <span>Usuarios internos</span
            ><strong
              >{{ company.usuarios_internos || 0 }} /
              {{ company.max_usuarios_internos || '—' }}</strong
            >
          </div>
          <div>
            <span>Productos activos</span
            ><strong
              >{{ company.productos_activos || 0 }} /
              {{ company.max_productos_activos || '—' }}</strong
            >
          </div>
        </section>

        <form class="platform-form" [formGroup]="form" (ngSubmit)="save()">
          <section>
            <header>
              <span>01</span>
              <div>
                <h2>Información comercial</h2>
                <p>Identidad y canales de contacto de la empresa.</p>
              </div>
            </header>
            <div class="platform-form-grid">
              <label>Nombre comercial<input formControlName="nombre" /></label>
              <label>Razón social<input formControlName="razon_social" /></label>
              <label>NIT<input formControlName="nit" /></label>
              <label
                >Correo de contacto<input type="email" formControlName="correo_contacto"
              /></label>
              <label>Teléfono de contacto<input formControlName="telefono_contacto" /></label>
              <label>URL del logotipo<input type="url" formControlName="logo_url" /></label>
              <label>Color principal<input type="color" formControlName="color_primario" /></label>
              <label
                >Color de interacción<input type="color" formControlName="color_primario_oscuro"
              /></label>
            </div>
          </section>
          <section>
            <header>
              <span>02</span>
              <div>
                <h2>Plan y vigencia</h2>
                <p>Capacidad contratada y fecha de vencimiento.</p>
              </div>
            </header>
            <div class="platform-form-grid">
              <label
                >Plan
                <select formControlName="id_plan">
                  @for (plan of plans(); track plan.id_plan) {
                    <option [value]="plan.id_plan">
                      {{ plan.nombre }} · {{ plan.max_sucursales_activas }} sucursales
                    </option>
                  }
                </select>
              </label>
              <label>Vencimiento opcional<input type="date" formControlName="fecha_fin" /></label>
              <label
                >Modalidad
                <select formControlName="modalidad">
                  <option value="MENSUAL">Mensual</option>
                  <option value="ANUAL">Anual</option>
                </select>
              </label>
            </div>
          </section>
          <footer>
            <p>Los cambios afectan el próximo acceso de esta empresa.</p>
            <button class="platform-primary" type="submit" [disabled]="form.invalid || saving()">
              {{ saving() ? 'Guardando…' : 'Guardar cambios' }}
            </button>
          </footer>
        </form>

        <form class="platform-form" [formGroup]="paymentForm" (ngSubmit)="registerPayment()">
          <section>
            <header>
              <span>03</span>
              <div>
                <h2>Registrar pago</h2>
                <p>Confirma el cobro y extiende automáticamente la suscripción.</p>
              </div>
            </header>
            <div class="platform-form-grid">
              <label
                >Periodo pagado
                <select formControlName="modalidad">
                  <option value="MENSUAL">Mensual</option>
                  <option value="ANUAL">Anual</option>
                </select>
              </label>
              <label
                >Método
                <select formControlName="metodo_pago">
                  <option value="TRANSFERENCIA">Transferencia</option>
                  <option value="QR">QR</option>
                  <option value="EFECTIVO">Efectivo</option>
                  <option value="OTRO">Otro</option>
                </select>
              </label>
              <label>Referencia<input formControlName="referencia" /></label>
              <label>Fecha del pago<input type="date" formControlName="fecha_pago" /></label>
            </div>
          </section>
          <footer>
            <p>
              Importe: Bs
              {{
                paymentForm.controls.modalidad.value === 'ANUAL'
                  ? selectedPlan()?.precio_anual
                  : selectedPlan()?.precio_mensual
              }}
            </p>
            <button
              class="platform-primary"
              type="submit"
              [disabled]="paymentForm.invalid || paying()"
            >
              {{ paying() ? 'Registrando…' : 'Confirmar pago' }}
            </button>
          </footer>
        </form>

        @if (payments().length) {
          <section class="platform-payment-history">
            <h2>Historial de pagos</h2>
            @for (payment of payments(); track payment.id_payment) {
              <div>
                <strong>Bs {{ payment.importe }}</strong>
                <span>{{ payment.fecha_pago }} · {{ payment.metodo_pago }}</span>
                <small>{{ payment.referencia || 'Sin referencia' }}</small>
              </div>
            }
          </section>
        }
      } @else if (error()) {
        <div class="platform-alert" role="alert">{{ error() }}</div>
      }
    </div>
  `,
})
export class PlatformTenantDetailPage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly platform = inject(PlatformService);
  private readonly errors = inject(ApiErrorService);
  private readonly route = inject(ActivatedRoute);
  readonly tenant = signal<PlatformTenant | null>(null);
  readonly plans = signal<PlatformPlan[]>([]);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly changingStatus = signal(false);
  readonly confirmingStatus = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  readonly payments = signal<PlatformPayment[]>([]);
  readonly paying = signal(false);
  readonly form = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.minLength(2)]],
    razon_social: [''],
    nit: [''],
    correo_contacto: ['', Validators.email],
    telefono_contacto: [''],
    logo_url: [''],
    color_primario: ['#064FE8', [Validators.required, Validators.pattern(/^#[0-9A-Fa-f]{6}$/)]],
    color_primario_oscuro: [
      '#0039B8',
      [Validators.required, Validators.pattern(/^#[0-9A-Fa-f]{6}$/)],
    ],
    id_plan: ['', Validators.required],
    modalidad: ['MENSUAL' as 'MENSUAL' | 'ANUAL', Validators.required],
    fecha_fin: [''],
  });
  readonly paymentForm = this.fb.nonNullable.group({
    modalidad: ['MENSUAL' as 'MENSUAL' | 'ANUAL', Validators.required],
    metodo_pago: [
      'TRANSFERENCIA' as 'TRANSFERENCIA' | 'QR' | 'EFECTIVO' | 'OTRO',
      Validators.required,
    ],
    referencia: [''],
    fecha_pago: [new Date().toISOString().slice(0, 10), Validators.required],
  });
  readonly selectedPlan = () =>
    this.plans().find((plan) => plan.id_plan === Number(this.form.controls.id_plan.value));
  private tenantId = 0;

  ngOnInit(): void {
    this.tenantId = Number(this.route.snapshot.paramMap.get('id'));
    forkJoin({
      tenant: this.platform.tenant(this.tenantId),
      plans: this.platform.plans(),
      payments: this.platform.payments(this.tenantId),
    }).subscribe({
      next: ({ tenant, plans, payments }) => {
        this.tenant.set(tenant);
        this.plans.set(plans.filter((plan) => plan.activo));
        this.payments.set(payments);
        this.form.setValue({
          nombre: tenant.nombre,
          razon_social: tenant.razon_social || '',
          nit: tenant.nit || '',
          correo_contacto: tenant.correo_contacto || '',
          telefono_contacto: tenant.telefono_contacto || '',
          logo_url: tenant.logo_url || '',
          color_primario: tenant.color_primario || '#064FE8',
          color_primario_oscuro: tenant.color_primario_oscuro || '#0039B8',
          id_plan: String(tenant.id_plan || ''),
          modalidad: tenant.modalidad || 'MENSUAL',
          fecha_fin: tenant.fecha_fin || '',
        });
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(this.errors.message(error, 'No se pudo cargar la empresa.'));
        this.loading.set(false);
      },
    });
  }

  save(): void {
    if (this.form.invalid || this.saving()) return;
    const value = this.form.getRawValue();
    const optional = (text: string): string | null => text.trim() || null;
    const payload: PlatformTenantUpdate = {
      nombre: value.nombre.trim(),
      razon_social: optional(value.razon_social),
      nit: optional(value.nit),
      correo_contacto: optional(value.correo_contacto),
      telefono_contacto: optional(value.telefono_contacto),
      logo_url: optional(value.logo_url),
      color_primario: value.color_primario,
      color_primario_oscuro: value.color_primario_oscuro,
      id_plan: Number(value.id_plan),
      modalidad: value.modalidad,
      fecha_fin: optional(value.fecha_fin),
    };
    this.saving.set(true);
    this.error.set('');
    this.success.set('');
    this.platform.updateTenant(this.tenantId, payload).subscribe({
      next: (tenant) => {
        this.tenant.set(tenant);
        this.success.set('Cambios guardados correctamente.');
        this.saving.set(false);
      },
      error: (error) => {
        this.error.set(this.errors.message(error, 'No se pudieron guardar los cambios.'));
        this.saving.set(false);
      },
    });
  }

  registerPayment(): void {
    if (this.paymentForm.invalid || this.paying()) return;
    const value = this.paymentForm.getRawValue();
    this.paying.set(true);
    this.error.set('');
    this.success.set('');
    this.platform
      .registerPayment(this.tenantId, {
        ...value,
        referencia: value.referencia.trim() || null,
      })
      .subscribe({
        next: (tenant) => {
          this.tenant.set(tenant);
          this.success.set('Pago registrado y suscripción renovada.');
          this.platform
            .payments(this.tenantId)
            .subscribe((payments) => this.payments.set(payments));
          this.paying.set(false);
        },
        error: (error) => {
          this.error.set(this.errors.message(error, 'No se pudo registrar el pago.'));
          this.paying.set(false);
        },
      });
  }

  toggleStatus(): void {
    const current = this.tenant();
    if (!current || this.changingStatus()) return;
    const estado = current.estado === 'ACTIVO' ? 'SUSPENDIDO' : 'ACTIVO';
    this.changingStatus.set(true);
    this.error.set('');
    this.success.set('');
    this.platform.updateTenantStatus(this.tenantId, estado).subscribe({
      next: (tenant) => {
        this.tenant.set(tenant);
        this.confirmingStatus.set(false);
        this.success.set(estado === 'ACTIVO' ? 'Empresa reactivada.' : 'Empresa suspendida.');
        this.changingStatus.set(false);
      },
      error: (error) => {
        this.error.set(this.errors.message(error, 'No se pudo cambiar el estado.'));
        this.changingStatus.set(false);
      },
    });
  }
}

@Component({
  selector: 'app-platform-plans',
  template: `
    <div class="platform-page">
      <header class="platform-heading">
        <div>
          <p class="eyebrow">Capacidad comercial</p>
          <h1>Planes</h1>
          <p>Reglas vigentes que Zentry aplica a cada empresa.</p>
        </div>
      </header>
      @if (error()) {
        <div class="platform-alert" role="alert">{{ error() }}</div>
      }
      <section class="platform-plan-grid">
        @for (plan of plans(); track plan.id_plan) {
          <article>
            <div class="platform-plan-code">{{ plan.codigo }}</div>
            <h2>{{ plan.nombre }}</h2>
            <strong>{{ plan.max_sucursales_activas }}</strong
            ><span>sucursales activas</span>
            <p>Bs {{ plan.precio_mensual }} mensual · Bs {{ plan.precio_anual }} anual</p>
            <ul>
              <li>{{ plan.max_usuarios_internos }} usuarios internos</li>
              <li>{{ plan.max_productos_activos }} productos activos</li>
              <li>{{ plan.almacenamiento_mb / 1024 }} GB de almacenamiento</li>
              <li [class.off]="!plan.permite_reportes_convencionales">
                Reportes convencionales
              </li>
              <li [class.off]="!plan.permite_reportes_ia">Reportes con IA</li>
              <li [class.off]="!plan.permite_offline">Operación offline</li>
            </ul>
            <small>{{ plan.activo ? 'Disponible para asignación' : 'Plan inactivo' }}</small>
          </article>
        }
      </section>
    </div>
  `,
})
export class PlatformPlansPage implements OnInit {
  private readonly platform = inject(PlatformService);
  private readonly errors = inject(ApiErrorService);
  readonly plans = signal<PlatformPlan[]>([]);
  readonly error = signal('');
  ngOnInit(): void {
    this.platform.plans().subscribe({
      next: (value) => this.plans.set(value),
      error: (error) =>
        this.error.set(this.errors.message(error, 'No se pudieron cargar los planes.')),
    });
  }
}
