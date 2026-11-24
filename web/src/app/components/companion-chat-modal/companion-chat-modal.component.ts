import { Component, Input, Output, EventEmitter, inject, OnInit, OnChanges, SimpleChanges, ElementRef, viewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PersonaItem } from '../../services/persona.service';
import { ChatService, ChatHistoryItem } from '../../services/chat.service';
import { AuthService } from '../../services/auth.service';
import { AlertService } from '../../services/alert.service';
import { MarkdownTextComponent } from '../markdown-text/markdown-text.component';

@Component({
  selector: 'app-companion-chat-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownTextComponent],
  template: `
    @if (persona) {
      <div class="chat-modal-container">
        <!-- Top Navigation Bar -->
        <header class="chat-header">
          <button class="back-btn" (click)="onClose()" aria-label="Back">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M15 18l-6-6 6-6" stroke="#FFFFFF" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>

          <div class="header-avatar" [style.border-color]="persona.border_color || '#F43F5E'" (click)="onOpenDetails()">
            @if (persona.image_url) {
              <img [src]="persona.image_url" [alt]="persona.name" />
            } @else {
              <div class="fallback-avatar" [style.background-color]="persona.border_color || '#F43F5E'">
                {{ (persona.name || 'A').charAt(0) }}
              </div>
            }
          </div>

          <div class="header-info" (click)="onOpenDetails()">
            <h3 class="header-name">{{ persona.name }}</h3>
            <div class="header-badge">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="#60A5FA" stroke-width="2" stroke-linecap="round"/>
              </svg>
              <span>Zero-Knowledge Encrypted Memory</span>
            </div>
          </div>

          <div class="header-actions">
            <button class="menu-icon-btn" (click)="onOpenDetails()" title="Persona Info">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="#A1A1AA" stroke-width="2"/>
                <path d="M12 16v-4M12 8h.01" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </header>

        <!-- Message Thread -->
        <main class="messages-container" #scrollContainer>
          @if (isLoading) {
            <div class="loading-state">
              <div class="spinner"></div>
              <span>Decrypting Reeve memory graph...</span>
            </div>
          }

          @if (!isLoading && messages.length === 0) {
            <!-- Empty state with opening greeting -->
            <div class="greeting-hero">
              <div class="hero-avatar" [style.border-color]="persona.border_color || '#F43F5E'">
                @if (persona.image_url) {
                  <img [src]="persona.image_url" [alt]="persona.name" />
                } @else {
                  <span>{{ (persona.name || 'A').charAt(0) }}</span>
                }
              </div>
              <h2 class="hero-name">{{ persona.name }}</h2>
              <p class="hero-tagline">{{ persona.tagline || 'AI Companion' }}</p>

              @if (persona.greeting) {
                <div class="first-opener-card">
                  <span class="opener-label">Opening message</span>
                  <app-markdown-text [content]="persona.greeting"></app-markdown-text>
                </div>
              }
            </div>
          }

          @for (msg of messages; track msg.id || $index) {
            <div class="message-row" [class.user-row]="msg.sender === 'user'" [class.bot-row]="msg.sender === 'bot'">
              @if (msg.sender === 'bot') {
                <div class="msg-avatar" [style.border-color]="persona.border_color || '#F43F5E'">
                  @if (persona.image_url) {
                    <img [src]="persona.image_url" [alt]="persona.name" />
                  } @else {
                    <span>{{ (persona.name || 'A').charAt(0) }}</span>
                  }
                </div>
              }

              <div class="message-bubble-wrapper">
                @if (editingMessageId === msg.id) {
                  <div class="edit-box">
                    <textarea [(ngModel)]="editingText" rows="3" class="edit-textarea"></textarea>
                    <div class="edit-actions">
                      <button class="btn-cancel-edit" (click)="cancelEdit()">Cancel</button>
                      <button class="btn-save-edit" (click)="saveEdit(msg)">Save</button>
                    </div>
                  </div>
                } @else {
                  <div class="message-bubble" [class.user-bubble]="msg.sender === 'user'" [class.bot-bubble]="msg.sender === 'bot'">
                    <app-markdown-text [content]="msg.text"></app-markdown-text>
                  </div>

                  <!-- Bot Variant Selector & Hover Actions -->
                  <div class="message-footer">
                    @if (msg.sender === 'bot' && msg.variants && msg.variants.length > 1) {
                      <div class="variant-switcher">
                        <button class="var-btn" [disabled]="(msg.active_variant_index || 0) <= 0" (click)="switchVariant(msg, (msg.active_variant_index || 0) - 1)">
                          &lt;
                        </button>
                        <span class="var-count">{{ (msg.active_variant_index || 0) + 1 }}/{{ msg.variants.length }}</span>
                        <button class="var-btn" [disabled]="(msg.active_variant_index || 0) >= msg.variants.length - 1" (click)="switchVariant(msg, (msg.active_variant_index || 0) + 1)">
                          &gt;
                        </button>
                      </div>
                    }

                    <div class="action-toolbar">
                      <button class="tool-btn" (click)="copyMessage(msg.text)" title="Copy text">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                          <rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" stroke-width="2"/>
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2"/>
                        </svg>
                      </button>

                      <button class="tool-btn" (click)="startEdit(msg)" title="Edit message">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                        </svg>
                      </button>

                      @if (msg.sender === 'bot') {
                        <button class="tool-btn" (click)="regenerateResponse(msg)" title="Regenerate alternative reply">
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                          </svg>
                        </button>
                      }

                      <button class="tool-btn tool-btn-del" (click)="deleteMessage(msg)" title="Delete message">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                          <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                        </svg>
                      </button>
                    </div>
                  </div>
                }
              </div>
            </div>
          }

          <!-- Typing Indicator -->
          @if (isGenerating) {
            <div class="message-row bot-row">
              <div class="msg-avatar" [style.border-color]="persona.border_color || '#F43F5E'">
                @if (persona.image_url) {
                  <img [src]="persona.image_url" [alt]="persona.name" />
                } @else {
                  <span>{{ (persona.name || 'A').charAt(0) }}</span>
                }
              </div>
              <div class="typing-bubble">
                <span class="dot"></span>
                <span class="dot"></span>
                <span class="dot"></span>
              </div>
            </div>
          }
        </main>

        <!-- Suggestion Chips -->
        <div class="suggestions-bar">
          <button class="suggestion-chip" (click)="sendAutonomousContinue()">
            Continue dialogue...
          </button>
          <button class="suggestion-chip" (click)="quickPrompt('*looks at you curiously* What are you thinking?')">
            What are you thinking?
          </button>
          <button class="suggestion-chip" (click)="quickPrompt('*smiles warmly* Tell me more.')">
            Tell me more
          </button>
        </div>

        <!-- Message Input Bar -->
        <footer class="chat-input-bar">
          <textarea
            [(ngModel)]="inputText"
            rows="1"
            class="chat-input"
            [placeholder]="'Message ' + persona.name + '...'"
            (keydown)="onKeyDown($event)"
          ></textarea>

          <button
            class="send-btn"
            [disabled]="!inputText.trim() || isGenerating"
            (click)="sendMessage()"
            aria-label="Send message"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M5 12h14M12 5l7 7-7 7" stroke="#000000" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </footer>
      </div>
    }
  `,
  styles: [`
    .chat-modal-container {
      position: fixed;
      inset: 0;
      z-index: 4000;
      background: #171717;
      display: flex;
      flex-direction: column;
      width: 100vw;
      height: 100vh;
      animation: fadeIn 0.18s ease;
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    .chat-header {
      height: 64px;
      background: #1C1C1F;
      border-bottom: 1px solid #28282C;
      display: flex;
      align-items: center;
      padding: 0 24px;
      gap: 14px;
      flex-shrink: 0;
      width: 100%;
      box-sizing: border-box;
    }

    .back-btn, .menu-icon-btn {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: background 0.15s;
    }
    .back-btn:hover, .menu-icon-btn:hover {
      background: #28282C;
    }

    .header-avatar {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      border-width: 2px;
      border-style: solid;
      overflow: hidden;
      cursor: pointer;
      flex-shrink: 0;
    }
    .header-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .fallback-avatar {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      color: #FFFFFF;
      font-size: 0.95rem;
    }

    .header-info {
      flex: 1;
      display: flex;
      flex-direction: column;
      cursor: pointer;
      min-width: 0;
    }

    .header-name {
      font-family: var(--font-brand);
      font-size: 1.05rem;
      color: #FFFFFF;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .header-badge {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 0.72rem;
      color: #60A5FA;
      font-weight: 500;
    }

    .messages-container {
      flex: 1;
      overflow-y: auto;
      padding: 24px 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      max-width: 960px;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
    }

    .loading-state {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      padding: 30px;
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

    .greeting-hero {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      padding: 24px 12px;
    }
    .hero-avatar {
      width: 80px;
      height: 80px;
      border-radius: 50%;
      border-width: 3px;
      border-style: solid;
      overflow: hidden;
      margin-bottom: 12px;
    }
    .hero-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .hero-avatar span {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
      font-family: var(--font-brand);
      font-size: 1.8rem;
    }
    .hero-name {
      font-family: var(--font-brand);
      font-size: 1.3rem;
      color: #FFFFFF;
    }
    .hero-tagline {
      font-size: 0.88rem;
      color: #A1A1AA;
      margin-bottom: 18px;
    }
    .first-opener-card {
      background: #202022;
      border: 1px solid #2E2E32;
      border-radius: 14px;
      padding: 14px;
      text-align: left;
      width: 100%;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .opener-label {
      display: block;
      font-size: 0.72rem;
      font-weight: 700;
      color: #71717A;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 6px;
    }

    .message-row {
      display: flex;
      gap: 10px;
      max-width: 88%;
    }
    .bot-row {
      align-self: flex-start;
    }
    .user-row {
      align-self: flex-end;
      flex-direction: row-reverse;
    }

    .msg-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      border-width: 1.5px;
      border-style: solid;
      overflow: hidden;
      flex-shrink: 0;
      margin-top: 2px;
    }
    .msg-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .msg-avatar span {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
      font-weight: 700;
      font-size: 0.8rem;
    }

    .message-bubble-wrapper {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .message-bubble {
      padding: 12px 16px;
      border-radius: 16px;
      font-size: 0.95rem;
      position: relative;
    }
    .bot-bubble {
      background: #202022;
      border: 1px solid #28282C;
      border-top-left-radius: 4px;
    }
    .user-bubble {
      background: #2A2A30;
      border: 1px solid #36363C;
      border-top-right-radius: 4px;
    }

    .message-footer {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 4px;
    }
    .user-row .message-footer {
      justify-content: flex-end;
    }

    .variant-switcher {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: #202024;
      border: 1px solid #2E2E32;
      border-radius: 6px;
      padding: 2px 6px;
    }
    .var-btn {
      font-size: 0.75rem;
      color: #A1A1AA;
      cursor: pointer;
    }
    .var-btn:disabled {
      opacity: 0.3;
      cursor: default;
    }
    .var-count {
      font-size: 0.72rem;
      color: #71717A;
    }

    .action-toolbar {
      display: flex;
      align-items: center;
      gap: 4px;
      opacity: 0.6;
      transition: opacity 0.15s;
    }
    .message-bubble-wrapper:hover .action-toolbar {
      opacity: 1;
    }

    .tool-btn {
      width: 22px;
      height: 22px;
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #71717A;
      cursor: pointer;
    }
    .tool-btn:hover {
      background: #28282C;
      color: #FFFFFF;
    }
    .tool-btn-del:hover {
      color: #EF4444;
    }

    .edit-box {
      background: #202022;
      border: 1px solid #3B82F6;
      border-radius: 12px;
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .edit-textarea {
      background: transparent;
      border: none;
      color: #FFFFFF;
      font-size: 0.92rem;
      outline: none;
      resize: vertical;
      font-family: inherit;
    }
    .edit-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
    }
    .btn-cancel-edit {
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 0.8rem;
      color: #A1A1AA;
    }
    .btn-save-edit {
      padding: 4px 12px;
      border-radius: 6px;
      font-size: 0.8rem;
      background: #3B82F6;
      color: #FFFFFF;
      font-weight: 600;
    }

    .typing-bubble {
      background: #202022;
      border: 1px solid #28282C;
      border-radius: 16px;
      border-top-left-radius: 4px;
      padding: 14px 18px;
      display: flex;
      gap: 5px;
      align-items: center;
    }
    .dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #A1A1AA;
      animation: bounceDot 1.4s infinite ease-in-out both;
    }
    .dot:nth-child(1) { animation-delay: -0.32s; }
    .dot:nth-child(2) { animation-delay: -0.16s; }

    .suggestions-bar {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 10px 24px;
      background: #171717;
      border-top: 1px solid #222226;
      scrollbar-width: none;
      max-width: 960px;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
    }
    .suggestions-bar::-webkit-scrollbar {
      display: none;
    }
    .suggestion-chip {
      padding: 6px 14px;
      border-radius: 9999px;
      background: #202022;
      border: 1px solid #2E2E32;
      color: #D4D4D8;
      font-size: 0.78rem;
      font-weight: 500;
      white-space: nowrap;
      transition: all 0.15s;
    }
    .suggestion-chip:hover {
      background: #28282C;
      border-color: #3F3F46;
      color: #FFFFFF;
    }

    .continue-bar {
      padding: 8px 24px;
      background: #171717;
      border-top: 1px solid #222226;
      display: flex;
      justify-content: center;
      max-width: 960px;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
    }

    .chat-input-bar {
      padding: 12px 24px 18px;
      background: #1C1C1F;
      border-top: 1px solid #28282C;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      box-sizing: border-box;
    }

    .chat-input-bar > * {
      max-width: 960px;
    }

    .chat-input {
      flex: 1;
      max-width: 900px;
      background: #242428;
      border: 1px solid #2E2E32;
      border-radius: 22px;
      padding: 12px 18px;
      color: #FFFFFF;
      font-size: 0.95rem;
      outline: none;
      resize: none;
      max-height: 100px;
      line-height: 1.4;
      transition: border-color 0.15s;
    }
    .chat-input:focus {
      border-color: #52525B;
    }

    .send-btn {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: #FFFFFF;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      flex-shrink: 0;
      transition: all 0.15s;
    }
    .send-btn:disabled {
      opacity: 0.3;
      cursor: default;
    }
    .send-btn:not(:disabled):hover {
      background: #E4E4E7;
      transform: scale(1.04);
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    @keyframes bounceDot {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }
    @keyframes slideUp {
      from { transform: translateY(100%); }
      to { transform: translateY(0); }
    }
  `]
})
export class CompanionChatModalComponent implements OnInit, OnChanges {
  private chatService = inject(ChatService);
  private authService = inject(AuthService);
  private alertService = inject(AlertService);

