import { Component, effect, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { PermissionService } from '../../core/permissions/permission.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';
import { NotificationBell } from '../../shared/components/notification-bell/notification-bell';
import { CommerceService } from '../../core/services/commerce.service';

@Component({
  selector: 'app-site-header',
  imports: [RouterLink, RouterLinkActive, NotificationBell],
  template: `
    <header class="site-header">
      <a class="brand" routerLink="/" [attr.aria-label]="tenant.name() + ', ir al inicio'">
        <img [src]="tenant.logoUrl()" [alt]="tenant.name()" class="brand-logo" />
      </a>
      <button
        class="menu-button"
        type="button"
        (click)="menuOpen.update((value) => !value)"
        [attr.aria-expanded]="menuOpen()"
        aria-controls="public-navigation"
      >
        Menú
      </button>
      <nav
        id="public-navigation"
        class="site-nav"
        [class.site-nav--open]="menuOpen()"
        aria-label="Navegación principal"
      >
        <a
          routerLink="/"
          routerLinkActive="active"
          [routerLinkActiveOptions]="{ exact: true }"
          (click)="closeMenu()"
          >Inicio</a
        >
        <a routerLink="/catalogo" routerLinkActive="active" (click)="closeMenu()">Catálogo</a>
        @if (auth.currentUser()) {
          @if (!permissions.hasAdminAccess()) {
            <a class="nav-cart-link" routerLink="/carrito" routerLinkActive="active" (click)="closeMenu()"
              [attr.aria-label]="commerce.cartCount() ? 'Carrito, ' + commerce.cartCount() + (commerce.cartCount() === 1 ? ' prenda' : ' prendas') : 'Carrito vacío'">
              <span>Carrito</span>
              @if (commerce.cartCount() > 0) {
                <span class="nav-cart-count" aria-hidden="true">{{ commerce.cartCount() > 99 ? '99+' : commerce.cartCount() }}</span>
              }
            </a>
            <span class="sr-only" role="status" aria-live="polite" aria-atomic="true">{{ commerce.cartCount() ? commerce.cartCount() + (commerce.cartCount() === 1 ? ' prenda en el carrito' : ' prendas en el carrito') : '' }}</span>
          }
          <app-notification-bell mode="public" />
          @if (permissions.hasAdminAccess()) {
            <a
              class="nav-admin-badge"
              routerLink="/admin"
              routerLinkActive="active"
              (click)="closeMenu()"
              title="Ir al panel operativo"
              aria-label="Ir al panel operativo"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                width="18"
                height="18"
                aria-hidden="true"
              >
                <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                <rect x="3" y="7" width="18" height="14" rx="3" />
                <line x1="3" y1="13" x2="10" y2="13" />
                <line x1="14" y1="13" x2="21" y2="13" />
                <rect x="10" y="11" width="4" height="5" rx="1" />
              </svg>
            </a>
          } @else {
            <a
              routerLink="/cuenta"
              routerLinkActive="active"
              (click)="closeMenu()"
              class="nav-account-link"
            >
              @if (auth.currentUser()?.avatar_url) {
                <img [src]="auth.currentUser()?.avatar_url" alt="" class="nav-avatar-mini" />
              }
              <span>Mi cuenta</span>
            </a>
            <button class="nav-action" type="button" (click)="logout()">Cerrar sesión</button>
          }
        } @else {
          <a routerLink="/login" routerLinkActive="active" (click)="closeMenu()">Ingresar</a>
          <a class="nav-signup" routerLink="/registro" (click)="closeMenu()">Crear cuenta</a>
        }
      </nav>
    </header>
  `,
  styles: `
    .nav-cart-link { display: inline-flex; align-items: center; gap: 7px; }
    .nav-cart-count { display: inline-flex; justify-content: center; align-items: center; min-width: 22px; height: 22px; padding: 0 6px; border-radius: 999px; background: var(--accent, #064fe8); color: #fff; font-size: 11px; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
  `,
})
export class SiteHeader {
  readonly auth = inject(AuthService);
  readonly permissions = inject(PermissionService);
  readonly tenant = inject(TenantContextService);
  readonly commerce = inject(CommerceService);
  private readonly router = inject(Router);
  readonly menuOpen = signal(false);

  constructor() {
    this.auth.restoreSession();
    effect((onCleanup) => {
      const user = this.auth.currentUser();
      const tenantId = this.tenant.tenant()?.id_tenant;
      const owner = user && tenantId && !this.permissions.hasAdminAccess() ? `${tenantId}:${user.id_usuario}` : '';
      this.commerce.setCartOwner(owner);
      if (owner) {
        const request = this.commerce.cart().subscribe({ error: () => {} });
        onCleanup(() => request.unsubscribe());
      }
    });
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }
  logout(): void {
    this.auth.logout();
    this.commerce.setCartOwner('');
    this.closeMenu();
    void this.router.navigateByUrl('/');
  }
}
