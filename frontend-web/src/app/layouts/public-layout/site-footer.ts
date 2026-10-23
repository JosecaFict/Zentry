import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TenantContextService } from '../../core/tenant/tenant-context.service';

@Component({
  selector: 'app-site-footer',
  imports: [RouterLink],
  template: `
    <footer class="site-footer">
      <div>
        <strong>{{ tenant.name().toUpperCase() }}</strong>
        <p>Catálogo, pedidos y atención conectados con nuestra operación.</p>
      </div>
      <nav aria-label="Navegación de pie de página">
        <a routerLink="/catalogo">Catálogo</a><a routerLink="/carrito">Carrito</a
        ><a routerLink="/pedidos">Pedidos</a>
      </nav>
      <p class="site-footer__note">Compra online con retiro o entrega según disponibilidad.</p>
    </footer>
  `,
})
export class SiteFooter {
  readonly tenant = inject(TenantContextService);
}
