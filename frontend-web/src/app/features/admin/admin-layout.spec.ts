import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { AuthService } from '../../core/auth/auth.service';
import { CommerceService } from '../../core/services/commerce.service';
import { AssistantService } from '../../core/services/assistant.service';
import { AdminLayout } from './admin-layout';

describe('AdminLayout', () => {
  function setup(userOverride = {}) {
    const userSignal = signal({
      id_usuario: 1,
      nombres: 'José Carlos',
      apellidos: 'Villarroel Dueñas',
      correo: 'jose@capricho.com',
      estado: 'ACTIVO' as const,
      roles: ['ADMIN'],
      permisos: ['admin.total', 'productos.ver', 'ventas.ver'],
      sucursal: null,
      telefono: null,
      ci: null,
      created_at: '2026-01-01',
      ...userOverride,
    });

    const authServiceMock = {
      currentUser: userSignal,
      logout: vi.fn(),
      restoreSession: vi.fn(),
    };

    const commerceServiceMock = {
      notifications: vi.fn(() => of([])),
    };

    TestBed.configureTestingModule({
      imports: [AdminLayout],
      providers: [
        provideRouter([
          { path: 'login', component: class {} },
          { path: 'cuenta', component: class {} },
        ]),
        { provide: AuthService, useValue: authServiceMock },
        { provide: CommerceService, useValue: commerceServiceMock },
        { provide: AssistantService, useValue: { list: vi.fn(() => of([])) } },
      ],
    });

    const fixture = TestBed.createComponent(AdminLayout);
    fixture.detectChanges();
    const router = TestBed.inject(Router);

    return { fixture, authServiceMock, router, component: fixture.componentInstance };
  }

  it('renders only given name (without surnames) in the header user profile', () => {
    const { fixture } = setup();
    const nameEl = fixture.debugElement.query(By.css('.admin-user-profile__name'));
    expect(nameEl).toBeTruthy();
    expect(nameEl.nativeElement.textContent.trim()).toBe('José Carlos');
    expect(nameEl.nativeElement.textContent).not.toContain('Villarroel');
    expect(nameEl.nativeElement.textContent).not.toContain('Dueñas');
  });

  it('renders avatar initial and role and branch labels in the header', () => {
    const { fixture } = setup();
    const avatarEl = fixture.debugElement.query(By.css('.admin-user-profile__avatar'));
    const roleEl = fixture.debugElement.query(By.css('.admin-user-profile__role'));
    const branchEl = fixture.debugElement.query(By.css('.admin-user-profile__branch'));

    expect(avatarEl.nativeElement.textContent.trim()).toBe('J');
    expect(roleEl.nativeElement.textContent.trim()).toBe('ADMIN');
    expect(branchEl.nativeElement.textContent.trim()).toBe('Todas las sucursales');
  });

  it('renders assigned branch name when role is not ADMIN', () => {
    const { fixture } = setup({
      roles: ['CAJERO'],
      sucursal: 'Sucursal Central',
    });
    const branchEl = fixture.debugElement.query(By.css('.admin-user-profile__branch'));
    expect(branchEl.nativeElement.textContent.trim()).toBe('Sucursal asignada: Sucursal Central');
  });

  it('includes store button pointing to root URL in header', () => {
    const { fixture } = setup();
    const storeBtn = fixture.debugElement.query(By.css('.admin-store-btn'));
    expect(storeBtn).toBeTruthy();
    expect(storeBtn.attributes['routerLink']).toBe('/');
  });

  it('includes Mi cuenta link and Cerrar sesión button in sidebar footer', () => {
    const { fixture, authServiceMock } = setup();
    const accountLink = fixture.debugElement.query(By.css('.admin-sidebar-footer__link'));
    const logoutBtn = fixture.debugElement.query(By.css('.admin-sidebar-footer__logout'));

    expect(accountLink).toBeTruthy();
    expect(accountLink.attributes['routerLink']).toBe('/admin/perfil');
    expect(accountLink.nativeElement.textContent).toContain('Mi cuenta');

    expect(logoutBtn).toBeTruthy();
    expect(logoutBtn.nativeElement.textContent).toContain('Cerrar sesión');

    logoutBtn.nativeElement.click();
    expect(authServiceMock.logout).toHaveBeenCalledTimes(1);
  });

  it('renders avatar image when avatar_url is present', () => {
    const { fixture } = setup({
      avatar_url: 'https://res.cloudinary.com/capricho/avatar.jpg',
    });
    const imgEl = fixture.debugElement.query(By.css('.admin-user-profile__avatar-img'));
    expect(imgEl).toBeTruthy();
    expect(imgEl.nativeElement.getAttribute('src')).toBe('https://res.cloudinary.com/capricho/avatar.jpg');
  });
});
