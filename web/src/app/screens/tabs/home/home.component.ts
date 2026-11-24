import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FeedService, FeedPersonaItem } from '../../../services/feed.service';
import { PersonaItem } from '../../../services/persona.service';
import { AuthService } from '../../../services/auth.service';
import { AlertService } from '../../../services/alert.service';
import { AmourLogoComponent } from '../../../components/amour-logo/amour-logo.component';
import { PersonaDetailModalComponent } from '../../../components/persona-detail-modal/persona-detail-modal.component';
import { PublisherProfileModalComponent } from '../../../components/publisher-profile-modal/publisher-profile-modal.component';
import { CompanionChatModalComponent } from '../../../components/companion-chat-modal/companion-chat-modal.component';

@Component({
  selector: 'app-home-screen',
  standalone: true,
  imports: [
    CommonModule,
    AmourLogoComponent,
    PersonaDetailModalComponent,
    PublisherProfileModalComponent,
    CompanionChatModalComponent
  ],
  template: `
    <div class="feed-container">
      <!-- App Header: only visible on mobile -->
      <header class="feed-header">
        <app-amour-logo [size]="140" [showText]="true" [animated]="false"></app-amour-logo>
      </header>

      <!-- Feed List -->
      <main class="feed-content">
        @if (feedService.isLoading() && feedService.feedItems().length === 0) {
          <div class="feed-loading">
            <div class="spinner"></div>
            <span>Loading discovery feed...</span>
          </div>
        }

        @for (item of feedService.feedItems(); track item.id) {
          <article class="feed-card">
            <!-- 1. Header: Publisher profile & Follow button -->
            <div class="card-header">
              <div class="publisher-info" (click)="openPublisher(item)">
                <div class="publisher-avatar">
                  @if (item.publisher_avatar) {
                    <img [src]="item.publisher_avatar" [alt]="item.publisher_name" />
                  } @else {
                    <span>{{ (item.publisher_name || 'C').charAt(0).toUpperCase() }}</span>
                  }
                </div>
                <div class="publisher-names">
                  <span class="pub-name">{{ item.publisher_name || 'Creator' }}</span>
                  <span class="pub-handle">{{ item.publisher_handle || '@creator' }}</span>
                </div>
              </div>

              <button
                class="follow-btn"
                [class.is-following]="item.is_following"
                (click)="toggleFollow(item)"
              >
                {{ item.is_following ? 'Following' : 'Follow' }}
              </button>
            </div>

            <!-- 2. Hero Media -->
            <div class="media-container" (dblclick)="onDoubleTap(item)">
              @if (item.image_url) {
                <img [src]="item.image_url" [alt]="item.name" class="media-image" (click)="openPersona(item)" />
              } @else {
                <div class="media-fallback" [style.background-color]="item.border_color || '#F43F5E'" (click)="openPersona(item)">
                  <span class="fallback-letter">{{ (item.name || 'A').charAt(0) }}</span>
                  <span class="fallback-name">{{ item.name }}</span>
                </div>
              }

              <!-- Floating Chat Button Badge -->
              <button class="floating-chat-btn" (click)="startChat(item)" title="Start Chat with {{ item.name }}">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#FFFFFF">
                  <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
                </svg>
              </button>

              <!-- Heart Pop Animation Indicator -->
              @if (poppingHeartId() === item.id) {
                <div class="heart-pop-overlay">
                  <svg width="84" height="84" viewBox="0 0 24 24" fill="#F43F5E">
                    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                  </svg>
                </div>
              }
            </div>

            <!-- 3. Actions Row (Like, Chat, Share) -->
            <div class="action-row">
              <div class="left-actions">
                <button class="action-btn" (click)="toggleLike(item)" title="Like">
                  @if (item.is_liked) {
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="#F43F5E">
                      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                    </svg>
                  } @else {
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                      <path d="M12.1 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54l-1.35 1.31z" stroke="#FFFFFF" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  }
                </button>

                <button class="action-btn" (click)="startChat(item)" title="Chat">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="#FFFFFF" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>

                <button class="action-btn" (click)="sharePersona(item)" title="Share Persona">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                    <path d="M22 2L11 13M22 2L15 22L11 13L2 9L22 2Z" stroke="#FFFFFF" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>

              <div class="right-actions">
                <button class="action-btn" (click)="openPersona(item)" title="View Details">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" stroke="#FFFFFF" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>
            </div>

            <!-- 4. Likes Count -->
            <div class="likes-count-row">
              <span class="likes-bold">{{ feedService.formatCount(item.likes_count) }} likes</span>
            </div>

            <!-- 5. Caption & Details -->
            <div class="caption-container">
              <p class="caption-line">
                <strong class="caption-pub">{{ item.publisher_name }}</strong>
                <span class="caption-persona">{{ item.name }}@if (item.age) {, {{ item.age }}}</span>
                @if (item.tagline) {
                  <span class="caption-tagline"> • {{ item.tagline }}</span>
                }
              </p>

              @if (item.greeting) {
                <div class="opener-preview-box" (click)="startChat(item)" title="Click to chat with {{ item.name }}">
                  <div class="opener-badge">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="#60A5FA" stroke-width="2"/>
                    </svg>
                    <span>Intro Greeting</span>
                  </div>
                  <p class="opener-text">"{{ item.greeting }}"</p>
                </div>
              }
            </div>
          </article>
        }
      </main>

      <!-- Sub Modals -->
      <app-persona-detail-modal
        [persona]="selectedPersona"
        (close)="selectedPersona = null"
        (startChat)="onModalStartChat($event)"
        (openPublisher)="onModalOpenPublisher($event)"
      ></app-persona-detail-modal>

      <app-publisher-profile-modal
        [isOpen]="isPublisherModalOpen"
        [publisherHandle]="selectedPubHandle"
        [publisherName]="selectedPubName"
        [publisherAvatar]="selectedPubAvatar"
        [isFollowing]="selectedPubIsFollowing"
        [publisherPersonas]="feedService.feedItems()"
        (close)="isPublisherModalOpen = false"
        (startChat)="onModalStartChat($event)"
        (selectPersona)="openPersona($event)"
      ></app-publisher-profile-modal>

      <app-companion-chat-modal
        [persona]="activeChatPersona"
        (close)="activeChatPersona = null"
        (openDetails)="openPersona($event)"
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

    .feed-container {
      width: 100%;
      min-height: 100%;
      display: flex;
      flex-direction: column;
      background: #000000;
      color: #FFFFFF;
    }

    /* Top Logo Header (only visible on mobile screens < 768px) */
    .feed-header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #000000;
      border-bottom: 1px solid #262626;
      flex-shrink: 0;
      z-index: 10;
    }

    @media (min-width: 768px) {
      .feed-header {
        display: none !important;
      }
    }

    /* Main Feed List (Instagram Web desktop width 470px centered) */
    .feed-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 28px;
      padding: 32px 16px 100px;
      max-width: 470px;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
    }

    @media (max-width: 767px) {
      .feed-content {
        padding: 0 0 80px 0;
        gap: 20px;
      }
    }

    .feed-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      padding: 60px 20px;
      color: #71717A;
      font-size: 0.92rem;
    }
    .spinner {
      width: 22px;
      height: 22px;
      border: 2px solid #333338;
      border-top-color: #3B82F6;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    /* Post Card: CRITICAL flex-shrink: 0 prevents flexbox from collapsing */
    .feed-card {
      background: #000000;
      border-bottom: 1px solid #262626;
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      width: 100%;
      box-sizing: border-box;
      padding-bottom: 16px;
    }

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 0 12px;
      flex-shrink: 0;
    }

    .publisher-info {
      display: flex;
      align-items: center;
      gap: 12px;
      cursor: pointer;
    }

    .publisher-avatar {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: #262626;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      color: #FFFFFF;
      font-size: 0.9rem;
      border: 1.5px solid #38383E;
      flex-shrink: 0;
    }
    .publisher-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .publisher-names {
      display: flex;
      flex-direction: column;
    }
    .pub-name {
      font-size: 14px;
      font-weight: 600;
      color: #FFFFFF;
      letter-spacing: -0.1px;
    }
    .pub-handle {
      font-size: 12px;
      color: #71717A;
    }

    .follow-btn {
      padding: 6px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      background: #0095F6;
      color: #FFFFFF;
      transition: background 0.15s;
      flex-shrink: 0;
    }
    .follow-btn:hover {
      background: #1877F2;
    }
    .follow-btn.is-following {
      background: #363636;
      color: #F5F5F5;
    }

    /* Hero Media Container */
    .media-container {
      position: relative;
      width: 100%;
      height: 585px;
      min-height: 470px;
      aspect-ratio: 1 / 1;
      background: #121212;
      border-radius: 4px;
      border: 1px solid #262626;
      overflow: hidden;
      cursor: pointer;
      flex-shrink: 0;
      box-sizing: border-box;
    }
    @media (max-width: 767px) {
      .media-container {
        height: 470px;
        border-radius: 0;
        border-left: none;
        border-right: none;
      }
    }
    .media-image {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .media-fallback {
      width: 100%;
      height: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 12px;
    }
    .fallback-letter {
      font-family: var(--font-brand);
      font-size: 4.5rem;
      color: #FFFFFF;
    }
    .fallback-name {
      font-family: var(--font-brand);
      font-size: 1.6rem;
      color: #FFFFFF;
    }

    .floating-chat-btn {
      position: absolute;
      top: 14px;
      right: 14px;
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: rgba(0, 0, 0, 0.68);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: transform 0.15s, background 0.15s;
      z-index: 5;
    }
    .floating-chat-btn:hover {
      background: rgba(0, 0, 0, 0.88);
      transform: scale(1.08);
    }

    .heart-pop-overlay {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      pointer-events: none;
      animation: popHeart 0.65s cubic-bezier(0.16, 1, 0.3, 1) forwards;
      z-index: 10;
    }

    /* Actions Row */
    .action-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 0 8px;
      flex-shrink: 0;
    }
    .left-actions {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .right-actions {
      display: flex;
      align-items: center;
    }
    .action-btn {
      display: flex;
      align-items: center;
      cursor: pointer;
      transition: transform 0.12s;
    }
    .action-btn:hover {
      transform: scale(1.1);
    }

    .likes-count-row {
      padding: 0 0 6px;
      flex-shrink: 0;
    }
    .likes-bold {
      font-size: 14px;
      font-weight: 700;
      color: #F5F5F5;
    }

    .caption-container {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 0;
      flex-shrink: 0;
    }
    .caption-line {
      font-size: 14px;
      line-height: 1.45;
      color: #F5F5F5;
    }
    .caption-pub {
      color: #FFFFFF;
      font-weight: 700;
      margin-right: 6px;
    }
    .caption-persona {
      font-weight: 600;
      color: #FFFFFF;
    }
    .caption-tagline {
      color: #A8A8A8;
      font-weight: 400;
    }

    .opener-preview-box {
      background: #121214;
      border: 1px solid #262626;
      border-radius: 10px;
      padding: 12px 14px;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
      margin-top: 4px;
    }
    .opener-preview-box:hover {
      background: #18181B;
      border-color: #38383E;
    }
    .opener-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 700;
      color: #60A5FA;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      margin-bottom: 4px;
    }
    .opener-text {
      font-size: 13.5px;
      color: #D4D4D8;
      font-style: italic;
      line-height: 1.45;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    @keyframes popHeart {
      0% { transform: scale(0.3); opacity: 0; }
      50% { transform: scale(1.3); opacity: 1; }
      100% { transform: scale(1.1); opacity: 0; }
    }
  `]
})
export class HomeScreenComponent implements OnInit {
  readonly feedService = inject(FeedService);
  private authService = inject(AuthService);
  private alertService = inject(AlertService);

