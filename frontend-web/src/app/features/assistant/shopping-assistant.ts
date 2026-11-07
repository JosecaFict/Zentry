import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, ElementRef, inject, OnDestroy, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import {
  AssistantConversation,
  AssistantMessage,
  AssistantService,
} from '../../core/services/assistant.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';
import { BolivianosPipe } from '../../shared/pipes/bolivianos.pipe';

@Component({
  selector: 'app-shopping-assistant',
  imports: [DatePipe, FormsModule, RouterLink, BolivianosPipe],
  templateUrl: './shopping-assistant.html',
  styleUrl: './shopping-assistant.scss',
})
export class ShoppingAssistant implements OnDestroy {
  readonly auth = inject(AuthService);
  readonly tenant = inject(TenantContextService);
  private readonly assistant = inject(AssistantService);
  private readonly scrollArea = viewChild<ElementRef<HTMLElement>>('messageList');

  readonly visible = computed(() =>
    this.auth.isAuthenticated()
      && this.auth.currentUser()?.roles.includes('CLIENTE') === true
      && this.auth.currentUser()?.roles.includes('ADMIN') !== true
      && this.auth.currentUser()?.roles.includes('SUPERADMIN') !== true,
  );
  readonly accentText = computed(() => {
    const hex = this.tenant.primaryColor().replace('#', '');
    if (!/^[0-9a-f]{6}$/i.test(hex)) return '#ffffff';
    const channels = [0, 2, 4].map((index) => {
      const value = parseInt(hex.slice(index, index + 2), 16) / 255;
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    });
    const luminance = channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    return luminance > 0.179 ? '#121418' : '#ffffff';
  });
  readonly open = signal(false);
  readonly historyOpen = signal(false);
  readonly busy = signal(false);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly voiceRecording = signal(false);
  readonly voiceTranscribing = signal(false);
  readonly voiceMessage = signal('');
  readonly conversations = signal<AssistantConversation[]>([]);
  readonly active = signal<AssistantConversation | null>(null);
  readonly messages = signal<AssistantMessage[]>([]);
  draft = '';
  private owner = '';
  private mediaRecorder: MediaRecorder | null = null;
  private mediaStream: MediaStream | null = null;
  private voiceChunks: Blob[] = [];
  private voiceTimer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    effect(() => {
      const user = this.auth.currentUser();
      const tenantId = this.tenant.tenant()?.id_tenant;
      // Discard in-memory chat whenever the account or tenant changes.
      const nextOwner = user && tenantId && user.roles.includes('CLIENTE')
        ? `${tenantId}:${user.id_usuario}` : '';
      if (nextOwner !== this.owner) {
        this.owner = nextOwner;
        this.reset();
      }
    });
  }

  toggle(): void {
    if (this.open()) {
      this.stopVoiceRecording();
      this.open.set(false);
      this.historyOpen.set(false);
      return;
    }
    this.open.set(true);
    this.loadConversations();
  }

  loadConversations(): void {
    const owner = this.owner;
    this.loading.set(true);
    this.error.set('');
    this.assistant.list().subscribe({
      next: (items) => {
        if (owner !== this.owner) return;
        const clientItems = items.filter((item) => item.modo === 'CLIENTE');
        this.conversations.set(clientItems);
        if (this.active()) {
          const current = clientItems.find((item) => item.id_conversacion === this.active()?.id_conversacion);
          if (!current) {
            this.active.set(null);
            this.messages.set([]);
          }
        }
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        if (owner !== this.owner) return;
        this.error.set(this.errorText(error, 'No pudimos cargar tus conversaciones.'));
        this.loading.set(false);
      },
    });
  }

  select(conversation: AssistantConversation): void {
    if (this.busy()) return;
    const owner = this.owner;
    this.active.set(conversation);
    this.messages.set([]);
    this.historyOpen.set(false);
    this.loading.set(true);
    this.error.set('');
    this.assistant.messages(conversation.id_conversacion).subscribe({
      next: (items) => {
        if (owner !== this.owner || this.active()?.id_conversacion !== conversation.id_conversacion) return;
        this.messages.set(items);
        this.loading.set(false);
        this.scrollToBottom();
      },
      error: (error: HttpErrorResponse) => {
        if (owner !== this.owner) return;
        this.error.set(this.errorText(error, 'No pudimos abrir esta conversación.'));
        this.loading.set(false);
      },
    });
  }

  newConversation(): void {
    if (this.busy()) return;
    this.active.set(null);
    this.messages.set([]);
    this.historyOpen.set(false);
    this.error.set('');
    this.draft = '';
  }

  send(): void {
    const question = this.draft.trim();
    if (!question || this.busy() || this.loading() || this.voiceRecording() || this.voiceTranscribing()) return;
    this.busy.set(true);
    const owner = this.owner;
    this.error.set('');
    const conversation = this.active();
    if (conversation?.estado === 'ACTIVA') {
      this.sendToConversation(conversation.id_conversacion, question);
    } else {
      this.assistant.create().subscribe({
        next: (created) => {
          if (owner !== this.owner) return;
          this.active.set(created);
          this.conversations.update((items) => [created, ...items]);
          this.sendToConversation(created.id_conversacion, question);
        },
        error: (error: HttpErrorResponse) => {
          if (owner !== this.owner) return;
          this.error.set(this.errorText(error, 'No pudimos iniciar la conversación.'));
          this.busy.set(false);
        },
      });
    }
  }

  archive(): void {
    const conversation = this.active();
    if (!conversation || this.busy()) return;
    this.busy.set(true);
    const owner = this.owner;
    this.assistant.archive(conversation.id_conversacion).subscribe({
      next: () => {
        if (owner !== this.owner) return;
        this.conversations.update((items) => items.map((item) =>
          item.id_conversacion === conversation.id_conversacion
            ? { ...item, estado: 'ARCHIVADA' }
            : item,
        ));
        this.busy.set(false);
        this.newConversation();
      },
      error: (error: HttpErrorResponse) => {
        if (owner !== this.owner) return;
        this.error.set(this.errorText(error, 'No pudimos archivar la conversación.'));
        this.busy.set(false);
      },
    });
  }

  onComposerKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  ngOnDestroy(): void {
    this.stopVoiceRecording();
  }

  async toggleVoiceRecording(): Promise<void> {
    if (this.voiceRecording()) {
      this.mediaRecorder?.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      this.voiceMessage.set('Este navegador no permite grabar audio. Puedes escribir tu pregunta.');
      return;
    }
    this.voiceMessage.set('');
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
        .find((candidate) => MediaRecorder.isTypeSupported(candidate));
      this.mediaRecorder = type
        ? new MediaRecorder(this.mediaStream, { mimeType: type })
        : new MediaRecorder(this.mediaStream);
      this.voiceChunks = [];
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size) this.voiceChunks.push(event.data);
      };
      this.mediaRecorder.onstop = () => this.finishVoiceRecording();
      this.mediaRecorder.start();
      this.voiceRecording.set(true);
      this.voiceTimer = setTimeout(() => this.mediaRecorder?.stop(), 60000);
    } catch {
      this.voiceMessage.set('No pudimos iniciar el micrófono. Revisa el permiso e inténtalo de nuevo.');
      this.stopVoiceTracks();
    }
  }

  private finishVoiceRecording(): void {
    const type = this.mediaRecorder?.mimeType || 'audio/webm';
    const audio = new Blob(this.voiceChunks, { type });
    this.voiceRecording.set(false);
    this.stopVoiceTracks();
    if (!audio.size) {
      this.voiceMessage.set('No se detectó audio. Inténtalo otra vez.');
      return;
    }
    this.voiceTranscribing.set(true);
    const owner = this.owner;
    this.assistant.transcribe(audio).subscribe({
      next: ({ texto }) => {
        if (owner !== this.owner) return;
        this.draft = texto;
        this.voiceMessage.set('Texto listo. Revísalo y presiona Enviar.');
        this.voiceTranscribing.set(false);
      },
      error: (error: HttpErrorResponse) => {
        if (owner !== this.owner) return;
        this.voiceMessage.set(error.error?.detail || 'No pudimos transcribir la grabación.');
        this.voiceTranscribing.set(false);
      },
    });
  }

  private stopVoiceRecording(): void {
    if (this.mediaRecorder?.state === 'recording') {
      this.mediaRecorder.onstop = null;
      this.mediaRecorder.stop();
    }
    this.voiceRecording.set(false);
    this.stopVoiceTracks();
  }

  private stopVoiceTracks(): void {
    if (this.voiceTimer) clearTimeout(this.voiceTimer);
    this.voiceTimer = null;
    this.mediaStream?.getTracks().forEach((track) => track.stop());
    this.mediaStream = null;
  }

  private sendToConversation(conversationId: string, question: string): void {
    const owner = this.owner;
    this.draft = '';
    this.assistant.send(conversationId, question).subscribe({
      next: (exchange) => {
        if (owner !== this.owner) return;
        if (this.active()?.id_conversacion === conversationId) {
          this.messages.update((items) => [...items, exchange.usuario, exchange.asistente]);
          this.scrollToBottom();
        }
        this.busy.set(false);
      },
      error: (error: HttpErrorResponse) => {
        if (owner !== this.owner) return;
        this.draft = question;
        this.error.set(this.errorText(error, 'No pudimos enviar el mensaje. Inténtalo de nuevo.'));
        this.busy.set(false);
      },
    });
  }

  private errorText(error: HttpErrorResponse, fallback: string): string {
    if (error.status === 503) return 'El asesor no está disponible en este momento. Inténtalo más tarde.';
    if (error.status === 403) return 'Tu cuenta no tiene acceso al asesor de compras.';
    return fallback;
  }

  private scrollToBottom(): void {
    requestAnimationFrame(() => {
      const element = this.scrollArea()?.nativeElement;
      if (element) element.scrollTop = element.scrollHeight;
    });
  }

  private reset(): void {
    this.stopVoiceRecording();
    this.open.set(false);
    this.historyOpen.set(false);
    this.active.set(null);
    this.conversations.set([]);
    this.messages.set([]);
    this.draft = '';
    this.error.set('');
    this.voiceTranscribing.set(false);
    this.voiceMessage.set('');
  }
}
