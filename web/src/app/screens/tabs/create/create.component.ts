import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { PersonaService, PersonaItem } from '../../../services/persona.service';
import { AuthService } from '../../../services/auth.service';
import { AlertService } from '../../../services/alert.service';
import { API_CONFIG } from '../../../services/config';
import { CompanionChatModalComponent } from '../../../components/companion-chat-modal/companion-chat-modal.component';

const BORDER_COLORS = [
  { label: 'Crimson', color: '#F43F5E' },
  { label: 'Violet', color: '#8B5CF6' },
  { label: 'Emerald', color: '#10B981' },
  { label: 'Amber', color: '#F59E0B' },
  { label: 'Sapphire', color: '#3B82F6' },
];

const MEMORY_TAGS = [
  { label: 'Relationship', template: '\nRelationship: ' },
  { label: 'Romantic Dynamic', template: '\nDynamic: ' },
  { label: 'Personality & Quirks', template: '\nPersonality & Quirks: ' },
  { label: 'Love Language', template: '\nLove Language: ' },
  { label: 'Shared Lore', template: '\nShared Lore: ' },
  { label: 'Texting Style', template: '\nTexting Style: ' },
];

@Component({
  selector: 'app-create-screen',
  standalone: true,
  imports: [CommonModule, FormsModule, CompanionChatModalComponent],
  template: `
    <div class="create-container">
      <header class="create-header">
        @if (stage > 0) {
          <button class="back-stage-btn" (click)="stage = stage - 1" aria-label="Previous step">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M15 18l-6-6 6-6" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round"/>
            </svg>
          </button>
        }
        <h1 class="header-title">
          {{ stage === 0 ? 'Amour Studio' : stage === 1 ? 'Persona Visuals' : stage === 2 ? 'Mind & Voice' : 'Launch Review' }}
        </h1>
        @if (stage > 0) {
          <span class="step-indicator">Step {{ stage }}/3</span>
        }
      </header>

      <main class="create-content">
        <!-- STAGE 0: Studio Portal Overview -->
        @if (stage === 0) {
          <div class="stage-portal">
            <div class="portal-badge">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="#F59E0B"/>
              </svg>
              <span>Persona Engine</span>
            </div>

            <h2 class="portal-title">Architect Private Minds</h2>
            <p class="portal-desc">
              Design custom companions with tailored personalities, unique voices, and end-to-end encrypted memory graphs.
            </p>

            <div class="features-list">
              <div class="feature-card">
                <div class="feature-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <rect x="3" y="3" width="18" height="18" rx="4" stroke="#60A5FA" stroke-width="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5" fill="#60A5FA"/>
                    <path d="M21 15l-5-5L5 21" stroke="#60A5FA" stroke-width="2"/>
                  </svg>
                </div>
                <div class="feature-text">
                  <h4>Visual Identity</h4>
                  <p>Custom portrait with AWS S3 storage and custom neon borders.</p>
                </div>
              </div>

              <div class="feature-card">
                <div class="feature-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7zM9 21h6" stroke="#A78BFA" stroke-width="2" stroke-linecap="round"/>
                  </svg>
                </div>
                <div class="feature-text">
                  <h4>Mind &amp; Dynamic</h4>
                  <p>Define backstories, shared lore, and AI-assisted traits.</p>
                </div>
              </div>

              <div class="feature-card">
                <div class="feature-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="#34D399" stroke-width="2" stroke-linecap="round"/>
                  </svg>
                </div>
                <div class="feature-text">
                  <h4>Zero-Knowledge Security</h4>
                  <p>All conversation memory stays strictly encrypted on your keys.</p>
                </div>
              </div>
            </div>

            <button class="stage-cta-btn" (click)="stage = 1">
              Start Designing Companion
            </button>
          </div>
        }

        <!-- STAGE 1: Visuals & Core Identity -->
        @if (stage === 1) {
          <div class="stage-form">
            <!-- Photo Upload Area -->
            <div class="photo-picker-section">
              <label class="photo-box" [style.border-color]="selectedBorderColor">
                @if (imageUrl) {
                  <img [src]="imageUrl" alt="Preview" class="uploaded-img" />
                } @else {
                  <div class="upload-placeholder">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" stroke="#A1A1AA" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                    <span>Upload Avatar</span>
                  </div>
                }
                <input type="file" accept="image/*" class="file-hidden-input" (change)="onFileSelected($event)" />
              </label>

              @if (isUploadingImage) {
                <span class="uploading-hint">Uploading to AWS S3...</span>
              }
            </div>

            <!-- Border Color Selector -->
            <div class="field-group">
              <label class="field-label">Border Accent</label>
              <div class="colors-row">
                @for (c of borderColors; track c.color) {
                  <button
                    type="button"
                    class="color-dot"
                    [style.background-color]="c.color"
                    [class.selected]="selectedBorderColor === c.color"
                    (click)="selectedBorderColor = c.color"
                    [title]="c.label"
                  ></button>
                }
              </div>
            </div>

            <!-- Name, Age, Tagline with AI Spark -->
            <div class="field-group">
              <div class="label-with-ai">
                <label class="field-label">Persona Name</label>
                <button type="button" class="spark-ai-btn" [disabled]="isSparking" (click)="sparkPersona()">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="#F59E0B">
                    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                  </svg>
                  <span>{{ isSparking ? 'Sparking...' : 'AI Spark' }}</span>
                </button>
              </div>
              <input type="text" [(ngModel)]="botName" class="text-input" placeholder="e.g. Maya, Julian, Dr. Aris..." />
            </div>

            <div class="field-row">
              <div class="field-group flex-1">
                <label class="field-label">Age</label>
                <input type="number" [(ngModel)]="age" class="text-input" placeholder="21" />
              </div>
            </div>

            <div class="field-group">
              <label class="field-label">Tagline / Persona Role</label>
              <input type="text" [(ngModel)]="tagline" class="text-input" placeholder="e.g. Free-spirited photographer from Kyoto" />
            </div>

            <button class="stage-cta-btn" [disabled]="!botName.trim()" (click)="stage = 2">
              Next: Mind &amp; Voice
            </button>
          </div>
        }

        <!-- STAGE 2: Mind & Voice -->
        @if (stage === 2) {
          <div class="stage-form">
            <div class="field-group">
              <div class="label-with-ai">
                <label class="field-label">Opening Greeting</label>
                <button type="button" class="spark-ai-btn" [disabled]="isSparkingGreeting" (click)="sparkGreeting()">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="#F59E0B">
                    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                  </svg>
                  <span>{{ isSparkingGreeting ? 'Sparking...' : 'AI Spark' }}</span>
                </button>
              </div>
              <textarea
                [(ngModel)]="greeting"
                rows="3"
                class="text-area"
                placeholder="*looks up from her sketchbook and smiles* Hey there. Didn't hear you come in..."
              ></textarea>
            </div>

            <div class="field-group">
              <label class="field-label">Quick Lore Templates</label>
              <div class="tags-cloud">
                @for (tag of memoryTags; track tag.label) {
                  <button type="button" class="tag-btn" (click)="appendTag(tag.template)">
                    + {{ tag.label }}
                  </button>
                }
              </div>
            </div>

            <div class="field-group">
              <div class="label-with-ai">
                <label class="field-label">Backstory &amp; Mind Profile</label>
                <button type="button" class="spark-ai-btn" [disabled]="isSparkingMemory" (click)="sparkMemory()">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="#F59E0B">
                    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                  </svg>
                  <span>{{ isSparkingMemory ? 'Sparking...' : 'AI Spark' }}</span>
                </button>
              </div>
              <textarea
                [(ngModel)]="memoryProfile"
                rows="6"
                class="text-area"
                placeholder="Relationship: Childhood best friend&#10;Dynamic: Playfully teasing, deeply empathetic&#10;Shared Lore: You met at an indie coffee shop..."
              ></textarea>
            </div>

            <button class="stage-cta-btn" (click)="stage = 3">
              Next: Launch Review
            </button>
          </div>
        }

        <!-- STAGE 3: Launch Review & Deploy -->
        @if (stage === 3) {
          <div class="stage-form">
            <!-- Access Tier -->
            <div class="field-group">
              <label class="field-label">Access Tier</label>
              <div class="tier-choice-row">
                <div
                  class="tier-box"
                  [class.selected]="accessTier === 'private'"
                  (click)="accessTier = 'private'"
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="#60A5FA" stroke-width="2"/>
                  </svg>
                  <h4>Private</h4>
                  <p>Only you can converse with this companion.</p>
                </div>

                <div
                  class="tier-box"
                  [class.selected]="accessTier === 'public'"
                  (click)="accessTier = 'public'"
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="#10B981" stroke-width="2"/>
                    <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" stroke="#10B981" stroke-width="1.8"/>
                  </svg>
                  <h4>Public</h4>
                  <p>Shared on Discovery feed for the community.</p>
                </div>
              </div>
            </div>

            <!-- Review Summary Card -->
            <div class="summary-card">
              <div class="summary-top">
                <div class="summary-avatar" [style.border-color]="selectedBorderColor">
                  @if (imageUrl) {
                    <img [src]="imageUrl" alt="Avatar" />
                  } @else {
                    <span>{{ (botName || 'A').charAt(0) }}</span>
                  }
                </div>
                <div>
                  <h3 class="summary-name">{{ botName }}@if (age) {, {{ age }}}</h3>
                  <p class="summary-tagline">{{ tagline || 'Companion' }}</p>
                </div>
              </div>

              @if (greeting) {
                <div class="summary-greeting">
                  <span class="preview-label">Greeting:</span>
                  <p>{{ greeting }}</p>
                </div>
              }
            </div>

            <button class="stage-cta-btn deploy-btn" [disabled]="isDeploying" (click)="deployPersona()">
              {{ isDeploying ? 'Deploying Persona...' : 'Deploy & Start Chatting' }}
            </button>
          </div>
        }
      </main>

      <app-companion-chat-modal
        [persona]="deployedPersona"
        (close)="deployedPersona = null"
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

    .create-container {
      width: 100%;
      min-height: 100%;
      display: flex;
      flex-direction: column;
      background: #000000;
    }

    .create-header {
      height: 64px;
      padding: 0 32px;
      display: flex;
      align-items: center;
      gap: 12px;
      border-bottom: 1px solid #262626;
      background: #000000;
      flex-shrink: 0;
    }

    .back-stage-btn {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: background 0.15s;
    }
    .back-stage-btn:hover {
      background: #28282C;
    }

    .header-title {
      font-family: var(--font-brand);
      font-size: 1.35rem;
      color: #FFFFFF;
      flex: 1;
    }

    .step-indicator {
      font-size: 0.82rem;
      color: #71717A;
      font-weight: 600;
    }

    .create-content {
      flex: 1;
      overflow-y: auto;
      padding: 32px 24px 100px;
      max-width: 680px;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
    }

    @media (max-width: 767px) {
      .create-content {
        padding: 20px 16px 90px;
      }
    }

    .stage-portal {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      padding: 10px 0;
    }

    .portal-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      border-radius: 9999px;
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid rgba(245, 158, 11, 0.3);
      color: #F59E0B;
      font-size: 0.78rem;
      font-weight: 700;
      margin-bottom: 16px;
    }

    .portal-title {
      font-family: var(--font-brand);
      font-size: 1.7rem;
      color: #FFFFFF;
      margin-bottom: 8px;
    }

    .portal-desc {
      font-size: 0.92rem;
      color: #A1A1AA;
      line-height: 1.5;
      margin-bottom: 28px;
      max-width: 360px;
    }

    .features-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
      width: 100%;
      margin-bottom: 30px;
    }

    .feature-card {
      background: #202022;
      border: 1px solid #28282C;
      border-radius: 14px;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      gap: 14px;
      text-align: left;
    }

    .feature-icon {
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: #28282C;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .feature-text h4 {
      font-size: 0.92rem;
      font-weight: 600;
      color: #FFFFFF;
      margin-bottom: 2px;
    }
    .feature-text p {
      font-size: 0.8rem;
      color: #A1A1AA;
      line-height: 1.35;
    }

    .stage-cta-btn {
      width: 100%;
      padding: 14px;
      border-radius: 12px;
      background: #FFFFFF;
      color: #000000;
      font-weight: 700;
      font-size: 0.96rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .stage-cta-btn:disabled {
      opacity: 0.4;
      cursor: default;
    }
    .stage-cta-btn:not(:disabled):hover {
      background: #E4E4E7;
      transform: translateY(-1px);
    }

    .stage-form {
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    .photo-picker-section {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }

    .photo-box {
      width: 100px;
      height: 100px;
      border-radius: 50%;
      border-width: 3px;
      border-style: solid;
      background: #202022;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      position: relative;
    }

    .uploaded-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .upload-placeholder {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      color: #71717A;
      font-size: 0.72rem;
      font-weight: 600;
    }

    .file-hidden-input {
      display: none;
    }

    .uploading-hint {
      font-size: 0.78rem;
      color: #3B82F6;
    }

    .field-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .label-with-ai {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .field-label {
      font-size: 0.82rem;
      font-weight: 600;
      color: #D4D4D8;
    }

    .spark-ai-btn {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid rgba(245, 158, 11, 0.3);
      border-radius: 9999px;
      padding: 3px 10px;
      color: #F59E0B;
      font-size: 0.75rem;
      font-weight: 700;
      cursor: pointer;
    }
    .spark-ai-btn:disabled {
      opacity: 0.5;
    }

    .colors-row {
      display: flex;
      gap: 12px;
    }
    .color-dot {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      cursor: pointer;
      border: 2px solid transparent;
      transition: transform 0.15s, border-color 0.15s;
    }
    .color-dot.selected {
      border-color: #FFFFFF;
      transform: scale(1.15);
    }

    .text-input, .text-area {
      background: #202022;
      border: 1px solid #2E2E32;
      border-radius: 12px;
      padding: 12px 14px;
      color: #FFFFFF;
      font-size: 0.92rem;
      outline: none;
      transition: border-color 0.15s;
    }
    .text-input:focus, .text-area:focus {
      border-color: #52525B;
    }

    .tags-cloud {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .tag-btn {
      background: #242428;
      border: 1px solid #2E2E32;
      border-radius: 8px;
      padding: 6px 10px;
      color: #D4D4D8;
      font-size: 0.78rem;
      cursor: pointer;
    }
    .tag-btn:hover {
      background: #2C2C32;
    }

    .tier-choice-row {
      display: flex;
      gap: 12px;
    }
    .tier-box {
      flex: 1;
      background: #202022;
      border: 2px solid #28282C;
      border-radius: 14px;
      padding: 14px;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      gap: 6px;
      transition: all 0.15s;
    }
    .tier-box.selected {
      border-color: #FFFFFF;
      background: #242428;
    }
    .tier-box h4 {
      font-size: 0.95rem;
      font-weight: 700;
      color: #FFFFFF;
    }
    .tier-box p {
      font-size: 0.78rem;
      color: #A1A1AA;
      line-height: 1.35;
    }

    .summary-card {
      background: #202022;
      border: 1px solid #2E2E32;
      border-radius: 16px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .summary-top {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .summary-avatar {
      width: 52px;
      height: 52px;
      border-radius: 50%;
      border-width: 2px;
      border-style: solid;
      background: #18181A;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: var(--font-brand);
      font-size: 1.3rem;
      color: #FFFFFF;
    }
    .summary-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .summary-name {
      font-family: var(--font-brand);
      font-size: 1.15rem;
      color: #FFFFFF;
    }
    .summary-tagline {
      font-size: 0.82rem;
      color: #A1A1AA;
    }
    .summary-greeting {
      background: #1C1C1F;
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 0.85rem;
      color: #D4D4D8;
      font-style: italic;
    }
    .preview-label {
      display: block;
      font-size: 0.72rem;
      color: #71717A;
      font-style: normal;
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 4px;
    }
  `]
})
export class CreateScreenComponent {
  private personaService = inject(PersonaService);
  private authService = inject(AuthService);
  private alertService = inject(AlertService);
  private router = inject(Router);

