import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { vi } from 'vitest';
import { AuthService } from '../../core/auth/auth.service';
import { AssistantService } from '../../core/services/assistant.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';
import { AdminAssistant } from './admin-assistant';

describe('AdminAssistant', () => {
  function setup(plan = 'PROFESIONAL', roles = ['ADMIN']) {
    const auth = { currentUser: signal({ id_usuario: 1, roles }) };
    const tenant = {
      tenant: signal({ id_tenant: 7, plan_codigo: plan }),
      name: signal('Casa Elena'),
      primaryColor: signal('#064fe8'),
    };
    const conversation = {
      id_conversacion: 'conversation-1', modo: 'EMPRESA' as const,
      proveedor: 'GROQ' as const, modelo: 'test', estado: 'ACTIVA' as const,
      created_at: '2026-11-07T12:00:00Z', updated_at: '2026-11-07T12:00:00Z',
    };
    const assistant = {
      list: vi.fn(() => of([])),
      create: vi.fn(() => of(conversation)),
      send: vi.fn(() => of({
        usuario: { id_mensaje: 1, rol: 'USUARIO', contenido: 'Hola', created_at: conversation.created_at, productos: [] },
        asistente: { id_mensaje: 2, rol: 'ASISTENTE', contenido: '¿En qué te ayudo?', created_at: conversation.created_at, productos: [] },
      })),
      messages: vi.fn(() => of([])),
    };
    TestBed.configureTestingModule({
      imports: [AdminAssistant],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: auth },
        { provide: TenantContextService, useValue: tenant },
        { provide: AssistantService, useValue: assistant },
      ],
    });
    const fixture = TestBed.createComponent(AdminAssistant);
    fixture.detectChanges();
    return { fixture, assistant };
  }

  it('opens a conversation for the administrator and sends a follow-up', () => {
    const { fixture, assistant } = setup();
    (fixture.nativeElement.querySelector('.admin-advisor-launcher') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Productos más vendidos');
    fixture.componentInstance.draft = 'Hola';
    fixture.componentInstance.send();
    fixture.detectChanges();
    expect(assistant.create).toHaveBeenCalledWith('EMPRESA');
    expect(assistant.send).toHaveBeenCalledWith('conversation-1', 'Hola');
    expect(fixture.nativeElement.textContent).toContain('¿En qué te ayudo?');
    expect(fixture.nativeElement.querySelector('.admin-advisor-report-link')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.admin-advisor-report-link').getAttribute('href')).toContain('pregunta=Hola');
  });

  it('shows general guidance for Basic and hides the report shortcut', () => {
    const { fixture } = setup('BASICO');
    (fixture.nativeElement.querySelector('.admin-advisor-launcher') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('plan Profesional');
    expect(fixture.nativeElement.querySelector('.admin-advisor-report-link')).toBeNull();
  });

  it('does not show the window to other roles', () => {
    const { fixture } = setup('PROFESIONAL', ['CAJERO']);
    expect(fixture.nativeElement.querySelector('.admin-advisor-launcher')).toBeNull();
  });
});
