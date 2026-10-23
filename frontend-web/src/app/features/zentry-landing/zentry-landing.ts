import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-zentry-landing',
  imports: [RouterLink],
  template: `
    <div class="zentry-site">
      <header class="zentry-nav">
        <a routerLink="/" aria-label="Zentry, inicio">
          <img src="/images/zentry-logo.svg" alt="Zentry" />
        </a>
        <nav aria-label="Navegación principal">
          <a href="#producto">Producto</a>
          <a href="#planes">Planes</a>
          <a class="zentry-nav__login" routerLink="/platform/login">Acceso plataforma</a>
        </nav>
      </header>

      <main>
        <section class="zentry-hero">
          <div>
            <p class="zentry-kicker">Comercio conectado, empresa por empresa</p>
            <h1>Tu operación comercial en un solo lugar.</h1>
            <p class="zentry-lead">
              Catálogo, inventario, ventas, clientes y sucursales bajo la identidad de tu empresa.
              Zentry organiza cada negocio en un espacio independiente y seguro.
            </p>
            <div class="zentry-actions">
              <a href="#planes" class="zentry-button">Ver planes</a>
              <a href="#contacto" class="zentry-text-link">Cómo contratar →</a>
            </div>
          </div>
          <div class="zentry-console" aria-label="Resumen de capacidades de Zentry">
            <span>PLATAFORMA / 01</span>
            <strong>Una vista clara de cada empresa.</strong>
            <dl>
              <div><dt>Operación</dt><dd>Ventas e inventario</dd></div>
              <div><dt>Relación</dt><dd>Clientes y pedidos</dd></div>
              <div><dt>Control</dt><dd>Roles y auditoría</dd></div>
              <div><dt>Escala</dt><dd>Planes y sucursales</dd></div>
            </dl>
          </div>
        </section>

        <section class="zentry-capabilities" id="producto">
          <header><p>Producto</p><h2>La estructura necesaria para operar y crecer.</h2></header>
          <div>
            <article><span>01</span><h3>Espacio propio</h3><p>Subdominio, identidad visual y cuentas independientes para cada empresa.</p></article>
            <article><span>02</span><h3>Control diario</h3><p>Productos, stock, sucursales, proveedores y ventas conectados.</p></article>
            <article><span>03</span><h3>Acceso seguro</h3><p>Permisos por rol y aislamiento de información entre organizaciones.</p></article>
          </div>
        </section>

        <section class="zentry-pricing" id="planes">
          <header><p>Planes</p><h2>Precios directos, sin promociones temporales.</h2></header>
          <div class="zentry-plan-grid">
            <article>
              <p class="zentry-plan-name">Básico</p><strong>Bs 300 <small>/ mes</small></strong>
              <span>Bs 3.600 al año</span>
              <ul><li>Hasta 2 sucursales</li><li>Productos, ventas y reservas</li><li>Operación offline</li><li>Reportes convencionales</li></ul>
              <a href="#contacto">Consultar plan</a>
            </article>
            <article class="is-featured">
              <p class="zentry-plan-name">Profesional</p><strong>Bs 700 <small>/ mes</small></strong>
              <span>Bs 8.400 al año</span>
              <ul><li>Hasta 10 sucursales</li><li>Productos, ventas y reservas</li><li>Operación offline</li><li>Reportes convencionales e IA</li></ul>
              <a href="#contacto">Consultar plan</a>
            </article>
          </div>
        </section>
      </main>
      <footer id="contacto"><img src="/images/zentry-mark.png" alt="" /><span>Zentry · El canal comercial se habilitará antes del lanzamiento.</span><a routerLink="/platform/login">Superadmin</a></footer>
    </div>
  `,
  styles: `
    :host { display: block; color: #121720; background: #f5f4ef; min-height: 100vh; }
    .zentry-site { --ink:#121720; --blue:#064fe8; margin:auto; border-inline:1px solid #d9d8d2; background:#faf9f5; font-family:Inter,Arial,sans-serif; }
    .zentry-nav { height:88px; display:flex; align-items:center; justify-content:space-between; padding:0 5vw; border-bottom:1px solid #d9d8d2; }
    .zentry-nav img { width:154px; display:block; }
    .zentry-nav nav { display:flex; align-items:center; gap:2rem; }
    .zentry-nav a { color:inherit; text-decoration:none; font-weight:650; }
    .zentry-nav__login { padding:.8rem 1.1rem; border:1px solid var(--ink); }
    .zentry-hero { display:grid; grid-template-columns:1.2fr .8fr; min-height:610px; border-bottom:1px solid #d9d8d2; }
    .zentry-hero > div { padding:7rem 6vw; }
    .zentry-hero h1 { max-width:760px; margin:.7rem 0 1.5rem; font-size:clamp(3.2rem,6vw,6.8rem); line-height:.9; letter-spacing:-.07em; }
    .zentry-kicker,.zentry-capabilities header p,.zentry-pricing header p { color:var(--blue); font-size:.76rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
    .zentry-lead { max-width:660px; color:#535861; font-size:1.15rem; line-height:1.7; }
    .zentry-actions { display:flex; align-items:center; gap:1.5rem; margin-top:2.5rem; }
    .zentry-button,.zentry-plan-grid a { color:white; background:var(--blue); padding:1rem 1.25rem; text-decoration:none; font-weight:750; }
    .zentry-text-link { color:var(--ink); font-weight:750; text-decoration:none; }
    .zentry-console { color:white; background:#121720; display:flex; flex-direction:column; justify-content:flex-end; }
    .zentry-console > span { margin-bottom:auto; color:#8b96a8; font:700 .72rem monospace; letter-spacing:.12em; }
    .zentry-console > strong { max-width:420px; font-size:2.4rem; line-height:1.05; letter-spacing:-.04em; }
    .zentry-console dl { margin:3rem 0 0; border-top:1px solid #39404b; }
    .zentry-console dl div { display:flex; justify-content:space-between; padding:1rem 0; border-bottom:1px solid #39404b; }
    .zentry-console dt { color:#9199a5; } .zentry-console dd { margin:0; font-weight:700; }
    .zentry-capabilities,.zentry-pricing { padding:6rem 5vw; border-bottom:1px solid #d9d8d2; }
    .zentry-capabilities header,.zentry-pricing header { max-width:760px; margin-bottom:3.5rem; }
    .zentry-capabilities h2,.zentry-pricing h2 { font-size:clamp(2.2rem,4vw,4.2rem); line-height:1; letter-spacing:-.055em; margin:.6rem 0; }
    .zentry-capabilities > div { display:grid; grid-template-columns:repeat(3,1fr); border-top:1px solid #bbbcb9; }
    .zentry-capabilities article { padding:2rem 2rem 2rem 0; border-right:1px solid #d9d8d2; }
    .zentry-capabilities article + article { padding-left:2rem; }
    .zentry-capabilities article span { color:var(--blue); font:700 .76rem monospace; }
    .zentry-capabilities h3 { font-size:1.4rem; margin:2.6rem 0 .6rem; }
    .zentry-capabilities article p { color:#62666e; line-height:1.6; }
    .zentry-plan-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); max-width:970px; }
    .zentry-plan-grid article { padding:2.5rem; border:1px solid #c9c9c5; background:#fff; }
    .zentry-plan-grid .is-featured { color:white; background:#121720; border-color:#121720; }
    .zentry-plan-name { color:var(--blue); font-weight:800; } .is-featured .zentry-plan-name { color:#8db1ff; }
    .zentry-plan-grid strong { display:block; margin:1.4rem 0 .3rem; font-size:3rem; letter-spacing:-.05em; }
    .zentry-plan-grid strong small { font-size:1rem; letter-spacing:0; }
    .zentry-plan-grid > article > span { color:#777d86; }
    .zentry-plan-grid ul { min-height:150px; margin:2rem 0; padding-left:1.2rem; line-height:2; }
    .zentry-plan-grid a { display:inline-block; }
    footer { display:flex; align-items:center; gap:1rem; padding:2rem 5vw; } footer img { width:30px; } footer a { margin-left:auto; color:inherit; }
    @media(max-width:800px){.zentry-nav nav > a:not(.zentry-nav__login){display:none}.zentry-hero{grid-template-columns:1fr}.zentry-hero>div{padding:4rem 1.5rem}.zentry-console{min-height:470px}.zentry-capabilities,.zentry-pricing{padding:4rem 1.5rem}.zentry-capabilities>div,.zentry-plan-grid{grid-template-columns:1fr}.zentry-capabilities article,.zentry-capabilities article+article{padding:2rem 0;border-right:0;border-bottom:1px solid #d9d8d2}.zentry-nav{padding:0 1.5rem}.zentry-nav img{width:125px}footer{padding:2rem 1.5rem}}
  `,
})
export class ZentryLanding {}
