import { Component, computed, input } from '@angular/core';

type Block = { type: 'paragraph'; text: string } | { type: 'table'; headers: string[]; rows: string[][] };

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
    } @else { <p><app-assistant-inline-text [text]="block.text" /></p> }
  }`,
  styles: `
    :host { display: block; min-width: 0; white-space: normal; }
    p { margin: 0 0 12px; white-space: pre-wrap; overflow-wrap: anywhere; }
    p:last-child { margin-bottom: 0; }
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
