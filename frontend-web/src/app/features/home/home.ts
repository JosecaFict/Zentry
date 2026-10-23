import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { OFFICIAL_CATEGORIES } from '../../core/config/api.config';
import { Product } from '../../core/models/catalog.model';
import { RecommendedProduct } from '../../core/models/recommendation.model';
import { ApiErrorService } from '../../core/services/api-error.service';
import { CatalogService } from '../../core/services/catalog.service';
import { RecommendationService } from '../../core/services/recommendation.service';
import { ProductCard } from '../../shared/components/product-card/product-card';
import { StatusPanel } from '../../shared/components/status-panel/status-panel';

@Component({
  selector: 'app-home',
  imports: [RouterLink, ProductCard, StatusPanel],
  template: `
    <!-- Shipping derivatives: assets/plates/hero-photo.png -> /images/hero-catalogo-oficial.jpg; assets/plates/men-photo.png -> /images/acceso-hombre-polo.jpg; assets/plates/women-photo.png -> /images/acceso-mujer-blusa.jpg; assets/plates/catalog-preview.png -> /images/catalogo-prendas-oficiales.jpg. -->
    <section class="home-hero" aria-labelledby="home-title">
      <div class="home-hero__copy">
        <h1 id="home-title">Vestir también es elegir</h1>
        <p>Encuentra prendas reales por estilo, talla y color.</p>
        <a class="button button--primary" routerLink="/catalogo">Ver catálogo</a>
      </div>
      <div class="home-hero__media">
        <img
          src="/images/hero-catalogo-oficial.jpg"
          alt="Modelos con polera, camisa y polo del catálogo"
          fetchpriority="high"
        />
        <span class="home-hero__reference">Fotografía de referencia</span>
      </div>
    </section>

    <section class="audience-grid page-shell" aria-labelledby="audience-title">
      <h2 id="audience-title" class="visually-hidden">Explorar por público</h2>
      <p class="visual-reference-note">Fotografías de referencia del catálogo oficial</p>
      <a
        class="audience-tile"
        routerLink="/catalogo"
        [queryParams]="{ publico_objetivo: 'HOMBRE' }"
      >
        <img src="/images/acceso-hombre-polo.jpg" alt="Hombre con polo azul marino" />
        <span><strong>Hombre</strong><small>Poleras · Camisas · Polos</small></span>
      </a>
      <a class="audience-tile" routerLink="/catalogo" [queryParams]="{ publico_objetivo: 'MUJER' }">
        <img src="/images/acceso-mujer-blusa.jpg" alt="Mujer con blusa azul cobalto" />
        <span><strong>Mujer</strong><small>Poleras · Camisas · Polos · Blusas</small></span>
      </a>
    </section>

    <section class="category-section page-shell" aria-labelledby="categories-title">
      <div class="section-heading">
        <h2 id="categories-title">El catálogo, sin categorías inventadas</h2>
        <p>Cuatro tipos de prenda. Dos públicos. Una selección clara.</p>
      </div>
      <div class="category-links">
        @for (category of categories; track category) {
          <a routerLink="/catalogo" [queryParams]="{ categoria: category }">{{
            categoryLabel(category)
          }}</a>
        }
      </div>
      <img
        class="category-strip"
        src="/images/catalogo-prendas-oficiales.jpg"
        alt="Polera, camisa, polo y blusa del catálogo"
        loading="lazy"
      />
      <p class="visual-reference-note">Composición visual de referencia</p>
    </section>

    <section class="featured-section page-shell" aria-labelledby="featured-title">
      <div class="section-heading section-heading--row">
        <div>
          <h2 id="featured-title">Prendas recientes</h2>
          <p>Datos obtenidos directamente del catálogo.</p>
        </div>
        <a class="text-link" routerLink="/catalogo">Ver todo el catálogo</a>
      </div>
      @if (loading()) {
        <div class="product-grid" aria-label="Cargando productos">
          @for (item of skeletons; track item) {
            <div class="product-skeleton"><span></span><i></i><i></i></div>
          }
        </div>
      } @else if (errorMessage()) {
        <app-status-panel
          kind="error"
          title="El catálogo no respondió"
          [message]="errorMessage()"
          (retry)="loadProducts()"
        />
      } @else if (products().length === 0) {
        <app-status-panel
          title="Aún no hay productos publicados"
          message="Cuando el catálogo tenga productos activos, aparecerán aquí."
        />
      } @else {
        <div class="product-grid">
          @for (product of products(); track product.id_producto) {
            <app-product-card [product]="product" />
          }
        </div>
      }
    </section>

    <!-- Recomendaciones Inteligentes -->
    @if (recommendationsList().length > 0) {
      <section class="featured-section page-shell" aria-labelledby="rec-title" style="margin-top: 3.5rem;">
        <div class="section-heading section-heading--row">
          <div>
            <div style="display: inline-flex; align-items: center; gap: 0.4rem; background: rgba(37, 99, 235, 0.1); color: #2563eb; padding: 0.25rem 0.65rem; border-radius: 999px; font-size: 0.8rem; font-weight: 700; margin-bottom: 0.4rem;">
              <span>✨ Sugerencias para ti</span>
            </div>
            <h2 id="rec-title">Recomendaciones personalizadas</h2>
            <p>Prendas seleccionadas según tus estilos favoritos, temporadas y tendencias.</p>
          </div>
          <a class="text-link" routerLink="/catalogo">Explorar catálogo</a>
        </div>
        <div class="product-grid">
          @for (item of recommendationsList(); track item.id_producto) {
            <a class="product-card" [routerLink]="['/catalogo', item.id_producto]" style="text-decoration: none; color: inherit; display: flex; flex-direction: column;">
              <div class="product-card__media" style="position: relative; aspect-ratio: 1; border-radius: 8px; overflow: hidden; background: #f1f5f9;">
                <img [src]="item.imagen_url || '/images/hero-catalogo-oficial.jpg'" [alt]="item.nombre" style="width: 100%; height: 100%; object-fit: cover;" />
                @if (item.descuento_porcentaje) {
                  <span style="position: absolute; top: 8px; left: 8px; background: #dc2626; color: #fff; font-weight: 800; font-size: 0.75rem; padding: 2px 6px; border-radius: 4px;">
                    -{{ item.descuento_porcentaje }}%
                  </span>
                }
                @if (item.motivo) {
                  <span style="position: absolute; bottom: 8px; left: 8px; background: rgba(15, 23, 42, 0.8); color: #fff; font-size: 0.7rem; font-weight: 600; padding: 2px 8px; border-radius: 4px; backdrop-filter: blur(4px);">
                    {{ item.motivo }}
                  </span>
                }
              </div>
              <div style="padding: 0.75rem 0.25rem 0; flex: 1; display: flex; flex-direction: column;">
                <span style="font-size: 0.75rem; color: var(--color-text-muted); text-transform: uppercase; font-weight: 700;">{{ item.categoria }} · {{ item.marca }}</span>
                <h3 style="font-size: 0.95rem; font-weight: 700; margin: 0.25rem 0 0.4rem; line-height: 1.3;">{{ item.nombre }}</h3>
                <div style="display: flex; gap: 0.5rem; align-items: baseline; margin-top: auto;">
                  @if (item.precio_promocional) {
                    <strong style="color: #2563eb; font-size: 1rem;">Bs. {{ item.precio_promocional }}</strong>
                    <del style="font-size: 0.8rem; color: var(--color-text-muted);">Bs. {{ item.precio_actual }}</del>
                  } @else {
                    <strong style="font-size: 1rem;">Bs. {{ item.precio_actual }}</strong>
                  }
                </div>
              </div>
            </a>
          }
        </div>
      </section>
    }
  `,
})
export class Home {
  private readonly catalog = inject(CatalogService);
  private readonly errors = inject(ApiErrorService);
  private readonly recService = inject(RecommendationService, { optional: true });

  readonly categories = OFFICIAL_CATEGORIES;
  readonly products = signal<Product[]>([]);
  readonly recommendationsList = signal<RecommendedProduct[]>([]);
  readonly loading = signal(true);
  readonly errorMessage = signal('');
  readonly skeletons = [1, 2, 3, 4];

  constructor() {
    this.loadProducts();
    this.loadRecommendations();
  }

  categoryLabel(category: string): string {
    return category.charAt(0) + category.slice(1).toLowerCase();
  }

  loadProducts(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.catalog
      .products({ page: 1, page_size: 4, activo: true, sort: '-created_at' })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (page) => this.products.set(page.items),
        error: (error) =>
          this.errorMessage.set(
            this.errors.message(error, 'No pudimos cargar los productos recientes.'),
          ),
      });
  }

  loadRecommendations(): void {
    if (!this.recService) return;
    this.recService.getPersonalizedRecommendations(4).subscribe({
      next: (items) => this.recommendationsList.set(items),
      error: () => {},
    });
  }
}
