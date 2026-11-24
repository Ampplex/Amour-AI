import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PersonaItem } from '../../services/persona.service';
import { MarkdownTextComponent } from '../markdown-text/markdown-text.component';

@Component({
  selector: 'app-persona-detail-modal',
  standalone: true,
  imports: [CommonModule, MarkdownTextComponent],
  template: `
    @if (persona) {
      <div class="modal-backdrop" (click)="onClose()">
        <div class="modal-card" (click)="$event.stopPropagation()">
          <button class="close-btn" (click)="onClose()" aria-label="Close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round"/>
            </svg>
          </button>

          <!-- Avatar & Header -->
          <div class="hero-section">
            <div class="avatar-ring" [style.border-color]="persona.border_color || '#F43F5E'">
              @if (persona.image_url) {
                <img [src]="persona.image_url" [alt]="persona.name" class="avatar-img" />
              } @else {
                <div class="avatar-fallback" [style.background-color]="persona.border_color || '#F43F5E'">
                  {{ (persona.name || 'A').charAt(0).toUpperCase() }}
                </div>
              }
            </div>

            <h2 class="persona-name">
              {{ persona.name }}
              @if (persona.age) {
                <span class="persona-age">, {{ persona.age }}</span>
              }
            </h2>

            @if (persona.tagline) {
              <p class="persona-tagline">{{ persona.tagline }}</p>
            }

            <!-- Badges -->
            <div class="badge-row">
              <span class="badge" [class.badge-public]="persona.visibility === 'public'">
                @if (persona.visibility === 'public') {
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
                    <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" stroke="currentColor" stroke-width="1.8"/>
                  </svg>
                  Community
                } @else {
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                  </svg>
                  Private
                }
              </span>

              @if (persona.likes_count !== undefined) {
                <span class="badge badge-meta">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="#F43F5E">
                    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                  </svg>
                  {{ persona.likes_count }} likes
                </span>
              }

              @if (persona.chats_count !== undefined) {
                <span class="badge badge-meta">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                  </svg>
                  {{ persona.chats_count }} chats
                </span>
              }
            </div>
          </div>

          <!-- Body details -->
          <div class="content-body">
            @if (persona.greeting) {
              <div class="info-section">
                <span class="section-label">Opening Greeting</span>
                <div class="bubble-box">
                  <app-markdown-text [content]="persona.greeting"></app-markdown-text>
                </div>
              </div>
            }

            @if (persona.memory_prompt) {
              <div class="info-section">
                <span class="section-label">Mind &amp; Persona Lore</span>
                <div class="bubble-box">
                  <p class="lore-text">{{ persona.memory_prompt }}</p>
                </div>
              </div>
            }

            @if (persona.publisher_name || persona.publisher_handle) {
              <div class="publisher-bar" (click)="onOpenPublisher()">
                <div class="pub-avatar">
                  {{ (persona.publisher_name || 'C').charAt(0).toUpperCase() }}
                </div>
                <div class="pub-meta">
                  <span class="pub-name">{{ persona.publisher_name || 'Creator' }}</span>
                  <span class="pub-handle">{{ persona.publisher_handle || '@creator' }}</span>
                </div>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M9 18l6-6-6-6" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round"/>
                </svg>
              </div>
            }
          </div>

          <!-- Action CTA -->
          <div class="cta-bar">
            <button class="chat-cta-btn" (click)="onStartChat()">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" fill="#000000" stroke="#000000" stroke-width="2"/>
              </svg>
              Start Conversation
            </button>
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 5000;
      background: rgba(0, 0, 0, 0.82);
      backdrop-filter: blur(10px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
      animation: fadeIn 0.18s ease-out;
    }

    .modal-card {
      background: #1C1C1F;
      border: 1px solid #2E2E32;
      border-radius: 20px;
      max-width: 560px;
      width: 100%;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      position: relative;
      box-shadow: 0 25px 50px rgba(0, 0, 0, 0.7);
      animation: popIn 0.22s cubic-bezier(0.16, 1, 0.3, 1);
      overflow: hidden;
    }

    .close-btn {
      position: absolute;
      top: 14px;
      right: 14px;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10;
      cursor: pointer;
      transition: background 0.15s;
    }
    .close-btn:hover {
      background: rgba(255, 255, 255, 0.2);
    }

    .hero-section {
      padding: 28px 20px 16px;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      background: linear-gradient(180deg, #242428 0%, #1C1C1F 100%);
      border-bottom: 1px solid #28282C;
    }

    .avatar-ring {
      width: 96px;
      height: 96px;
      border-radius: 50%;
      border-width: 3px;
      border-style: solid;
      padding: 3px;
      margin-bottom: 12px;
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
    }

    .avatar-img {
      width: 100%;
      height: 100%;
      border-radius: 50%;
      object-fit: cover;
    }

    .avatar-fallback {
      width: 100%;
      height: 100%;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: var(--font-brand);
      font-size: 2rem;
      color: #FFFFFF;
    }

    .persona-name {
      font-family: var(--font-brand);
      font-size: 1.45rem;
      color: #FFFFFF;
      letter-spacing: 0.2px;
      margin-bottom: 4px;
    }

    .persona-age {
      font-size: 1.15rem;
      color: #A1A1AA;
      font-weight: 400;
    }

    .persona-tagline {
      font-size: 0.92rem;
      color: #A1A1AA;
      margin-bottom: 12px;
      max-width: 90%;
    }

    .badge-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: center;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 0.78rem;
      font-weight: 600;
      background: #28282C;
      color: #D4D4D8;
      border: 1px solid #38383E;
    }
    .badge-public {
      background: rgba(59, 130, 246, 0.15);
      color: #60A5FA;
      border-color: rgba(59, 130, 246, 0.3);
    }
    .badge-meta {
      background: #242428;
    }

    .content-body {
      padding: 16px 20px;
      overflow-y: auto;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .info-section {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .section-label {
      font-size: 0.78rem;
      font-weight: 700;
      color: #71717A;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .bubble-box {
      background: #242428;
      border: 1px solid #2E2E32;
      border-radius: 12px;
      padding: 12px 14px;
      font-size: 0.92rem;
    }

    .lore-text {
      color: #D4D4D8;
      line-height: 1.5;
      font-size: 0.9rem;
      white-space: pre-wrap;
    }

    .publisher-bar {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      background: #242428;
      border: 1px solid #2E2E32;
      border-radius: 12px;
      cursor: pointer;
      transition: background 0.15s;
    }
    .publisher-bar:hover {
      background: #2A2A30;
    }

    .pub-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: #3F3F46;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 0.85rem;
    }

    .pub-meta {
      display: flex;
      flex-direction: column;
      flex: 1;
    }
    .pub-name {
      font-size: 0.88rem;
      font-weight: 600;
      color: #FFFFFF;
    }
    .pub-handle {
      font-size: 0.78rem;
      color: #71717A;
    }

    .cta-bar {
      padding: 16px 20px;
      border-top: 1px solid #28282C;
      background: #1C1C1F;
    }

    .chat-cta-btn {
      width: 100%;
      padding: 14px;
      background: #FFFFFF;
      color: #000000;
      border-radius: 12px;
      font-weight: 700;
      font-size: 0.96rem;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.15s ease;
    }
    .chat-cta-btn:hover {
      background: #E4E4E7;
      transform: translateY(-1px);
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    @keyframes popIn {
      from { transform: scale(0.92); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
  `]
})
export class PersonaDetailModalComponent {
  @Input() persona: PersonaItem | null = null;
  @Output() close = new EventEmitter<void>();
  @Output() startChat = new EventEmitter<PersonaItem>();
  @Output() openPublisher = new EventEmitter<PersonaItem>();

  onClose(): void {
    this.close.emit();
  }

  onStartChat(): void {
    if (this.persona) {
      this.startChat.emit(this.persona);
    }
  }

  onOpenPublisher(): void {
    if (this.persona) {
      this.openPublisher.emit(this.persona);
    }
  }
}
