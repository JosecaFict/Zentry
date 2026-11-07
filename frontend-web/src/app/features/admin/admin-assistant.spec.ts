import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
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
      exportReport: vi.fn(() => of(new Blob(['test'], { type: 'application/pdf' }))),
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

  it('downloads the report attached to the selected message, not the latest question', () => {
    const { fixture, assistant } = setup();
    fixture.componentInstance.open.set(true);
    fixture.componentInstance.draft = 'Ventas de septiembre';
    fixture.componentInstance.send();
    const message = { id_mensaje: 2, rol: 'ASISTENTE' as const, contenido: 'Reporte', created_at: '2026-11-07T12:00:00Z', productos: [], reporte_exportable: true };
    fixture.componentInstance.messages.set([message]);
    fixture.componentInstance.draft = 'Otra pregunta';
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Descargar PDF');
    expect(fixture.nativeElement.textContent).toContain('Descargar Excel');
    const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:report');
    const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const pending = new Subject<Blob>();
    assistant.exportReport.mockReturnValue(pending);
    fixture.componentInstance.downloadReport(message, 'xlsx');
    fixture.componentInstance.downloadReport(message, 'pdf');
    expect(assistant.exportReport).toHaveBeenCalledTimes(1);
    expect(assistant.exportReport).toHaveBeenCalledWith('conversation-1', 2, 'xlsx');
    expect(fixture.componentInstance.downloading()?.format).toBe('xlsx');
    pending.next(new Blob(['report'])); pending.complete();
    expect(click).toHaveBeenCalledOnce();
    expect(fixture.componentInstance.downloading()).toBeNull();
    create.mockRestore(); revoke.mockRestore(); click.mockRestore();
  });

  it('does not offer downloads for a normal message and handles changed permissions', () => {
    const { fixture, assistant } = setup();
    fixture.componentInstance.open.set(true);
    fixture.componentInstance.draft = 'Hola';
    fixture.componentInstance.send();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.admin-advisor-downloads')).toBeNull();
    const message = { ...fixture.componentInstance.messages()[1], reporte_exportable: true };
    assistant.exportReport.mockReturnValue(throwError(() => ({ status: 403 })));
    fixture.componentInstance.downloadReport(message, 'pdf');
    expect(fixture.componentInstance.downloading()).toBeNull();
    expect(fixture.componentInstance.error()).toContain('acceso');
  });
});
