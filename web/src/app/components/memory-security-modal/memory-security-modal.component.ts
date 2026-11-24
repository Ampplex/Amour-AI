import { Component, Input, Output, EventEmitter, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { KeyService } from '../../services/key.service';
import { AuthService } from '../../services/auth.service';
import { AlertService } from '../../services/alert.service';

@Component({
  selector: 'app-memory-security-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    @if (isOpen) {
      <div class="modal-backdrop" (click)="onClose()">
        <div class="modal-card" (click)="$event.stopPropagation()">
          <div class="modal-header">
            <div class="header-left">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="#60A5FA" stroke-width="2" stroke-linecap="round"/>
              </svg>
              <h3 class="modal-title">Encrypted Memory Security</h3>
            </div>
            <button class="close-btn" (click)="onClose()">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <!-- Mode Toggle Tabs -->
          <div class="tab-pill-row">
            <button
              class="tab-pill"
              [class.active]="activeTab === 'backup'"
              (click)="activeTab = 'backup'"
            >
              Backup &amp; Recovery
            </button>
            <button
              class="tab-pill"
              [class.active]="activeTab === 'restore'"
              (click)="activeTab = 'restore'"
            >
              Restore from Phrase
            </button>
          </div>

          @if (activeTab === 'backup') {
            <div class="tab-content">
              <p class="section-desc">
                Your companion memories are end-to-end encrypted with a 256-bit client key. Back up your key using a zero-knowledge 12-word recovery phrase.
              </p>

              @if (phraseWords.length > 0) {
                <div class="phrase-grid">
                  @for (word of phraseWords; track $index) {
                    <div class="phrase-chip">
                      <span class="chip-num">{{ $index + 1 }}</span>
                      <span class="chip-word">{{ word }}</span>
                    </div>
                  }
                </div>

                <div class="phrase-actions">
                  <button class="copy-phrase-btn" (click)="copyPhrase()">
                    {{ isCopied ? 'Copied to Clipboard' : 'Copy 12-Word Phrase' }}
                  </button>

                  <button class="backup-btn" [disabled]="isBackingUp" (click)="backupToServer()">
                    {{ isBackingUp ? 'Backing Up...' : 'Save Encrypted Backup to Cloud' }}
                  </button>
                </div>
              } @else {
                <button class="generate-btn" (click)="generatePhrase()">
                  Generate 12-Word Recovery Phrase
                </button>
              }
            </div>
          } @else {
            <div class="tab-content">
              <p class="section-desc">
                Enter your 12-word recovery phrase to restore your private memory encryption key on this device.
              </p>

              <textarea
                [(ngModel)]="restorePhraseInput"
                rows="3"
                class="restore-input"
                placeholder="abandon ability able about above absent absorb abstract absurd abuse access accident"
              ></textarea>

              <button class="restore-btn" [disabled]="isRestoring" (click)="restoreFromPhrase()">
                {{ isRestoring ? 'Restoring...' : 'Restore Memory Key' }}
              </button>
            </div>
          }
        </div>
      </div>
    }
  `,
  styles: [`
    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 6000;
      background: rgba(0, 0, 0, 0.85);
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
      margin-bottom: 16px;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 10px;
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

    .tab-pill-row {
      display: flex;
      background: #242428;
      border-radius: 12px;
      padding: 4px;
      margin-bottom: 20px;
      gap: 4px;
    }

    .tab-pill {
      flex: 1;
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      color: #A1A1AA;
      transition: all 0.15s ease;
    }
    .tab-pill.active {
      background: #323238;
      color: #FFFFFF;
    }

    .section-desc {
      font-size: 0.88rem;
      color: #A1A1AA;
      line-height: 1.45;
      margin-bottom: 18px;
    }

    .phrase-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-bottom: 20px;
    }

    .phrase-chip {
      background: #242428;
      border: 1px solid #2E2E34;
      border-radius: 8px;
      padding: 8px 10px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .chip-num {
      font-size: 0.72rem;
      color: #71717A;
      font-weight: 700;
    }

    .chip-word {
      font-size: 0.88rem;
      color: #FFFFFF;
      font-weight: 600;
    }

    .phrase-actions {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .generate-btn, .copy-phrase-btn, .backup-btn, .restore-btn {
      width: 100%;
      padding: 12px;
      border-radius: 10px;
      font-size: 0.92rem;
      font-weight: 700;
      transition: all 0.15s ease;
    }

    .generate-btn, .backup-btn, .restore-btn {
      background: #FFFFFF;
      color: #000000;
    }
    .generate-btn:hover, .backup-btn:hover, .restore-btn:hover {
      background: #E4E4E7;
    }

    .copy-phrase-btn {
      background: #28282C;
      color: #FFFFFF;
      border: 1px solid #38383E;
    }

    .restore-input {
      width: 100%;
      background: #242428;
      border: 1px solid #2E2E32;
      border-radius: 12px;
      padding: 12px;
      color: #FFFFFF;
      font-size: 0.9rem;
      line-height: 1.4;
      outline: none;
      resize: vertical;
      margin-bottom: 16px;
    }
    .restore-input:focus {
      border-color: #52525B;
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
export class MemorySecurityModalComponent implements OnInit {
  private keyService = inject(KeyService);
  private authService = inject(AuthService);
  private alertService = inject(AlertService);

  @Input() isOpen = false;
  @Output() close = new EventEmitter<void>();

  activeTab: 'backup' | 'restore' = 'backup';
  phraseWords: string[] = [];
  isCopied = false;
  isBackingUp = false;
  isRestoring = false;
  restorePhraseInput = '';

  ngOnInit(): void {
    this.generatePhrase();
  }

  onClose(): void {
    this.close.emit();
  }

  generatePhrase(): void {
    const phrase = this.keyService.generateRecoveryPhrase();
    this.phraseWords = phrase.split(' ');
  }

  copyPhrase(): void {
    const phrase = this.phraseWords.join(' ');
    navigator.clipboard.writeText(phrase);
    this.isCopied = true;
    setTimeout(() => {
      this.isCopied = false;
    }, 2500);
  }

  async backupToServer(): Promise<void> {
    const user = this.authService.currentUser();
    if (!user) {
      this.alertService.showAlert('Sign In Required', 'Please sign in to back up your encrypted memory key.', [{ text: 'OK', style: 'primary' }], 'warning');
      return;
    }

    this.isBackingUp = true;
    const phrase = this.phraseWords.join(' ');
    const res = await this.keyService.backupEncryptedKeyToServer(user.id, phrase, user.token);
    this.isBackingUp = false;

    if (res.success) {
      this.alertService.showAlert('Encrypted Backup Saved', 'Your 256-bit memory key was encrypted with your recovery phrase and backed up safely.', [{ text: 'Done', style: 'primary' }], 'success');
    } else {
      this.alertService.showAlert('Backup Notice', res.error || 'Failed to save encrypted backup', [{ text: 'OK', style: 'primary' }], 'danger');
    }
  }

  async restoreFromPhrase(): Promise<void> {
    const user = this.authService.currentUser();
    if (!user) {
      this.alertService.showAlert('Sign In Required', 'Please sign in to restore memory keys for your account.', [{ text: 'OK', style: 'primary' }], 'warning');
      return;
    }

    if (!this.restorePhraseInput.trim()) {
      this.alertService.showAlert('Phrase Required', 'Please enter your 12-word recovery phrase.', [{ text: 'OK', style: 'primary' }], 'warning');
      return;
    }

    this.isRestoring = true;
    const res = await this.keyService.restoreKeyFromServerWithPhrase(user.id, this.restorePhraseInput, user.token);
    this.isRestoring = false;

    if (res.success) {
      this.alertService.showAlert('Restoration Complete', 'Your memory key has been decrypted and saved. Your companion chats are now fully unlocked!', [{ text: 'Great', style: 'primary' }], 'success');
      this.onClose();
    } else {
      this.alertService.showAlert('Restoration Failed', res.error || 'Could not restore key', [{ text: 'OK', style: 'primary' }], 'danger');
    }
  }
}
