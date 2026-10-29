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
        <div>
          <span class="eyebrow">MODELOS · DATOS DE LOS ÚLTIMOS 6 MESES</span>
          <h1>Analítica inteligente</h1>
          <p>Predicción de demanda y segmentos de clientes calculados exclusivamente con datos de esta empresa.</p>
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
        <section class="state" aria-live="polite"><strong>Entrenando los modelos con datos autorizados…</strong></section>
      } @else if (data(); as dashboard) {
        <section class="model-strip" aria-label="Información de los modelos">
          <div><span>Periodo analizado</span><strong>{{ dashboard.periodo_desde | date:'dd/MM/yyyy' }} — {{ dashboard.periodo_hasta | date:'dd/MM/yyyy' }}</strong></div>
          <div><span>Alcance</span><strong>{{ dashboard.sucursal }}</strong></div>
          <div><span>Predicción</span><strong>{{ dashboard.prediccion_demanda.modelo }}</strong></div>
          <div><span>Segmentación</span><strong>{{ dashboard.segmentacion_clientes.modelo }}</strong></div>
        </section>

        <section class="forecast" aria-labelledby="forecast-title">
          <header>
            <div><span class="eyebrow">MODELO SUPERVISADO</span><h2 id="forecast-title">Demanda prevista</h2><p>Unidades esperadas para las próximas cuatro semanas.</p></div>
            <div class="confidence"><span>Confianza</span><strong [class]="'confidence--' + dashboard.prediccion_demanda.confianza.toLowerCase()">{{ dashboard.prediccion_demanda.confianza }}</strong></div>
          </header>
          @if (dashboard.prediccion_demanda.pronostico.length) {
            <div class="forecast-grid">
              @for (point of dashboard.prediccion_demanda.pronostico; track point.semana; let index = $index) {
                <article>
                  <span>SEMANA {{ index + 1 }} · {{ point.semana | date:'dd MMM' }}</span>
                  <strong>{{ point.unidades_estimadas }}</strong>
                  <p>unidades estimadas</p>
                  <div class="range" [style.--range]="forecastHeight(point.unidades_estimadas) + '%'">
                    <i></i><small>{{ point.intervalo_inferior }}–{{ point.intervalo_superior }} u.</small>
                  </div>
                  <b>{{ point.ingresos_estimados | currency:'BOB':'Bs ':'1.2-2' }}</b>
                </article>
              }
            </div>
            <footer class="model-quality">
              <div><span>Error medio (MAE)</span><strong>{{ dashboard.prediccion_demanda.mae_unidades }} unidades</strong></div>
              <div><span>R² del entrenamiento</span><strong>{{ dashboard.prediccion_demanda.r2_unidades | number:'1.3-3' }}</strong></div>
              <div><span>Tendencia semanal</span><strong>{{ signed(dashboard.prediccion_demanda.tendencia_por_semana) }} unidades</strong></div>
              <p>{{ dashboard.prediccion_demanda.advertencia || 'La serie dispone de evidencia suficiente para orientar la planificación.' }}</p>
            </footer>
          } @else {
            <div class="state"><strong>Datos insuficientes</strong><p>{{ dashboard.prediccion_demanda.advertencia }}</p></div>
          }
        </section>

        <section class="segments" aria-labelledby="segments-title">
          <header><div><span class="eyebrow">MODELO NO SUPERVISADO</span><h2 id="segments-title">Segmentos de clientes</h2><p>K-means agrupa por recencia, frecuencia y valor monetario, sin etiquetas manuales.</p></div><strong>{{ dashboard.segmentacion_clientes.clientes_analizados }} clientes analizados</strong></header>
          @if (dashboard.segmentacion_clientes.segmentos.length) {
            <div class="segment-grid">
              @for (segment of dashboard.segmentacion_clientes.segmentos; track segment.segmento) {
                <article [class]="'segment segment--' + segment.segmento.toLowerCase()">
                  <header><span>{{ segment.segmento.replace('_', ' ') }}</span><strong>{{ segment.porcentaje | number:'1.0-1' }}%</strong></header>
                  <div class="segment-count"><strong>{{ segment.clientes }}</strong><span>clientes</span></div>
                  <p>{{ segment.descripcion }}</p>
                  <dl>
                    <div><dt>Última compra</dt><dd>{{ segment.recencia_promedio_dias }} días</dd></div>
                    <div><dt>Frecuencia</dt><dd>{{ segment.frecuencia_promedio }} compras</dd></div>
                    <div><dt>Gasto promedio</dt><dd>{{ segment.gasto_promedio | currency:'BOB':'Bs ':'1.2-2' }}</dd></div>
                  </dl>
                  <footer><span>ACCIÓN SUGERIDA</span><p>{{ segment.accion_recomendada }}</p></footer>
                </article>
              }
            </div>
          } @else {
            <div class="state"><strong>Se necesitan al menos tres clientes con compras.</strong></div>
          }
        </section>

        <aside class="method-note">
          <strong>Cómo leer este panel</strong>
          <p>Las predicciones son apoyo para decisiones, no garantías. Cada actualización vuelve a calcular los modelos con los datos disponibles y conserva el aislamiento de la empresa y sucursal seleccionadas.</p>
        </aside>
      }
    </main>
  `,
  styleUrl: './analytics-dashboard.scss',
  styles: [`
    :host{display:block;color:#121418}.analytics-shell{max-width:1400px;margin:0 auto;padding:4rem 2rem 6rem}.analytics-heading{display:flex;justify-content:space-between;gap:3rem;padding-bottom:2rem;border-bottom:1px solid #cbd0d6}.eyebrow{color:#064fe8;font-size:.72rem;font-weight:800;letter-spacing:.16em}.analytics-heading h1{margin:.45rem 0;font-size:clamp(2.7rem,5vw,4.5rem);line-height:1;letter-spacing:-.045em}.analytics-heading p,.forecast header p,.segments header p{max-width:700px;margin:.5rem 0 0;color:#565d67}.analytics-controls{display:grid;grid-template-columns:minmax(210px,1fr) auto;gap:.45rem 1rem;align-self:end;min-width:400px}.analytics-controls label{grid-column:1/-1;font-size:.78rem;font-weight:800}.analytics-controls select,.analytics-controls button,.state button{min-height:48px;border:1px solid #9aa3ad;border-radius:8px;background:#fff;padding:.7rem .85rem;font:inherit}.analytics-controls button,.state button{border-color:#064fe8;background:#064fe8;color:#fff;font-weight:800;cursor:pointer}.analytics-controls button:disabled{opacity:.55}.model-strip{display:grid;grid-template-columns:repeat(4,1fr);margin-top:2rem;border-block:1px solid #cbd0d6}.model-strip div{padding:1.2rem;border-right:1px solid #cbd0d6}.model-strip div:last-child{border:0}.model-strip span,.confidence span,.model-quality span,.method-note p{display:block;color:#565d67;font-size:.78rem}.model-strip strong{display:block;margin-top:.4rem;font-size:.92rem}.forecast,.segments{margin-top:4.5rem}.forecast>header,.segments>header{display:flex;justify-content:space-between;gap:2rem;align-items:end;padding-bottom:1.25rem;border-bottom:1px solid #121418}.forecast h2,.segments h2{margin:.35rem 0 0;font-size:clamp(2rem,4vw,3.25rem);letter-spacing:-.035em}.confidence{text-align:right}.confidence strong{display:block;margin-top:.4rem;padding:.35rem .65rem;border:1px solid #064fe8;border-radius:999px;color:#064fe8}.confidence--baja{border-color:#b42318!important;color:#b42318!important}.forecast-grid{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid #cbd0d6}.forecast-grid article{min-height:310px;padding:1.5rem;border-right:1px solid #cbd0d6}.forecast-grid article:last-child{border:0}.forecast-grid article>span{font-size:.72rem;font-weight:800;letter-spacing:.09em}.forecast-grid article>strong{display:block;margin-top:1.25rem;font-size:3.5rem;line-height:1}.forecast-grid article>p{margin:.2rem 0;color:#565d67}.forecast-grid article>b{display:block;margin-top:1.1rem}.range{position:relative;height:86px;margin-top:1rem;border-bottom:1px solid #cbd0d6}.range i{position:absolute;right:0;bottom:0;left:0;height:var(--range);background:#064fe8}.range small{position:absolute;right:0;top:0;color:#565d67}.model-quality{display:grid;grid-template-columns:repeat(3,1fr) 2fr;border-bottom:1px solid #cbd0d6}.model-quality>*{padding:1.1rem;border-right:1px solid #cbd0d6}.model-quality>*:last-child{border:0}.model-quality strong{display:block;margin-top:.3rem}.segments>header>strong{font-size:1.1rem}.segment-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1.25rem;margin-top:1.5rem}.segment{padding:1.5rem;border:1px solid #cbd0d6;border-top:4px solid #064fe8;background:#fff}.segment--en_riesgo{border-top-color:#b42318}.segment>header{display:flex;justify-content:space-between;font-size:.8rem;font-weight:800;letter-spacing:.08em}.segment-count{display:flex;align-items:baseline;gap:.5rem;margin-top:1.6rem}.segment-count strong{font-size:3.25rem}.segment>p{min-height:50px;color:#565d67}.segment dl{margin:1.5rem 0;border-block:1px solid #cbd0d6}.segment dl div{display:flex;justify-content:space-between;gap:1rem;padding:.75rem 0;border-bottom:1px solid #e4e7eb}.segment dl div:last-child{border:0}.segment dt{color:#565d67}.segment dd{margin:0;font-weight:800;text-align:right}.segment footer span{font-size:.68rem;color:#064fe8;font-weight:800;letter-spacing:.12em}.segment footer p{margin:.45rem 0 0}.method-note,.state{margin-top:2rem;padding:1.25rem 0;border-block:1px solid #cbd0d6}.state--error{border-color:#b42318;color:#b42318}.state p{margin:.4rem 0}.state button{margin-top:.75rem}.method-note{display:grid;grid-template-columns:220px 1fr;gap:2rem}.method-note p{margin:0;font-size:.9rem}@media(max-width:980px){.analytics-heading{display:grid}.analytics-controls{min-width:0}.model-strip{grid-template-columns:repeat(2,1fr)}.model-strip div:nth-child(2){border-right:0}.forecast-grid{grid-template-columns:repeat(2,1fr)}.forecast-grid article:nth-child(2){border-right:0}.model-quality{grid-template-columns:repeat(2,1fr)}.segment-grid{grid-template-columns:1fr}}@media(max-width:600px){.analytics-shell{padding:2.5rem 1rem 4rem}.analytics-controls{grid-template-columns:1fr}.analytics-controls button{grid-column:1}.model-strip,.forecast-grid,.model-quality{grid-template-columns:1fr}.model-strip div,.forecast-grid article,.model-quality>*{border-right:0;border-bottom:1px solid #cbd0d6}.forecast>header,.segments>header{align-items:start;flex-direction:column}.confidence{text-align:left}.method-note{grid-template-columns:1fr}}
  `],
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
  forecastHeight(value: number): number { return Math.max(8, Math.round(value * 100 / this.maxForecast())); }
  signed(value: number): string { return `${value > 0 ? '+' : ''}${value}`; }
}
