import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, Observable, of } from 'rxjs';
import { AuthService } from '../auth/auth.service';
import { ADMIN_PERMISSIONS, PermissionService } from '../permissions/permission.service';
import { UserResponse } from '../models/auth.model';

function resolveUser(auth: AuthService): Observable<UserResponse | null> {
  const user = auth.currentUser();
  return user ? of(user) : auth.loadCurrentUser().pipe(catchError(() => of(null)));
}

export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const permissions = inject(PermissionService);
  const router = inject(Router);
  if (!auth.token())
    return router.createUrlTree(['/login'], { queryParams: { returnUrl: '/admin' } });
  return resolveUser(auth).pipe(
    map((user) =>
      user && permissions.hasAny(ADMIN_PERMISSIONS) ? true : router.createUrlTree(['/admin/403']),
    ),
  );
};

export const requireAnyPermission =
  (...required: string[]): CanActivateFn =>
  () => {
    const auth = inject(AuthService);
    const permissions = inject(PermissionService);
    const router = inject(Router);
    if (!auth.token()) return router.createUrlTree(['/login']);
    return resolveUser(auth).pipe(
      map((user) =>
        user && permissions.hasAny(required) ? true : router.createUrlTree(['/admin/403']),
      ),
    );
  };

export const requireAllPermissions =
  (...permissions: readonly string[]): CanActivateFn =>
  () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    if (!auth.token()) return router.createUrlTree(['/login']);
    return resolveUser(auth).pipe(
      map((user) =>
        user && permissions.every((permission) => user.permisos.includes(permission))
          ? true
          : router.createUrlTree(['/admin/403']),
      ),
    );
  };

export const platformGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.token()) {
    return router.createUrlTree(['/platform/login'], { queryParams: { returnUrl: '/platform' } });
  }
  return resolveUser(auth).pipe(
    map((user) =>
      user?.roles.includes('SUPERADMIN') &&
      user.permisos.some((permission) => permission.startsWith('platform.'))
        ? true
        : router.createUrlTree(['/admin/403']),
    ),
  );
};