  @Input() persona: PersonaItem | null = null;
  @Output() close = new EventEmitter<void>();
  @Output() openDetails = new EventEmitter<PersonaItem>();

  scrollContainer = viewChild<ElementRef>('scrollContainer');

  messages: ChatHistoryItem[] = [];
  inputText = '';
  isLoading = false;
  isGenerating = false;

  editingMessageId: string | null = null;
  editingText = '';

  ngOnInit(): void {
    if (this.persona) {
      this.loadHistory();
    }
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['persona'] && this.persona) {
      this.loadHistory();
    }
  }

  onClose(): void {
    this.close.emit();
  }

  onOpenDetails(): void {
    if (this.persona) {
      this.openDetails.emit(this.persona);
    }
  }

  async loadHistory(): Promise<void> {
    if (!this.persona) return;
    const user = this.authService.currentUser();
    const effectiveUserId = user?.id || 'guest';

    this.isLoading = true;
    const res = await this.chatService.fetchChatHistory(this.persona.id, effectiveUserId, 1, 50, user?.token);
    this.isLoading = false;

    if (res && res.results) {
      this.messages = res.results;
      this.scrollToBottom();
    }
  }

  async sendMessage(customText?: string): Promise<void> {
    const textToSend = (customText || this.inputText).trim();
    if (!textToSend || !this.persona || this.isGenerating) return;

    const user = this.authService.currentUser();
    const effectiveUserId = user?.id || 'guest';

    // 1. Optimistic user message bubble
    const userMsgId = 'opt-usr-' + Date.now().toString(36);
    const userMsg: ChatHistoryItem = {
      id: userMsgId,
      user_id: effectiveUserId,
      persona_id: this.persona.id,
      namespace: effectiveUserId,
      sender: 'user',
      text: textToSend,
      created_at: new Date().toISOString(),
    };
    this.messages.push(userMsg);
    if (!customText) {
      this.inputText = '';
    }
    this.scrollToBottom();

    // 2. Trigger Bot generation
    this.isGenerating = true;
    const payload = {
      message: textToSend,
      persona_id: this.persona.id,
      persona_name: this.persona.name,
      greeting: this.persona.greeting,
      memory_prompt: this.persona.memory_prompt,
      client_time: new Date().toLocaleTimeString(),
      client_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      user_id: effectiveUserId,
      user_name: user?.name,
    };

    const res = await this.chatService.sendChatMessage(payload, user?.token);
    this.isGenerating = false;

    if (res && res.reply) {
      const botMsg: ChatHistoryItem = {
        id: res.id,
        user_id: effectiveUserId,
        persona_id: this.persona.id,
        namespace: res.namespace || effectiveUserId,
        sender: 'bot',
        text: res.reply,
        variants: res.variants || [res.reply],
        active_variant_index: res.active_variant_index ?? 0,
        conflict_stage: res.conflict_stage,
        conflict_level: res.conflict_level,
        created_at: new Date().toISOString(),
      };
      this.messages.push(botMsg);
      this.scrollToBottom();
    } else {
      this.alertService.showAlert('Message Notice', 'Could not receive a reply from companion. Please check your connection.', [{ text: 'OK', style: 'primary' }], 'warning');
    }
  }

  async sendAutonomousContinue(): Promise<void> {
    if (!this.persona || this.isGenerating) return;
    const user = this.authService.currentUser();
    const effectiveUserId = user?.id || 'guest';

    this.isGenerating = true;
    const payload = {
      message: '...',
      persona_id: this.persona.id,
      persona_name: this.persona.name,
      greeting: this.persona.greeting,
      memory_prompt: this.persona.memory_prompt,
      client_time: new Date().toLocaleTimeString(),
      client_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      user_id: effectiveUserId,
      user_name: user?.name,
      is_autonomous_continue: true,
    };

    const res = await this.chatService.sendChatMessage(payload, user?.token);
    this.isGenerating = false;

    if (res && res.reply) {
      const botMsg: ChatHistoryItem = {
        id: res.id,
        user_id: effectiveUserId,
        persona_id: this.persona.id,
        namespace: res.namespace || effectiveUserId,
        sender: 'bot',
        text: res.reply,
        variants: res.variants || [res.reply],
        active_variant_index: res.active_variant_index ?? 0,
        conflict_stage: res.conflict_stage,
        created_at: new Date().toISOString(),
      };
      this.messages.push(botMsg);
      this.scrollToBottom();
    }
  }

  quickPrompt(prompt: string): void {
    this.sendMessage(prompt);
  }

  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  copyMessage(text: string): void {
    navigator.clipboard.writeText(text);
    this.alertService.showAlert('Copied', 'Message copied to clipboard.', [{ text: 'OK', style: 'primary' }], 'info');
  }

  startEdit(msg: ChatHistoryItem): void {
    this.editingMessageId = msg.id;
    this.editingText = msg.text;
  }

  cancelEdit(): void {
    this.editingMessageId = null;
    this.editingText = '';
  }

  async saveEdit(msg: ChatHistoryItem): Promise<void> {
    if (!this.editingText.trim()) return;
    const user = this.authService.currentUser();
    const effectiveUserId = user?.id || 'guest';

    msg.text = this.editingText;
    this.editingMessageId = null;

    if (msg.sender === 'bot') {
      await this.chatService.editBotChatMessage(msg.id, this.editingText, effectiveUserId, user?.token);
    }
  }

  async switchVariant(msg: ChatHistoryItem, targetIndex: number): Promise<void> {
    if (!msg.variants || targetIndex < 0 || targetIndex >= msg.variants.length) return;
    const user = this.authService.currentUser();
    const effectiveUserId = user?.id || 'guest';

    msg.active_variant_index = targetIndex;
    msg.text = msg.variants[targetIndex];

    await this.chatService.switchChatMessageVariant(msg.id, targetIndex, effectiveUserId, user?.token);
  }

  async regenerateResponse(msg: ChatHistoryItem): Promise<void> {
    if (!this.persona || this.isGenerating) return;
    const user = this.authService.currentUser();
    const effectiveUserId = user?.id || 'guest';

    this.isGenerating = true;
    const payload = {
      regenerate_bot_message_id: msg.id,
      message: 'regenerate',
      persona_id: this.persona.id,
      persona_name: this.persona.name,
      greeting: this.persona.greeting,
      memory_prompt: this.persona.memory_prompt,
      client_time: new Date().toLocaleTimeString(),
      client_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      user_id: effectiveUserId,
    };

    const res = await this.chatService.sendChatMessage(payload, user?.token);
    this.isGenerating = false;

    if (res && res.reply) {
      msg.text = res.reply;
      msg.variants = res.variants || [...(msg.variants || []), res.reply];
      msg.active_variant_index = res.active_variant_index ?? msg.variants.length - 1;
    }
  }

  deleteMessage(msg: ChatHistoryItem): void {
    this.alertService.showAlert(
      'Delete Message',
      'Permanently delete this message from your companion memory?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            const user = this.authService.currentUser();
            const effectiveUserId = user?.id || 'guest';
            this.messages = this.messages.filter((m) => m.id !== msg.id);
            await this.chatService.deleteChatMessage(msg.id, effectiveUserId, user?.token);
          },
        },
      ],
      'danger'
    );
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      const el = this.scrollContainer()?.nativeElement;
      if (el) {
        el.scrollTop = el.scrollHeight;
      }
    }, 60);
  }
}
