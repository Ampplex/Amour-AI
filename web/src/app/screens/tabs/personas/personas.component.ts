import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { PersonaService, PersonaItem } from '../../../services/persona.service';
import { AuthService } from '../../../services/auth.service';
import { AlertService } from '../../../services/alert.service';
import { MarkdownTextComponent } from '../../../components/markdown-text/markdown-text.component';
import { PersonaDetailModalComponent } from '../../../components/persona-detail-modal/persona-detail-modal.component';
import { EditPublicPersonaModalComponent } from '../../../components/edit-public-persona-modal/edit-public-persona-modal.component';
import { CompanionChatModalComponent } from '../../../components/companion-chat-modal/companion-chat-modal.component';

@Component({
  selector: 'app-personas-screen',
  standalone: true,
  imports: [
    CommonModule,
    MarkdownTextComponent,
    PersonaDetailModalComponent,
    EditPublicPersonaModalComponent,
    CompanionChatModalComponent
  ],
  template: `
    <div class="personas-container">
      <!-- Header -->
      <header class="personas-header">
        <div class="header-title-box">
          <h1 class="header-title">My Personas</h1>
          <span class="count-badge">{{ filteredPersonas().length }}</span>
        </div>

        <button class="create-trigger-btn" (click)="navigateToCreate()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 5v14M5 12h14" stroke="#000000" stroke-width="2.5" stroke-linecap="round"/>
          </svg>
          Create
        </button>
      </header>

      <!-- Filter Tabs -->
      <div class="filter-bar">
        <button
          class="filter-tab"
          [class.active]="activeFilter() === 'all'"
          (click)="activeFilter.set('all')"
        >
          All
        </button>
        <button
          class="filter-tab"
          [class.active]="activeFilter() === 'private'"
          (click)="activeFilter.set('private')"
        >
          Private
        </button>
        <button
          class="filter-tab"
          [class.active]="activeFilter() === 'public'"
          (click)="activeFilter.set('public')"
        >
          Public
        </button>
      </div>

      <!-- Roster List -->
      <main class="roster-content">
        @if (personaService.isLoading() && personaService.personas().length === 0) {
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading personas...</span>
          </div>
        }

        @if (!personaService.isLoading() && filteredPersonas().length === 0) {
          <div class="empty-state">
            <div class="empty-icon-circle">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
                <path d="M12 2a5 5 0 1 0 5 5 5 5 0 0 0-5-5zm0 14c-4.42 0-8 2.24-8 5v1h16v-1c0-2.76-3.58-5-8-5z" fill="#71717A"/>
              </svg>
            </div>
            <h3 class="empty-title">No Personas Yet</h3>
            <p class="empty-desc">Create your first private companion or choose from the public community roster.</p>
            <button class="empty-cta" (click)="navigateToCreate()">Create Persona</button>
          </div>
        }

        @for (item of filteredPersonas(); track item.id) {
          <div class="persona-card" (click)="openDetail(item)">
            <div class="card-top">
              <div class="avatar-squircle" [style.border-color]="item.border_color || '#F43F5E'">
                @if (item.image_url) {
                  <img [src]="item.image_url" [alt]="item.name" />
                } @else {
                  <span>{{ (item.name || 'P').charAt(0).toUpperCase() }}</span>
                }
              </div>

              <div class="persona-meta">
                <div class="name-row">
                  <h3 class="persona-name">
                    {{ item.name }}
                    @if (item.age) {
                      <span class="persona-age">, {{ item.age }}</span>
                    }
                  </h3>

                  <span class="vis-badge" [class.badge-public]="item.visibility === 'public'">
                    @if (item.visibility === 'public') {
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
                        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
                        <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" stroke="currentColor" stroke-width="2"/>
                      </svg>
                      Public
                    } @else {
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="currentColor" stroke-width="2"/>
                      </svg>
                      Private
                    }
                  </span>
                </div>

                @if (item.tagline) {
                  <p class="persona-tagline">{{ item.tagline }}</p>
                }
              </div>
            </div>

            @if (item.greeting) {
              <div class="opener-snippet">
                <app-markdown-text [content]="item.greeting"></app-markdown-text>
              </div>
            }

            <div class="card-bottom">
              <div class="left-actions">
                <button class="action-icon-btn" (click)="openEdit(item); $event.stopPropagation()" title="Edit Persona">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round"/>
                  </svg>
                </button>

                <button class="action-icon-btn del-btn" (click)="confirmDelete(item); $event.stopPropagation()" title="Delete Persona">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                    <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="#71717A" stroke-width="2" stroke-linecap="round"/>
                  </svg>
                </button>
              </div>

              <button class="chat-action-btn" (click)="startChat(item); $event.stopPropagation()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="#000000">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                Chat
              </button>
            </div>
          </div>
        }
      </main>

      <!-- Modals -->
      <app-persona-detail-modal
        [persona]="selectedDetailPersona"
        (close)="selectedDetailPersona = null"
        (startChat)="onStartChatFromModal($event)"
      ></app-persona-detail-modal>

      <app-edit-public-persona-modal
        [persona]="editingPersona"
        (close)="editingPersona = null"
        (saved)="onCustomizationSaved()"
      ></app-edit-public-persona-modal>

      <app-companion-chat-modal
        [persona]="activeChatPersona"
        (close)="activeChatPersona = null"
        (openDetails)="openDetail($event)"
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

    .personas-container {
      width: 100%;
      min-height: 100%;
      display: flex;
      flex-direction: column;
      background: #000000;
    }

    .personas-header {
      height: 64px;
      padding: 0 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #262626;
      background: #000000;
      flex-shrink: 0;
    }

    .header-title-box {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .header-title {
      font-family: var(--font-brand);
      font-size: 1.45rem;
      color: #FFFFFF;
    }

    .count-badge {
      padding: 2px 8px;
      border-radius: 9999px;
      background: #28282C;
      border: 1px solid #38383E;
      font-size: 0.75rem;
      font-weight: 700;
      color: #A1A1AA;
    }

    .create-trigger-btn {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 18px;
      border-radius: 9999px;
      background: #FFFFFF;
      color: #000000;
      font-weight: 700;
      font-size: 0.88rem;
      transition: background 0.15s;
    }
    .create-trigger-btn:hover {
      background: #E4E4E7;
    }

    .filter-bar {
      display: flex;
      padding: 14px 32px;
      gap: 10px;
      border-bottom: 1px solid #242428;
      background: #171717;
      flex-shrink: 0;
    }

    .filter-tab {
      padding: 6px 16px;
      border-radius: 9999px;
      background: #202022;
      border: 1px solid #2E2E32;
      color: #A1A1AA;
      font-size: 0.85rem;
      font-weight: 600;
      transition: all 0.15s;
    }
    .filter-tab.active {
      background: #FFFFFF;
      color: #000000;
      border-color: #FFFFFF;
    }

    .roster-content {
      flex: 1;
      overflow-y: auto;
      padding: 24px 32px 100px;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 20px;
      align-content: start;
    }

    @media (max-width: 767px) {
      .personas-header, .filter-bar {
        padding-left: 16px;
        padding-right: 16px;
      }
      .roster-content {
        display: flex;
        flex-direction: column;
        padding: 16px 16px 80px;
        gap: 14px;
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
      padding: 60px 20px;
    }
    .empty-icon-circle {
      width: 64px;
      height: 64px;
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
      margin-bottom: 20px;
    }
    .empty-cta {
      padding: 10px 20px;
      border-radius: 10px;
      background: #FFFFFF;
      color: #000000;
      font-weight: 700;
      font-size: 0.9rem;
    }

    .persona-card {
      background: #202022;
      border: 1px solid #28282C;
      border-radius: 16px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
    }
    .persona-card:hover {
      border-color: #38383E;
      background: #242426;
    }

    .card-top {
      display: flex;
      gap: 14px;
      align-items: center;
    }

    .avatar-squircle {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      border-width: 2px;
      border-style: solid;
      background: #18181A;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .avatar-squircle img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .avatar-squircle span {
      font-family: var(--font-brand);
      font-size: 1.4rem;
      color: #FFFFFF;
    }

    .persona-meta {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    .name-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }

    .persona-name {
      font-family: var(--font-brand);
      font-size: 1.1rem;
      color: #FFFFFF;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .persona-age {
      font-size: 0.95rem;
      color: #A1A1AA;
      font-weight: 400;
    }

    .vis-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 0.72rem;
      font-weight: 600;
      background: #28282C;
      color: #A1A1AA;
    }
    .vis-badge.badge-public {
      background: rgba(59, 130, 246, 0.15);
      color: #60A5FA;
    }

    .persona-tagline {
      font-size: 0.82rem;
      color: #A1A1AA;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-top: 2px;
    }

    .opener-snippet {
      background: #1C1C1F;
      border: 1px solid #26262A;
      border-radius: 10px;
      padding: 8px 12px;
      font-size: 0.82rem;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .card-bottom {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .left-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .action-icon-btn {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: #28282C;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: background 0.15s;
    }
    .action-icon-btn:hover {
      background: #323236;
    }
    .del-btn:hover svg path {
      stroke: #EF4444;
    }

    .chat-action-btn {
      padding: 7px 18px;
      border-radius: 9999px;
      background: #FFFFFF;
      color: #000000;
      font-weight: 700;
      font-size: 0.82rem;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
    }
    .chat-action-btn:hover {
      background: #E4E4E7;
      transform: translateY(-1px);
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  `]
})
export class PersonasScreenComponent implements OnInit {
  readonly personaService = inject(PersonaService);
  private authService = inject(AuthService);
  private alertService = inject(AlertService);
  private router = inject(Router);

