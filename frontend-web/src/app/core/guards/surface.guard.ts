import { inject } from '@angular/core';
import { CanMatchFn } from '@angular/router';
import { TenantHostService } from '../tenant/tenant-context.service';

export const mainSurfaceGuard: CanMatchFn = () => inject(TenantHostService).slug === null;

export const tenantSurfaceGuard: CanMatchFn = () => inject(TenantHostService).slug !== null;