  selectedPersona: PersonaItem | null = null;
  activeChatPersona: PersonaItem | null = null;

  isPublisherModalOpen = false;
  selectedPubHandle = '';
  selectedPubName = '';
  selectedPubAvatar = '';
  selectedPubIsFollowing = false;

  readonly poppingHeartId = signal<string | null>(null);

  ngOnInit(): void {
    const user = this.authService.currentUser();
    this.feedService.fetchFeedPage(1, 10, false, user?.id);
  }

  toggleLike(item: FeedPersonaItem): void {
    const user = this.authService.currentUser();
    this.feedService.togglePersonaLike(item.id, !!item.is_liked, user?.id);
  }

  onDoubleTap(item: FeedPersonaItem): void {
    const user = this.authService.currentUser();
    if (!item.is_liked) {
      this.feedService.togglePersonaLike(item.id, false, user?.id);
    }
    this.poppingHeartId.set(item.id);
    setTimeout(() => {
      this.poppingHeartId.set(null);
    }, 650);
  }

  toggleFollow(item: FeedPersonaItem): void {
    const user = this.authService.currentUser();
    this.feedService.togglePublisherFollow(item.publisher_handle, !!item.is_following, user?.id);
  }

  openPersona(item: PersonaItem): void {
    this.selectedPersona = item;
  }