  stage = 0; // 0: Portal, 1: Visuals, 2: Mind, 3: Launch

  readonly borderColors = BORDER_COLORS;
  readonly memoryTags = MEMORY_TAGS;

  imageUrl = '';
  selectedBorderColor = '#F43F5E';
  botName = '';
  age = '21';
  tagline = '';
  greeting = '';
  memoryProfile = '';
  accessTier: 'private' | 'public' = 'private';

  isUploadingImage = false;
  isSparking = false;
  isSparkingGreeting = false;
  isSparkingMemory = false;
  isDeploying = false;

  deployedPersona: PersonaItem | null = null;

  async onFileSelected(event: any): Promise<void> {
    const file = event.target?.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = reader.result as string;
      this.imageUrl = dataUrl;

      // Extract base64
      const base64Data = dataUrl.split(',')[1];
      if (base64Data) {
        this.isUploadingImage = true;
        const s3Url = await this.personaService.uploadPersonaAvatarToS3(base64Data, file.name || 'avatar.jpg');
        this.isUploadingImage = false;
        if (s3Url) {
          this.imageUrl = s3Url;
        }
      }
    };
    reader.readAsDataURL(file);
  }

  async sparkPersona(): Promise<void> {
    this.isSparking = true;
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/memory/generate-persona/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ field: 'name' }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.name) this.botName = data.name;
          if (data.age) this.age = String(data.age);
          if (data.tagline) this.tagline = data.tagline;
          break;
        }
      } catch {}
    }
    this.isSparking = false;
  }

  async sparkGreeting(): Promise<void> {
    this.isSparkingGreeting = true;
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/memory/generate-persona/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ field: 'greeting', name: this.botName, tagline: this.tagline }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.greeting) this.greeting = data.greeting;
          break;
        }
      } catch {}
    }
    this.isSparkingGreeting = false;
  }

  async sparkMemory(): Promise<void> {
    this.isSparkingMemory = true;
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/memory/generate-persona/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ field: 'memory', name: this.botName, tagline: this.tagline }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.memory_prompt) this.memoryProfile = data.memory_prompt;
          break;
        }
      } catch {}
    }
    this.isSparkingMemory = false;
  }

  appendTag(template: string): void {
    this.memoryProfile = (this.memoryProfile ? this.memoryProfile + '\n' : '') + template;
  }

  async deployPersona(): Promise<void> {
    const user = this.authService.currentUser();
    this.isDeploying = true;

    const newPersona = await this.personaService.savePersonaToRoster(
      {
        name: this.botName.trim(),
        tagline: this.tagline.trim(),
        age: parseInt(this.age) || 21,
        border_color: this.selectedBorderColor,
        image_url: this.imageUrl,
        greeting: this.greeting.trim(),
        memory_prompt: this.memoryProfile.trim(),
        visibility: this.accessTier,
        publisher_name: user?.name || 'Creator',
        publisher_handle: `@${(user?.username || user?.name || 'creator').toLowerCase().replace(/\s+/g, '_')}`,
        publisher_avatar: user?.picture || '',
      },
      user?.id
    );

    this.isDeploying = false;
    this.alertService.showAlert('Persona Deployed', `"${newPersona.name}" is now live and saved in your companion roster.`, [{ text: 'Start Chat', style: 'primary' }], 'success');
    this.deployedPersona = newPersona;
  }
}
