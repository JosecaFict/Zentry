import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-platform-layout',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <div
      class="platform-shell"
      [class.nav-open]="navOpen()"
      [class.nav-collapsed]="railCollapsed()"
    >
      <button
        class="platform-backdrop"
        type="button"
        (click)="navOpen.set(false)"
        aria-label="Cerrar navegación"
      ></button>
      <aside class="platform-rail" aria-label="Navegación de plataforma">
        <button
          type="button"
          class="platform-rail-toggle"
          (click)="railCollapsed.set(true)"
          aria-label="Ocultar menú lateral"
          title="Ocultar menú"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m15 18-6-6 6-6" />
          </svg>
        </button>
        <a class="platform-wordmark" routerLink="/platform" (click)="navOpen.set(false)">
          <img src="/images/zentry-logo-white.png" alt="Zentry" />
          <small>Control de plataforma</small>
        </a>
        <nav>
          <p>Operación SaaS</p>
          <a
            routerLink="/platform"
            routerLinkActive="active"
            [routerLinkActiveOptions]="{ exact: true }"
            (click)="navOpen.set(false)"
            >Resumen</a
          >
          <a routerLink="/platform/empresas" routerLinkActive="active" (click)="navOpen.set(false)"
            >Empresas</a
          >
          <a routerLink="/platform/planes" routerLinkActive="active" (click)="navOpen.set(false)"
            >Planes</a
          >
        </nav>
        <div class="platform-rail-footer">
          <span>{{ initials() }}</span>
          <div>
            <strong>{{ displayName() }}</strong
            ><small>Superadmin global</small>
          </div>
          <button type="button" (click)="logout()">Salir</button>
        </div>
      </aside>
      <section class="platform-workspace">
        <header class="platform-topbar">
          <button
            type="button"
            class="platform-menu"
            (click)="openNavigation()"
            [attr.aria-label]="railCollapsed() ? 'Mostrar menú lateral' : 'Abrir navegación'"
            title="Mostrar menú"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
          <div><span>PLATAFORMA</span><strong>Zentry multitenant</strong></div>
          <span class="platform-scope">Alcance global</span>
        </header>
        <main class="platform-main"><router-outlet /></main>
      </section>
    </div>
  `,
})
export class PlatformLayout {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly navOpen = signal(false);
  readonly railCollapsed = signal(false);
  readonly user = this.auth.currentUser;
  readonly displayName = computed(() => {
    const user = this.user();
    return user ? `${user.nombres} ${user.apellidos}`.trim() : 'Superadmin';
  });
  readonly initials = computed(() =>
    this.displayName()
      .split(' ')
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase(),
  );

  constructor() {
    this.auth.restoreSession();
  }

  openNavigation(): void {
    if (this.railCollapsed()) {
      this.railCollapsed.set(false);
      return;
    }
    this.navOpen.update((value) => !value);
  }

  logout(): void {
    this.auth.logout();
    void this.router.navigate(['/platform/login']);
  }
}