  openPublisher(item: FeedPersonaItem): void {
    this.selectedPubHandle = item.publisher_handle;
    this.selectedPubName = item.publisher_name;
    this.selectedPubAvatar = item.publisher_avatar || '';
    this.selectedPubIsFollowing = !!item.is_following;
    this.isPublisherModalOpen = true;
  }

  startChat(item: PersonaItem): void {
    this.activeChatPersona = item;
  }

  sharePersona(item: FeedPersonaItem): void {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      const shareUrl = `${window.location.origin}/tabs/personas?id=${item.id}`;
      navigator.clipboard.writeText(shareUrl);
      this.alertService.showAlert('Link Copied', `Share link for ${item.name} copied to clipboard!`, [{ text: 'OK', style: 'primary' }], 'info');
    }
  }

  onModalStartChat(persona: PersonaItem): void {
    this.selectedPersona = null;
    this.isPublisherModalOpen = false;
    this.activeChatPersona = persona;
  }

  onModalOpenPublisher(item: PersonaItem): void {
    this.selectedPersona = null;
    this.selectedPubHandle = item.publisher_handle || '';
    this.selectedPubName = item.publisher_name || '';
    this.selectedPubAvatar = item.publisher_avatar || '';
    this.selectedPubIsFollowing = false;
    this.isPublisherModalOpen = true;
  }
}
