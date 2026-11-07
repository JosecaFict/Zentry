import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { API_BASE_URL } from '../config/api.config';

export interface AssistantConversation {
  id_conversacion: string;
  modo: 'EMPRESA' | 'CLIENTE';
  proveedor: 'GROQ' | 'GEMINI';
  modelo: string;
  estado: 'ACTIVA' | 'ARCHIVADA';
  created_at: string;
  updated_at: string;
}

export interface AssistantMessage {
  id_mensaje: number;
  rol: 'USUARIO' | 'ASISTENTE';
  contenido: string;
  created_at: string;
  productos: AssistantProduct[];
  reporte_exportable?: boolean;
}

export interface AssistantProduct {
  id_producto: number;
  nombre: string;
  categoria: string;
  marca: string;
  precio: string;
  precio_original: string | null;
  descuento_porcentaje: string | null;
  promocion_nombre: string | null;
  imagen_url: string | null;
  tallas: string[];
  colores: string[];
  permite_vestidor: boolean;
}

export interface AssistantExchange {
  usuario: AssistantMessage;
  asistente: AssistantMessage;
}

@Injectable({ providedIn: 'root' })
export class AssistantService {
  private readonly http = inject(HttpClient);
  private readonly base = `${API_BASE_URL}/assistant/conversations`;

  list() {
    return this.http.get<AssistantConversation[]>(this.base);
  }

  create(mode: 'CLIENTE' | 'EMPRESA' = 'CLIENTE') {
    return this.http.post<AssistantConversation>(this.base, { modo: mode });
  }

  messages(conversationId: string) {
    return this.http.get<AssistantMessage[]>(`${this.base}/${conversationId}/messages`);
  }

  send(conversationId: string, content: string) {
    return this.http.post<AssistantExchange>(`${this.base}/${conversationId}/messages`, {
      contenido: content,
    });
  }

  transcribe(audio: Blob) {
    const form = new FormData();
    const extension = audio.type.includes('ogg') ? 'ogg' : audio.type.includes('mp4') ? 'm4a' : 'webm';
    form.append('audio', audio, `consulta.${extension}`);
    return this.http.post<{ texto: string }>(`${API_BASE_URL}/assistant/transcribe`, form);
  }

  archive(conversationId: string) {
    return this.http.post<void>(`${this.base}/${conversationId}/archive`, {});
  }

  exportReport(conversationId: string, messageId: number, format: 'pdf' | 'xlsx') {
    return this.http.get(`${this.base}/${conversationId}/messages/${messageId}/export/${format}`, { responseType: 'blob' });
  }
}
