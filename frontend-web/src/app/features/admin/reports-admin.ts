import { CommonModule, DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { finalize } from 'rxjs/operators';
import { Branch } from '../../core/models/catalog.model';
import { CustomerReport, InventoryReport, ProductReport, SalesReport } from '../../core/models/reports.model';
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
    :host{display:block;color:#121418}.reports-page{max-width:1400px;margin:0 auto;padding:2.5rem 2rem 5rem}.reports-heading{display:flex;align-items:end;justify-content:space-between;gap:2rem;padding-bottom:1.75rem;border-bottom:1px solid #cbd0d6}.reports-heading h1{margin:0;font-size:clamp(2.25rem,4vw,3.7rem);line-height:1;letter-spacing:-.035em}.reports-heading p,.report-panel p,.report-table-section p{margin:.7rem 0 0;color:#565d67}.report-actions{display:flex;gap:.65rem}.refresh,.export{display:inline-flex;align-items:center;justify-content:center;gap:.65rem;min-height:48px;padding:.7rem 1rem;border:1px solid #121418;border-radius:8px;background:transparent;font:inherit;font-weight:700;cursor:pointer}.export{border-color:#064fe8;color:#064fe8}.refresh svg{width:19px;fill:none;stroke:currentColor;stroke-width:1.8}.refresh:hover{background:#121418;color:white}.export:hover{background:#064fe8;color:white}.refresh:disabled,.export:disabled{cursor:wait;opacity:.55}.report-filters{display:grid;grid-template-columns:repeat(3,minmax(160px,1fr)) auto;gap:1rem;align-items:end;padding:1.4rem 0 2.5rem}.report-filters label{display:grid;gap:.45rem;font-size:.83rem;font-weight:700}.report-filters input,.report-filters select{min-height:48px;padding:.65rem .8rem;border:1px solid #aab1ba;border-radius:8px;background:#fff;color:#121418;font:inherit}.report-filters button,.report-state button{min-height:48px;padding:.7rem 1.35rem;border:1px solid #064fe8;border-radius:8px;background:#064fe8;color:#fff;font:inherit;font-weight:700;cursor:pointer}.report-filters :focus-visible,.refresh:focus-visible,.export:focus-visible,.report-state button:focus-visible{outline:3px solid rgba(6,79,232,.28);outline-offset:2px}.report-summary{display:grid;grid-template-columns:minmax(280px,.85fr) 1.5fr;background:#121720;color:#fff}.summary-primary{display:flex;flex-direction:column;justify-content:center;min-height:220px;padding:2rem 2.4rem;border-right:1px solid #3a414d}.summary-primary span{color:#b8c1ce;font-size:.85rem;font-weight:700}.summary-primary strong{margin:.45rem 0;font-size:clamp(2.7rem,5vw,4.8rem);line-height:1;font-variant-numeric:tabular-nums;letter-spacing:-.04em}.summary-primary small{color:#b8c1ce}.report-summary dl{display:grid;grid-template-columns:repeat(2,1fr);margin:0}.report-summary dl div{display:flex;flex-direction:column;justify-content:center;padding:1.7rem 2rem;border-bottom:1px solid #3a414d}.report-summary dl div:nth-child(odd){border-right:1px solid #3a414d}.report-summary dl div:nth-child(n+3){border-bottom:0}.report-summary dt{color:#b8c1ce;font-size:.82rem}.report-summary dd{margin:.35rem 0 0;font-size:1.55rem;font-weight:700;font-variant-numeric:tabular-nums}.reports-grid{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(280px,.75fr);border-bottom:1px solid #cbd0d6}.report-panel{min-height:340px;padding:2rem 0}.report-panel+ .report-panel{padding-left:2rem;border-left:1px solid #cbd0d6}.report-panel:first-child{padding-right:2rem}.report-panel h2,.report-table-section h2{margin:0;font-size:1.45rem;letter-spacing:-.025em}.bars{display:flex;align-items:end;gap:max(5px,1.1vw);height:220px;margin-top:2rem;padding-top:2rem;border-bottom:1px solid #aab1ba;overflow-x:auto}.bar-column{display:grid;grid-template-rows:24px 1fr 28px;align-items:end;justify-items:center;min-width:max(42px,calc((100% - 2rem)/var(--bar-count)));height:100%}.bar-column i{display:block;width:min(28px,65%);min-height:3px;background:#064fe8}.bar-column time{padding-top:.55rem;color:#565d67;font-size:.72rem}.bar-value{opacity:0;font-size:.68rem;white-space:nowrap;transition:opacity .15s}.bar-column:hover .bar-value{opacity:1}.stock-reading{display:flex;align-items:baseline;gap:.7rem;margin-top:4rem}.stock-reading strong{font-size:3.5rem;line-height:1;font-variant-numeric:tabular-nums}.stock-reading span{color:#565d67}.stock-rule{height:8px;margin:1.5rem 0;background:#dfe3e8}.stock-rule span{display:block;height:100%;background:#064fe8}.report-table-section{padding:2.5rem 0;border-bottom:1px solid #cbd0d6}.report-table-section header{margin-bottom:1.5rem}.table-scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{padding:1rem .85rem;border-bottom:1px solid #dfe3e8;text-align:left}th{color:#565d67;font-size:.76rem;text-transform:uppercase;letter-spacing:.06em}td small{display:block;margin-top:.25rem;color:#68717d}.numeric{text-align:right}.empty,.empty-cell{padding:3rem 1rem!important;color:#68717d;text-align:center!important}.report-state{display:flex;align-items:center;justify-content:center;min-height:280px;border-top:1px solid #cbd0d6;border-bottom:1px solid #cbd0d6}.report-state--error{flex-direction:column;gap:.7rem;color:#8f1d14}.report-state--error span{color:#565d67}.report-state--error button{margin-top:.5rem}@media(max-width:900px){.reports-page{padding:2rem 1rem 4rem}.report-filters{grid-template-columns:repeat(2,1fr)}.report-summary{grid-template-columns:1fr}.summary-primary{border-right:0;border-bottom:1px solid #3a414d}.reports-grid{grid-template-columns:1fr}.report-panel+ .report-panel{padding-left:0;border-left:0;border-top:1px solid #cbd0d6}.report-panel:first-child{padding-right:0}}@media(max-width:560px){.reports-heading{align-items:start;flex-direction:column}.report-actions{display:grid;grid-template-columns:1fr 1fr;width:100%}.refresh{grid-column:1/-1}.report-filters{grid-template-columns:1fr}.report-filters button{width:100%}.report-summary dl{grid-template-columns:1fr}.report-summary dl div,.report-summary dl div:nth-child(odd){border-right:0;border-bottom:1px solid #3a414d}.summary-primary{padding:1.6rem}.report-summary dl div{padding:1.25rem 1.6rem}.bars{gap:10px}.bar-column{min-width:44px}}
  `],
})
export class ReportsAdmin implements OnInit {
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
  readonly healthyStockPercent = computed(() => {
    const report = this.inventory();
    if (!report?.items.length) return 0;
    return Math.max(0, Math.round(((report.items.length - report.items_criticos) / report.items.length) * 100));
  });
  dateFrom = this.isoDate(new Date(new Date().setDate(new Date().getDate() - 89)));
  dateTo = this.isoDate(new Date());
  branchId: number | null = null;

  ngOnInit() {
    this.catalogService.branches().subscribe({ next: (items) => this.branches.set(items) });
    this.loadReports();
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

  barHeight(value: number) {
    const maximum = Math.max(...(this.sales()?.serie.map((item) => item.ingresos) ?? [0]));
    return maximum ? Math.max(3, Math.round((value / maximum) * 100)) : 3;
  }

  private isoDate(value: Date) { return value.toISOString().slice(0, 10); }
}
