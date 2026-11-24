import { Component, Input, Output, EventEmitter, inject, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PersonaItem, PersonaService } from '../../services/persona.service';
import { AuthService } from '../../services/auth.service';
import { AlertService } from '../../services/alert.service';

@Component({
  selector: 'app-edit-public-persona-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    @if (persona) {
      <div class="modal-backdrop" (click)="onClose()">
        <div class="modal-card" (click)="$event.stopPropagation()">
          <div class="modal-header">
            <h3 class="modal-title">Customize Persona</h3>
            <button class="close-btn" (click)="onClose()">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <p class="subtitle">
            Changes made here are private to your conversations with {{ persona.name }}.
          </p>

          <div class="form-body">
            <div class="field-group">
              <label class="field-label">Tagline</label>
              <input type="text" [(ngModel)]="tagline" class="text-input" placeholder="Companion dynamic or role..." />
            </div>

            <div class="field-group">
              <label class="field-label">Custom Greeting</label>
              <textarea [(ngModel)]="greeting" rows="3" class="text-area" placeholder="How they initiate conversations with you..."></textarea>
            </div>

            <div class="field-group">
              <label class="field-label">Backstory &amp; Mind Profile</label>
              <textarea [(ngModel)]="memoryPrompt" rows="4" class="text-area" placeholder="Specific memories, tone of voice, or lore..."></textarea>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn-cancel" (click)="onClose()">Cancel</button>
            <button class="btn-save" (click)="onSave()">Save Changes</button>
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 5500;
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
      max-width: 540px;
      width: 100%;
      padding: 24px;
      display: flex;
      flex-direction: column;
      box-shadow: 0 25px 50px rgba(0, 0, 0, 0.7);
      animation: popIn 0.22s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .modal-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 6px;
    }

    .modal-title {
      font-family: var(--font-brand);
      font-size: 1.25rem;
      color: #FFFFFF;
    }

    .close-btn {
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }

    .subtitle {
      font-size: 0.85rem;
      color: #A1A1AA;
      margin-bottom: 20px;
      line-height: 1.4;
    }

    .form-body {
      display: flex;
      flex-direction: column;
      gap: 16px;
      margin-bottom: 24px;
    }

    .field-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .field-label {
      font-size: 0.8rem;
      font-weight: 600;
      color: #D4D4D8;
    }

    .text-input, .text-area {
      background: #242428;
      border: 1px solid #2E2E32;
      border-radius: 10px;
      padding: 10px 14px;
      color: #FFFFFF;
      font-size: 0.92rem;
      outline: none;
      transition: border-color 0.15s;
    }
    .text-input:focus, .text-area:focus {
      border-color: #52525B;
    }

    .modal-footer {
      display: flex;
      gap: 12px;
      justify-content: flex-end;
    }

    .btn-cancel {
      padding: 10px 18px;
      border-radius: 10px;
      background: #28282C;
      color: #D4D4D8;
      font-weight: 600;
      font-size: 0.9rem;
    }

    .btn-save {
      padding: 10px 22px;
      border-radius: 10px;
      background: #FFFFFF;
      color: #000000;
      font-weight: 700;
      font-size: 0.9rem;
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
export class EditPublicPersonaModalComponent implements OnChanges {
  private personaService = inject(PersonaService);
  private authService = inject(AuthService);
  private alertService = inject(AlertService);

  @Input() persona: PersonaItem | null = null;
  @Output() close = new EventEmitter<void>();
  @Output() saved = new EventEmitter<void>();

  tagline = '';
  greeting = '';
  memoryPrompt = '';

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['persona'] && this.persona) {
      const user = this.authService.currentUser();
      const custom = this.personaService.getPersonaCustomization(this.persona.id, user?.id);
      this.tagline = custom?.tagline ?? this.persona.tagline ?? '';
      this.greeting = custom?.greeting ?? this.persona.greeting ?? '';
      this.memoryPrompt = custom?.memory_prompt ?? this.persona.memory_prompt ?? '';
    }
  }

  onClose(): void {
    this.close.emit();
  }

  onSave(): void {
    if (!this.persona) return;
    const user = this.authService.currentUser();
    this.personaService.savePersonaCustomization(
      this.persona.id,
      {
        tagline: this.tagline,
        greeting: this.greeting,
        memory_prompt: this.memoryPrompt,
      },
      user?.id
    );

    this.alertService.showAlert('Changes Saved', 'Your personal adjustments for this persona have been updated.', [{ text: 'OK', style: 'primary' }], 'success');
    this.saved.emit();
    this.onClose();
  }
}
