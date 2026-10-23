import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { catchError, Observable, of, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { API_BASE_URL } from '../config/api.config';
import { TenantBrand, TenantBrandUpdate } from '../models/tenant.model';

const RESERVED_SUBDOMAINS = new Set(['www', 'app', 'api', 'platform']);

@Injectable({ providedIn: 'root' })
export class TenantHostService {
  readonly isPlatformSurface = window.location.pathname.startsWith('/platform');
  readonly slug = this.resolveSlug(window.location.hostname);

  private resolveSlug(hostname: string): string | null {
    const host = hostname.toLowerCase();
    if (this.isPlatformSurface) return null;
    if (host.endsWith('.localhost')) {
      return this.validSlug(host.slice(0, -'.localhost'.length));
    }
    const baseDomain = environment.tenantBaseDomain.trim().toLowerCase();
    if (baseDomain && host.endsWith(`.${baseDomain}`)) {
      return this.validSlug(host.slice(0, -(baseDomain.length + 1)));
    }
    if (host === 'localhost' || host === '127.0.0.1') {
      return environment.defaultTenantSlug || null;
    }
    return null;
  }

  private validSlug(value: string): string | null {
    return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value) && !RESERVED_SUBDOMAINS.has(value)
      ? value
      : null;
  }
}

@Injectable({ providedIn: 'root' })
export class TenantContextService {
  private readonly http = inject(HttpClient);
  private readonly host = inject(TenantHostService);
  private readonly state = signal<TenantBrand | null>(null);
  private readonly unavailableState = signal(false);

  readonly tenant = this.state.asReadonly();
  readonly unavailable = this.unavailableState.asReadonly();
  readonly name = computed(() => this.state()?.nombre || 'Tienda');
  readonly logoUrl = computed(() => {
    const tenant = this.state();
    if (tenant?.logo_url) return tenant.logo_url;
    return tenant?.slug === 'capricho-store'
      ? '/images/logo-capricho.png'
      : '/images/zentry-mark.png';
  });
  readonly adminLogoUrl = computed(() => {
    const tenant = this.state();
    if (tenant?.logo_url) return tenant.logo_url;
    return tenant?.slug === 'capricho-store'
      ? '/images/logo-capricho-white.png'
      : '/images/zentry-logo-white.png';
  });
  readonly primaryColor = computed(() => this.state()?.color_primario || '#064FE8');
  readonly primaryDarkColor = computed(() => this.state()?.color_primario_oscuro || '#0039B8');

  load(): Observable<TenantBrand | null> {
    if (!this.host.slug) return of(null);
    return this.http
      .get<TenantBrand>(`${API_BASE_URL}/tenant/context`)
      .pipe(
        tap((tenant) => {
          this.unavailableState.set(false);
          this.setTenant(tenant);
        }),
        catchError((error: HttpErrorResponse) => {
          this.unavailableState.set(error.status === 403);
          return of(null);
        }),
      );
  }

  updateBrand(payload: TenantBrandUpdate): Observable<TenantBrand> {
    return this.http
      .put<TenantBrand>(`${API_BASE_URL}/tenant/brand`, payload)
      .pipe(tap((tenant) => this.setTenant(tenant)));
  }

  private setTenant(tenant: TenantBrand): void {
    this.state.set(tenant);
    document.documentElement.style.setProperty('--accent', tenant.color_primario);
    document.documentElement.style.setProperty('--primary', tenant.color_primario);
    document.documentElement.style.setProperty('--accent-dark', tenant.color_primario_oscuro);
  }
}
