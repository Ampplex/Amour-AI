import { Component, Input, Output, EventEmitter, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FeedService } from '../../services/feed.service';
import { PersonaItem } from '../../services/persona.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-publisher-profile-modal',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (isOpen) {
      <div class="modal-backdrop" (click)="onClose()">
        <div class="modal-card" (click)="$event.stopPropagation()">
          <button class="close-btn" (click)="onClose()" aria-label="Close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round"/>
            </svg>
          </button>

          <!-- Profile Header -->
          <div class="header-section">
            <div class="avatar-large">
              @if (publisherAvatar) {
                <img [src]="publisherAvatar" [alt]="publisherName" class="avatar-img" />
              } @else {
                <span class="avatar-initial">{{ (publisherName || 'C').charAt(0).toUpperCase() }}</span>
              }
            </div>

            <h2 class="publisher-name">{{ publisherName || 'Creator' }}</h2>
            <span class="publisher-handle">{{ publisherHandle || '@creator' }}</span>

            <button
              class="follow-toggle-btn"
              [class.is-following]="isFollowing"
              (click)="toggleFollow()"
            >
              {{ isFollowing ? 'Following' : 'Follow' }}
            </button>
          </div>

          <!-- Description / Roster Section -->
          <div class="roster-section">
            <h4 class="section-title">Published Personas</h4>
            <div class="persona-chips-list">
              @for (p of publisherPersonas; track p.id) {
                <div class="roster-item" (click)="onSelectPersona(p)">
                  <div class="p-thumb" [style.border-color]="p.border_color || '#F43F5E'">
                    @if (p.image_url) {
                      <img [src]="p.image_url" [alt]="p.name" />
                    } @else {
                      <span>{{ (p.name || 'P').charAt(0) }}</span>
                    }
                  </div>
                  <div class="p-info">
                    <span class="p-name">{{ p.name }}</span>
                    <span class="p-tagline">{{ p.tagline || 'AI Companion' }}</span>
                  </div>
                  <button class="chat-mini-btn" (click)="onStartChat(p); $event.stopPropagation()">
                    Chat
                  </button>
                </div>
              }
            </div>
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 5200;
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
      max-width: 580px;
      width: 100%;
      max-height: 80vh;
      display: flex;
      flex-direction: column;
      position: relative;
      box-shadow: 0 25px 50px rgba(0, 0, 0, 0.7);
      overflow: hidden;
      animation: popIn 0.22s cubic-bezier(0.16, 1, 0.3, 1);
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
    }

    .header-section {
      padding: 28px 20px 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      background: linear-gradient(180deg, #26262B 0%, #1C1C1F 100%);
      border-bottom: 1px solid #28282C;
    }

    .avatar-large {
      width: 80px;
      height: 80px;
      border-radius: 50%;
      background: #2E2E34;
      border: 2px solid #3F3F46;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 12px;
      overflow: hidden;
    }

    .avatar-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .avatar-initial {
      font-family: var(--font-brand);
      font-size: 2rem;
      color: #FFFFFF;
    }

    .publisher-name {
      font-family: var(--font-brand);
      font-size: 1.35rem;
      color: #FFFFFF;
      margin-bottom: 2px;
    }

    .publisher-handle {
      font-size: 0.88rem;
      color: #71717A;
      margin-bottom: 16px;
    }

    .follow-toggle-btn {
      padding: 8px 24px;
      border-radius: 9999px;
      font-size: 0.88rem;
      font-weight: 700;
      background: #FFFFFF;
      color: #000000;
      transition: all 0.15s ease;
    }
    .follow-toggle-btn.is-following {
      background: #27272A;
      color: #D4D4D8;
      border: 1px solid #3F3F46;
    }

    .roster-section {
      padding: 18px 20px;
      overflow-y: auto;
      flex: 1;
    }

    .section-title {
      font-size: 0.82rem;
      font-weight: 700;
      color: #71717A;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 12px;
    }

    .persona-chips-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .roster-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 12px;
      background: #242428;
      border: 1px solid #2E2E32;
      border-radius: 12px;
      cursor: pointer;
      transition: background 0.15s;
    }
    .roster-item:hover {
      background: #2A2A30;
    }

    .p-thumb {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      border-width: 2px;
      border-style: solid;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #1C1C1F;
      overflow: hidden;
      flex-shrink: 0;
    }
    .p-thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .p-thumb span {
      font-weight: 700;
      font-size: 0.9rem;
    }

    .p-info {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
    }
    .p-name {
      font-size: 0.92rem;
      font-weight: 600;
      color: #FFFFFF;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .p-tagline {
      font-size: 0.78rem;
      color: #A1A1AA;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .chat-mini-btn {
      padding: 6px 14px;
      border-radius: 8px;
      background: #3B82F6;
      color: #FFFFFF;
      font-weight: 600;
      font-size: 0.8rem;
      transition: background 0.15s;
    }
    .chat-mini-btn:hover {
      background: #2563EB;
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
export class PublisherProfileModalComponent {
  private feedService = inject(FeedService);
  private authService = inject(AuthService);

  @Input() isOpen = false;
  @Input() publisherHandle = '';
  @Input() publisherName = '';
  @Input() publisherAvatar = '';
  @Input() isFollowing = false;
  @Input() publisherPersonas: PersonaItem[] = [];

  @Output() close = new EventEmitter<void>();
  @Output() selectPersona = new EventEmitter<PersonaItem>();
  @Output() startChat = new EventEmitter<PersonaItem>();

  onClose(): void {
    this.close.emit();
  }

  async toggleFollow(): Promise<void> {
    const user = this.authService.currentUser();
    const res = await this.feedService.togglePublisherFollow(this.publisherHandle, this.isFollowing, user?.id);
    this.isFollowing = res.following;
  }

  onSelectPersona(p: PersonaItem): void {
    this.selectPersona.emit(p);
  }

  onStartChat(p: PersonaItem): void {
    this.startChat.emit(p);
  }
}
