import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  inject,
  isDevMode,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideRouter, Router } from '@angular/router';
import { provideServiceWorker } from '@angular/service-worker';
import { catchError, firstValueFrom, of } from 'rxjs';

import { routes } from './app.routes';
import { AuthService } from './core/auth/auth.service';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { TenantContextService } from './core/tenant/tenant-context.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideServiceWorker('ngsw-worker.js', {
      enabled: !isDevMode(),
      registrationStrategy: 'registerWhenStable:30000',
    }),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideAppInitializer(async () => {
      const auth = inject(AuthService);
      const tenant = inject(TenantContextService);
      const router = inject(Router);
      await firstValueFrom(tenant.load().pipe(catchError(() => of(null))));
      if (tenant.unavailable()) {
        await router.navigateByUrl('/servicio-no-disponible');
        return;
      }
      if (auth.token() && !auth.currentUser()) {
        await firstValueFrom(auth.loadCurrentUser().pipe(catchError(() => of(null))));
      }
    }),
  ],
};
