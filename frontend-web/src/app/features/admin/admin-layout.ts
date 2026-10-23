import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { AdminNavGroup, visibleAdminNavigation } from './admin-navigation';
import { NotificationBell } from '../../shared/components/notification-bell/notification-bell';
import { TenantContextService } from '../../core/tenant/tenant-context.service';

@Component({
  selector: 'app-admin-layout',
  imports: [RouterLink, RouterLinkActive, RouterOutlet, NotificationBell],
  template: `
    <!-- THESIS: Un taller operativo de moda, no un mosaico SaaS; la tarea y el estado mandan. OWN-WORLD: papel frío, grafito, líneas cromadas y cobalto reservado a acción y selección. STORY: el equipo reconoce su alcance, entra al módulo permitido y actúa con contexto. FIRST VIEWPORT: rail lateral estable, cabecera de identidad y área de trabajo densa sin tarjetas decorativas. FORM: extensión Operate del sistema aprobado. FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance -->
    <div class="admin-shell" [class.sidebar-collapsed]="sidebarCollapsed()">
      <button
        class="admin-backdrop"
        [class.is-open]="menuOpen()"
        (click)="menuOpen.set(false)"
        aria-label="Cerrar menú"
      ></button>
      <aside
        class="admin-sidebar"
        [class.is-open]="menuOpen()"
        [class.is-collapsed]="sidebarCollapsed()"
        aria-label="Navegación administrativa"
      >
        <div class="admin-brand-row">
          <a
            class="admin-brand"
            routerLink="/admin"
            (click)="menuOpen.set(false)"
            [attr.aria-label]="tenant.name() + ', ir al panel operativo'"
          >
            <img [src]="tenant.adminLogoUrl()" [alt]="tenant.name()" class="admin-brand-logo" />
          </a>
          <button
            type="button"
            class="admin-sidebar-collapse-btn"
            (click)="toggleSidebar()"
            title="Ocultar menú lateral"
            aria-label="Ocultar menú lateral"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              width="16"
              height="16"
              aria-hidden="true"
            >
              <path d="m15 18-6-6 6-6" />
            </svg>
          </button>
        </div>
        <nav>
          @for (group of visibleNavigation(); track group.label) {
            <section class="admin-nav-group" [class.is-expanded]="isGroupExpanded(group)">
              <h2>
                <button
                  type="button"
                  class="admin-nav-trigger"
                  (click)="toggleGroup(group)"
                  [attr.aria-expanded]="isGroupExpanded(group)"
                  [attr.aria-controls]="'admin-nav-group-' + $index"
                  [attr.aria-label]="
                    (isGroupExpanded(group) ? 'Ocultar ' : 'Mostrar ') + group.label
                  "
                >
                  <span>{{ group.label }}</span>
                  <svg aria-hidden="true" viewBox="0 0 16 16" fill="none">
                    <path d="M6 3.5 10.5 8 6 12.5" />
                  </svg>
                </button>
              </h2>
              <div [id]="'admin-nav-group-' + $index" [hidden]="!isGroupExpanded(group)">
                @for (item of group.items; track item.path) {
                  <a
                    [routerLink]="item.path"
                    routerLinkActive="active"
                    [routerLinkActiveOptions]="{ exact: item.exact ?? false }"
                    (click)="menuOpen.set(false)"
                    >{{ item.label }}</a
                  >
                }
              </div>
            </section>
          }
        </nav>
        <div class="admin-sidebar-footer">
          <a
            class="admin-sidebar-footer__link"
            routerLink="/admin/perfil"
            routerLinkActive="active"
            (click)="menuOpen.set(false)"
            title="Mi cuenta"
          >
            @if (user()?.avatar_url) {
              <img [src]="user()?.avatar_url" alt="" class="admin-sidebar-avatar-mini" />
            } @else {
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                width="18"
                height="18"
                aria-hidden="true"
              >
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            }
            <span>Mi cuenta</span>
          </a>
          <button
            type="button"
            class="admin-sidebar-footer__logout"
            (click)="logout()"
            title="Cerrar sesión"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              width="18"
              height="18"
              aria-hidden="true"
            >
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span>Cerrar sesión</span>
          </button>
        </div>
      </aside>
      <div class="admin-workspace">
        <header class="admin-header">
          <div class="admin-header__left">
            <button
              class="admin-menu-toggle-btn"
              type="button"
              (click)="toggleSidebar()"
              [attr.aria-label]="
                sidebarCollapsed() ? 'Mostrar menú lateral' : 'Ocultar menú lateral'
              "
              [title]="sidebarCollapsed() ? 'Mostrar menú' : 'Ocultar menú'"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                width="18"
                height="18"
                aria-hidden="true"
              >
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <div class="admin-header__titles">
              <strong class="admin-company-name">{{ tenant.name() }}</strong>
              <span class="admin-context">Panel operativo</span>
            </div>
          </div>
          <div class="admin-header__right">
            <a
              class="admin-store-btn"
              routerLink="/"
              title="Ir a la tienda pública"
              aria-label="Ir a la tienda pública"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                width="18"
                height="18"
                aria-hidden="true"
              >
                <path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7" />
                <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
                <path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4" />
                <path d="M2 7h20" />
              </svg>
              <span class="admin-store-btn__label">Tienda</span>
            </a>
            <app-notification-bell mode="admin" />
            <span class="admin-header__divider" aria-hidden="true"></span>
            <div class="admin-user-profile">
              <div
                class="admin-user-profile__avatar"
                [class.has-image]="!!user()?.avatar_url"
                aria-hidden="true"
              >
                @if (user()?.avatar_url) {
                  <img
                    [src]="user()?.avatar_url"
                    [alt]="displayName()"
                    class="admin-user-profile__avatar-img"
                  />
                } @else {
                  {{ userInitial() }}
                }
              </div>
              <div class="admin-user-profile__details">
                <span class="admin-user-profile__name">{{ displayName() }}</span>
                <span class="admin-user-profile__role">{{ roleLabel() }}</span>
                <small class="admin-user-profile__branch">{{ branchLabel() }}</small>
              </div>
            </div>
          </div>
        </header>
        @if (subscriptionMessage(); as message) {
          <aside
            class="admin-subscription-alert"
            [class.is-critical]="tenant.tenant()?.subscription_estado === 'GRACIA'"
            role="status"
          >
            <strong>{{ subscriptionTitle() }}</strong>
            <span>{{ message }}</span>
          </aside>
        }
        <main class="admin-main" id="contenido"><router-outlet /></main>
      </div>
    </div>
  `,
})
export class AdminLayout {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly tenant = inject(TenantContextService);
  readonly menuOpen = signal(false);
  readonly sidebarCollapsed = signal(false);
  readonly expandedGroups = signal<Record<string, boolean>>({});
  readonly user = this.auth.currentUser;
  readonly displayName = computed(() => this.user()?.nombres?.trim() || 'Usuario');
  readonly userInitial = computed(() => this.displayName().charAt(0).toUpperCase());
  readonly roleLabel = computed(() => this.user()?.roles.join(' · ') || 'Sin rol asignado');
  readonly branchLabel = computed(() => {
    const user = this.user();
    if (user?.roles.includes('ADMIN')) return 'Todas las sucursales';
    return user?.sucursal ? `Sucursal asignada: ${user.sucursal}` : 'Sin sucursal asignada';
  });
  readonly visibleNavigation = computed(() => visibleAdminNavigation(this.user()?.permisos ?? []));
  readonly subscriptionTitle = computed(() =>
    this.tenant.tenant()?.subscription_estado === 'GRACIA'
      ? 'La suscripción está en periodo de gracia'
      : 'La suscripción está próxima a vencer',
  );
  readonly subscriptionMessage = computed(() => {
    const context = this.tenant.tenant();
    if (!context || !this.user()?.roles.includes('ADMIN')) return null;
    if (context.subscription_estado === 'GRACIA') {
      return `Regulariza la renovación antes del ${context.fecha_fin_gracia || 'fin del periodo de gracia'} para evitar la suspensión.`;
    }
    if (context.subscription_estado === 'POR_VENCER') {
      const days = context.dias_para_vencimiento;
      return days === 0
        ? 'La suscripción vence hoy. Contacta con Zentry para registrar la renovación.'
        : `Quedan ${days} día${days === 1 ? '' : 's'} para renovar el servicio.`;
    }
    return null;
  });

