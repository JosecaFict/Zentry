import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, ElementRef, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { AssistantConversation, AssistantMessage, AssistantService } from '../../core/services/assistant.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';
import { AssistantMessageBody } from './assistant-message';

@Component({
  selector: 'app-admin-assistant',
  imports: [FormsModule, RouterLink, AssistantMessageBody],
  templateUrl: './admin-assistant.html',
  styleUrl: './admin-assistant.scss',
})
export class AdminAssistant {
  private readonly auth = inject(AuthService);
  private readonly assistant = inject(AssistantService);
  readonly tenant = inject(TenantContextService);
  private readonly messageList = viewChild<ElementRef<HTMLElement>>('messageList');

  readonly visible = computed(() => this.auth.currentUser()?.roles.includes('ADMIN') === true);
  readonly professional = computed(() => ['PROFESIONAL', 'EMPRESARIAL'].includes(this.tenant.tenant()?.plan_codigo ?? ''));
  readonly open = signal(false);
  readonly historyOpen = signal(false);
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly downloading = signal<{ messageId: number; format: 'pdf' | 'xlsx' } | null>(null);
  readonly conversations = signal<AssistantConversation[]>([]);
  readonly active = signal<AssistantConversation | null>(null);
  readonly messages = signal<AssistantMessage[]>([]);
  readonly lastQuestion = computed(() => [...this.messages()].reverse().find((item) => item.rol === 'USUARIO')?.contenido ?? '');
  draft = '';
  private owner = '';

  constructor() {
    effect(() => {
      const user = this.auth.currentUser();
      const tenantId = this.tenant.tenant()?.id_tenant;
      const owner = user?.roles.includes('ADMIN') && tenantId ? `${tenantId}:${user.id_usuario}` : '';
      if (owner !== this.owner) {
        this.owner = owner;
        this.reset();
      }
    });
  }

  toggle(): void {
    this.open.set(!this.open());
    this.historyOpen.set(false);
    if (this.open()) this.loadConversations();
  }

  loadConversations(): void {
    const owner = this.owner;
    this.loading.set(true);
    this.error.set('');
    this.assistant.list().subscribe({
      next: (items) => {
        if (owner !== this.owner) return;
        this.conversations.set(items.filter((item) => item.modo === 'EMPRESA'));
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        if (owner !== this.owner) return;
        this.error.set(this.errorText(error, 'No pudimos cargar las conversaciones.'));
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
        this.error.set(this.errorText(error, 'No pudimos abrir la conversación.'));
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
    if (!question || this.busy() || this.loading()) return;
    this.busy.set(true);
    this.error.set('');
    const owner = this.owner;
    const conversation = this.active();
    if (conversation?.estado === 'ACTIVA') {
      this.sendToConversation(conversation.id_conversacion, question);
      return;
    }
    this.assistant.create('EMPRESA').subscribe({
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

  archive(): void {
    const conversation = this.active();
    if (!conversation || this.busy()) return;
    const owner = this.owner;
    this.busy.set(true);
    this.assistant.archive(conversation.id_conversacion).subscribe({
      next: () => {
        if (owner !== this.owner) return;
        this.conversations.update((items) => items.map((item) =>
          item.id_conversacion === conversation.id_conversacion ? { ...item, estado: 'ARCHIVADA' } : item,
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

  downloadReport(message: AssistantMessage, format: 'pdf' | 'xlsx'): void {
    const conversation = this.active();
    if (!conversation || !message.reporte_exportable || !this.professional() || this.downloading()) return;
    const owner = this.owner;
    this.downloading.set({ messageId: message.id_mensaje, format });
    this.error.set('');
    this.assistant.exportReport(conversation.id_conversacion, message.id_mensaje, format).subscribe({
      next: (blob) => {
        if (owner !== this.owner) return;
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `reporte-chat-${message.id_mensaje}.${format}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        this.downloading.set(null);
      },
      error: (error: HttpErrorResponse) => {
        if (owner !== this.owner) return;
        this.downloading.set(null);
        this.error.set(error.status === 409
          ? 'Este mensaje no tiene un reporte guardado. Realiza una nueva consulta para descargarlo.'
          : this.errorText(error, 'No pudimos descargar el reporte. Inténtalo nuevamente.'));
      },
    });
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  private sendToConversation(id: string, question: string): void {
    const owner = this.owner;
    this.draft = '';
    this.assistant.send(id, question).subscribe({
      next: (exchange) => {
        if (owner !== this.owner) return;
        if (this.active()?.id_conversacion === id) {
          this.messages.update((items) => [...items, exchange.usuario, exchange.asistente]);
          this.scrollToBottom();
        }
        this.busy.set(false);
      },
      error: (error: HttpErrorResponse) => {
        if (owner !== this.owner) return;
        this.draft = question;
        this.error.set(this.errorText(error, 'No pudimos enviar la pregunta.'));
        this.busy.set(false);
      },
    });
  }

  private errorText(error: HttpErrorResponse, fallback: string): string {
    if (error.status === 503) return 'El asistente no está disponible ahora. Inténtalo más tarde.';
    if (error.status === 403) return 'Tu cuenta no tiene acceso al asistente.';
    return fallback;
  }

  private scrollToBottom(): void {
    requestAnimationFrame(() => {
      const element = this.messageList()?.nativeElement;
      if (element) element.scrollTop = element.scrollHeight;
    });
  }

  private reset(): void {
    this.open.set(false);
    this.historyOpen.set(false);
    this.conversations.set([]);
    this.active.set(null);
    this.messages.set([]);
    this.busy.set(false);
    this.loading.set(false);
    this.error.set('');
    this.downloading.set(null);
    this.draft = '';
  }
}
