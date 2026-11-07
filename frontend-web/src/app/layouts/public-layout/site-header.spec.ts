import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { AuthService } from '../../core/auth/auth.service';
import { PermissionService } from '../../core/permissions/permission.service';
import { CommerceService } from '../../core/services/commerce.service';
import { SiteHeader } from './site-header';
import { TenantContextService } from '../../core/tenant/tenant-context.service';

describe('SiteHeader', () => {
  function setup(authenticated = true, hasAdmin = true) {
    const userSignal = signal(
      authenticated
        ? {
            id_usuario: 1,
            nombres: 'José Carlos',
            apellidos: 'Villarroel Dueñas',
            correo: 'jose@capricho.com',
            estado: 'ACTIVO' as const,
            roles: hasAdmin ? ['ADMIN'] : ['CLIENTE'],
            permisos: hasAdmin ? ['admin.total', 'productos.ver'] : [],
            sucursal: null,
            telefono: null,
            ci: null,
            created_at: '2026-01-01',
          }
        : null,
    );

    const authServiceMock = {
      currentUser: userSignal,
      restoreSession: vi.fn(),
      logout: vi.fn(),
    };

    const permissionServiceMock = {
      hasAdminAccess: signal(hasAdmin),
      has: vi.fn((perm: string) => hasAdmin),
      hasAny: vi.fn((perms: readonly string[]) => hasAdmin),
    };

    const cartCount = signal(0);
    const commerceServiceMock = {
      notifications: vi.fn(() => of([])),
      cartCount,
      setCartOwner: vi.fn(() => cartCount.set(0)),
      cart: vi.fn(() => of({ items: [], total: '0' })),
    };
    const tenantMock = { tenant: signal({ id_tenant: 7 }), name: signal('Capricho Store'), logoUrl: signal('/logo.png') };

    TestBed.configureTestingModule({
      imports: [SiteHeader],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authServiceMock },
        { provide: PermissionService, useValue: permissionServiceMock },
        { provide: CommerceService, useValue: commerceServiceMock },
        { provide: TenantContextService, useValue: tenantMock },
      ],
    });

    const fixture = TestBed.createComponent(SiteHeader);
    fixture.detectChanges();

    return { fixture, component: fixture.componentInstance, authServiceMock, commerceServiceMock, tenantMock };
  }

  it('hides Carrito, Mi cuenta and Cerrar sesión for admin staff, rendering only the briefcase icon button pointing to /admin', () => {
    const { fixture } = setup(true, true);

    const links = fixture.debugElement.queryAll(By.css('a'));
    const linkTexts = links.map((l) => l.nativeElement.textContent.trim());

    // Admin should NOT see Carrito
    expect(linkTexts).not.toContain('Carrito');

    // Admin should NOT see Mi cuenta in the public header
    expect(linkTexts).not.toContain('Mi cuenta');

    // Admin should NOT see Cerrar sesión in the public header
    const logoutBtn = fixture.debugElement.query(By.css('.nav-action'));
    expect(logoutBtn).toBeNull();

    // Admin should see briefcase icon button pointing to /admin without text "Panel"
    const adminBadge = fixture.debugElement.query(By.css('.nav-admin-badge'));
    expect(adminBadge).toBeTruthy();
    expect(adminBadge.attributes['routerLink']).toBe('/admin');
    expect(adminBadge.nativeElement.textContent.trim()).toBe('');
    expect(adminBadge.query(By.css('svg'))).toBeTruthy();
  });

  it('renders Carrito, hides Panel badge and links Mi cuenta to /cuenta for regular customers', () => {
    const { fixture } = setup(true, false);

    const links = fixture.debugElement.queryAll(By.css('a'));
    const linkTexts = links.map((l) => l.nativeElement.textContent.trim());

    // Customer SHOULD see Carrito
    expect(linkTexts).toContain('Carrito');

    // Customer should NOT see the admin badge
    const adminBadge = fixture.debugElement.query(By.css('.nav-admin-badge'));
    expect(adminBadge).toBeNull();

    // Customer Mi cuenta should point to /cuenta
    const myAccountLink = links.find((l) => l.nativeElement.textContent.trim() === 'Mi cuenta');
    expect(myAccountLink).toBeTruthy();
    expect(myAccountLink?.attributes['routerLink']).toBe('/cuenta');
  });

  it('renders Ingresar and Crear cuenta for unauthenticated visitors', () => {
    const { fixture } = setup(false, false);

    const links = fixture.debugElement.queryAll(By.css('a'));
    const linkTexts = links.map((l) => l.nativeElement.textContent.trim());

    expect(linkTexts).toContain('Ingresar');
    expect(linkTexts).toContain('Crear cuenta');
    expect(linkTexts).not.toContain('Carrito');
    expect(linkTexts).not.toContain('Mi cuenta');
  });

  it('hydrates the customer cart and displays its total units accessibly', () => {
    const { fixture, commerceServiceMock } = setup(true, false);
    expect(commerceServiceMock.cart).toHaveBeenCalledOnce();
    expect(commerceServiceMock.setCartOwner).toHaveBeenCalledWith('7:1');
    commerceServiceMock.cartCount.set(5);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.nav-cart-count').textContent).toBe('5');
    expect(fixture.nativeElement.querySelector('.nav-cart-link').getAttribute('aria-label')).toBe('Carrito, 5 prendas');
    commerceServiceMock.cartCount.set(120);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.nav-cart-count').textContent).toBe('99+');
    expect(fixture.nativeElement.querySelector('.nav-cart-link').getAttribute('aria-label')).toBe('Carrito, 120 prendas');
  });

  it('clears the badge when the account or tenant changes', () => {
    const { fixture, commerceServiceMock, authServiceMock, tenantMock } = setup(true, false);
    commerceServiceMock.cartCount.set(4);
    fixture.detectChanges();
    authServiceMock.currentUser.set({ ...authServiceMock.currentUser()!, id_usuario: 2 });
    fixture.detectChanges();
    expect(commerceServiceMock.setCartOwner).toHaveBeenLastCalledWith('7:2');
    expect(fixture.nativeElement.querySelector('.nav-cart-count')).toBeNull();
    tenantMock.tenant.set({ id_tenant: 8 });
    fixture.detectChanges();
    expect(commerceServiceMock.setCartOwner).toHaveBeenLastCalledWith('8:2');
  });
});
