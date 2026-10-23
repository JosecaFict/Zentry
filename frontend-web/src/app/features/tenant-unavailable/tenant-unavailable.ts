import { Component, inject } from '@angular/core';
import { TenantHostService } from '../../core/tenant/tenant-context.service';

@Component({
  selector: 'app-tenant-unavailable',
  template: `
    <main class="tenant-unavailable">
      <img src="/images/zentry-logo.svg" alt="Zentry" />
      <p>ESPACIO EMPRESARIAL</p>
      <h1>Servicio temporalmente no disponible.</h1>
      <span>El espacio <strong>{{ host.slug }}</strong> se encuentra suspendido. El administrador de la empresa puede contactar con Zentry para regularizar la suscripción.</span>
      <a href="mailto:soporte@zentry.bo">Contactar con soporte</a>
    </main>
  `,
  styles: `
    :host{display:grid;min-height:100vh;place-items:center;background:#f5f4ef;color:#121720;font-family:Inter,Arial,sans-serif}.tenant-unavailable{width:min(680px,calc(100% - 3rem));padding:4rem;border:1px solid #d3d2cd;background:#fff}.tenant-unavailable img{width:150px;margin-bottom:4rem}.tenant-unavailable p{color:#064fe8;font-size:.75rem;font-weight:800;letter-spacing:.14em}.tenant-unavailable h1{margin:.8rem 0 1.2rem;font-size:clamp(2.5rem,6vw,4.8rem);line-height:.95;letter-spacing:-.06em}.tenant-unavailable span{display:block;max-width:570px;color:#62666e;line-height:1.7}.tenant-unavailable a{display:inline-block;margin-top:2rem;padding:1rem 1.2rem;color:#fff;background:#064fe8;text-decoration:none;font-weight:750}@media(max-width:600px){.tenant-unavailable{padding:2.5rem 1.5rem}.tenant-unavailable img{margin-bottom:3rem}}
  `,
})
export class TenantUnavailable {
  readonly host = inject(TenantHostService);
}
