import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ConnectivityService {
  private readonly onlineState = signal(typeof navigator === 'undefined' || navigator.onLine);

  readonly online = this.onlineState.asReadonly();

  constructor() {
    if (typeof window === 'undefined') return;
    window.addEventListener('online', () => this.onlineState.set(true));
    window.addEventListener('offline', () => this.onlineState.set(false));
  }
}