  constructor() {
    this.auth.restoreSession();
    if (typeof window !== 'undefined' && window.localStorage) {
      this.sidebarCollapsed.set(
        localStorage.getItem('capricho_admin_sidebar_collapsed') === 'true',
      );
    }
  }

  toggleSidebar(): void {
    if (typeof window !== 'undefined' && window.innerWidth < 960) {
      this.menuOpen.update((open) => !open);
    } else {
      const next = !this.sidebarCollapsed();
      this.sidebarCollapsed.set(next);
      if (typeof window !== 'undefined' && window.localStorage) {
        localStorage.setItem('capricho_admin_sidebar_collapsed', String(next));
      }
    }
  }

  isGroupExpanded(group: AdminNavGroup): boolean {
    return this.expandedGroups()[group.label] ?? this.isGroupActive(group);
  }

  toggleGroup(group: AdminNavGroup): void {
    const expanded = this.isGroupExpanded(group);
    this.expandedGroups.update((groups) => ({ ...groups, [group.label]: !expanded }));
  }

  private isGroupActive(group: AdminNavGroup): boolean {
    const currentPath = this.router.url.split(/[?#]/, 1)[0];
    return group.items.some((item) =>
      item.exact
        ? currentPath === item.path
        : currentPath === item.path || currentPath.startsWith(`${item.path}/`),
    );
  }

  logout(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }
}
