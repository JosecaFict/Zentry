import { Component, computed, input } from '@angular/core';

type Block = { type: 'paragraph'; text: string } | { type: 'table'; headers: string[]; rows: string[][] } | { type: 'facts'; entries: Array<{ label: string; value: string }> };

function fact(line: string): { label: string; value: string } | null {
  const match = /^(Producto|Categoría|Unidades vendidas|Ingresos):\s*(.+)$/.exec(line.trim());
  return match ? { label: match[1], value: match[2] } : null;
}

function cells(line: string): string[] {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
}

export function parseAssistantMessage(text: string): Block[] {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  const flush = () => {
    if (paragraph.length) blocks.push({ type: 'paragraph', text: paragraph.join('\n') });
    paragraph = [];
  };
  for (let i = 0; i < lines.length; i++) {
    if (fact(lines[i])) {
      flush();
      const entries: Array<{ label: string; value: string }> = [];
      while (i < lines.length) {
        const entry = fact(lines[i]);
        if (!entry) break;
        entries.push(entry);
        i++;
      }
      i--;
      blocks.push({ type: 'facts', entries });
      continue;
    }
    const headers = cells(lines[i]);
    const divider = cells(lines[i + 1] ?? '');
    if (lines[i].includes('|') && headers.length > 1 && divider.length === headers.length && divider.every((cell) => /^:?-{3,}:?$/.test(cell))) {
      flush();
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        const row = cells(lines[i]);
        rows.push(headers.map((_, index) => row[index] ?? ''));
        i++;
      }
      i--;
      blocks.push({ type: 'table', headers, rows });
    } else if (!lines[i].trim()) {
      flush();
    } else {
      paragraph.push(lines[i]);
    }
  }
  flush();
  return blocks;
}

@Component({
  selector: 'app-assistant-inline-text',
  template: `@for (part of parts(); track $index) {@if (part.bold) {<strong>{{ part.text }}</strong>} @else {<span>{{ part.text }}</span>}}`,
})
export class AssistantInlineText {
  readonly text = input.required<string>();
  readonly parts = computed(() => this.text().split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part) => ({
    bold: part.startsWith('**') && part.endsWith('**'),
    text: part.startsWith('**') && part.endsWith('**') ? part.slice(2, -2) : part,
  })));
}

@Component({
  selector: 'app-assistant-message',
  imports: [AssistantInlineText],
  template: `@for (block of blocks(); track $index) {
    @if (block.type === 'table') {
      <div class="table-scroll" tabindex="0" role="region" aria-label="Tabla de resultados del reporte">
        <table>
          <thead><tr>@for (header of block.headers; track $index) {<th scope="col"><app-assistant-inline-text [text]="header" /></th>}</tr></thead>
          <tbody>@for (row of block.rows; track $index) {<tr>@for (cell of row; track $index) {<td><app-assistant-inline-text [text]="cell" /></td>}</tr>}</tbody>
        </table>
      </div>
    } @else if (block.type === 'facts') {
      <dl class="report-facts">
        @for (entry of block.entries; track $index) {
          <div [class.product-name]="entry.label === 'Producto'">
            <dt>{{ entry.label }}</dt><dd><app-assistant-inline-text [text]="entry.value" /></dd>
          </div>
        }
      </dl>
    } @else { <p><app-assistant-inline-text [text]="block.text" /></p> }
  }`,
  styles: `
    :host { display: block; min-width: 0; white-space: normal; }
    p { margin: 0 0 12px; white-space: pre-wrap; overflow-wrap: anywhere; }
    p:last-child { margin-bottom: 0; }
    .report-facts { margin: 16px 0; }
    .report-facts > div { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; padding: 9px 0; border-bottom: 1px solid #d4d9e0; }
    .report-facts dt { color: #565d67; font-size: 12px; }
    .report-facts dd { margin: 0; text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
    .report-facts .product-name { display: block; padding-top: 0; padding-bottom: 14px; }
    .product-name dt { margin-bottom: 4px; }
    .product-name dd { text-align: left; font-size: 16px; line-height: 1.4; }
    .table-scroll { max-width: 100%; overflow-x: auto; margin: 12px 0; }
    .table-scroll:focus-visible { outline: 2px solid var(--chat-accent, #064fe8); outline-offset: 2px; }
    table { width: max-content; min-width: 100%; border-collapse: collapse; font-size: 12px; line-height: 1.45; }
    th, td { max-width: 200px; padding: 8px 10px; border-bottom: 1px solid #cbd0d6; text-align: left; vertical-align: top; white-space: normal; overflow-wrap: anywhere; }
    th { font-weight: 700; }
    td { font-variant-numeric: tabular-nums; }
  `,
})
export class AssistantMessageBody {
  readonly text = input.required<string>();
  readonly blocks = computed(() => parseAssistantMessage(this.text()));
}
