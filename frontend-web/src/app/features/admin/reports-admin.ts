import { CommonModule, DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { finalize } from 'rxjs/operators';
import { Branch } from '../../core/models/catalog.model';
import { AIReportResponse, BranchSalesReport, CategoryRevenueReport, CustomerReport, InventoryReport, ProductReport, SalesReport } from '../../core/models/reports.model';
import { CatalogService } from '../../core/services/catalog.service';
import { ReportFilters, ReportsService } from '../../core/services/reports.service';
import { BolivianosPipe } from '../../shared/pipes/bolivianos.pipe';

@Component({
  selector: 'app-reports-admin',
  imports: [CommonModule, FormsModule, DatePipe, DecimalPipe, BolivianosPipe],
  template: `
    <main class="reports-page">
      <header class="reports-heading">
        <div>
          <h1>Reportes comerciales</h1>
          <p>Ventas, productos, clientes e inventario reunidos en una lectura operativa.</p>
        </div>
        <div class="report-actions">
          <button type="button" class="export" (click)="exportReport('xlsx')" [disabled]="loading() || !!exporting()">Excel</button>
          <button type="button" class="export" (click)="exportReport('pdf')" [disabled]="loading() || !!exporting()">PDF</button>
          <button type="button" class="refresh" (click)="loadReports()" [disabled]="loading()">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.34 5.66M20 4v7h-7" /></svg>
            {{ loading() ? 'Actualizando' : 'Actualizar' }}
          </button>
        </div>
      </header>

      <form class="report-filters" (ngSubmit)="applyFilters()">
        <label>Desde<input type="date" name="desde" [(ngModel)]="dateFrom" [max]="dateTo" /></label>
        <label>Hasta<input type="date" name="hasta" [(ngModel)]="dateTo" [min]="dateFrom" /></label>
        <label>Sucursal
          <select name="branch" [(ngModel)]="branchId">
            <option [ngValue]="null">Todas las sucursales</option>
            @for (branch of branches(); track branch.id_sucursal) {
              <option [ngValue]="branch.id_sucursal">{{ branch.nombre }}</option>
            }
          </select>
        </label>
        <button type="submit" [disabled]="loading() || !dateFrom || !dateTo">Aplicar filtros</button>
      </form>

      <section class="ai-assistant" aria-labelledby="ai-report-title">
        <div class="ai-copy">
          <span>PLAN PROFESIONAL · ASISTENTE DE IA</span>
          <h2 id="ai-report-title">Pregunta por tu operación</h2>
          <p>Describe el reporte que necesitas. Zentry interpretará la consulta y usará únicamente datos autorizados de esta empresa.</p>
        </div>
        <form class="ai-form" (ngSubmit)="askAssistant()">
          <label for="ai-question">Tu consulta</label>
          <div class="ai-query-row">
            <input id="ai-question" name="aiQuestion" [(ngModel)]="aiQuestion" maxlength="500" placeholder="Ej.: ¿Cuáles fueron mis productos más vendidos este mes?" />
            <button
              type="button"
              class="voice-button"
              [class.voice-button--recording]="voiceRecording()"
              [disabled]="aiLoading() || voiceTranscribing()"
              [attr.aria-pressed]="voiceRecording()"
              [attr.aria-label]="voiceRecording() ? 'Detener grabación' : 'Dictar consulta'"
              (click)="toggleVoiceRecording()">
              @if (voiceTranscribing()) {
                <span class="voice-spinner" aria-hidden="true"></span>
              } @else if (voiceRecording()) {
                <span class="voice-stop" aria-hidden="true"></span>
              } @else {
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z"/><path d="M5 11v1a7 7 0 0 0 14 0v-1M12 19v3M8 22h8"/></svg>
              }
            </button>
            <button class="ai-submit" type="submit" [disabled]="aiLoading() || voiceRecording() || voiceTranscribing() || !aiQuestion.trim()">{{ aiLoading() ? 'Analizando…' : 'Consultar' }}</button>
          </div>
          <small>La IA interpreta filtros; nunca escribe ni ejecuta consultas SQL. Puedes dictar y revisar el texto antes de consultar.</small>
          <p class="voice-status" aria-live="polite">
            @if (voiceRecording()) { <span class="recording-dot"></span> Grabando · {{ voiceSeconds() }} s de 60 s }
            @else if (voiceTranscribing()) { Transcribiendo tu consulta… }
            @else if (voiceMessage()) { {{ voiceMessage() }} }
          </p>
        </form>
        @if (aiError()) { <p class="ai-error" role="alert">{{ aiError() }}</p> }
        @if (aiResult(); as result) {
          <article class="ai-result">
            <header>
              <div><span>{{ result.interpretacion.tipo_reporte }} · {{ aiPeriodLabel() }}</span><h3>{{ result.titulo }}</h3></div>
              <div class="ai-result-side">
                <p>{{ result.resumen }}</p>
                @if (!result.interpretacion.necesita_aclaracion) {
                  <div class="ai-export-actions" aria-label="Exportar este reporte">
                    <button type="button" (click)="exportAssistant('xlsx')" [disabled]="!!aiExporting()">{{ aiExporting() === 'xlsx' ? 'Generando…' : 'Excel' }}</button>
                    <button type="button" (click)="exportAssistant('pdf')" [disabled]="!!aiExporting()">{{ aiExporting() === 'pdf' ? 'Generando…' : 'PDF' }}</button>
                  </div>
                }
              </div>
            </header>
            @if (!result.interpretacion.necesita_aclaracion) {
              <div class="ai-applied-filters" aria-label="Filtros interpretados">
                @for (filter of aiAppliedFilters(); track filter) { <span>{{ filter }}</span> }
              </div>
            }
            @if (result.interpretacion.necesita_aclaracion) {
              <div class="ai-clarification" role="status">
                <strong>Completa tu consulta</strong>
                <p>{{ result.interpretacion.pregunta_aclaracion }}</p>
              </div>
            } @else if (aiBranchSales(); as report) {
              <dl class="ai-metrics ai-metrics--three">
                <div><dt>Ingresos</dt><dd>{{ report.ingresos | bolivianos }}</dd></div>
                <div><dt>Ventas</dt><dd>{{ report.total_ventas | number }}</dd></div>
                <div><dt>Unidades</dt><dd>{{ report.total_unidades | number }}</dd></div>
              </dl>
              <div class="ai-comparison" aria-label="Comparación de ingresos por sucursal">
                @for (item of report.sucursales; track item.id_sucursal) {
                  <div><span>{{ item.sucursal }}</span><i><b [style.width.%]="comparisonWidth(item.ingresos, branchRevenueValues(report))"></b></i><strong>{{ item.ingresos | bolivianos }}</strong></div>
                }
              </div>
              <div class="ai-table"><table>
                <thead><tr><th>Sucursal</th><th class="numeric">Ventas</th><th class="numeric">Unidades</th><th class="numeric">Ingresos</th><th class="numeric">Participación</th></tr></thead>
                <tbody>
                  @for (item of report.sucursales; track item.id_sucursal) {
                    <tr><td><strong>{{ item.sucursal }}</strong></td><td class="numeric">{{ item.ventas }}</td><td class="numeric">{{ item.unidades }}</td><td class="numeric">{{ item.ingresos | bolivianos }}</td><td class="numeric">{{ item.participacion | number:'1.1-2' }}%</td></tr>
                  } @empty { <tr><td colspan="5" class="ai-empty">No se encontraron ventas por sucursal en ese período.</td></tr> }
                </tbody>
              </table></div>
            } @else if (aiSales(); as report) {
              <dl class="ai-metrics">
                <div><dt>Ingresos</dt><dd>{{ report.ingresos | bolivianos }}</dd></div>
                <div><dt>Ventas</dt><dd>{{ report.total_ventas | number }}</dd></div>
                <div><dt>Unidades</dt><dd>{{ report.total_unidades | number }}</dd></div>
                <div><dt>Ticket promedio</dt><dd>{{ report.ticket_promedio | bolivianos }}</dd></div>
              </dl>
              @if (report.serie.length) {
                <div class="ai-chart" aria-label="Ingresos diarios del reporte solicitado">
                  @for (point of report.serie; track point.fecha) {
                    <div [title]="(point.ingresos | bolivianos) + ''">
                      <i [style.height.%]="aiBarHeight(point.ingresos, report)"></i>
                      <time>{{ point.fecha | date: 'dd/MM' }}</time>
                    </div>
                  }
                </div>
              } @else { <p class="ai-empty">No se encontraron ventas para los criterios solicitados.</p> }
            } @else if (aiProducts(); as report) {
              <div class="ai-table"><table>
                <thead><tr><th>#</th><th>Producto</th><th>Categoría</th><th class="numeric">Unidades</th><th class="numeric">Ingresos</th></tr></thead>
                <tbody>
                  @for (item of report.productos; track item.id_producto) {
                    <tr><td>{{ item.posicion }}</td><td><strong>{{ item.producto }}</strong></td><td>{{ item.categoria }}</td><td class="numeric">{{ item.unidades }}</td><td class="numeric">{{ item.ingresos | bolivianos }}</td></tr>
                  } @empty { <tr><td colspan="5" class="ai-empty">No se encontraron productos para los criterios solicitados.</td></tr> }
                </tbody>
              </table></div>
            } @else if (aiInventory(); as report) {
              <dl class="ai-metrics ai-metrics--three">
                <div><dt>Disponibles</dt><dd>{{ report.unidades_disponibles | number }}</dd></div>
                <div><dt>Ítems críticos</dt><dd>{{ report.items_criticos | number }}</dd></div>
                <div><dt>Valor</dt><dd>{{ report.valor_total | bolivianos }}</dd></div>
              </dl>
              <div class="ai-table"><table>
                <thead><tr><th>Producto</th><th>Variante</th><th>SKU</th><th>Sucursal</th><th class="numeric">Disponible</th><th class="numeric">Mínimo</th></tr></thead>
                <tbody>
                  @for (item of report.items; track item.id_variante + '-' + item.sucursal) {
                    <tr><td><strong>{{ item.producto }}</strong><small>{{ item.categoria }}</small></td><td>{{ item.talla }} · {{ item.color }}</td><td>{{ item.sku }}</td><td>{{ item.sucursal }}</td><td class="numeric">{{ item.stock_disponible }}</td><td class="numeric">{{ item.stock_minimo }}</td></tr>
                  } @empty { <tr><td colspan="6" class="ai-empty">No existen artículos para los criterios solicitados.</td></tr> }
                </tbody>
              </table></div>
            } @else if (aiCategories(); as report) {
              <dl class="ai-metrics ai-metrics--three">
                <div><dt>Ingresos</dt><dd>{{ report.ingresos | bolivianos }}</dd></div>
                <div><dt>Unidades</dt><dd>{{ report.total_unidades | number }}</dd></div>
                <div><dt>Categorías</dt><dd>{{ report.categorias.length | number }}</dd></div>
              </dl>
              <div class="ai-comparison" aria-label="Comparación de ingresos por categoría">
                @for (item of report.categorias; track item.id_categoria) {
                  <div><span>{{ item.categoria }}</span><i><b [style.width.%]="comparisonWidth(item.ingresos, categoryRevenueValues(report))"></b></i><strong>{{ item.ingresos | bolivianos }}</strong></div>
                }
              </div>
              <div class="ai-table"><table>
                <thead><tr><th>Categoría</th><th class="numeric">Unidades</th><th class="numeric">Ingresos</th><th class="numeric">Participación</th></tr></thead>
                <tbody>
                  @for (item of report.categorias; track item.id_categoria) {
                    <tr><td><strong>{{ item.categoria }}</strong></td><td class="numeric">{{ item.unidades }}</td><td class="numeric">{{ item.ingresos | bolivianos }}</td><td class="numeric">{{ item.participacion | number:'1.1-2' }}%</td></tr>
                  } @empty { <tr><td colspan="4" class="ai-empty">No se encontraron ingresos por categoría para ese período.</td></tr> }
                </tbody>
              </table></div>
            } @else if (aiCustomers(); as report) {
              <div class="ai-table"><table>
                <thead><tr><th>Cliente</th><th class="numeric">Compras</th><th class="numeric">Unidades</th><th class="numeric">Gasto</th></tr></thead>
                <tbody>
                  @for (item of report.clientes; track item.id_cliente) {
                    <tr><td><strong>{{ item.cliente }}</strong><small>{{ item.correo }}</small></td><td class="numeric">{{ item.compras }}</td><td class="numeric">{{ item.unidades }}</td><td class="numeric">{{ item.gasto_total | bolivianos }}</td></tr>
                  } @empty { <tr><td colspan="4" class="ai-empty">No se encontraron clientes para los criterios solicitados.</td></tr> }
                </tbody>
              </table></div>
            } @else if (aiSummarySales(); as report) {
              <dl class="ai-metrics">
                <div><dt>Ingresos</dt><dd>{{ report.ingresos | bolivianos }}</dd></div>
                <div><dt>Ventas</dt><dd>{{ report.total_ventas | number }}</dd></div>
                <div><dt>Unidades</dt><dd>{{ report.total_unidades | number }}</dd></div>
                <div><dt>Ticket promedio</dt><dd>{{ report.ticket_promedio | bolivianos }}</dd></div>
              </dl>
            }
          </article>
        }
      </section>

      @if (error()) {
        <section class="report-state report-state--error" role="alert">
          <strong>No pudimos generar los reportes.</strong>
          <span>{{ error() }}</span>
          <button type="button" (click)="loadReports()">Intentar de nuevo</button>
        </section>
      } @else if (loading() && !sales()) {
        <section class="report-state" aria-busy="true"><strong>Preparando indicadores…</strong></section>
      } @else if (sales(); as salesData) {
        <section class="report-summary" aria-label="Resumen del periodo">
          <div class="summary-primary">
            <span>Ingresos del periodo</span>
            <strong>{{ salesData.ingresos | bolivianos }}</strong>
            <small>{{ salesData.desde | date: 'dd MMM' }} — {{ salesData.hasta | date: 'dd MMM yyyy' }}</small>
          </div>
          <dl>
            <div><dt>Ventas</dt><dd>{{ salesData.total_ventas | number }}</dd></div>
            <div><dt>Unidades</dt><dd>{{ salesData.total_unidades | number }}</dd></div>
            <div><dt>Ticket promedio</dt><dd>{{ salesData.ticket_promedio | bolivianos }}</dd></div>
            <div><dt>Inventario valorizado</dt><dd>{{ inventory()?.valor_total ?? 0 | bolivianos }}</dd></div>
          </dl>
        </section>

        <section class="reports-grid">
          <article class="report-panel trend-panel">
            <header><div><h2>Ritmo de ventas</h2><p>Ingresos pagados por día.</p></div></header>
            @if (salesData.serie.length) {
              <div class="bars" [style.--bar-count]="salesData.serie.length">
                @for (point of salesData.serie; track point.fecha) {
                  <div class="bar-column" [title]="(point.ingresos | bolivianos) + ''">
                    <span class="bar-value">{{ point.ingresos | bolivianos }}</span>
                    <i [style.height.%]="barHeight(point.ingresos)"></i>
                    <time>{{ point.fecha | date: 'dd/MM' }}</time>
                  </div>
                }
              </div>
            } @else { <p class="empty">No existen ventas pagadas en este periodo.</p> }
          </article>

          <article class="report-panel stock-panel">
            <header><div><h2>Estado del inventario</h2><p>Disponibilidad actual después de reservas.</p></div></header>
            <div class="stock-reading"><strong>{{ inventory()?.unidades_disponibles ?? 0 | number }}</strong><span>unidades disponibles</span></div>
            <div class="stock-rule"><span [style.width.%]="healthyStockPercent()"></span></div>
            <p><b>{{ inventory()?.items_criticos ?? 0 }}</b> variantes requieren reposición.</p>
          </article>
        </section>

        <section class="report-table-section">
          <header><div><h2>Productos con mayor movimiento</h2><p>Ordenados por ingresos dentro del periodo.</p></div></header>
          <div class="table-scroll"><table>
            <thead><tr><th>Producto</th><th>Categoría</th><th class="numeric">Unidades</th><th class="numeric">Ingresos</th></tr></thead>
            <tbody>
              @for (item of products()?.productos ?? []; track item.id_producto) {
                <tr><td><strong>{{ item.producto }}</strong></td><td>{{ item.categoria }}</td><td class="numeric">{{ item.unidades }}</td><td class="numeric">{{ item.ingresos | bolivianos }}</td></tr>
              } @empty { <tr><td colspan="4" class="empty-cell">Sin productos vendidos en el periodo.</td></tr> }
            </tbody>
          </table></div>
        </section>

        <section class="report-table-section">
          <header><div><h2>Clientes con mayor actividad</h2><p>Frecuencia, gasto y fecha de su compra más reciente.</p></div></header>
          <div class="table-scroll"><table>
            <thead><tr><th>Cliente</th><th class="numeric">Compras</th><th class="numeric">Unidades</th><th class="numeric">Gasto total</th><th>Última compra</th></tr></thead>
            <tbody>
              @for (item of customers()?.clientes ?? []; track item.id_cliente) {
                <tr><td><strong>{{ item.cliente }}</strong><small>{{ item.correo }}</small></td><td class="numeric">{{ item.compras }}</td><td class="numeric">{{ item.unidades }}</td><td class="numeric">{{ item.gasto_total | bolivianos }}</td><td>{{ item.ultima_compra | date: 'dd/MM/yyyy' }}</td></tr>
              } @empty { <tr><td colspan="5" class="empty-cell">Todavía no existen compras asociadas a clientes.</td></tr> }
            </tbody>
          </table></div>
        </section>
      }
    </main>
  `,
  styles: [`
    :host{display:block;color:#121418}.reports-page{max-width:1400px;margin:0 auto;padding:2.5rem 2rem 5rem}.reports-heading{display:flex;align-items:end;justify-content:space-between;gap:2rem;padding-bottom:1.75rem;border-bottom:1px solid #cbd0d6}.reports-heading h1{margin:0;font-size:clamp(2.25rem,4vw,3.7rem);line-height:1;letter-spacing:-.035em}.reports-heading p,.report-panel p,.report-table-section p{margin:.7rem 0 0;color:#565d67}.report-actions{display:flex;gap:.65rem}.refresh,.export{display:inline-flex;align-items:center;justify-content:center;gap:.65rem;min-height:48px;padding:.7rem 1rem;border:1px solid #121418;border-radius:8px;background:transparent;font:inherit;font-weight:700;cursor:pointer}.export{border-color:#064fe8;color:#064fe8}.refresh svg{width:19px;fill:none;stroke:currentColor;stroke-width:1.8}.refresh:hover{background:#121418;color:white}.export:hover{background:#064fe8;color:white}.refresh:disabled,.export:disabled{cursor:wait;opacity:.55}.report-filters{display:grid;grid-template-columns:repeat(3,minmax(160px,1fr)) auto;gap:1rem;align-items:end;padding:1.4rem 0 2rem}.report-filters label{display:grid;gap:.45rem;font-size:.83rem;font-weight:700}.report-filters input,.report-filters select{min-height:48px;padding:.65rem .8rem;border:1px solid #aab1ba;border-radius:8px;background:#fff;color:#121418;font:inherit}.report-filters button,.report-state button{min-height:48px;padding:.7rem 1.35rem;border:1px solid #064fe8;border-radius:8px;background:#064fe8;color:#fff;font:inherit;font-weight:700;cursor:pointer}.ai-assistant{display:grid;grid-template-columns:minmax(240px,.7fr) minmax(360px,1.3fr);gap:2rem;margin-bottom:2.5rem;padding:2rem;background:#eef3ff;border:1px solid #b9c9ef}.ai-copy span,.ai-result span{color:#064fe8;font-size:.72rem;font-weight:800;letter-spacing:.1em}.ai-copy h2{margin:.55rem 0;font-size:1.75rem}.ai-copy p{margin:0;color:#505a68;line-height:1.55}.ai-form label{display:block;margin-bottom:.5rem;font-size:.82rem;font-weight:800}.ai-form>div{display:flex}.ai-form input{width:100%;min-height:52px;padding:0 .9rem;border:1px solid #7f8ba0;border-right:0;border-radius:7px 0 0 7px;font:inherit}.ai-form button{min-width:120px;border:0;border-radius:0 7px 7px 0;background:#064fe8;color:white;font:inherit;font-weight:800}.ai-form button:disabled{opacity:.55}.ai-form small{display:block;margin-top:.55rem;color:#647086}.ai-error{grid-column:1/-1;margin:0;color:#9c2218}.ai-result{grid-column:1/-1;display:flex;justify-content:space-between;gap:2rem;padding-top:1.3rem;border-top:1px solid #b9c9ef}.ai-result h3{margin:.3rem 0 0}.ai-result p{max-width:580px;margin:0;color:#344055}.report-filters :focus-visible,.refresh:focus-visible,.export:focus-visible,.report-state button:focus-visible,.ai-form :focus-visible{outline:3px solid rgba(6,79,232,.28);outline-offset:2px}.report-summary{display:grid;grid-template-columns:minmax(280px,.85fr) 1.5fr;background:#121720;color:#fff}.summary-primary{display:flex;flex-direction:column;justify-content:center;min-height:220px;padding:2rem 2.4rem;border-right:1px solid #3a414d}.summary-primary span{color:#b8c1ce;font-size:.85rem;font-weight:700}.summary-primary strong{margin:.45rem 0;font-size:clamp(2.7rem,5vw,4.8rem);line-height:1;font-variant-numeric:tabular-nums;letter-spacing:-.04em}.summary-primary small{color:#b8c1ce}.report-summary dl{display:grid;grid-template-columns:repeat(2,1fr);margin:0}.report-summary dl div{display:flex;flex-direction:column;justify-content:center;padding:1.7rem 2rem;border-bottom:1px solid #3a414d}.report-summary dl div:nth-child(odd){border-right:1px solid #3a414d}.report-summary dl div:nth-child(n+3){border-bottom:0}.report-summary dt{color:#b8c1ce;font-size:.82rem}.report-summary dd{margin:.35rem 0 0;font-size:1.55rem;font-weight:700;font-variant-numeric:tabular-nums}.reports-grid{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(280px,.75fr);border-bottom:1px solid #cbd0d6}.report-panel{min-height:340px;padding:2rem 0}.report-panel+ .report-panel{padding-left:2rem;border-left:1px solid #cbd0d6}.report-panel:first-child{padding-right:2rem}.report-panel h2,.report-table-section h2{margin:0;font-size:1.45rem;letter-spacing:-.025em}.bars{display:flex;align-items:end;gap:max(5px,1.1vw);height:220px;margin-top:2rem;padding-top:2rem;border-bottom:1px solid #aab1ba;overflow-x:auto}.bar-column{display:grid;grid-template-rows:24px 1fr 28px;align-items:end;justify-items:center;min-width:max(42px,calc((100% - 2rem)/var(--bar-count)));height:100%}.bar-column i{display:block;width:min(28px,65%);min-height:3px;background:#064fe8}.bar-column time{padding-top:.55rem;color:#565d67;font-size:.72rem}.bar-value{opacity:0;font-size:.68rem;white-space:nowrap;transition:opacity .15s}.bar-column:hover .bar-value{opacity:1}.stock-reading{display:flex;align-items:baseline;gap:.7rem;margin-top:4rem}.stock-reading strong{font-size:3.5rem;line-height:1;font-variant-numeric:tabular-nums}.stock-reading span{color:#565d67}.stock-rule{height:8px;margin:1.5rem 0;background:#dfe3e8}.stock-rule span{display:block;height:100%;background:#064fe8}.report-table-section{padding:2.5rem 0;border-bottom:1px solid #cbd0d6}.report-table-section header{margin-bottom:1.5rem}.table-scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{padding:1rem .85rem;border-bottom:1px solid #dfe3e8;text-align:left}th{color:#565d67;font-size:.76rem;text-transform:uppercase;letter-spacing:.06em}td small{display:block;margin-top:.25rem;color:#68717d}.numeric{text-align:right}.empty,.empty-cell{padding:3rem 1rem!important;color:#68717d;text-align:center!important}.report-state{display:flex;align-items:center;justify-content:center;min-height:280px;border-top:1px solid #cbd0d6;border-bottom:1px solid #cbd0d6}.report-state--error{flex-direction:column;gap:.7rem;color:#8f1d14}.report-state--error span{color:#565d67}.report-state--error button{margin-top:.5rem}@media(max-width:900px){.reports-page{padding:2rem 1rem 4rem}.report-filters{grid-template-columns:repeat(2,1fr)}.ai-assistant{grid-template-columns:1fr}.ai-result{grid-column:1}.report-summary{grid-template-columns:1fr}.summary-primary{border-right:0;border-bottom:1px solid #3a414d}.reports-grid{grid-template-columns:1fr}.report-panel+ .report-panel{padding-left:0;border-left:0;border-top:1px solid #cbd0d6}.report-panel:first-child{padding-right:0}}@media(max-width:560px){.reports-heading{align-items:start;flex-direction:column}.report-actions{display:grid;grid-template-columns:1fr 1fr;width:100%}.refresh{grid-column:1/-1}.report-filters{grid-template-columns:1fr}.report-filters button{width:100%}.ai-assistant{padding:1.3rem}.ai-form>div,.ai-result{flex-direction:column}.ai-form input{border-right:1px solid #7f8ba0;border-radius:7px}.ai-form button{min-height:48px;border-radius:7px}.report-summary dl{grid-template-columns:1fr}.report-summary dl div,.report-summary dl div:nth-child(odd){border-right:0;border-bottom:1px solid #3a414d}.summary-primary{padding:1.6rem}.report-summary dl div{padding:1.25rem 1.6rem}.bars{gap:10px}.bar-column{min-width:44px}}
    .ai-result{display:block}.ai-result>header{display:flex;justify-content:space-between;gap:2rem;align-items:end}.ai-result>header p{max-width:580px}.ai-result-side{display:grid;justify-items:end;gap:.75rem}.ai-export-actions{display:flex;gap:.5rem}.ai-export-actions button{min-height:38px;padding:.45rem .8rem;border:1px solid #064fe8;border-radius:8px;background:transparent;color:#064fe8;font:inherit;font-size:.8rem;font-weight:800;cursor:pointer}.ai-export-actions button:hover{background:#064fe8;color:#fff}.ai-export-actions button:disabled{cursor:wait;opacity:.55}.ai-applied-filters{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:1rem}.ai-applied-filters span{padding:.3rem .6rem;border:1px solid #8fa5ce;border-radius:999px;color:#26344a;font-size:.72rem;font-weight:700}.ai-clarification{margin-top:1.25rem;padding:1rem 1.1rem;border:1px solid #8fa5ce;background:#fff}.ai-clarification p{margin:.35rem 0 0}.ai-metrics{display:grid;grid-template-columns:repeat(4,1fr);margin:1.5rem 0 0;border-block:1px solid #b9c9ef}.ai-metrics--three{grid-template-columns:repeat(3,1fr)}.ai-metrics div{padding:1rem;border-right:1px solid #b9c9ef}.ai-metrics div:last-child{border-right:0}.ai-metrics dt{color:#59677c;font-size:.75rem}.ai-metrics dd{margin:.35rem 0 0;font-size:1.35rem;font-weight:800}.ai-comparison{display:grid;gap:.65rem;margin-top:1.25rem}.ai-comparison>div{display:grid;grid-template-columns:minmax(110px,.45fr) minmax(180px,1fr) minmax(110px,.35fr);gap:.8rem;align-items:center}.ai-comparison span{overflow:hidden;color:#26344a;text-overflow:ellipsis;white-space:nowrap}.ai-comparison i{height:9px;background:#d6e0f6}.ai-comparison b{display:block;height:100%;min-width:3px;background:#064fe8}.ai-comparison strong{text-align:right;font-size:.82rem}.ai-table{max-height:340px;margin-top:1rem;overflow:auto;background:#fff}.ai-table table{min-width:680px}.ai-table th,.ai-table td{padding:.8rem}.ai-chart{display:flex;align-items:end;gap:5px;height:170px;margin-top:1.25rem;padding-top:1rem;border-bottom:1px solid #8fa5ce;overflow-x:auto}.ai-chart>div{display:grid;grid-template-rows:1fr 24px;align-items:end;justify-items:center;min-width:32px;height:100%}.ai-chart i{display:block;width:18px;min-height:3px;background:#064fe8}.ai-chart time{font-size:.65rem;color:#59677c}.ai-empty{padding:2rem!important;text-align:center!important;color:#59677c}@media(max-width:700px){.ai-result>header{align-items:start;flex-direction:column}.ai-result-side{justify-items:start}.ai-metrics,.ai-metrics--three{grid-template-columns:repeat(2,1fr)}.ai-metrics div:nth-child(2){border-right:0}.ai-comparison>div{grid-template-columns:90px 1fr}.ai-comparison strong{grid-column:2;text-align:left}}
    .ai-query-row{display:flex}.ai-form .ai-submit{min-width:120px;border:0;border-radius:0 7px 7px 0;background:#064fe8;color:#fff;font:inherit;font-weight:800}.voice-button{display:grid;place-items:center;flex:0 0 52px;min-width:52px;min-height:52px;border:1px solid #7f8ba0;border-radius:0;background:#fff;color:#064fe8;cursor:pointer}.voice-button svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round}.voice-button--recording{background:#fff3f1;color:#b42318}.voice-stop{width:13px;height:13px;border-radius:2px;background:currentColor}.voice-spinner{width:18px;height:18px;border:2px solid #b9c9ef;border-top-color:#064fe8;border-radius:50%;animation:voice-spin .7s linear infinite}.voice-status{min-height:1.35rem;margin:.5rem 0 0;color:#505a68;font-size:.82rem}.recording-dot{display:inline-block;width:8px;height:8px;margin-right:.35rem;border-radius:50%;background:#b42318;animation:voice-pulse 1.2s ease-in-out infinite}@keyframes voice-spin{to{transform:rotate(360deg)}}@keyframes voice-pulse{50%{opacity:.35}}@media(max-width:560px){.ai-query-row{display:grid;grid-template-columns:1fr 52px}.ai-query-row input{min-width:0;border-right:0;border-radius:7px 0 0 7px;font-size:16px}.voice-button{border-radius:0 7px 7px 0}.ai-form .ai-submit{grid-column:1/-1;min-height:48px;margin-top:.6rem;border-radius:7px}}
  `],
})
export class ReportsAdmin implements OnInit, OnDestroy {
  private readonly reportsService = inject(ReportsService);
  private readonly catalogService = inject(CatalogService);
  readonly branches = signal<Branch[]>([]);
  readonly sales = signal<SalesReport | null>(null);
  readonly products = signal<ProductReport | null>(null);
  readonly inventory = signal<InventoryReport | null>(null);
  readonly customers = signal<CustomerReport | null>(null);
  readonly loading = signal(false);
  readonly exporting = signal<'' | 'xlsx' | 'pdf'>('');
  readonly error = signal('');
  readonly aiLoading = signal(false);
  readonly aiExporting = signal<'' | 'xlsx' | 'pdf'>('');
  readonly aiError = signal('');
  readonly aiResult = signal<AIReportResponse | null>(null);
  readonly voiceRecording = signal(false);
  readonly voiceTranscribing = signal(false);
  readonly voiceSeconds = signal(0);
  readonly voiceMessage = signal('');
  private mediaRecorder: MediaRecorder | null = null;
  private mediaStream: MediaStream | null = null;
  private voiceChunks: Blob[] = [];
  private voiceTimer: ReturnType<typeof setInterval> | null = null;
  readonly healthyStockPercent = computed(() => {
    const report = this.inventory();
    if (!report?.items.length) return 0;
    return Math.max(0, Math.round(((report.items.length - report.items_criticos) / report.items.length) * 100));
  });
  dateFrom = this.isoDate(new Date(new Date().setDate(new Date().getDate() - 89)));
  dateTo = this.isoDate(new Date());
  branchId: number | null = null;
  aiQuestion = '';

  ngOnInit() {
    this.catalogService.branches().subscribe({ next: (items) => this.branches.set(items) });
    this.loadReports();
  }

  ngOnDestroy() {
    this.stopVoiceTracks();
  }

  async toggleVoiceRecording() {
    if (this.voiceRecording()) {
      this.mediaRecorder?.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      this.voiceMessage.set('Este navegador no permite grabar audio. Puedes escribir tu consulta.');
      return;
    }
    this.voiceMessage.set('');
    this.aiError.set('');
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = this.voiceMimeType();
      this.mediaRecorder = mimeType
        ? new MediaRecorder(this.mediaStream, { mimeType })
        : new MediaRecorder(this.mediaStream);
      this.voiceChunks = [];
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size) this.voiceChunks.push(event.data);
      };
      this.mediaRecorder.onstop = () => this.finishVoiceRecording();
      this.mediaRecorder.start();
      this.voiceRecording.set(true);
      this.voiceSeconds.set(0);
      this.voiceTimer = setInterval(() => {
        const seconds = this.voiceSeconds() + 1;
        this.voiceSeconds.set(seconds);
        if (seconds >= 60 && this.mediaRecorder?.state === 'recording') this.mediaRecorder.stop();
      }, 1000);
    } catch (error) {
      const denied = error instanceof DOMException && error.name === 'NotAllowedError';
      this.voiceMessage.set(denied
        ? 'Permite el acceso al micrófono para dictar tu consulta.'
        : 'No pudimos iniciar el micrófono. Puedes escribir tu consulta.');
      this.stopVoiceTracks();
    }
  }

  private finishVoiceRecording() {
    const type = this.mediaRecorder?.mimeType || 'audio/webm';
    const audio = new Blob(this.voiceChunks, { type });
    this.voiceRecording.set(false);
    this.stopVoiceTracks();
    if (!audio.size) {
      this.voiceMessage.set('No se detectó audio. Intenta grabar nuevamente.');
      return;
    }
    this.voiceTranscribing.set(true);
    this.voiceMessage.set('');
    this.reportsService.transcribeVoice(audio)
      .pipe(finalize(() => this.voiceTranscribing.set(false)))
      .subscribe({
        next: ({ texto }) => {
          this.aiQuestion = texto;
          this.voiceMessage.set('Texto listo. Revísalo y presiona Consultar.');
        },
        error: (error) => this.voiceMessage.set(
          error?.error?.detail ?? 'No pudimos transcribir la grabación. Intenta nuevamente.',
        ),
      });
  }

  private stopVoiceTracks() {
    if (this.voiceTimer) clearInterval(this.voiceTimer);
    this.voiceTimer = null;
    this.mediaStream?.getTracks().forEach((track) => track.stop());
    this.mediaStream = null;
  }

  private voiceMimeType() {
    return ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
      .find((type) => MediaRecorder.isTypeSupported(type)) ?? '';
  }

  applyFilters() { if (this.dateFrom <= this.dateTo) this.loadReports(); }

  loadReports() {
    const filters: ReportFilters = { desde: this.dateFrom, hasta: this.dateTo, id_sucursal: this.branchId };
    this.loading.set(true); this.error.set('');
    forkJoin({
      sales: this.reportsService.sales(filters), products: this.reportsService.products(filters),
      inventory: this.reportsService.inventory(filters), customers: this.reportsService.customers(filters),
    }).pipe(finalize(() => this.loading.set(false))).subscribe({
      next: (data) => { this.sales.set(data.sales); this.products.set(data.products); this.inventory.set(data.inventory); this.customers.set(data.customers); },
      error: (error) => this.error.set(error?.error?.detail ?? 'Verifica tu conexión y vuelve a intentarlo.'),
    });
  }

  exportReport(format: 'xlsx' | 'pdf') {
    const filters: ReportFilters = { desde: this.dateFrom, hasta: this.dateTo, id_sucursal: this.branchId };
    this.exporting.set(format); this.error.set('');
    this.reportsService.export(filters, format).pipe(finalize(() => this.exporting.set(''))).subscribe({
      next: (response) => {
        if (!response.body) return;
        const disposition = response.headers.get('content-disposition') ?? '';
        const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? `reporte-comercial.${format}`;
        const url = URL.createObjectURL(response.body);
        const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
        URL.revokeObjectURL(url);
      },
      error: (error) => this.error.set(error?.error?.detail ?? 'No pudimos exportar el reporte.'),
    });
  }

  askAssistant() {
    const question = this.aiQuestion.trim();
    if (!question) return;
    this.aiLoading.set(true); this.aiError.set(''); this.aiResult.set(null);
    this.reportsService.askAssistant(question, this.branchId)
      .pipe(finalize(() => this.aiLoading.set(false)))
      .subscribe({
        next: (result) => this.aiResult.set(result),
        error: (error) => this.aiError.set(error?.error?.detail ?? 'No pudimos consultar al asistente.'),
      });
  }

  exportAssistant(format: 'xlsx' | 'pdf') {
    const result = this.aiResult();
    if (!result || result.interpretacion.necesita_aclaracion) return;
    this.aiExporting.set(format); this.aiError.set('');
    this.reportsService.exportAssistant(result, this.branchId, format)
      .pipe(finalize(() => this.aiExporting.set('')))
      .subscribe({
        next: (response) => {
          if (!response.body) return;
          const disposition = response.headers.get('content-disposition') ?? '';
          const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? `reporte-generado.${format}`;
          const url = URL.createObjectURL(response.body);
          const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
          URL.revokeObjectURL(url);
        },
        error: (error) => this.aiError.set(error?.error?.detail ?? 'No pudimos exportar este reporte.'),
      });
  }

  aiAppliedFilters() {
    const plan = this.aiResult()?.interpretacion;
    if (!plan) return [];
    const selectedBranch = this.branches().find((item) => item.id_sucursal === this.branchId)?.nombre;
    return [
      `Período: ${this.aiPeriodLabel()}`,
      `Sucursal: ${plan.sucursal || selectedBranch || 'todas'}`,
      plan.categoria ? `Categoría: ${plan.categoria}` : '',
      plan.producto ? `Producto: ${plan.producto}` : '',
      `Agrupación: ${plan.agrupacion.toLocaleLowerCase('es')}`,
    ].filter(Boolean);
  }

  aiPeriodLabel() {
    const result = this.aiResult();
    if (result?.interpretacion.tipo_reporte === 'INVENTARIO') return 'estado actual';
    const plan = result?.interpretacion;
    if (plan?.fecha_desde && plan.fecha_hasta) return `${plan.fecha_desde} — ${plan.fecha_hasta}`;
    return `${plan?.dias ?? 0} días`;
  }

  aiSales(): SalesReport | null {
    const result = this.aiResult();
    return result?.interpretacion.tipo_reporte === 'VENTAS' && result.interpretacion.agrupacion !== 'SUCURSAL'
      ? result.datos as unknown as SalesReport : null;
  }

  aiBranchSales(): BranchSalesReport | null {
    const result = this.aiResult();
    return result?.interpretacion.tipo_reporte === 'VENTAS' && result.interpretacion.agrupacion === 'SUCURSAL'
      ? result.datos as unknown as BranchSalesReport : null;
  }

  aiProducts(): ProductReport | null {
    const result = this.aiResult();
    return result?.interpretacion.tipo_reporte === 'PRODUCTOS'
      ? result.datos as unknown as ProductReport : null;
  }

  aiInventory(): InventoryReport | null {
    const result = this.aiResult();
    return result?.interpretacion.tipo_reporte === 'INVENTARIO'
      ? result.datos as unknown as InventoryReport : null;
  }

  aiCustomers(): CustomerReport | null {
    const result = this.aiResult();
    return result?.interpretacion.tipo_reporte === 'CLIENTES'
      ? result.datos as unknown as CustomerReport : null;
  }

  aiCategories(): CategoryRevenueReport | null {
    const result = this.aiResult();
    return result?.interpretacion.tipo_reporte === 'INGRESOS_CATEGORIA'
      ? result.datos as unknown as CategoryRevenueReport : null;
  }

  aiSummarySales(): SalesReport | null {
    const result = this.aiResult();
    if (result?.interpretacion.tipo_reporte !== 'RESUMEN') return null;
    return (result.datos['ventas'] ?? null) as SalesReport | null;
  }

  aiBarHeight(value: number, report: SalesReport) {
    const maximum = Math.max(...report.serie.map((item) => item.ingresos), 0);
    return maximum ? Math.max(3, Math.round((value / maximum) * 100)) : 3;
  }

  branchRevenueValues(report: BranchSalesReport) {
    return report.sucursales.map((item) => item.ingresos);
  }

  categoryRevenueValues(report: CategoryRevenueReport) {
    return report.categorias.map((item) => item.ingresos);
  }

  comparisonWidth(value: number, values: number[]) {
    const maximum = Math.max(...values, 0);
    return maximum ? Math.max(2, Math.round((value / maximum) * 100)) : 2;
  }

  barHeight(value: number) {
    const maximum = Math.max(...(this.sales()?.serie.map((item) => item.ingresos) ?? [0]));
    return maximum ? Math.max(3, Math.round((value / maximum) * 100)) : 3;
  }

  private isoDate(value: Date) { return value.toISOString().slice(0, 10); }
}
