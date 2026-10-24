import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { TenantContextService } from '../../core/tenant/tenant-context.service';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-tenant-brand-admin',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="brand-settings">
      <header class="brand-settings__header">
        <div>
          <h1>Marca de la empresa</h1>
          <p>Esta identidad aparece en la tienda pública y en el panel de tu equipo.</p>
        </div>
        <span class="brand-settings__status"
          >Subdominio: {{ tenantSubdomain() }}</span
        >
      </header>

      <div class="brand-settings__layout">
        <form class="brand-settings__form" [formGroup]="form" (ngSubmit)="save()">
          <label>
            <span>Nombre comercial</span>
            <input formControlName="nombre" autocomplete="organization" />
            @if (form.controls.nombre.touched && form.controls.nombre.invalid) {
              <small>Escribe al menos 2 caracteres.</small>
            }
          </label>

          <div class="logo-upload">
            <span class="logo-upload__label">Logotipo de la tienda</span>
            <div class="logo-upload__controls">
              <label class="logo-upload__picker">
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  (change)="selectLogo($event)"
                />
                <span>{{ selectedLogo() ? 'Cambiar archivo' : 'Seleccionar imagen' }}</span>
              </label>
              <button
                class="logo-upload__button"
                type="button"
                [disabled]="!selectedLogo() || uploadingLogo()"
                (click)="uploadLogo()"
              >
                {{ uploadingLogo() ? 'Subiendo…' : 'Subir logotipo' }}
              </button>
              @if (tenant.tenant()?.logo_url) {
                <button
                  class="logo-upload__remove"
                  type="button"
                  [disabled]="uploadingLogo()"
                  (click)="deleteLogo()"
                >
                  Eliminar actual
                </button>
              }
            </div>
            @if (selectedLogo()) {
              <small class="field-help">{{ selectedLogo()?.name }}</small>
            } @else {
              <small class="field-help">PNG, JPG o WebP. Tamaño máximo: 2 MB.</small>
            }
          </div>

          <div class="brand-settings__colors">
            <label>
              <span>Color principal</span>
              <div class="color-field">
                <input
                  formControlName="color_primario"
                  type="color"
                  aria-label="Elegir color principal"
                />
                <input
                  formControlName="color_primario"
                  maxlength="7"
                  aria-label="Código del color principal"
                />
              </div>
            </label>
            <label>
              <span>Color de interacción</span>
              <div class="color-field">
                <input
                  formControlName="color_primario_oscuro"
                  type="color"
                  aria-label="Elegir color de interacción"
                />
                <input
                  formControlName="color_primario_oscuro"
                  maxlength="7"
                  aria-label="Código del color de interacción"
                />
              </div>
            </label>
          </div>

          @if (message()) {
            <p class="brand-settings__message" [class.is-error]="hasError()" role="status">
              {{ message() }}
            </p>
          }

          <button type="submit" [disabled]="form.invalid || saving()">
            {{ saving() ? 'Guardando…' : 'Guardar identidad' }}
          </button>
        </form>

        <aside class="brand-preview" [style.--preview-accent]="form.controls.color_primario.value">
          <span>Vista previa</span>
          <div class="brand-preview__logo">
            <img [src]="previewLogo()" alt="" />
          </div>
          <h2>{{ form.controls.nombre.value || 'Nombre de la empresa' }}</h2>
          <p>La marca se aplicará en toda la experiencia de tu empresa.</p>
          <button type="button">Acción principal</button>
        </aside>
      </div>
    </section>
  `,
  styles: `
    .brand-settings {
      max-width: 1120px;
      margin: 0 auto;
      padding: 36px 28px 64px;
    }
    .brand-settings__header {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 24px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }
    h1 {
      margin: 0 0 8px;
      color: var(--ink);
      font-size: clamp(1.8rem, 3vw, 2.6rem);
      letter-spacing: -0.035em;
    }
    .brand-settings__header p,
    .brand-preview p {
      margin: 0;
      color: var(--ink-soft);
    }
    .brand-settings__status {
      color: var(--accent-dark);
      font-size: 0.82rem;
      font-weight: 700;
    }
    .brand-settings__layout {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
      gap: 56px;
      padding-top: 36px;
    }
    .brand-settings__form {
      display: grid;
      gap: 24px;
    }
    label {
      display: grid;
      gap: 8px;
      color: var(--ink);
      font-weight: 700;
    }
    .logo-upload {
      display: grid;
      gap: 8px;
    }
    .logo-upload__label {
      color: var(--ink);
      font-weight: 700;
    }
    .logo-upload__controls {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .logo-upload__picker input {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
    }
    .logo-upload__picker span,
    .logo-upload__button {
      display: inline-flex;
      min-height: 46px;
      box-sizing: border-box;
      align-items: center;
      justify-content: center;
      padding: 0 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      color: var(--ink);
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    .logo-upload__picker:focus-within span {
      outline: 3px solid color-mix(in srgb, var(--accent) 24%, transparent);
      border-color: var(--accent);
    }
    .logo-upload__button {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }
    .logo-upload__button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .logo-upload__remove {
      min-height: 46px;
      padding: 0 4px;
      border: 0;
      background: transparent;
      color: var(--danger);
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    .logo-upload__remove:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    input {
      min-height: 48px;
      box-sizing: border-box;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      color: var(--ink);
      font: inherit;
    }
    input:focus-visible {
      outline: 3px solid color-mix(in srgb, var(--accent) 24%, transparent);
      border-color: var(--accent);
    }
    small {
      color: var(--danger);
      font-weight: 400;
    }
    .field-help {
      color: var(--ink-soft);
    }
    .brand-settings__colors {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }
    .color-field {
      display: grid;
      grid-template-columns: 52px 1fr;
      gap: 10px;
    }
    .color-field input[type='color'] {
      width: 52px;
      padding: 5px;
      cursor: pointer;
    }
    .brand-settings__form > button,
    .brand-preview button {
      min-height: 48px;
      padding: 0 20px;
      border: 1px solid var(--accent);
      border-radius: 8px;
      background: var(--accent);
      color: #fff;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    .brand-settings__form > button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .brand-settings__message {
      margin: 0;
      color: #047857;
    }
    .brand-settings__message.is-error {
      color: var(--danger);
    }
    .brand-preview {
      align-self: start;
      padding: 28px;
      border-top: 4px solid var(--preview-accent);
      border-bottom: 1px solid var(--line);
      background: var(--surface);
    }
    .brand-preview > span {
      color: var(--ink-soft);
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .brand-preview__logo {
      display: flex;
      height: 72px;
      align-items: center;
      margin: 28px 0 22px;
    }
    .brand-preview__logo img {
      max-width: 190px;
      max-height: 72px;
      object-fit: contain;
    }
    .brand-preview h2 {
      margin: 0 0 10px;
      color: var(--ink);
      font-size: 1.7rem;
    }
    .brand-preview button {
      margin-top: 24px;
      background: var(--preview-accent);
      border-color: var(--preview-accent);
    }
    @media (max-width: 800px) {
      .brand-settings {
        padding: 24px 18px 48px;
      }
      .brand-settings__header {
        align-items: flex-start;
        flex-direction: column;
      }
      .brand-settings__layout {
        grid-template-columns: 1fr;
        gap: 32px;
      }
    }
    @media (max-width: 520px) {
      .brand-settings__colors {
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class TenantBrandAdmin {
  readonly tenant = inject(TenantContextService);
  readonly saving = signal(false);
  readonly uploadingLogo = signal(false);
  readonly selectedLogo = signal<File | null>(null);
  readonly localLogoPreview = signal<string | null>(null);
  readonly message = signal('');
  readonly hasError = signal(false);
  readonly form = new FormGroup({
    nombre: new FormControl(this.tenant.name(), {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(2), Validators.maxLength(150)],
    }),
    color_primario: new FormControl(this.tenant.primaryColor(), {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(/^#[0-9A-Fa-f]{6}$/)],
    }),
    color_primario_oscuro: new FormControl(this.tenant.primaryDarkColor(), {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(/^#[0-9A-Fa-f]{6}$/)],
    }),
  });

  tenantSubdomain(): string {
    const slug = this.tenant.tenant()?.slug ?? '';
    const domain = environment.tenantBaseDomain || 'localhost';
    return slug ? `${slug}.${domain}` : domain;
  }

  previewLogo(): string {
    return this.localLogoPreview() || this.tenant.logoUrl();
  }

  selectLogo(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    this.message.set('');
    this.hasError.set(false);
    if (!file) {
      this.selectedLogo.set(null);
      this.localLogoPreview.set(null);
      return;
    }
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      this.selectedLogo.set(null);
      this.localLogoPreview.set(null);
      this.hasError.set(true);
      this.message.set('Usa un logotipo PNG, JPG o WebP.');
      input.value = '';
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      this.selectedLogo.set(null);
      this.localLogoPreview.set(null);
      this.hasError.set(true);
      this.message.set('El logotipo no debe superar 2 MB.');
      input.value = '';
      return;
    }
    this.selectedLogo.set(file);
    const reader = new FileReader();
    reader.onload = () => this.localLogoPreview.set(String(reader.result));
    reader.readAsDataURL(file);
  }

  uploadLogo(): void {
    const file = this.selectedLogo();
    if (!file || this.uploadingLogo()) return;
    this.uploadingLogo.set(true);
    this.message.set('');
    this.hasError.set(false);
    this.tenant.uploadLogo(file).subscribe({
      next: () => {
        this.uploadingLogo.set(false);
        this.selectedLogo.set(null);
        this.localLogoPreview.set(null);
        this.message.set('Logotipo actualizado correctamente.');
      },
      error: (error: HttpErrorResponse) => {
        this.uploadingLogo.set(false);
        this.hasError.set(true);
        this.message.set(error.error?.detail || 'No se pudo subir el logotipo.');
      },
    });
  }

  deleteLogo(): void {
    if (this.uploadingLogo()) return;
    this.uploadingLogo.set(true);
    this.message.set('');
    this.hasError.set(false);
    this.tenant.deleteLogo().subscribe({
      next: () => {
        this.uploadingLogo.set(false);
        this.selectedLogo.set(null);
        this.localLogoPreview.set(null);
        this.message.set('Logotipo eliminado correctamente.');
      },
      error: (error: HttpErrorResponse) => {
        this.uploadingLogo.set(false);
        this.hasError.set(true);
        this.message.set(error.error?.detail || 'No se pudo eliminar el logotipo.');
      },
    });
  }

  save(): void {
    if (this.form.invalid || this.saving()) return;
    this.saving.set(true);
    this.message.set('');
    this.hasError.set(false);
    const value = this.form.getRawValue();
    this.tenant.updateBrand(value).subscribe({
      next: () => {
        this.saving.set(false);
        this.message.set('Identidad actualizada correctamente.');
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.hasError.set(true);
        this.message.set(error.error?.detail || 'No se pudo guardar la identidad.');
      },
    });
  }
}
