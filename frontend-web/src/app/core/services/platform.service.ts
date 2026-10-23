import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../config/api.config';
import {
  PlatformOverview,
  PlatformPayment,
  PlatformPaymentCreate,
  PlatformPlan,
  PlatformTenant,
  PlatformTenantCreate,
  PlatformTenantUpdate,
} from '../models/platform.model';

@Injectable({ providedIn: 'root' })
export class PlatformService {
  private readonly http = inject(HttpClient);

  overview(): Observable<PlatformOverview> {
    return this.http.get<PlatformOverview>(`${API_BASE_URL}/platform/overview`);
  }

  tenants(): Observable<PlatformTenant[]> {
    return this.http.get<PlatformTenant[]>(`${API_BASE_URL}/platform/tenants`);
  }

  createTenant(payload: PlatformTenantCreate): Observable<PlatformTenant> {
    return this.http.post<PlatformTenant>(`${API_BASE_URL}/platform/tenants`, payload);
  }

  tenant(tenantId: number): Observable<PlatformTenant> {
    return this.http.get<PlatformTenant>(`${API_BASE_URL}/platform/tenants/${tenantId}`);
  }

  updateTenant(tenantId: number, payload: PlatformTenantUpdate): Observable<PlatformTenant> {
    return this.http.put<PlatformTenant>(`${API_BASE_URL}/platform/tenants/${tenantId}`, payload);
  }

  updateTenantStatus(
    tenantId: number,
    estado: 'ACTIVO' | 'SUSPENDIDO',
  ): Observable<PlatformTenant> {
    return this.http.patch<PlatformTenant>(`${API_BASE_URL}/platform/tenants/${tenantId}/status`, {
      estado,
    });
  }

  plans(): Observable<PlatformPlan[]> {
    return this.http.get<PlatformPlan[]>(`${API_BASE_URL}/platform/plans`);
  }

  payments(tenantId: number): Observable<PlatformPayment[]> {
    return this.http.get<PlatformPayment[]>(
      `${API_BASE_URL}/platform/tenants/${tenantId}/payments`,
    );
  }

  registerPayment(tenantId: number, payload: PlatformPaymentCreate): Observable<PlatformTenant> {
    return this.http.post<PlatformTenant>(
      `${API_BASE_URL}/platform/tenants/${tenantId}/payments`,
      payload,
    );
  }
}
