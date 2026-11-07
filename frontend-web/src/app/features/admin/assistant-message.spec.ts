import { TestBed } from '@angular/core/testing';
import { AssistantMessageBody, parseAssistantMessage } from './assistant-message';

describe('Assistant report messages', () => {
  it('renders a real table and bold values without treating content as HTML', () => {
    TestBed.configureTestingModule({ imports: [AssistantMessageBody] });
    const fixture = TestBed.createComponent(AssistantMessageBody);
    fixture.componentRef.setInput('text', 'Resultados de **septiembre**.\n\n| Producto | Ingresos |\n| --- | --- |\n| <img src=x onerror=alert(1)> | **Bs 4.200,00** |');
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    expect(element.querySelectorAll('table')).toHaveLength(1);
    expect(element.querySelectorAll('th')).toHaveLength(2);
    expect(element.querySelector('td strong')?.textContent).toBe('Bs 4.200,00');
    expect(element.querySelector('img')).toBeNull();
    expect(element.textContent).toContain('<img src=x onerror=alert(1)>');
    expect(element.textContent).not.toContain('**');
    expect(element.querySelector('.table-scroll')?.getAttribute('tabindex')).toBe('0');
  });

  it('keeps normal text containing a pipe as text', () => {
    expect(parseAssistantMessage('Talla M | color verde')).toEqual([{ type: 'paragraph', text: 'Talla M | color verde' }]);
  });

  it('presents product figures as labeled facts with no Markdown characters', () => {
    TestBed.configureTestingModule({ imports: [AssistantMessageBody] });
    const fixture = TestBed.createComponent(AssistantMessageBody);
    fixture.componentRef.setInput('text', 'Claro. Para septiembre de 2026, encontré este resultado:\n\nProducto: Polo Ralph Lauren Classic Fit\nCategoría: Polo\nUnidades vendidas: 21\nIngresos: Bs 4.200,00\n\n¿Quieres que revisemos también las ventas por sucursal?');
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    expect(element.querySelectorAll('dl dt')).toHaveLength(4);
    expect(element.querySelector('.product-name dd')?.textContent).toBe('Polo Ralph Lauren Classic Fit');
    expect(element.querySelectorAll('dl dd')[2].textContent).toBe('21');
    expect(element.querySelectorAll('dl dd')[3].textContent).toBe('Bs 4.200,00');
    expect(element.textContent).not.toContain('**');
    expect(element.textContent).toContain('septiembre de 2026');
  });
});