  activeFilter = signal<'all' | 'private' | 'public'>('all');

  selectedDetailPersona: PersonaItem | null = null;
  editingPersona: PersonaItem | null = null;
  activeChatPersona: PersonaItem | null = null;

  readonly filteredPersonas = computed<PersonaItem[]>(() => {
    const list = this.personaService.personas();
    const filter = this.activeFilter();
    if (filter === 'private') return list.filter(p => p.visibility !== 'public');
    if (filter === 'public') return list.filter(p => p.visibility === 'public');
    return list;
  });

  ngOnInit(): void {
    const user = this.authService.currentUser();
    this.personaService.fetchAndSyncPersonas(user?.id);
  }

  navigateToCreate(): void {
    this.router.navigate(['/tabs/create']);
  }

  openDetail(p: PersonaItem): void {
    this.selectedDetailPersona = p;
  }

  openEdit(p: PersonaItem): void {
    this.editingPersona = p;
  }

  startChat(p: PersonaItem): void {
    this.activeChatPersona = p;
  }

  onStartChatFromModal(p: PersonaItem): void {
    this.selectedDetailPersona = null;
    this.activeChatPersona = p;
  }

  onCustomizationSaved(): void {
    const user = this.authService.currentUser();
    this.personaService.fetchAndSyncPersonas(user?.id);
  }

  confirmDelete(p: PersonaItem): void {
    this.alertService.showAlert(
      'Delete Persona',
      `Are you sure you want to remove "${p.name}" from your active roster?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            const user = this.authService.currentUser();
            await this.personaService.deletePersonaFromRoster(p.id, user?.id);
          },
        },
      ],
      'danger'
    );
  }
}
