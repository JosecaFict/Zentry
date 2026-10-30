import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE_URL } from '../config/api.config';
import {
  CatalogSnapshot,
  PendingOfflineOperation,
  SyncBatchResponse,
  SyncDeviceResponse,
} from './offline.models';

@Injectable({ providedIn: 'root' })
export class SyncApiService {
  private readonly http = inject(HttpClient);

  registerDevice(payload: {
    id_dispositivo: string;
    nombre: string;
    plataforma: 'PWA';
    version_app: string;
    id_sucursal: number;
  }): Observable<SyncDeviceResponse> {
    return this.http.post<SyncDeviceResponse>(`${API_BASE_URL}/sync/devices`, payload);
  }

  catalog(branchId: number): Observable<CatalogSnapshot> {
    const params = new HttpParams().set('id_sucursal', branchId);
    return this.http.get<CatalogSnapshot>(`${API_BASE_URL}/sync/catalog`, { params });
  }

  submitBatch(
    idLote: string,
    deviceId: string,
    operations: PendingOfflineOperation[],
  ): Observable<SyncBatchResponse> {
    return this.http.post<SyncBatchResponse>(`${API_BASE_URL}/sync/batches`, {
      id_lote: idLote,
      id_dispositivo: deviceId,
      fecha_cliente: new Date().toISOString(),
      operaciones: operations.map(({ id_operacion, tipo, fecha_cliente, payload }) => ({
        id_operacion,
        tipo,
        fecha_cliente,
        payload,
      })),
    });
  }

  batch(idLote: string): Observable<SyncBatchResponse> {
    return this.http.get<SyncBatchResponse>(`${API_BASE_URL}/sync/batches/${idLote}`);
  }

  confirmBatch(idLote: string, deviceId: string): Observable<SyncBatchResponse> {
    return this.http.post<SyncBatchResponse>(
      `${API_BASE_URL}/sync/batches/${idLote}/confirm`,
      { id_dispositivo: deviceId },
    );
  }
}
