import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-zentry-landing',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="landing">
      <header class="site-header">
        <a class="brand" href="#inicio" aria-label="Zentry, inicio">
          <img src="/images/zentry-logo.svg" alt="" />
          <span>Zentry</span>
        </a>

        <nav aria-label="Navegación principal">
          <a href="#producto">Producto</a>
          <a href="#planes">Planes</a>
          <a href="mailto:contacto@zentrysaas.store">Contacto</a>
          <a class="header-cta" routerLink="/platform/login">Acceso plataforma</a>
        </nav>
      </header>

      <section class="hero section-shell" id="inicio">
        <div class="hero-copy">
          <p class="eyebrow">Comercio conectado · empresa por empresa</p>
          <h1>Controla tu operación.<br /><span>Haz crecer cada sucursal.</span></h1>
          <p class="hero-summary">
            Ventas, inventario, clientes y equipos reunidos en una plataforma
            segura que mantiene cada empresa completamente independiente.
          </p>
          <div class="hero-actions">
            <a class="button primary" href="#planes">Ver planes</a>
            <a class="text-link" href="#producto">Conocer Zentry <span aria-hidden="true">→</span></a>
          </div>
          <dl class="hero-proof">
            <div><dt>Multitenant</dt><dd>Datos aislados por empresa</dd></div>
            <div><dt>Multisucursal</dt><dd>Control desde un solo lugar</dd></div>
            <div><dt>Online + offline</dt><dd>Operación continua</dd></div>
          </dl>
        </div>

        <div class="product-preview" aria-label="Vista previa del panel de Zentry">
          <div class="preview-topbar">
            <span class="preview-brand"><img src="/images/zentry-logo.svg" alt="" /> Zentry</span>
            <span>Panel operativo</span>
          </div>
          <div class="preview-body">
            <aside aria-hidden="true">
              <i class="active"></i><i></i><i></i><i></i><i></i>
            </aside>
            <div class="preview-content">
              <div class="preview-heading">
                <div><small>VISTA GENERAL</small><strong>Centro de comando</strong></div>
                <span>Este mes</span>
              </div>
              <div class="metric-grid">
                <article><small>Ventas</small><b>Bs 48.620</b><em>+12,4%</em></article>
                <article><small>Pedidos</small><b>186</b><em>14 pendientes</em></article>
                <article><small>Sucursales</small><b>5</b><em>todas activas</em></article>
              </div>
              <div class="chart-panel">
                <div class="chart-title"><span>Facturación semanal</span><small>Últimos 7 días</small></div>
                <svg viewBox="0 0 560 180" role="img" aria-label="Gráfico ascendente de facturación">
                  <defs>
                    <linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stop-color="#1658f4" stop-opacity=".24" />
                      <stop offset="100%" stop-color="#1658f4" stop-opacity="0" />
                    </linearGradient>
                  </defs>
                  <path class="grid" d="M20 35H540M20 80H540M20 125H540M20 165H540" />
                  <path class="area" d="M20 144 C80 132 94 94 150 108 S230 142 286 88 S374 56 420 70 S492 34 540 30 L540 165 L20 165Z" />
                  <path class="line" d="M20 144 C80 132 94 94 150 108 S230 142 286 88 S374 56 420 70 S492 34 540 30" />
                  <circle cx="20" cy="144" r="4" /><circle cx="150" cy="108" r="4" />
                  <circle cx="286" cy="88" r="4" /><circle cx="420" cy="70" r="4" /><circle cx="540" cy="30" r="4" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="capability-strip" aria-label="Capacidades principales">
        <article><span>01</span><strong>Inventario conectado</strong><p>Stock y movimientos por sucursal en tiempo real.</p></article>
        <article><span>02</span><strong>Ventas y clientes</strong><p>Pedidos, reservas e historial en un solo flujo.</p></article>
        <article><span>03</span><strong>Decisiones con datos</strong><p>Reportes claros y analítica para dirigir mejor.</p></article>
        <article><span>04</span><strong>Acceso seguro</strong><p>Roles, auditoría y aislamiento entre empresas.</p></article>
      </section>

      <section class="product-section section-shell" id="producto">
        <div class="section-intro">
          <p class="eyebrow">Una operación más simple</p>
          <h2>Todo lo que tu empresa necesita para vender y crecer.</h2>
          <p>Zentry conecta el trabajo diario sin obligarte a saltar entre sistemas.</p>
        </div>
        <div class="feature-grid">
          <article>
            <span class="feature-number">01</span>
            <h3>Tu empresa, tu espacio</h3>
            <p>Subdominio propio, identidad visual, usuarios y catálogo separados del resto.</p>
            <ul><li>Branding configurable</li><li>Contexto por tenant</li><li>Accesos por rol</li></ul>
          </article>
          <article>
            <span class="feature-number">02</span>
            <h3>Control de cada sucursal</h3>
            <p>Compras, stock, ventas, reservas y transferencias conectadas de extremo a extremo.</p>
            <ul><li>Inventario centralizado</li><li>Operación offline</li><li>Sincronización segura</li></ul>
          </article>
          <article>
            <span class="feature-number">03</span>
            <h3>Información que ayuda</h3>
            <p>Paneles, exportaciones y modelos analíticos para convertir datos en acciones.</p>
            <ul><li>Reportes comerciales</li><li>Excel y PDF</li><li>IA en plan Profesional</li></ul>
          </article>
        </div>
      </section>

      <section class="plans-section" id="planes">
        <div class="section-shell">
          <div class="plans-heading">
            <div>
              <p class="eyebrow">Planes claros</p>
              <h2>Elige la capacidad que tu empresa necesita.</h2>
            </div>
            <p>Precios directos, sin promociones temporales ni costos escondidos.</p>
          </div>

          <div class="plans-grid">
            <article class="plan-card">
              <div class="plan-top"><span>BÁSICO</span><strong>Para comenzar</strong></div>
              <div class="price"><b>Bs 300</b><span>/ mes</span></div>
              <p class="annual">Bs 3.600 al año</p>
              <ul>
                <li><b>2</b> sucursales activas</li>
                <li><b>5</b> usuarios internos</li>
                <li><b>3.000</b> productos activos</li>
                <li><b>5 GB</b> de almacenamiento</li>
                <li>Reportes convencionales</li>
                <li>Operación offline</li>
              </ul>
              <a class="button secondary" href="mailto:contacto@zentrysaas.store?subject=Plan%20Básico%20Zentry">Consultar plan</a>
            </article>

            <article class="plan-card featured">
              <div class="plan-top"><span>PROFESIONAL</span><strong>Para escalar</strong></div>
              <div class="price"><b>Bs 700</b><span>/ mes</span></div>
              <p class="annual">Bs 8.400 al año</p>
              <ul>
                <li><b>10</b> sucursales activas</li>
                <li><b>25</b> usuarios internos</li>
                <li><b>20.000</b> productos activos</li>
                <li><b>25 GB</b> de almacenamiento</li>
                <li>Reportes convencionales y con IA</li>
                <li>Operación offline</li>
              </ul>
              <a class="button light" href="mailto:contacto@zentrysaas.store?subject=Plan%20Profesional%20Zentry">Consultar plan</a>
            </article>
          </div>
        </div>
      </section>

      <section class="closing-cta">
        <div>
          <p class="eyebrow">Zentry para tu empresa</p>
          <h2>Convierte una operación dispersa en una sola visión.</h2>
        </div>
        <div>
          <p>Organiza cada sucursal, protege tus datos y toma decisiones con información confiable.</p>
          <a class="button primary" href="mailto:contacto@zentrysaas.store?subject=Quiero%20conocer%20Zentry">Hablar con nosotros</a>
        </div>
      </section>

      <footer>
        <div class="brand"><img src="/images/zentry-logo.svg" alt="" /><span>Zentry</span></div>
        <p>Operación comercial conectada, empresa por empresa.</p>
        <div><a href="#producto">Producto</a><a href="#planes">Planes</a><a routerLink="/platform/login">Superadmin</a></div>
      </footer>
    </main>
  `,
  styles: [`
    :host { display: block; color: #11141b; background: #f7f6f2; }
    * { box-sizing: border-box; }
    .landing { min-height: 100vh; font-family: Inter, "Segoe UI", Arial, sans-serif; overflow: hidden; }
    a { color: inherit; }
    .site-header { height: 76px; padding: 0 clamp(24px, 5vw, 88px); display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #d8d8d2; background: rgba(247,246,242,.94); position: relative; z-index: 5; }
    .brand { display: inline-flex; align-items: center; gap: 10px; text-decoration: none; font-weight: 800; font-size: 18px; }
    .brand img { width: 34px; height: 34px; object-fit: contain; }
    nav { display: flex; align-items: center; gap: 30px; font-weight: 700; font-size: 14px; }
    nav a { text-decoration: none; }
    nav a:not(.header-cta):hover { color: #0b50ed; }
    .header-cta { border: 1px solid #151820; padding: 12px 17px; transition: .2s ease; }
    .header-cta:hover { background: #111722; color: #fff; }
    .section-shell { max-width: 1480px; margin: 0 auto; padding-inline: clamp(24px, 5vw, 88px); }
    .hero { min-height: 720px; display: grid; grid-template-columns: minmax(0, .95fr) minmax(520px, 1.05fr); align-items: center; gap: clamp(44px, 6vw, 96px); padding-block: 72px; }
    .eyebrow { margin: 0 0 18px; color: #0756ef; font-size: 12px; font-weight: 900; letter-spacing: .16em; text-transform: uppercase; }
    h1, h2, h3, p { margin-top: 0; }
    h1 { margin-bottom: 25px; font-size: clamp(54px, 5.6vw, 92px); line-height: .94; letter-spacing: -.065em; max-width: 800px; }
    h1 span { color: #0d53e9; }
    .hero-summary { max-width: 650px; color: #515967; font-size: 18px; line-height: 1.7; }
    .hero-actions { display: flex; align-items: center; gap: 28px; margin-top: 34px; }
    .button { min-height: 50px; padding: 0 22px; display: inline-flex; align-items: center; justify-content: center; text-decoration: none; font-weight: 800; border: 1px solid transparent; }
    .primary { background: #0d55ed; color: #fff; }
    .primary:hover { background: #0845c5; }
    .text-link { text-decoration: none; font-weight: 800; border-bottom: 1px solid #151820; padding-bottom: 4px; }
    .hero-proof { display: grid; grid-template-columns: repeat(3, 1fr); margin: 52px 0 0; padding-top: 22px; border-top: 1px solid #d7d7d1; }
    .hero-proof div { padding-right: 18px; }
    .hero-proof dt { font-size: 13px; font-weight: 850; margin-bottom: 6px; }
    .hero-proof dd { margin: 0; color: #697180; font-size: 12px; line-height: 1.4; }
    .product-preview { border: 1px solid #28303e; background: #101722; color: #fff; box-shadow: 26px 28px 0 #dce5f8; transform: rotate(.2deg); }
    .preview-topbar { height: 58px; display: flex; align-items: center; justify-content: space-between; padding: 0 22px; border-bottom: 1px solid #2a3443; color: #9aa9be; font-size: 11px; text-transform: uppercase; letter-spacing: .12em; }
    .preview-brand { display: flex; align-items: center; gap: 8px; color: #fff; font-weight: 800; font-size: 13px; letter-spacing: 0; text-transform: none; }
    .preview-brand img { width: 23px; height: 23px; }
    .preview-body { display: grid; grid-template-columns: 62px 1fr; min-height: 480px; }
    .preview-body aside { padding: 30px 17px; border-right: 1px solid #293342; display: flex; flex-direction: column; gap: 22px; }
    .preview-body aside i { width: 27px; height: 7px; border-radius: 4px; background: #475467; }
    .preview-body aside i.active { background: #1c60f3; }
    .preview-content { padding: 32px; }
    .preview-heading { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 26px; }
    .preview-heading small { color: #6fa0ff; font-size: 9px; letter-spacing: .15em; display: block; margin-bottom: 8px; }
    .preview-heading strong { font-size: 25px; }
    .preview-heading > span { color: #93a0b3; font-size: 11px; border: 1px solid #344052; padding: 8px 10px; }
    .metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 18px; }
    .metric-grid article, .chart-panel { border: 1px solid #2b3647; background: #151e2b; }
    .metric-grid article { padding: 16px; display: grid; gap: 7px; }
    .metric-grid small { color: #91a0b5; font-size: 10px; }
    .metric-grid b { font-size: 19px; }
    .metric-grid em { color: #6fa0ff; font-size: 9px; font-style: normal; }
    .chart-panel { padding: 18px; }
    .chart-title { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .chart-title span { font-size: 12px; font-weight: 800; }
    .chart-title small { color: #76859b; font-size: 9px; }
    svg { width: 100%; height: auto; overflow: visible; }
    svg .grid { fill: none; stroke: #2d394b; stroke-width: 1; }
    svg .area { fill: url(#chartFill); }
    svg .line { fill: none; stroke: #2d6bff; stroke-width: 4; stroke-linecap: round; }
    svg circle { fill: #101722; stroke: #4c80ff; stroke-width: 3; }
    .capability-strip { max-width: 100%; display: grid; grid-template-columns: repeat(4, 1fr); border-block: 1px solid #d5d5ce; background: #fff; }
    .capability-strip article { min-height: 190px; padding: 34px clamp(24px, 3vw, 54px); border-right: 1px solid #d5d5ce; }
    .capability-strip article:last-child { border-right: 0; }
    .capability-strip span { color: #0a56ef; font-size: 11px; font-weight: 900; }
    .capability-strip strong { display: block; margin: 28px 0 9px; font-size: 18px; }
    .capability-strip p { margin: 0; color: #626a76; line-height: 1.55; font-size: 14px; }
    .product-section { padding-block: 120px; }
    .section-intro { display: grid; grid-template-columns: .35fr .9fr .55fr; gap: 35px; align-items: end; margin-bottom: 50px; }
    .section-intro .eyebrow { align-self: start; }
    .section-intro h2, .plans-heading h2, .closing-cta h2 { margin: 0; font-size: clamp(38px, 4vw, 64px); line-height: 1.02; letter-spacing: -.045em; }
    .section-intro > p:last-child, .plans-heading > p { color: #5d6571; line-height: 1.6; }
    .feature-grid { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid #bebfbc; border-bottom: 1px solid #bebfbc; }
    .feature-grid article { padding: 35px 34px 40px 0; min-height: 370px; border-right: 1px solid #d1d2ce; }
    .feature-grid article + article { padding-left: 34px; }
    .feature-grid article:last-child { border-right: 0; }
    .feature-number { color: #0d55ed; font-size: 11px; font-weight: 900; }
    .feature-grid h3 { margin: 55px 0 16px; font-size: 25px; }
    .feature-grid p { color: #5c6470; line-height: 1.65; min-height: 80px; }
    .feature-grid ul, .plan-card ul { margin: 24px 0 0; padding: 0; list-style: none; }
    .feature-grid li { padding: 9px 0; border-top: 1px solid #deded9; font-size: 14px; }
    .plans-section { background: #111722; color: #fff; padding-block: 110px; }
    .plans-section .section-shell { max-width: 1320px; }
    .plans-heading { display: grid; grid-template-columns: 1fr .45fr; gap: 50px; align-items: end; padding-bottom: 44px; border-bottom: 1px solid #3a424f; }
    .plans-heading > p { color: #aab3c1; margin-bottom: 4px; }
    .plans-grid { display: grid; grid-template-columns: repeat(2, 1fr); max-width: 980px; margin-top: 46px; }
    .plan-card { background: #fff; color: #131720; padding: 40px; min-height: 610px; border: 1px solid #ccd0d7; display: flex; flex-direction: column; }
    .plan-card.featured { background: #151f2d; color: #fff; border-color: #445064; }
    .plan-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 46px; }
    .plan-top span { color: #0d55ed; font-size: 11px; letter-spacing: .15em; font-weight: 900; }
    .featured .plan-top span { color: #72a0ff; }
    .plan-top strong { font-size: 13px; color: #68707d; }
    .featured .plan-top strong { color: #a8b1bf; }
    .price { display: flex; align-items: baseline; gap: 9px; }
    .price b { font-size: 48px; letter-spacing: -.045em; }
    .price span, .annual { color: #6e7580; }
    .featured .price span, .featured .annual { color: #a6afbc; }
    .annual { margin: 4px 0 28px; font-size: 14px; }
    .plan-card ul { border-top: 1px solid #d8dbe0; margin-bottom: 34px; }
    .featured ul { border-color: #394556; }
    .plan-card li { display: flex; justify-content: space-between; padding: 13px 0; border-bottom: 1px solid #e1e2e5; font-size: 14px; }
    .featured li { border-color: #394556; }
    .plan-card .button { margin-top: auto; align-self: flex-start; }
    .secondary { border-color: #111722; }
    .secondary:hover { background: #111722; color: #fff; }
    .light { background: #fff; color: #111722; }
    .closing-cta { padding: 90px clamp(24px, 5vw, 88px); background: #e8edf8; display: grid; grid-template-columns: 1.1fr .7fr; gap: 8vw; align-items: end; }
    .closing-cta > div:last-child { max-width: 520px; }
    .closing-cta > div:last-child p { color: #555e6c; line-height: 1.65; margin-bottom: 26px; }
    footer { min-height: 130px; padding: 34px clamp(24px, 5vw, 88px); display: grid; grid-template-columns: .4fr 1fr auto; align-items: center; gap: 35px; border-top: 1px solid #d1d2ce; }
    footer p { margin: 0; color: #646c78; font-size: 13px; }
    footer > div:last-child { display: flex; gap: 24px; font-size: 13px; }

    @media (max-width: 1050px) {
      .hero { grid-template-columns: 1fr; }
      .product-preview { max-width: 760px; }
      .capability-strip { grid-template-columns: repeat(2, 1fr); }
      .capability-strip article:nth-child(2) { border-right: 0; }
      .capability-strip article:nth-child(-n+2) { border-bottom: 1px solid #d5d5ce; }
      .section-intro { grid-template-columns: 1fr 1.6fr; }
      .section-intro > p:last-child { grid-column: 2; }
      .plans-grid { max-width: none; }
    }
    @media (max-width: 760px) {
      .site-header { height: auto; min-height: 68px; padding-block: 12px; }
      nav { gap: 12px; }
      nav > a:not(.header-cta) { display: none; }
      .header-cta { padding: 10px 12px; font-size: 12px; }
      .hero { min-height: auto; padding-block: 58px 72px; grid-template-columns: 1fr; }
      h1 { font-size: clamp(48px, 15vw, 68px); }
      .hero-summary { font-size: 16px; }
      .hero-proof { grid-template-columns: 1fr; gap: 16px; }
      .product-preview { box-shadow: 12px 14px 0 #dce5f8; }
      .preview-body { grid-template-columns: 1fr; min-height: 410px; }
      .preview-body aside { display: none; }
      .preview-content { padding: 20px; }
      .metric-grid { grid-template-columns: 1fr 1fr; }
      .metric-grid article:last-child { display: none; }
      .capability-strip { grid-template-columns: 1fr; }
      .capability-strip article { min-height: 150px; border-right: 0; border-bottom: 1px solid #d5d5ce; }
      .section-intro, .plans-heading, .closing-cta { grid-template-columns: 1fr; }
      .section-intro > p:last-child { grid-column: auto; }
      .feature-grid, .plans-grid { grid-template-columns: 1fr; }
      .feature-grid article, .feature-grid article + article { padding: 34px 0; border-right: 0; border-bottom: 1px solid #d1d2ce; min-height: auto; }
      .feature-grid h3 { margin-top: 28px; }
      .feature-grid p { min-height: 0; }
      .product-section, .plans-section { padding-block: 80px; }
      .plan-card { min-height: 560px; padding: 30px 24px; }
      .closing-cta { padding-block: 72px; }
      footer { grid-template-columns: 1fr; }
      footer > div:last-child { flex-wrap: wrap; }
    }
  `],
})
export class ZentryLanding {}
