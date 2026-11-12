import { Injectable, signal } from '@angular/core';

import { API_BASE_URL } from '../config/api.config';

/** Cada cuánto se confirma que el servidor responde mientras la página está visible. */
export const CONNECTIVITY_CHECK_INTERVAL_MS = 30_000;
const PING_TIMEOUT_MS = 5_000;

/**
 * Estado real de la conexión. `navigator.onLine` solo dice si hay red (WiFi
 * o cable), no si hay internet ni si el servidor responde; por eso además se
 * hace un ping a `/health` al iniciar, al cambiar la red, al volver a la
 * pestaña y cada 30 s.
 */
@Injectable({ providedIn: 'root' })
export class ConnectivityService {
  private readonly onlineState = signal(typeof navigator === 'undefined' || navigator.onLine);
  private readonly checkedAtState = signal<Date | null>(null);
  private readonly offlineSinceState = signal<Date | null>(null);
  private timer?: ReturnType<typeof setInterval>;
  private running: Promise<boolean> | null = null;

  readonly online = this.onlineState.asReadonly();
  /** Última verificación terminada (cambia en cada chequeo, aunque el estado no cambie). */
  readonly checkedAt = this.checkedAtState.asReadonly();
  readonly offlineSince = this.offlineSinceState.asReadonly();

  constructor() {
    if (typeof window === 'undefined') return;
    window.addEventListener('online', () => void this.check());
    window.addEventListener('offline', () => this.set(false));
  }

  /** Empieza los chequeos periódicos (una vez, desde el arranque de la app). */
  start(): void {
    if (this.timer || typeof window === 'undefined') return;
    void this.check();
    this.timer = setInterval(() => {
      if (document.visibilityState === 'visible') void this.check();
    }, CONNECTIVITY_CHECK_INTERVAL_MS);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') void this.check();
    });
  }

  /** Verifica ahora; si ya hay una verificación en curso, devuelve esa. */
  check(): Promise<boolean> {
    return (this.running ??= this.probe().then((online) => {
      this.set(online);
      return online;
    }).finally(() => (this.running = null)));
  }

  private async probe(): Promise<boolean> {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), PING_TIMEOUT_MS);
    try {
      // ngsw-bypass: que el service worker no responda desde su caché.
      const response = await fetch(`${API_BASE_URL}/health?ngsw-bypass=true`, {
        cache: 'no-store',
        signal: controller.signal,
      });
      // Un 4xx también prueba que hay red hasta el servidor.
      return response.status < 500;
    } catch {
      return false;
    } finally {
      clearTimeout(timeout);
    }
  }

  private set(online: boolean): void {
    this.onlineState.set(online);
    this.offlineSinceState.set(online ? null : (this.offlineSinceState() ?? new Date()));
    this.checkedAtState.set(new Date());
  }
}
