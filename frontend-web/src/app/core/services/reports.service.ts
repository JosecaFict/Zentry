import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { API_BASE_URL } from '../config/api.config';
import { CustomerReport, InventoryReport, ProductReport, SalesReport } from '../models/reports.model';

export interface ReportFilters { desde: string; hasta: string; id_sucursal?: number | null; }

@Injectable({ providedIn: 'root' })
export class ReportsService {
  private readonly http = inject(HttpClient);

  private params(filters: ReportFilters, extra?: Record<string, string | number | boolean>) {
    let params = new HttpParams().set('desde', filters.desde).set('hasta', filters.hasta);
    if (filters.id_sucursal) params = params.set('id_sucursal', filters.id_sucursal);
    Object.entries(extra ?? {}).forEach(([key, value]) => (params = params.set(key, value)));
    return params;
  }

  sales(filters: ReportFilters) {
    return this.http.get<SalesReport>(`${API_BASE_URL}/admin/reports/sales`, { params: this.params(filters) });
  }
  products(filters: ReportFilters) {
    return this.http.get<ProductReport>(`${API_BASE_URL}/admin/reports/products`, {
      params: this.params(filters, { limite: 10 }),
    });
  }
  inventory(filters: ReportFilters) {
    return this.http.get<InventoryReport>(`${API_BASE_URL}/admin/reports/inventory`, {
      params: this.params(filters),
    });
  }
  customers(filters: ReportFilters) {
    return this.http.get<CustomerReport>(`${API_BASE_URL}/admin/reports/customers`, {
      params: this.params(filters, { limite: 10 }),
    });
  }
}
