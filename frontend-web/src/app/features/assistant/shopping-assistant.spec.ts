import { computed, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of, Subject } from 'rxjs';
import { provideRouter } from '@angular/router';
import { describe, expect, it, vi } from 'vitest';
import { AuthService } from '../../core/auth/auth.service';
import { AssistantConversation, AssistantService } from '../../core/services/assistant.service';
import { TenantContextService } from '../../core/tenant/tenant-context.service';
import { ShoppingAssistant } from './shopping-assistant';

const conversation: AssistantConversation = {
  id_conversacion: 'conversation-1',
  modo: 'CLIENTE',
  proveedor: 'GEMINI',
  modelo: 'gemini-2.5-flash',
  estado: 'ACTIVA',
  created_at: '2026-11-06T12:00:00Z',
  updated_at: '2026-11-06T12:00:00Z',
};

describe('ShoppingAssistant', () => {
  function setup(listResult = of([conversation])) {
    const user = signal({ id_usuario: 10, roles: ['CLIENTE'] } as never);
    const tenant = signal({ id_tenant: 7 } as never);
    const assistant = {
      list: vi.fn(() => listResult),
      create: vi.fn(() => of(conversation)),
      messages: vi.fn(() => of([])),
      send: vi.fn(() => of({
        usuario: { id_mensaje: 1, rol: 'USUARIO', contenido: 'Hola', created_at: '2026-11-06' },
        asistente: { id_mensaje: 2, rol: 'ASISTENTE', contenido: 'Hola', created_at: '2026-11-06' },
      })),
      archive: vi.fn(() => of(undefined)),
    };
    TestBed.configureTestingModule({
      imports: [ShoppingAssistant],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { currentUser: user, isAuthenticated: computed(() => !!user()) } },
        { provide: TenantContextService, useValue: {
          tenant, name: signal('Tienda Uno'), primaryColor: signal('#20c8b7'),
          primaryDarkColor: signal('#087c72'),
        } },
        { provide: AssistantService, useValue: assistant },
      ],
    });
    const fixture = TestBed.createComponent(ShoppingAssistant);
    fixture.detectChanges();
    return { fixture, user, tenant, assistant };
  }

  it('shows the launcher only to signed-in clients and opens a foldable panel', () => {
    const { fixture, user, assistant } = setup();
    expect(fixture.nativeElement.querySelector('.advisor-launcher')).toBeTruthy();
    fixture.nativeElement.querySelector('.advisor-launcher').click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.advisor-panel')).toBeTruthy();
    expect(assistant.list).toHaveBeenCalledOnce();
    fixture.nativeElement.querySelector('.advisor-launcher').click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.advisor-panel')).toBeNull();
    user.set({ id_usuario: 20, roles: ['ADMIN'] } as never);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.advisor-launcher')).toBeNull();
  });

  it('discards a previous user response after switching accounts', () => {
    const pending = new Subject<AssistantConversation[]>();
    const { fixture, user } = setup(pending);
    fixture.nativeElement.querySelector('.advisor-launcher').click();
    fixture.detectChanges();
    user.set({ id_usuario: 20, roles: ['CLIENTE'] } as never);
    fixture.detectChanges();
    pending.next([conversation]);
    fixture.detectChanges();
    expect(fixture.componentInstance.conversations()).toEqual([]);
    expect(fixture.componentInstance.open()).toBe(false);
  });

  it('creates a client conversation and sends through the backend', () => {
    const { fixture, assistant } = setup();
    fixture.componentInstance.toggle();
    fixture.componentInstance.draft = 'Hola';
    fixture.componentInstance.send();
    fixture.detectChanges();
    expect(assistant.create).toHaveBeenCalledOnce();
    expect(assistant.send).toHaveBeenCalledWith('conversation-1', 'Hola');
    expect(fixture.componentInstance.messages()).toHaveLength(2);
  });

  it('renders the verified product card with price and detail link', () => {
    const { fixture } = setup();
    fixture.componentInstance.toggle();
    fixture.componentInstance.messages.set([{
      id_mensaje: 2, rol: 'ASISTENTE', contenido: 'Encontré una opción para ti.',
      created_at: '2026-11-06T12:00:00Z', productos: [{
        id_producto: 7, nombre: 'Polera azul', categoria: 'POLERA', marca: 'Marca',
        precio: '250.00', precio_original: '300.00', descuento_porcentaje: '16.67', promocion_nombre: 'Oferta de hoy',
        imagen_url: null, tallas: ['M'], colores: ['Azul'],
        permite_vestidor: true,
      }],
    }]);
    fixture.detectChanges();
    const card = fixture.nativeElement.querySelector('.advisor-product');
    expect(card.textContent).toContain('Polera azul');
    expect(card.textContent).toContain('250');
    expect(card.textContent).toContain('Oferta de hoy');
    expect(card.textContent).toContain('Antes');
    expect(card.querySelector('a').getAttribute('href')).toBe('/productos/7');
  });
});
