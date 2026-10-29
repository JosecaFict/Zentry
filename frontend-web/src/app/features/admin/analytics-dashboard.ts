import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs';
import { Branch } from '../../core/models/catalog.model';
import { AnalyticsDashboard } from '../../core/models/reports.model';
import { CatalogService } from '../../core/services/catalog.service';
import { ReportsService } from '../../core/services/reports.service';

@Component({
  selector: 'app-analytics-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <main class="analytics-shell">
      <header class="analytics-heading">
        <div class="heading-copy">
          <h1>Analítica inteligente</h1>
          <p>Anticipa la demanda y reconoce patrones de compra con los datos de esta empresa.</p>
        </div>
        <div class="analytics-controls">
          <label for="analytics-branch">Sucursal</label>
          <select id="analytics-branch" [ngModel]="branchId()" (ngModelChange)="changeBranch($event)">
            <option [ngValue]="null">Todas las sucursales</option>
            @for (branch of branches(); track branch.id_sucursal) {
              <option [ngValue]="branch.id_sucursal">{{ branch.nombre }}</option>
            }
          </select>
          <button type="button" (click)="load()" [disabled]="loading()">
            {{ loading() ? 'Calculando…' : 'Actualizar modelos' }}
          </button>
        </div>
      </header>

      @if (error()) {
        <section class="state state--error" role="alert">
          <strong>No pudimos calcular la analítica.</strong><p>{{ error() }}</p>
          <button type="button" (click)="load()">Reintentar</button>
        </section>
      } @else if (loading() && !data()) {
        <section class="state state--loading" aria-live="polite"><span class="loading-line" aria-hidden="true"></span><strong>Entrenando los modelos con datos autorizados…</strong></section>
      } @else if (data(); as dashboard) {
        <section class="model-strip" aria-label="Información de los modelos">
          <div><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2v3M18 2v3M3.5 9h17M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2Z"/></svg><span>Periodo analizado</span><strong>{{ dashboard.periodo_desde | date:'dd/MM/yyyy' }} — {{ dashboard.periodo_hasta | date:'dd/MM/yyyy' }}</strong></div>
          <div><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s7-5.2 7-12a7 7 0 1 0-14 0c0 6.8 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5"/></svg><span>Alcance</span><strong>{{ dashboard.sucursal }}</strong></div>
          <div><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18 9 12l4 3 7-9M16 6h4v4"/></svg><span>Predicción</span><strong>{{ dashboard.prediccion_demanda.modelo }}</strong></div>
          <div><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="8" cy="8" r="3"/><circle cx="17" cy="7" r="2.5"/><path d="M2.5 20c.3-4 2-6 5.5-6s5.2 2 5.5 6M14 14c3.9-.8 6.5 1.2 7 5"/></svg><span>Segmentación</span><strong>{{ dashboard.segmentacion_clientes.modelo }}</strong></div>
        </section>

        <section class="forecast" aria-labelledby="forecast-title">
          <header class="section-heading">
            <div><h2 id="forecast-title">Demanda prevista</h2><p>Unidades e ingresos estimados para las próximas cuatro semanas.</p></div>
            <div class="confidence"><span>Confianza del modelo</span><strong [class]="'confidence--' + dashboard.prediccion_demanda.confianza.toLowerCase()">{{ dashboard.prediccion_demanda.confianza }}</strong></div>
          </header>
          @if (dashboard.prediccion_demanda.pronostico.length) {
            <div class="forecast-layout">
              <div class="forecast-visual">
                <div class="chart-heading">
                  <div><span>Proyección semanal</span><strong>{{ forecastTotal() }} unidades</strong></div>
                  <div class="chart-legend"><i></i> Estimación <i></i> Intervalo esperado</div>
                </div>
                <div class="chart-wrap">
                  <svg class="forecast-chart" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Tendencia de unidades estimadas por semana">
                    <g class="chart-grid" aria-hidden="true"><path d="M8 20H94M8 42H94M8 64H94M8 86H94" /></g>
                    <polygon class="confidence-band" [attr.points]="bandPoints()" />
                    <polyline class="forecast-line" [attr.points]="linePoints()" />
                    @for (point of chartPoints(); track point.x) {<circle class="forecast-dot" [attr.cx]="point.x" [attr.cy]="point.y" r="1.6" />}
                  </svg>
                  <div class="chart-axis" aria-hidden="true">
                    @for (point of dashboard.prediccion_demanda.pronostico; track point.semana) {<span>{{ point.semana | date:'dd MMM' }}</span>}
                  </div>
                </div>
              </div>
              <aside class="model-performance" aria-label="Rendimiento del modelo">
                <h3>Rendimiento del modelo</h3>
                <dl>
                  <div><dt>Confianza</dt><dd [class]="'text--' + dashboard.prediccion_demanda.confianza.toLowerCase()">{{ dashboard.prediccion_demanda.confianza }}</dd></div>
                  <div><dt>Error medio</dt><dd>{{ dashboard.prediccion_demanda.mae_unidades }} u.</dd></div>
                  <div><dt>R² entrenamiento</dt><dd>{{ dashboard.prediccion_demanda.r2_unidades | number:'1.3-3' }}</dd></div>
                  <div><dt>Tendencia semanal</dt><dd>{{ signed(dashboard.prediccion_demanda.tendencia_por_semana) }} u.</dd></div>
                </dl>
                <p>{{ dashboard.prediccion_demanda.advertencia || 'La serie dispone de evidencia suficiente para orientar la planificación.' }}</p>
              </aside>
            </div>
            <div class="forecast-table-wrap">
              <table class="forecast-table">
                <thead><tr><th>Semana</th><th>Estimación</th><th>Rango esperado</th><th>Ingresos previstos</th></tr></thead>
                <tbody>
                  @for (point of dashboard.prediccion_demanda.pronostico; track point.semana; let index = $index) {
                    <tr>
                      <td data-label="Semana"><span>0{{ index + 1 }}</span>{{ point.semana | date:'dd MMM yyyy' }}</td>
                      <td data-label="Estimación"><strong>{{ point.unidades_estimadas }}</strong> unidades</td>
                      <td data-label="Rango esperado">{{ point.intervalo_inferior }}–{{ point.intervalo_superior }} unidades</td>
                      <td data-label="Ingresos previstos"><strong>{{ point.ingresos_estimados | currency:'BOB':'Bs ':'1.2-2' }}</strong></td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          } @else {<div class="state"><strong>Datos insuficientes</strong><p>{{ dashboard.prediccion_demanda.advertencia }}</p></div>}
        </section>

        <section class="segments" aria-labelledby="segments-title">
          <header class="section-heading">
            <div><h2 id="segments-title">Segmentos de clientes</h2><p>K-means agrupa por recencia, frecuencia y valor monetario, sin etiquetas manuales.</p></div>
            <strong>{{ dashboard.segmentacion_clientes.clientes_analizados }} clientes analizados</strong>
          </header>
          @if (dashboard.segmentacion_clientes.segmentos.length) {
            <div class="segment-distribution" aria-label="Distribución porcentual de los segmentos">
              @for (segment of dashboard.segmentacion_clientes.segmentos; track segment.segmento) {
                <span [class]="'distribution--' + segment.segmento.toLowerCase()" [style.width.%]="segment.porcentaje"><b>{{ segment.segmento.replace('_', ' ') }}</b><small>{{ segment.porcentaje | number:'1.0-1' }}%</small></span>
              }
            </div>
            <div class="segment-grid">
              @for (segment of dashboard.segmentacion_clientes.segmentos; track segment.segmento) {
                <article [class]="'segment segment--' + segment.segmento.toLowerCase()">
                  <header><span>{{ segment.segmento.replace('_', ' ') }}</span><div><strong>{{ segment.clientes }}</strong><small>clientes</small></div></header>
                  <p>{{ segment.descripcion }}</p>
                  <dl>
                    <div><dt>Última compra</dt><dd>{{ segment.recencia_promedio_dias }} días</dd></div>
                    <div><dt>Frecuencia</dt><dd>{{ segment.frecuencia_promedio }} compras</dd></div>
                    <div><dt>Gasto promedio</dt><dd>{{ segment.gasto_promedio | currency:'BOB':'Bs ':'1.2-2' }}</dd></div>
                  </dl>
                  <footer><span>Acción sugerida</span><p>{{ segment.accion_recomendada }}</p></footer>
                </article>
              }
            </div>
          } @else {<div class="state"><strong>Se necesitan al menos tres clientes con compras.</strong></div>}
        </section>

        <aside class="method-note">
          <strong>Cómo leer este panel</strong>
          <p>Las predicciones apoyan decisiones, no ofrecen garantías. Cada actualización recalcula los modelos con los datos disponibles y conserva el aislamiento de la empresa y la sucursal seleccionada.</p>
        </aside>
      }
    </main>
  `,
  styleUrl: './analytics-dashboard.scss',
})
export class AnalyticsDashboardPage implements OnInit {
  private readonly reports = inject(ReportsService);
  private readonly catalog = inject(CatalogService);
  readonly data = signal<AnalyticsDashboard | null>(null);
  readonly branches = signal<Branch[]>([]);
  readonly branchId = signal<number | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly maxForecast = computed(() => Math.max(1, ...(this.data()?.prediccion_demanda.pronostico.map(point => point.intervalo_superior) ?? [1])));
  readonly chartPoints = computed(() => this.data()?.prediccion_demanda.pronostico.map((point, index) => ({
    x: 8 + index * 28,
    y: this.chartY(point.unidades_estimadas),
    lowerY: this.chartY(point.intervalo_inferior),
    upperY: this.chartY(point.intervalo_superior),
  })) ?? []);
  readonly linePoints = computed(() => this.chartPoints().map(point => `${point.x},${point.y}`).join(' '));
  readonly bandPoints = computed(() => {
    const points = this.chartPoints();
    return [...points.map(point => `${point.x},${point.upperY}`), ...[...points].reverse().map(point => `${point.x},${point.lowerY}`)].join(' ');
  });
  readonly forecastTotal = computed(() => this.data()?.prediccion_demanda.pronostico.reduce((total, point) => total + point.unidades_estimadas, 0) ?? 0);

  ngOnInit(): void {
    this.catalog.branches().subscribe({ next: branches => this.branches.set(branches) });
    this.load();
  }
  changeBranch(value: number | null): void { this.branchId.set(value); this.load(); }
  load(): void {
    this.loading.set(true); this.error.set(null);
    this.reports.analyticsDashboard(this.branchId()).pipe(finalize(() => this.loading.set(false))).subscribe({
      next: response => this.data.set(response),
      error: err => this.error.set(err?.error?.detail || 'No se pudieron calcular los modelos.'),
    });
  }
  signed(value: number): string { return `${value > 0 ? '+' : ''}${value}`; }
  private chartY(value: number): number { return Math.round((86 - (value / this.maxForecast()) * 66) * 10) / 10; }
}
