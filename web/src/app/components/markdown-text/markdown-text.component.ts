import { Component, Input, computed } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface TextToken {
  type: 'dialogue' | 'action' | 'bold' | 'bold-action' | 'code';
  text: string;
}

@Component({
  selector: 'app-markdown-text',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span class="markdown-container">
      @for (token of tokens(); track $index) {
        @switch (token.type) {
          @case ('dialogue') {
            <span class="token-dialogue">{{ token.text }}</span>
          }
          @case ('action') {
            <span class="token-action">{{ token.text }}</span>
          }
          @case ('bold') {
            <strong class="token-bold">{{ token.text }}</strong>
          }
          @case ('bold-action') {
            <strong class="token-bold-action">{{ token.text }}</strong>
          }
          @case ('code') {
            <code class="token-code">{{ token.text }}</code>
          }
        }
      }
    </span>
  `,
  styles: [`
    .markdown-container {
      display: inline;
      line-height: 1.58;
      font-size: 0.96rem;
      word-break: break-word;
      white-space: pre-wrap;
    }
    .token-dialogue {
      color: #FFFFFF;
      font-style: normal;
      font-weight: 400;
    }
    .token-action {
      color: #9CA3AF;
      font-style: italic;
      font-weight: 400;
    }
    .token-bold {
      color: #FFFFFF;
      font-weight: 700;
      font-style: normal;
    }
    .token-bold-action {
      color: #D1D5DB;
      font-weight: 700;
      font-style: italic;
    }
    .token-code {
      background: rgba(255, 255, 255, 0.1);
      padding: 2px 5px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 0.88em;
      color: #93C5FD;
    }
  `]
})
export class MarkdownTextComponent {
  @Input() content = '';

  readonly tokens = computed<TextToken[]>(() => {
    const raw = this.content || '';
    if (!raw) return [];

    const hasQuotes = /([“"„«][^”"»]*[”"»])/.test(raw);
    const hasAsterisks = /(\*[^*]+\*|_[^_]+_)/.test(raw);

    const parsed: TextToken[] = [];

    if (hasQuotes) {
      const quoteRegex = /([“"„«][^”"»]*[”"»])/g;
      const segments = raw.split(quoteRegex);

      for (const segment of segments) {
        if (!segment) continue;
        const isQuote = /^[“"„«].*[”"»]$/s.test(segment) && segment.length >= 2;
        if (isQuote) {
          parsed.push({ type: 'dialogue', text: segment });
        } else {
          this.tokenizeMarkdown(segment, parsed, true);
        }
      }
    } else if (hasAsterisks) {
      this.tokenizeMarkdown(raw, parsed, false);
    } else {
      parsed.push({ type: 'dialogue', text: raw });
    }

    return parsed;
  });

  private tokenizeMarkdown(input: string, tokens: TextToken[], defaultToAction = false): void {
    const regex = /(\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_|`[^`]+`)/g;
    const parts = input.split(regex);

    for (const part of parts) {
      if (!part) continue;

      if (part.startsWith('***') && part.endsWith('***') && part.length > 6) {
        tokens.push({ type: 'bold-action', text: part.slice(3, -3) });
      } else if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        tokens.push({ type: 'bold', text: part.slice(2, -2) });
      } else if (
        (part.startsWith('*') && part.endsWith('*') && part.length > 2) ||
        (part.startsWith('_') && part.endsWith('_') && part.length > 2)
      ) {
        tokens.push({ type: 'action', text: part.slice(1, -1) });
      } else if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
        tokens.push({ type: 'code', text: part.slice(1, -1) });
      } else {
        tokens.push({
          type: defaultToAction ? 'action' : 'dialogue',
          text: part,
        });
      }
    }
  }
}
