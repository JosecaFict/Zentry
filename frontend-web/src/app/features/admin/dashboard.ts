import { CommonModule, DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { Branch } from '../../core/models/catalog.model';
import {
  AdminDashboardSummary,
  DashboardBranchShare,
  DashboardDailyRevenue,
} from '../../core/models/commerce.model';
import { CatalogService } from '../../core/services/catalog.service';
import { CommerceService } from '../../core/services/commerce.service';
import { BolivianosPipe } from '../../shared/pipes/bolivianos.pipe';
import { availableAdminModules } from './admin-navigation';

interface ChartPoint {
  x: number;
  y: number;
  data: DashboardDailyRevenue;
}

interface DonutSegment {
  branch: DashboardBranchShare;
  color: string;
  dashArray: string;
  dashOffset: number;
}

@Component({
  selector: 'app-admin-dashboard',
  imports: [CommonModule, RouterLink, FormsModule, BolivianosPipe, DatePipe, DecimalPipe],
  template: `
    <div class="admin-page">
      <!-- Encabezado y Barra de Herramientas -->
      <header class="admin-page-heading">
        <div>
          <p class="eyebrow">Panel ejecutivo</p>
          <h1>Centro de Comando</h1>
          <p>
            Monitoreo en tiempo real de facturación, flujo de pedidos en tienda y probador virtual.
          </p>
        </div>

        <div class="dashboard-toolbar">
          <label class="sr-only" for="branchFilter">Filtrar por sucursal</label>
          <select
            id="branchFilter"
            class="dashboard-branch-select"
            [value]="selectedBranchId() ?? ''"
            (change)="onBranchChange($any($event.target).value)"
            [disabled]="loading()"
          >
            <option value="">Todas las sucursales (Global)</option>
            @for (b of branches(); track b.id_sucursal) {
              <option [value]="b.id_sucursal">{{ b.nombre }}</option>
            }
          </select>

          <button
            type="button"
            class="dashboard-refresh-btn"
            [class.is-spinning]="loading()"
            (click)="loadSummary()"
            [disabled]="loading()"
            title="Actualizar métricas"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <polyline points="23 4 23 10 17 10"></polyline>
              <polyline points="1 20 1 14 7 14"></polyline>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
            </svg>
            <span>Actualizar</span>
          </button>

          <span class="dashboard-sync-tag">
            Sincronizado: {{ lastUpdated() | date: 'shortTime' }}
          </span>
        </div>
      </header>

      @if (error()) {
        <div class="admin-notice admin-notice--error" role="alert">
          <span>{{ error() }}</span>
        </div>
      }

      @if (loading() && !summary()) {
        <div class="dashboard-loading-skeleton" aria-busy="true" aria-label="Cargando métricas...">
          <div class="skeleton-bar"></div>
          <div class="skeleton-bar"></div>
        </div>
      }

      @if (summary(); as data) {
        <!-- Tarjetas de KPIs Ejecutivos -->
        <section class="dashboard-kpi-grid" aria-label="Métricas Principales">
          <!-- KPI 1: Facturación del Mes -->
          <article class="dashboard-kpi-card">
            <div class="kpi-head">
              <span class="kpi-label">Ventas del Mes</span>
              <div class="kpi-icon kpi-icon--sales" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="1" x2="12" y2="23"></line>
                  <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
                </svg>
              </div>
            </div>
            <div class="kpi-metric">
              {{ data.kpis.ventas_mes_total | bolivianos }}
            </div>
            <div class="kpi-footer">
              <span
                class="kpi-chip"
                [class.kpi-chip--positive]="data.kpis.ventas_crecimiento_pct >= 0"
                [class.kpi-chip--negative]="data.kpis.ventas_crecimiento_pct < 0"
              >
                {{ data.kpis.ventas_crecimiento_pct >= 0 ? '▲ +' : '▼ '
                }}{{ data.kpis.ventas_crecimiento_pct | number: '1.1-1' }}%
              </span>
              <span>vs. mes anterior</span>
            </div>
          </article>

          <!-- KPI 2: Pedidos Pendientes -->
          <a routerLink="/admin/pedidos" class="dashboard-kpi-card" title="Ver pedidos pendientes">
            <div class="kpi-head">
              <span class="kpi-label">Pedidos Pendientes</span>
              <div class="kpi-icon kpi-icon--orders" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path>
                  <line x1="3" y1="6" x2="21" y2="6"></line>
                  <path d="M16 10a4 4 0 0 1-8 0"></path>
                </svg>
              </div>
            </div>
            <div class="kpi-metric">
              {{ data.kpis.pedidos_pendientes }}
            </div>
            <div class="kpi-footer">
              <span class="kpi-chip kpi-chip--warning">Por despachar / retirar</span>
              <span>Atención requerida</span>
            </div>
          </a>

          <!-- KPI 3: Reservas Probador Hoy -->
          <a routerLink="/admin/reservas" class="dashboard-kpi-card" title="Ver agenda de probador">
            <div class="kpi-head">
              <span class="kpi-label">Reservas Probador</span>
              <div class="kpi-icon kpi-icon--reservations" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                  <line x1="16" y1="2" x2="16" y2="6"></line>
                  <line x1="8" y1="2" x2="8" y2="6"></line>
                  <line x1="3" y1="10" x2="21" y2="10"></line>
                </svg>
              </div>
            </div>
            <div class="kpi-metric">
              {{ data.kpis.reservas_hoy }}
            </div>
            <div class="kpi-footer">
              <span class="kpi-chip kpi-chip--indigo">Citas agendadas hoy</span>
              <span>Probador activo</span>
            </div>
          </a>

          <!-- KPI 4: Alertas de Stock Crítico -->
          <a
            routerLink="/admin/inventario"
            class="dashboard-kpi-card"
            title="Ver inventario con stock crítico"
          >
            <div class="kpi-head">
              <span class="kpi-label">Stock Crítico</span>
              <div class="kpi-icon kpi-icon--stock" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path
                    d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
                  ></path>
                  <line x1="12" y1="9" x2="12" y2="13"></line>
                  <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
              </div>
            </div>
            <div class="kpi-metric">
              {{ data.kpis.alertas_stock_critico }}
            </div>
            <div class="kpi-footer">
              <span class="kpi-chip kpi-chip--critical">Stock disponible ≤ 3 u.</span>
              <span>Alerta reposición</span>
            </div>
          </a>
        </section>

        <!-- Fila de Visualizaciones Gráficas Nativas SVG -->
        <div class="dashboard-visuals-grid">
          <!-- Curva Semanal -->
          <section class="dashboard-panel" aria-labelledby="weeklyTrendTitle">
            <header class="panel-header">
              <div class="panel-titles">
                <h2 id="weeklyTrendTitle">Tendencia de Facturación Semanal</h2>
                <p>Evolución diaria de ventas completadas en los últimos 7 días.</p>
              </div>
              @if (hoveredPoint(); as hp) {
                <div class="trend-badge trend-badge--indigo">
                  {{ hp.data.dia_nombre }} {{ hp.data.fecha | date: 'dd/MM' }}:
                  <strong>{{ hp.data.total | bolivianos }}</strong>
                </div>
              }
            </header>

            <div class="chart-container-svg">
              <svg viewBox="0 0 700 230" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="weeklyAreaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#064fe8" stop-opacity="0.32" />
                    <stop offset="100%" stop-color="#064fe8" stop-opacity="0.0" />
                  </linearGradient>
                </defs>

                <!-- Líneas Guía Horizontales -->
                @for (g of yAxisGrid(); track g.y) {
                  <line x1="55" [attr.y1]="g.y" x2="665" [attr.y2]="g.y" class="grid-line" />
                  <text x="50" [attr.y]="g.y + 4" text-anchor="end" class="grid-label">
                    {{ g.val >= 1000 ? (g.val / 1000 | number: '1.0-1') + 'k' : g.val }}
                  </text>
                }

                <!-- Área con Degradado Suave -->
                @if (weeklyAreaPath()) {
                  <path [attr.d]="weeklyAreaPath()" class="chart-area-fill" />
                }

                <!-- Curva Bezier -->
                @if (weeklyLinePath()) {
                  <path [attr.d]="weeklyLinePath()" class="chart-curve-stroke" />
                }

                <!-- Puntos Interactivos por Día -->
                @for (pt of weeklyPoints(); track pt.data.fecha; let idx = $index) {
                  <!-- Barra de interacción invisible para facilitar hover -->
                  <rect
                    [attr.x]="pt.x - 30"
                    y="10"
                    width="60"
                    height="190"
                    fill="transparent"
                    (mouseenter)="onHoverPoint(idx)"
                    (mouseleave)="onHoverPoint(null)"
                    style="cursor: pointer;"
                  />

                  <!-- Punto en la curva -->
                  <circle
                    [attr.cx]="pt.x"
                    [attr.cy]="pt.y"
                    r="4.5"
                    class="chart-interactive-dot"
                    [class.is-active]="activeDayIndex() === idx"
                    (mouseenter)="onHoverPoint(idx)"
                    (mouseleave)="onHoverPoint(null)"
                  />

                  <!-- Etiqueta del Día -->
                  <text [attr.x]="pt.x" y="202" class="day-label">{{ pt.data.dia_nombre }}</text>
                  <text [attr.x]="pt.x" y="217" class="day-sub">
                    {{ pt.data.fecha | date: 'dd/MM' }}
                  </text>
                }
              </svg>
            </div>
          </section>

          <!-- Dona de Participación por Sucursal -->
          <section class="dashboard-panel" aria-labelledby="branchShareTitle">
            <header class="panel-header">
              <div class="panel-titles">
                <h2 id="branchShareTitle">Ventas por Sucursal</h2>
                <p>Participación relativa sobre la facturación del periodo.</p>
              </div>
            </header>

            <div class="donut-wrap">
              <div class="donut-svg-box">
                <svg viewBox="0 0 200 200">
                  <!-- Pista de Fondo -->
                  <circle
                    cx="100"
                    cy="100"
                    r="65"
                    fill="none"
                    stroke="#f1f5f9"
                    stroke-width="18"
                  />

                  <!-- Segmentos de Sucursal -->
                  @for (seg of donutSegments(); track seg.branch.id_sucursal) {
                    <circle
                      cx="100"
                      cy="100"
                      r="65"
                      fill="none"
                      [attr.stroke]="seg.color"
                      stroke-width="18"
                      [attr.stroke-dasharray]="seg.dashArray"
                      [attr.stroke-dashoffset]="seg.dashOffset"
                      class="donut-segment"
                    />
                  }
                </svg>

                <div class="donut-center-info">
                  <span class="donut-center-title">Total</span>
                  <span class="donut-center-val">{{ totalBranchSales() | bolivianos }}</span>
                </div>
              </div>

              <!-- Leyenda Detallada de Sucursales -->
              <div class="donut-legend-list">
                @for (seg of donutSegments(); track seg.branch.id_sucursal) {
                  <div class="donut-legend-item">
                    <div class="legend-left">
                      <span
                        class="legend-color-dot"
                        [style.backgroundColor]="seg.color"
                        aria-hidden="true"
                      ></span>
                      <span class="legend-name">{{ seg.branch.nombre }}</span>
                    </div>
                    <div class="legend-right">
                      <span class="legend-pct">{{ seg.branch.porcentaje }}%</span>
                      <span class="legend-total">{{ seg.branch.total | bolivianos }}</span>
                    </div>
                  </div>
                }
                @if (donutSegments().length === 0) {
                  <p class="dashboard-empty-note">Sin transacciones registradas este mes.</p>
                }
              </div>
            </div>
          </section>
        </div>

        <!-- Fila de Feeds Accionables -->
        <div class="dashboard-feeds-grid">
          <!-- Feed de Pedidos Urgentes -->
          <section class="dashboard-panel" aria-labelledby="urgentOrdersTitle">
            <header class="panel-header">
              <div class="panel-titles">
                <h2 id="urgentOrdersTitle">Pedidos Urgentes por Despachar</h2>
                <p>Órdenes pagadas o en camino que requieren acción operativa inmediata.</p>
              </div>
              <a routerLink="/admin/pedidos" class="panel-link">Ver todos los pedidos →</a>
            </header>

            @if (data.pedidos_urgentes.length > 0) {
              <div class="table-responsive">
                <table class="orders-mini-table">
                  <thead>
                    <tr>
                      <th>Pedido</th>
                      <th>Cliente</th>
                      <th>Entrega</th>
                      <th>Estado</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (order of data.pedidos_urgentes; track order.id_pedido) {
                      <tr>
                        <td>
                          <a
                            routerLink="/admin/pedidos"
                            class="order-id-badge"
                            title="Ver en pedidos"
                          >
                            #{{ order.id_pedido }}
                          </a>
                        </td>
                        <td class="client-name-cell">{{ order.cliente_nombre }}</td>
                        <td>
                          <span class="delivery-badge">
                            @if (order.tipo_entrega === 'ENVIO_DOMICILIO') {
                              <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2"
                              >
                                <rect x="1" y="3" width="15" height="13"></rect>
                                <polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon>
                                <circle cx="5.5" cy="18.5" r="2.5"></circle>
                                <circle cx="18.5" cy="18.5" r="2.5"></circle>
                              </svg>
                            } @else {
                              <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2"
                              >
                                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                                <polyline points="9 22 9 12 15 12 15 22"></polyline>
                              </svg>
                            }
                            {{ deliveryLabel(order.tipo_entrega) }}
                          </span>
                        </td>
                        <td>
                          <span class="status-pill" [class]="orderStatusClass(order.estado)">
                            {{ orderStatusLabel(order.estado) }}
                          </span>
                        </td>
                        <td class="order-total-cell">{{ order.total | bolivianos }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            } @else {
              <div class="dashboard-empty-note">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <path d="M8 12l2 2 4-4"></path>
                </svg>
                <p>Todos los pedidos han sido despachados exitosamente.</p>
              </div>
            }
          </section>

          <!-- Feed de Top 5 Prendas Más Vendidas -->
          <section class="dashboard-panel" aria-labelledby="topProductsTitle">
            <header class="panel-header">
              <div class="panel-titles">
                <h2 id="topProductsTitle">Top Prendas Más Vendidas</h2>
                <p>Prendas líderes en unidades adquiridas en la tienda.</p>
              </div>
              <a routerLink="/admin/productos" class="panel-link">Ver catálogo →</a>
            </header>

            @if (data.top_productos.length > 0) {
              <div class="top-products-list">
                @for (prod of data.top_productos; track prod.id_producto; let idx = $index) {
                  <article class="top-product-item">
                    <div class="product-left-block">
                      <span class="rank-number" [class]="rankClass(idx + 1)">
                        #{{ idx + 1 }}
                      </span>

                      <div class="product-thumb-box">
                        @if (prod.imagen_url) {
                          <img
                            [src]="prod.imagen_url"
                            [alt]="prod.nombre"
                            loading="lazy"
                            (error)="onImgError($event)"
                          />
                        } @else {
                          <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.5"
                          >
                            <path
                              d="M20.38 3.46L16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z"
                            ></path>
                          </svg>
                        }
                      </div>

                      <div class="product-meta">
                        <h3 class="product-name" [title]="prod.nombre">{{ prod.nombre }}</h3>
                        <p class="product-sub">{{ prod.categoria }} · {{ prod.marca }}</p>
                      </div>
                    </div>

                    <div class="product-right-block">
                      <span class="product-units-pill"> {{ prod.unidades_vendidas }} u. </span>
                      <div class="product-revenue">
                        {{ prod.total_recaudado | bolivianos }}
                      </div>
                    </div>
                  </article>
                }
              </div>
            } @else {
              <div class="dashboard-empty-note">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                  <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
                </svg>
                <p>No se registran ventas para los filtros seleccionados.</p>
              </div>
            }
          </section>
        </div>
      }

      <!-- Accesos Rápidos Operativos -->
      <section class="admin-quick">
        <header>
          <h2>Accesos Rápidos</h2>
          <p>Módulos operativos habilitados según tus permisos de acceso.</p>
        </header>
        <div class="admin-link-grid">
          @for (item of quickLinks(); track item.path) {
            <a [routerLink]="item.path">
              <span>{{ item.label }}</span>
              <small>Abrir módulo →</small>
            </a>
          }
        </div>
      </section>
    </div>
  `,
})
/** [CU-16] Dashboard Comercial y Métricas de Rendimiento */
export class AdminDashboard implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly commerce = inject(CommerceService);
  private readonly catalog = inject(CatalogService);

  readonly user = this.auth.currentUser;
  readonly branches = signal<Branch[]>([]);
  readonly selectedBranchId = signal<number | null>(null);

  readonly summary = signal<AdminDashboardSummary | null>(null);
  readonly loading = signal<boolean>(true);
  readonly error = signal<string | null>(null);
  readonly lastUpdated = signal<Date>(new Date());
  readonly activeDayIndex = signal<number | null>(null);

  readonly availableModules = computed(() => availableAdminModules(this.user()?.permisos ?? []));
  readonly quickLinks = computed(() => this.availableModules().slice(0, 6));

  readonly branchColors = [
    '#064fe8', // Cobalt Royal
    '#6366f1', // Indigo Vivid
    '#0ea5e9', // Sky Cyan
    '#10b981', // Emerald
    '#f59e0b', // Amber
    '#ec4899', // Rose
    '#8b5cf6', // Violet
  ];

  readonly weeklyPoints = computed<ChartPoint[]>(() => {
    const trend = this.summary()?.tendencia_semanal ?? [];
    if (!trend.length) return [];
    const totals = trend.map((d) => Number(d.total) || 0);
    const maxVal = Math.max(...totals, 100) * 1.18; // 18% margen superior
    const count = trend.length;
    const left = 70;
    const right = 665;
    const bottom = 180;
    const usableWidth = right - left;
    const usableHeight = 150;

    return trend.map((day, i) => {
      const x = left + (count > 1 ? (i * usableWidth) / (count - 1) : usableWidth / 2);
      const val = Number(day.total) || 0;
      const y = bottom - (val / maxVal) * usableHeight;
      return { x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10, data: day };
    });
  });

  readonly weeklyLinePath = computed<string>(() => {
    const pts = this.weeklyPoints();
    if (pts.length < 2) return pts.length === 1 ? `M ${pts[0].x},${pts[0].y}` : '';
    let d = `M ${pts[0].x},${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i];
      const p1 = pts[i + 1];
      const dx = (p1.x - p0.x) / 2;
      const cpx1 = Math.round((p0.x + dx) * 10) / 10;
      const cpy1 = p0.y;
      const cpx2 = Math.round((p0.x + dx) * 10) / 10;
      const cpy2 = p1.y;
      d += ` C ${cpx1},${cpy1} ${cpx2},${cpy2} ${p1.x},${p1.y}`;
    }
    return d;
  });

  readonly weeklyAreaPath = computed<string>(() => {
    const pts = this.weeklyPoints();
    if (pts.length < 2) return '';
    const line = this.weeklyLinePath();
    const first = pts[0];
    const last = pts[pts.length - 1];
    return `${line} L ${last.x},185 L ${first.x},185 Z`;
  });

  readonly yAxisGrid = computed(() => {
    const trend = this.summary()?.tendencia_semanal ?? [];
    const totals = trend.map((d) => Number(d.total) || 0);
    const maxVal = Math.max(...totals, 100) * 1.18;
    return [
      { y: 30, val: Math.round(maxVal) },
      { y: 80, val: Math.round((maxVal * 2) / 3) },
      { y: 130, val: Math.round(maxVal / 3) },
      { y: 180, val: 0 },
    ];
  });

  readonly totalBranchSales = computed(() => {
    const shares = this.summary()?.ventas_por_sucursal ?? [];
    return shares.reduce((sum, b) => sum + (Number(b.total) || 0), 0);
  });

  readonly donutSegments = computed<DonutSegment[]>(() => {
    const shares = this.summary()?.ventas_por_sucursal ?? [];
    if (!shares.length) return [];
    const r = 65;
    const circumference = 2 * Math.PI * r; // ~408.407
    let cumulative = 0;

    return shares.map((b, idx) => {
      const pct = b.porcentaje;
      const dashLength = (pct / 100) * circumference;
      const dashArray = `${dashLength} ${circumference - dashLength}`;
      const dashOffset = -cumulative;
      cumulative += dashLength;
      const color = this.branchColors[idx % this.branchColors.length];
      return {
        branch: b,
        color,
        dashArray,
        dashOffset,
      };
    });
  });

  readonly hoveredPoint = computed(() => {
    const idx = this.activeDayIndex();
    if (idx === null) return null;
    const pts = this.weeklyPoints();
    return pts[idx] ?? null;
  });

  ngOnInit(): void {
    this.catalog.branches().subscribe({
      next: (b) => this.branches.set(b),
    });
    this.loadSummary();
  }

  loadSummary(): void {
    this.loading.set(true);
    this.error.set(null);

    this.commerce
      .adminDashboardSummary(this.selectedBranchId())
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (res) => {
          this.summary.set(res);
          this.lastUpdated.set(new Date());
        },
        error: (err) => {
          const detail = err?.error?.detail || err?.message;
          this.error.set(
            typeof detail === 'string' ? detail : 'No se pudieron cargar los datos del dashboard.'
          );
        },
      });
  }

  onBranchChange(val: string | number | null): void {
    if (val === '' || val === null || val === undefined || val === 'null') {
      this.selectedBranchId.set(null);
    } else {
      const num = Number(val);
      this.selectedBranchId.set(Number.isFinite(num) ? num : null);
    }
    this.loadSummary();
  }

  onHoverPoint(index: number | null): void {
    this.activeDayIndex.set(index);
  }

  onImgError(e: Event): void {
    const el = e.target as HTMLElement;
    if (el) el.style.display = 'none';
  }

  orderStatusLabel(estado: string): string {
    switch (estado) {
      case 'PAGADO':
        return 'Pagado';
      case 'PREPARANDO':
        return 'Preparando';
      case 'LISTO_PARA_ENVIO':
        return 'Listo Envío';
      case 'LISTO_PARA_RETIRO':
        return 'Listo Retiro';
      case 'EN_CAMINO':
        return 'En camino';
      case 'ENTREGADO':
        return 'Entregado';
      default:
        return estado;
    }
  }

  orderStatusClass(estado: string): string {
    switch (estado) {
      case 'PAGADO':
        return 'status-pill--pagado';
      case 'PREPARANDO':
        return 'status-pill--preparando';
      case 'LISTO_PARA_ENVIO':
      case 'LISTO_PARA_RETIRO':
        return 'status-pill--listo';
      case 'EN_CAMINO':
        return 'status-pill--en_camino';
      default:
        return '';
    }
  }

  deliveryLabel(tipo: string): string {
    return tipo === 'ENVIO_DOMICILIO' ? 'A Domicilio' : 'Retiro Tienda';
  }

  rankClass(rank: number): string {
    if (rank === 1) return 'rank-number--1';
    if (rank === 2) return 'rank-number--2';
    if (rank === 3) return 'rank-number--3';
    return 'rank-number--other';
  }
}
