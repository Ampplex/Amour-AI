import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ConversationService, ConversationItem } from '../../../services/conversation.service';
import { PersonaItem } from '../../../services/persona.service';
import { AuthService } from '../../../services/auth.service';
import { CompanionChatModalComponent } from '../../../components/companion-chat-modal/companion-chat-modal.component';

@Component({
  selector: 'app-chats-screen',
  standalone: true,
  imports: [CommonModule, CompanionChatModalComponent],
  template: `
    <div class="chats-container">
      <header class="chats-header">
        <h1 class="header-title">Chats</h1>
      </header>

      <main class="chats-content">
        @if (conversationService.isLoading() && conversationService.conversations().length === 0) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading active conversations...</span>
          </div>
        }

        @if (!conversationService.isLoading() && conversationService.conversations().length === 0) {
          <div class="empty-state">
            <div class="empty-icon-box">
              <svg width="44" height="44" viewBox="0 0 24 24" fill="none">
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" stroke="#4B5563" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <h3 class="empty-title">No Conversations Yet</h3>
            <p class="empty-desc">Explore personas on Home or create a custom companion to begin your private chats.</p>
          </div>
        }

        <div class="threads-list">
          @for (conv of conversationService.conversations(); track conv.persona.id) {
            <div class="chat-thread-card" (click)="openChat(conv.persona)">
              <div class="thread-avatar" [style.border-color]="conv.persona.border_color || '#F43F5E'">
                @if (conv.persona.image_url) {
                  <img [src]="conv.persona.image_url" [alt]="conv.persona.name" />
                } @else {
                  <span>{{ (conv.persona.name || 'C').charAt(0) }}</span>
                }
              </div>

              <div class="thread-main">
                <div class="thread-top">
                  <h3 class="thread-name">{{ conv.persona.name }}</h3>
                  <span class="thread-time">{{ formatTime(conv.last_message.created_at) }}</span>
                </div>

                <p class="thread-snippet">
                  {{ conv.last_message.sender === 'user' ? 'You: ' : '' }}{{ conv.last_message.text }}
                </p>
              </div>
            </div>
          }
        </div>
      </main>

      <app-companion-chat-modal
        [persona]="activeChatPersona"
        (close)="activeChatPersona = null"
      ></app-companion-chat-modal>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      width: 100%;
      min-height: 100%;
      background: #000000;
    }

    .chats-container {
      width: 100%;
      min-height: 100%;
      display: flex;
      flex-direction: column;
      background: #000000;
    }

    .chats-header {
      height: 64px;
      padding: 0 32px;
      display: flex;
      align-items: center;
      border-bottom: 1px solid #262626;
      background: #000000;
      flex-shrink: 0;
    }

    .header-title {
      font-family: var(--font-brand);
      font-size: 1.45rem;
      color: #FFFFFF;
    }

    .chats-content {
      flex: 1;
      overflow-y: auto;
      max-width: 800px;
      width: 100%;
      margin: 0 auto;
      padding: 24px 20px 100px;
      box-sizing: border-box;
    }

    @media (max-width: 767px) {
      .chats-header {
        padding: 0 16px;
      }
      .chats-content {
        padding: 0 0 80px 0;
      }
    }

    .loading-state {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      padding: 40px;
      color: #71717A;
      font-size: 0.88rem;
    }
    .spinner {
      width: 18px;
      height: 18px;
      border: 2px solid #333338;
      border-top-color: #3B82F6;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      padding: 70px 20px;
    }
    .empty-icon-box {
      width: 72px;
      height: 72px;
      border-radius: 50%;
      background: #202022;
      border: 1px solid #2E2E32;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
    }
    .empty-title {
      font-family: var(--font-brand);
      font-size: 1.25rem;
      color: #FFFFFF;
      margin-bottom: 8px;
    }
    .empty-desc {
      font-size: 0.88rem;
      color: #A1A1AA;
      max-width: 280px;
      line-height: 1.45;
    }

    .threads-list {
      display: flex;
      flex-direction: column;
    }

    .chat-thread-card {
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 14px 16px;
      border-bottom: 1px solid #202022;
      cursor: pointer;
      transition: background 0.15s;
    }
    .chat-thread-card:hover {
      background: #1C1C1F;
    }

    .thread-avatar {
      width: 48px;
      height: 48px;
      border-radius: 50%;
      border-width: 2px;
      border-style: solid;
      background: #202022;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .thread-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .thread-avatar span {
      font-family: var(--font-brand);
      font-size: 1.25rem;
      color: #FFFFFF;
    }

    .thread-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    .thread-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 4px;
    }

    .thread-name {
      font-size: 0.98rem;
      font-weight: 600;
      color: #FFFFFF;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .thread-time {
      font-size: 0.75rem;
      color: #71717A;
      flex-shrink: 0;
      margin-left: 8px;
    }

    .thread-snippet {
      font-size: 0.85rem;
      color: #A1A1AA;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      line-height: 1.35;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  `]
})
export class ChatsScreenComponent implements OnInit {
  readonly conversationService = inject(ConversationService);
  private authService = inject(AuthService);

  activeChatPersona: PersonaItem | null = null;

  ngOnInit(): void {
    const user = this.authService.currentUser();
    if (user?.id) {
      this.conversationService.fetchUserConversations(user.id, user.token);
    }
  }

  openChat(p: PersonaItem): void {
    this.activeChatPersona = p;
  }

  formatTime(dateString?: string): string {
    if (!dateString) return '';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return '';

    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes}m`;
    if (diffHours < 24) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) {
      return date.toLocaleDateString([], { weekday: 'short' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }
}
