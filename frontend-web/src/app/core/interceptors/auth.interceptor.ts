import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../auth/auth.service';
import { TenantHostService } from '../tenant/tenant-context.service';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const tenantHost = inject(TenantHostService);
  const token = auth.token();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (tenantHost.slug && !request.url.includes('/platform/')) {
    headers['X-Tenant-Slug'] = tenantHost.slug;
  }
  const authorizedRequest = Object.keys(headers).length
    ? request.clone({ setHeaders: headers })
    : request;

  return next(authorizedRequest).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && token) {
        auth.logout();
        const loginPath = tenantHost.isPlatformSurface ? '/platform/login' : '/login';
        void router.navigate([loginPath], { queryParams: { sesion: 'expirada' } });
      }
      return throwError(() => error);
    }),
  );
};
