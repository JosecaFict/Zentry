import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { API_BASE_URL } from '../config/api.config';
import {
  ChangePasswordRequest,
  LoginRequest,
  MessageResponse,
  PasswordRecoveryRequest,
  PasswordRecoveryVerifyRequest,
  PasswordRecoveryVerifyResponse,
  PasswordResetRequest,
  RegisterRequest,
  TokenResponse,
  UpdateProfileRequest,
  UserResponse,
} from '../models/auth.model';
import { TokenStorageService } from './token-storage.service';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly tokenStorage = inject(TokenStorageService);
  private readonly sessionKey = 'zentry_cached_session';
  private readonly currentUserState = signal<UserResponse | null>(this.readCachedUser());
  private readonly loadingState = signal(false);

  readonly currentUser = this.currentUserState.asReadonly();
  readonly loading = this.loadingState.asReadonly();
  readonly isAuthenticated = computed(() => !!this.currentUserState() && !!this.tokenStorage.get());

  register(payload: RegisterRequest): Observable<UserResponse> {  // [CU-01] Registro de cliente
    return this.http.post<UserResponse>(`${API_BASE_URL}/auth/register`, payload);
  }

  login(payload: LoginRequest): Observable<TokenResponse> {  // [CU-01] Inicio de sesión (Login)
    this.clearCachedUser();
    this.currentUserState.set(null);
    return this.http
      .post<TokenResponse>(`${API_BASE_URL}/auth/login`, payload)
      .pipe(tap((response) => this.tokenStorage.set(response.access_token)));
  }

  requestPasswordRecovery(payload: PasswordRecoveryRequest): Observable<MessageResponse> {  // [CU-08] Solicitar código OTP
    return this.http.post<MessageResponse>(
      `${API_BASE_URL}/auth/password-recovery/request`,
      payload,
    );
  }

  verifyPasswordRecoveryCode(  // [CU-08] Verificar código OTP
    payload: PasswordRecoveryVerifyRequest,
  ): Observable<PasswordRecoveryVerifyResponse> {
    return this.http.post<PasswordRecoveryVerifyResponse>(
      `${API_BASE_URL}/auth/password-recovery/verify`,
      payload,
    );
  }

  resetPassword(payload: PasswordResetRequest): Observable<MessageResponse> {  // [CU-08] Restablecer contraseña con token OTP
    return this.http.post<MessageResponse>(`${API_BASE_URL}/auth/password-recovery/reset`, payload);
  }

  updateProfile(payload: UpdateProfileRequest): Observable<UserResponse> {  // [CU-01] Actualizar datos del perfil
    return this.http
      .patch<UserResponse>(`${API_BASE_URL}/auth/me`, payload)
      .pipe(tap((user) => this.setCurrentUser(user)));
  }

  uploadAvatar(file: File): Observable<UserResponse> {  // [CU-01] Subir foto de perfil a Cloudinary
    const formData = new FormData();
    formData.append('file', file);
    return this.http
      .post<UserResponse>(`${API_BASE_URL}/auth/me/avatar`, formData)
      .pipe(tap((user) => this.setCurrentUser(user)));
  }

  deleteAvatar(): Observable<UserResponse> {  // [CU-01] Eliminar foto de perfil
    return this.http
      .delete<UserResponse>(`${API_BASE_URL}/auth/me/avatar`)
      .pipe(tap((user) => this.setCurrentUser(user)));
  }

  changePassword(payload: ChangePasswordRequest): Observable<MessageResponse> {  // [CU-01] Cambiar contraseña
    return this.http.post<MessageResponse>(`${API_BASE_URL}/auth/change-password`, payload);
  }

  loadCurrentUser(): Observable<UserResponse> {  // [CU-01] Cargar usuario actual (/auth/me)
    this.loadingState.set(true);
    return this.http.get<UserResponse>(`${API_BASE_URL}/auth/me`).pipe(
      tap({
        next: (user) => {
          this.setCurrentUser(user);
          this.loadingState.set(false);
        },
        error: () => this.loadingState.set(false),
      }),
    );
  }

  restoreSession(): void {
    if (!this.tokenStorage.get() || this.currentUserState() || this.loadingState()) return;
    this.loadCurrentUser().subscribe({
      error: (error) => {
        if (error?.status && error.status !== 0) this.logout();
      },
    });
  }

  token(): string | null {
    return this.tokenStorage.get();
  }

  logout(): void {
    this.tokenStorage.clear();
    this.currentUserState.set(null);
    this.clearCachedUser();
  }

  private setCurrentUser(user: UserResponse): void {
    this.currentUserState.set(user);
    const token = this.tokenStorage.get();
    if (typeof localStorage === 'undefined' || !token) return;
    localStorage.setItem(
      this.sessionKey,
      JSON.stringify({ tokenMarker: this.tokenMarker(token), user }),
    );
  }

  private readCachedUser(): UserResponse | null {
    if (typeof localStorage === 'undefined') return null;
    const token = this.tokenStorage.get();
    if (!token) return null;
    try {
      const cached = JSON.parse(localStorage.getItem(this.sessionKey) ?? 'null') as {
        tokenMarker?: string;
        user?: UserResponse;
      } | null;
      return cached?.tokenMarker === this.tokenMarker(token) && cached.user ? cached.user : null;
    } catch {
      this.clearCachedUser();
      return null;
    }
  }

  private clearCachedUser(): void {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(this.sessionKey);
  }

  private tokenMarker(token: string): string {
    return token.slice(-24);
  }
}
