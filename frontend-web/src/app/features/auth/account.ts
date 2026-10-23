import { CommonModule, DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { PermissionService } from '../../core/permissions/permission.service';
import { CommerceService } from '../../core/services/commerce.service';
import { Order } from '../../core/models/commerce.model';
import { BolivianosPipe } from '../../shared/pipes/bolivianos.pipe';

@Component({
  selector: 'app-account',
  imports: [CommonModule, RouterLink, DatePipe, BolivianosPipe],
  template: `
    <main class="account-dashboard page-shell">
      @if (auth.currentUser(); as user) {
        <!-- Encabezado de Perfil Editorial -->
        <header class="account-header-card">
          <div class="account-profile-main">
            <div class="account-avatar-wrapper">
              <div class="account-avatar" [class.has-image]="!!user.avatar_url" aria-hidden="true">
                @if (user.avatar_url) {
                  <img [src]="user.avatar_url" [alt]="user.nombres" class="account-avatar__img" />
                } @else {
                  {{ initials() }}
                }
              </div>
              <label class="account-avatar-action" title="Cambiar foto de perfil" [class.is-loading]="uploadingAvatar()">
                @if (uploadingAvatar()) {
                  <span class="avatar-mini-spinner"></span>
                } @else {
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/>
                    <circle cx="12" cy="13" r="3"/>
                  </svg>
                }
                <input type="file" accept="image/jpeg,image/png,image/webp" style="display:none;" (change)="onAvatarSelected($event)" [disabled]="uploadingAvatar()" />
              </label>
              @if (user.avatar_url) {
                <button class="account-avatar-delete-link" type="button" (click)="deleteAvatar()" title="Eliminar foto de perfil">
                  Quitar foto
                </button>
              }
            </div>
            <div class="account-profile-info">
              <span class="account-eyebrow">Espacio personal</span>
              <h1>Hola, {{ user.nombres }}</h1>
              <div class="account-badge-row">
                <span class="account-status-pill is-active">
                  <span class="status-dot"></span>
                  {{ user.estado || 'Activo' }}
                </span>
                <span class="account-role-pill">
                  {{ user.roles.join(', ') || 'Cliente Registrado' }}
                </span>
              </div>
            </div>
          </div>

          <div class="account-header-actions">
            <a class="button button--primary" routerLink="/catalogo">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/>
                <path d="M3 6h18"/>
                <path d="M16 10a4 4 0 0 1-8 0"/>
              </svg>
              Explorar catálogo
            </a>
            <button class="button button--secondary" type="button" (click)="logout()" title="Cerrar sesión segura">
              Cerrar sesión
            </button>
          </div>
        </header>

        <!-- Métricas y Accesos Clave -->
        <section class="account-metrics-grid" aria-label="Resumen de actividad">
          <a class="account-metric-card" routerLink="/pedidos">
            <div class="metric-icon-wrap metric-icon--blue">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <path d="m7.5 4.27 9 5.15"/>
                <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/>
                <path d="m3.3 7 8.7 5 8.7-5"/>
                <path d="M12 22V12"/>
              </svg>
            </div>
            <div class="metric-content">
              <span class="metric-value">{{ orders().length }}</span>
              <span class="metric-title">Mis pedidos</span>
              <span class="metric-hint">Seguimiento y facturas</span>
            </div>
            <span class="metric-arrow" aria-hidden="true">→</span>
          </a>

          <a class="account-metric-card" routerLink="/reservas">
            <div class="metric-icon-wrap metric-icon--emerald">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/>
                <path d="M3 6h18"/>
                <path d="M16 10a4 4 0 0 1-8 0"/>
              </svg>
            </div>
            <div class="metric-content">
              <span class="metric-value">{{ reservationsCount() }}</span>
              <span class="metric-title">Mis reservas</span>
              <span class="metric-hint">Apartados en tienda</span>
            </div>
            <span class="metric-arrow" aria-hidden="true">→</span>
          </a>

          <a class="account-metric-card" routerLink="/direcciones">
            <div class="metric-icon-wrap metric-icon--amber">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>
                <circle cx="12" cy="10" r="3"/>
              </svg>
            </div>
            <div class="metric-content">
              <span class="metric-value">{{ addressesCount() }}</span>
              <span class="metric-title">Direcciones</span>
              <span class="metric-hint">Puntos con GPS</span>
            </div>
            <span class="metric-arrow" aria-hidden="true">→</span>
          </a>

          <a class="account-metric-card" routerLink="/notificaciones">
            <div class="metric-icon-wrap metric-icon--purple">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>
                <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>
              </svg>
            </div>
            <div class="metric-content">
              <span class="metric-value">{{ unreadNotificationsCount() }}</span>
              <span class="metric-title">Notificaciones</span>
              <span class="metric-hint">{{ unreadNotificationsCount() > 0 ? 'Avisos pendientes' : 'Al día' }}</span>
            </div>
            <span class="metric-arrow" aria-hidden="true">→</span>
          </a>
        </section>

        <!-- Cuadrícula Principal: Datos del Perfil y Accesos Directos -->
        <section class="account-main-grid">
          <!-- Columna Izquierda: Información de Perfil -->
          <article class="account-card">
            <header class="account-card__header">
              <div class="account-card__icon-badge">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
              </div>
              <div>
                <h2>Datos del perfil</h2>
                <p>Información personal y de contacto registrada</p>
              </div>
            </header>

            <dl class="account-profile-list">
              <div class="profile-row">
                <dt>Nombre completo</dt>
                <dd><strong>{{ user.nombres }} {{ user.apellidos }}</strong></dd>
              </div>

              <div class="profile-row">
                <dt>Correo electrónico</dt>
                <dd>
                  <span>{{ user.correo }}</span>
                  <span class="profile-verified-tag">Verificado</span>
                </dd>
              </div>

              <div class="profile-row">
                <dt>Teléfono de contacto</dt>
                <dd>{{ user.telefono || 'No registrado' }}</dd>
              </div>

              <div class="profile-row">
                <dt>Cédula de Identidad (CI)</dt>
                <dd>{{ user.ci || 'No registrado' }}</dd>
              </div>

              @if (user.sucursal) {
                <div class="profile-row">
                  <dt>Sucursal preferida</dt>
                  <dd>{{ user.sucursal }}</dd>
                </div>
              }

              <div class="profile-row">
                <dt>Tipo de cuenta</dt>
                <dd>{{ user.roles.join(', ') || 'Cliente' }}</dd>
              </div>
            </dl>

            <div class="account-security-note">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
              <span>Tus transacciones y datos están protegidos bajo cifrado seguro.</span>
            </div>
          </article>

          <!-- Columna Derecha: Accesos Directos Comerciales -->
          <article class="account-card">
            <header class="account-card__header">
              <div class="account-card__icon-badge">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="m10 15 5-3-5-3v6Z"/>
                </svg>
              </div>
              <div>
                <h2>Gestión comercial</h2>
                <p>Accesos directos para tus compras, pedidos y entregas</p>
              </div>
            </header>

            <div class="account-services-grid">
              <a class="service-tile" routerLink="/pedidos">
                <div class="service-tile__icon">📦</div>
                <div class="service-tile__body">
                  <h3>Mis Pedidos</h3>
                  <p>Estado en tiempo real de despacho y descarga de facturas oficiales en PDF.</p>
                </div>
                <span class="service-tile__arrow">→</span>
              </a>

              <a class="service-tile" routerLink="/reservas">
                <div class="service-tile__icon">🛍️</div>
                <div class="service-tile__body">
                  <h3>Mis Reservas</h3>
                  <p>Prendas apartadas para retiro o prueba en sucursales físicas Capricho.</p>
                </div>
                <span class="service-tile__arrow">→</span>
              </a>

              <a class="service-tile" routerLink="/direcciones">
                <div class="service-tile__icon">📍</div>
                <div class="service-tile__body">
                  <h3>Libreta de Direcciones</h3>
                  <p>Administra tus ubicaciones con geolocalización en mapa para envíos a domicilio.</p>
                </div>
                <span class="service-tile__arrow">→</span>
              </a>

              <a class="service-tile" routerLink="/historial">
                <div class="service-tile__icon">📜</div>
                <div class="service-tile__body">
                  <h3>Historial de Compras</h3>
                  <p>Revisa tus compras realizadas, transacciones anteriores y recibos de pago.</p>
                </div>
                <span class="service-tile__arrow">→</span>
              </a>
            </div>
          </article>
        </section>

        <!-- Sección de Pedidos Recientes -->
        <section class="account-recent-section">
          <div class="recent-section-header">
            <div>
              <h2>Últimos pedidos</h2>
              <p>Seguimiento inmediato de tus compras más recientes</p>
            </div>
            @if (orders().length > 0) {
              <a class="button button--secondary button--small" routerLink="/pedidos">
                Ver todos ({{ orders().length }}) →
              </a>
            }
          </div>

          @if (actionFeedback()) {
            <div class="notice notice--success" style="margin-bottom: 1rem;">
              {{ actionFeedback() }}
            </div>
          }

          @if (ordersLoading()) {
            <div class="account-orders-loading">
              <div class="skeleton-order-card"></div>
              <div class="skeleton-order-card"></div>
            </div>
          } @else if (orders().length === 0) {
            <div class="account-empty-orders">
              <div class="empty-orders-icon">🛍️</div>
              <h3>Aún no has realizado pedidos</h3>
              <p>Descubre las prendas en tendencia y realiza tu primera compra con entrega rápida o retiro en sucursal.</p>
              <a class="button button--primary" routerLink="/catalogo">Ver catálogo oficial</a>
            </div>
          } @else {
            <div class="account-orders-list">
              @for (order of recentOrders(); track order.id_pedido) {
                <article class="account-order-item">
                  <div class="order-item-header">
                    <div>
                      <span class="order-number">Pedido #{{ order.id_pedido }}</span>
                      <time class="order-date">{{ order.fecha_creacion | date: 'mediumDate' }}</time>
                    </div>
                    <span class="account-order-chip" [attr.data-status]="order.estado">
                      {{ order.estado }}
                    </span>
                  </div>

                  <div class="order-item-body">
                    <div class="order-modality-info">
                      <span class="modality-badge">
                        {{ order.modalidad_entrega === 'DELIVERY' ? '🛵 Delivery a domicilio' : '🏬 Retiro en tienda' }}
                      </span>
                      <p class="order-destination">
                        {{ order.direccion_entrega || order.sucursal || 'Sucursal central' }}
                      </p>
                    </div>

                    <div class="order-total-block">
                      <span class="total-label">Total abonado</span>
                      <strong class="total-value">{{ order.total | bolivianos }}</strong>
                    </div>
                  </div>

                  <footer class="order-item-footer">
                    @if (order.modalidad_entrega === 'DELIVERY' && order.estado === 'EN_CAMINO') {
                      <button
                        class="button button--primary button--small btn-confirm-delivery"
                        type="button"
                        [disabled]="confirmingId() === order.id_pedido"
                        (click)="confirmDelivery(order.id_pedido)"
                      >
                        {{ confirmingId() === order.id_pedido ? 'Confirmando…' : '✓ Confirmar recepción' }}
                      </button>
                    }
                    <button
                      class="button button--secondary button--small"
                      type="button"
                      [disabled]="downloadingId() === order.id_pedido"
                      (click)="downloadInvoice(order.id_pedido)"
                      title="Descargar factura en PDF"
                    >
                      {{ downloadingId() === order.id_pedido ? 'Generando PDF…' : '📄 Descargar Factura PDF' }}
                    </button>
                    <a class="button button--quiet button--small" routerLink="/pedidos">
                      Ver seguimiento →
                    </a>
                  </footer>
                </article>
              }
            </div>
          }
        </section>
      } @else {
        <div class="account-loading-state">
          <span class="account-spinner"></span>
          <p>Cargando información de tu cuenta…</p>
        </div>
      }
    </main>
  `,
})
export class Account implements OnInit {
  readonly auth = inject(AuthService);
  readonly permissions = inject(PermissionService);
  private readonly router = inject(Router);
  private readonly commerce = inject(CommerceService);

  readonly orders = signal<Order[]>([]);
  readonly ordersLoading = signal(true);
  readonly reservationsCount = signal(0);
  readonly addressesCount = signal(0);
  readonly unreadNotificationsCount = signal(0);
  readonly downloadingId = signal<number | null>(null);
  readonly confirmingId = signal<number | null>(null);
  readonly actionFeedback = signal<string | null>(null);
  readonly uploadingAvatar = signal(false);
  readonly avatarError = signal<string | null>(null);

  onAvatarSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    if (file.size > 5 * 1024 * 1024) {
      this.actionFeedback.set('La imagen supera el límite de 5 MB.');
      setTimeout(() => this.actionFeedback.set(null), 5000);
      return;
    }
    this.uploadingAvatar.set(true);
    this.auth.uploadAvatar(file).subscribe({
      next: () => {
        this.uploadingAvatar.set(false);
        this.actionFeedback.set('¡Foto de perfil actualizada con éxito!');
        setTimeout(() => this.actionFeedback.set(null), 5000);
      },
      error: () => {
        this.uploadingAvatar.set(false);
        this.actionFeedback.set('No se pudo subir la foto de perfil.');
        setTimeout(() => this.actionFeedback.set(null), 5000);
      },
    });
    input.value = '';
  }

  deleteAvatar(): void {
    if (!window.confirm('¿Deseas eliminar tu foto de perfil actual?')) return;
    this.uploadingAvatar.set(true);
    this.auth.deleteAvatar().subscribe({
      next: () => {
        this.uploadingAvatar.set(false);
        this.actionFeedback.set('Foto de perfil eliminada.');
        setTimeout(() => this.actionFeedback.set(null), 4000);
      },
      error: () => {
        this.uploadingAvatar.set(false);
      },
    });
  }

  readonly initials = computed(() => {
    const user = this.auth.currentUser();
    if (!user) return 'CS';
    const first = (user.nombres || '').trim().charAt(0);
    const last = (user.apellidos || '').trim().charAt(0);
    return (first + last).toUpperCase() || 'CS';
  });

  readonly recentOrders = computed(() => this.orders().slice(0, 2));

  constructor() {
    if (this.permissions.hasAdminAccess()) {
      void this.router.navigate(['/admin/perfil'], { replaceUrl: true });
    }
  }

  ngOnInit(): void {
    this.loadAccountOverview();
  }

  loadAccountOverview(): void {
    this.ordersLoading.set(true);
    this.commerce.orders().subscribe({
      next: (list) => {
        this.orders.set(list || []);
        this.ordersLoading.set(false);
      },
      error: () => this.ordersLoading.set(false),
    });

    this.commerce.reservations().subscribe({
      next: (list) => this.reservationsCount.set((list || []).length),
      error: () => {},
    });

    this.commerce.addresses().subscribe({
      next: (list) =>
        this.addressesCount.set((list || []).filter((a) => a.activo !== false).length),
      error: () => {},
    });

    this.commerce.notifications().subscribe({
      next: (list) =>
        this.unreadNotificationsCount.set(
          (list || []).filter((n) => n.estado !== 'LEIDO').length,
        ),
      error: () => {},
    });
  }

  downloadInvoice(orderId: number): void {
    this.downloadingId.set(orderId);
    this.commerce.orderInvoice(orderId).subscribe({
      next: (blob) => {
        this.downloadingId.set(null);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `factura_pedido_${orderId}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
      },
      error: () => this.downloadingId.set(null),
    });
  }

  confirmDelivery(orderId: number): void {
    const confirmed = window.confirm('¿Confirmas que recibiste tu pedido de forma satisfactoria?');
    if (!confirmed) return;

    this.confirmingId.set(orderId);
    this.actionFeedback.set(null);
    this.commerce.confirmDelivery(orderId).subscribe({
      next: (updatedOrder) => {
        this.confirmingId.set(null);
        this.orders.update((list) =>
          list.map((o) => (o.id_pedido === updatedOrder.id_pedido ? updatedOrder : o))
        );
        this.actionFeedback.set(`¡Pedido #${orderId} confirmado como entregado!`);
        setTimeout(() => this.actionFeedback.set(null), 6000);
      },
      error: () => {
        this.confirmingId.set(null);
        this.actionFeedback.set('No se pudo confirmar la entrega del pedido.');
      },
    });
  }

  logout(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }
}
