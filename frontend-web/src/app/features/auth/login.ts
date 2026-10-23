import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize, switchMap } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { UserResponse } from '../../core/models/auth.model';
import { ADMIN_PERMISSIONS } from '../../core/permissions/permission.service';
import { ApiErrorService } from '../../core/services/api-error.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';
import { PasswordField } from './password-field';

export function resolveLoginDestination(user: UserResponse, returnUrl: string | null): string {
  const requestedPath = returnUrl?.trim();
  if (requestedPath?.startsWith('/') && !requestedPath.startsWith('//')) {
    return requestedPath;
  }
  if (user.roles.includes('SUPERADMIN')) return '/platform';
  const hasAdminAccess = ADMIN_PERMISSIONS.some((permission) => user.permisos.includes(permission));
  return hasAdminAccess ? '/admin' : '/catalogo';
}

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink, PasswordField],
  template: `
    <section class="auth-page auth-page--login" [class.auth-page--platform]="isPlatformLogin">
      <div class="auth-visual" aria-hidden="true">
        @if (isPlatformLogin) {
          <div class="auth-platform-visual">
            <img src="/images/zentry-logo-white.png" alt="" />
            <p>Control global para operar empresas, planes y accesos desde un solo lugar.</p>
          </div>
        } @else {
          <img src="/images/acceso-hombre-polo.jpg" alt="" />
        }
      </div>
      <div class="auth-panel">
        @if (!isPlatformLogin) {
          <a class="back-link" routerLink="/">Volver al inicio</a>
        } @else {
          <p class="auth-platform-kicker">Administración de plataforma</p>
        }
        <div class="auth-brand-header">
          <a
            [routerLink]="isPlatformLogin ? '/platform/login' : '/'"
            class="auth-brand-link"
            [attr.aria-label]="isPlatformLogin ? 'Zentry' : tenant.name()"
          >
            <img
              [src]="isPlatformLogin ? '/images/zentry-logo.png' : tenant.logoUrl()"
              [alt]="isPlatformLogin ? 'Zentry' : tenant.name()"
              class="auth-brand-logo"
            />
          </a>
        </div>
        <h1>{{ isPlatformLogin ? 'Accede a Zentry' : 'Bienvenido a ' + tenant.name() }}</h1>
        @if (registrationComplete()) {
          <div class="notice notice--success" role="status">
            Tu cuenta fue creada. Ya puedes ingresar.
          </div>
        }
        @if (sessionExpired()) {
          <div class="notice notice--warning" role="status">
            Tu sesión expiró. Ingresa nuevamente para continuar.
          </div>
        }
        @if (errorMessage()) {
          <div class="notice notice--error" role="alert">{{ errorMessage() }}</div>
        }
        <form class="form-stack" [formGroup]="form" (ngSubmit)="submit()" novalidate>
          <div class="field">
            <label for="login-email">Correo electrónico</label>
            <input
              id="login-email"
              type="email"
              formControlName="correo"
              autocomplete="email"
              [attr.aria-invalid]="invalid('correo')"
            />
            @if (invalid('correo')) {
              <p class="field-error">Ingresa un correo electrónico válido.</p>
            }
          </div>
          <app-password-field
            fieldId="login-password"
            label="Contraseña"
            autocomplete="current-password"
            [control]="form.controls.password"
            [invalid]="invalid('password')"
            [errorText]="invalid('password') ? 'La contraseña es obligatoria.' : ''"
          />
          @if (!isPlatformLogin) {
            <a class="auth-assist-link" routerLink="/recuperar-contrasena">
              ¿Olvidaste tu contraseña?
            </a>
          }
          <button
            class="button button--primary button--full"
            type="submit"
            [disabled]="form.invalid || submitting()"
          >
            {{ submitting() ? 'Ingresando…' : 'Ingresar' }}
          </button>
        </form>
        @if (!isPlatformLogin) {
          <p class="auth-switch">
            ¿Aún no tienes cuenta? <a routerLink="/registro">Crear cuenta</a>
          </p>
        } @else {
          <p class="auth-switch">Acceso reservado para administradores globales.</p>
        }
      </div>
    </section>
  `,
})
/** [CU-01] Componente de Inicio de Sesión (Login) */
export class Login {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly errors = inject(ApiErrorService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly tenant = inject(TenantContextService);
  readonly submitting = signal(false);
  readonly errorMessage = signal('');
  readonly sessionExpired = signal(this.route.snapshot.queryParamMap.get('sesion') === 'expirada');
  readonly registrationComplete = signal(
    this.route.snapshot.queryParamMap.get('registro') === 'completo',
  );
  readonly isPlatformLogin = this.route.snapshot.data['platformLogin'] === true;
  readonly form = this.fb.nonNullable.group({
    correo: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  invalid(name: 'correo' | 'password'): boolean {
    const control = this.form.controls[name];
    return control.invalid && (control.touched || this.form.touched);
  }

  submit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.submitting()) return;
    this.submitting.set(true);
    this.errorMessage.set('');
    this.auth
      .login(this.form.getRawValue())
      .pipe(
        switchMap(() => this.auth.loadCurrentUser()),
        finalize(() => this.submitting.set(false)),
      )
      .subscribe({
        next: (user) => {
          if (this.isPlatformLogin && !user.roles.includes('SUPERADMIN')) {
            this.auth.logout();
            this.errorMessage.set('Esta cuenta no tiene acceso global a Zentry.');
            return;
          }
          void this.router.navigateByUrl(
            resolveLoginDestination(user, this.route.snapshot.queryParamMap.get('returnUrl')),
          );
        },
        error: (error) =>
          this.errorMessage.set(this.errors.message(error, 'Correo o contraseña incorrectos.')),
      });
  }
}
