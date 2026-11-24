import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService, GoogleUser } from '../../../services/auth.service';
import { AlertService } from '../../../services/alert.service';
import { MemorySecurityModalComponent } from '../../../components/memory-security-modal/memory-security-modal.component';

@Component({
  selector: 'app-profile-screen',
  standalone: true,
  imports: [CommonModule, FormsModule, MemorySecurityModalComponent],
  template: `
    <div class="profile-container">
      <header class="profile-header">
        <h1 class="header-title">Profile</h1>
      </header>

      <main class="profile-content">
        <!-- 1. User Card -->
        <div class="user-hero-card">
          <div class="user-avatar-box">
            @if (user?.picture) {
              <img [src]="user?.picture" [alt]="user?.name" class="user-avatar-img" />
            } @else {
              <div class="user-avatar-fallback">
                {{ (user?.name || 'U').charAt(0).toUpperCase() }}
              </div>
            }
          </div>

          <div class="user-info">
            <h2 class="user-name">{{ user?.name || 'Guest User' }}</h2>
            <span class="user-username">&#64;{{ user?.username || 'user' }}</span>
            <span class="user-email">{{ user?.email || 'No email attached' }}</span>
          </div>

          <button class="edit-profile-btn" (click)="openEditProfileModal()">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>
            </svg>
            Edit Profile
          </button>
        </div>

        <!-- 2. Companion Reply Length Preference -->
        <div class="settings-group">
          <div class="group-header">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="#A1A1AA" stroke-width="1.8"/>
            </svg>
            <span class="group-title">Companion Reply Length</span>
          </div>

          <div class="length-options-grid">
            <button
              class="length-card"
              [class.active]="selectedReplyLength === 'short'"
              (click)="setReplyLength('short')"
            >
              <span class="length-title">Short &amp; Snappy</span>
              <span class="length-desc">Quick, brisk back-and-forth messages</span>
            </button>

            <button
              class="length-card"
              [class.active]="selectedReplyLength === 'default'"
              (click)="setReplyLength('default')"
            >
              <span class="length-title">Balanced &amp; Adaptive</span>
              <span class="length-desc">Natural conversational flow</span>
            </button>

            <button
              class="length-card"
              [class.active]="selectedReplyLength === 'long'"
              (click)="setReplyLength('long')"
            >
              <span class="length-title">Deep &amp; Narrative</span>
              <span class="length-desc">Rich roleplay, atmosphere &amp; depth</span>
            </button>
          </div>
        </div>

        <!-- 3. Security & Memory Section -->
        <div class="settings-group">
          <div class="group-header">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="#60A5FA" stroke-width="1.8"/>
            </svg>
            <span class="group-title">Encryption &amp; Zero-Knowledge</span>
          </div>

          <button class="menu-item-row" (click)="isSecurityModalOpen = true">
            <div class="menu-item-left">
              <span class="menu-item-name">Memory Recovery Phrase</span>
              <span class="menu-item-sub">View 12-word seed and cloud backup</span>
            </div>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M9 18l6-6-6-6" stroke="#71717A" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </button>
        </div>

        <!-- 4. Account Actions -->
        <div class="settings-group">
          <div class="group-header">
            <span class="group-title">Account</span>
          </div>

          <a href="https://amour-ai-v3e4.onrender.com/privacy/" target="_blank" class="menu-item-row">
            <div class="menu-item-left">
              <span class="menu-item-name">Privacy Policy</span>
            </div>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3" stroke="#71717A" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
          </a>

          <button class="menu-item-row" (click)="handleLogout()">
            <div class="menu-item-left">
              <span class="menu-item-name">Sign Out</span>
            </div>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" stroke="#71717A" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
          </button>

          <button class="menu-item-row danger-row" (click)="confirmDeleteAccount()">
            <div class="menu-item-left">
              <span class="menu-item-name danger-text">Delete Account</span>
              <span class="menu-item-sub danger-sub">Permanently erase profile &amp; encrypted history</span>
            </div>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="#EF4444" stroke-width="1.8" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
      </main>

      <!-- Edit Profile Modal -->
      @if (isEditModalOpen) {
        <div class="modal-backdrop" (click)="isEditModalOpen = false">
          <div class="modal-card" (click)="$event.stopPropagation()">
            <h3 class="modal-title">Edit Profile</h3>

            <div class="avatar-edit-box">
              <label class="avatar-edit-label">
                @if (editAvatarUri) {
                  <img [src]="editAvatarUri" alt="Avatar" class="avatar-edit-img" />
                } @else {
                  <span class="avatar-edit-char">{{ (editName || 'U').charAt(0) }}</span>
                }
                <div class="camera-badge">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" stroke="#FFFFFF" stroke-width="2"/>
                    <circle cx="12" cy="13" r="4" stroke="#FFFFFF" stroke-width="2"/>
                  </svg>
                </div>
                <input type="file" accept="image/*" class="file-hidden" (change)="onAvatarSelected($event)" />
              </label>
            </div>

            <div class="field-group">
              <label class="field-label">Full Name</label>
              <input type="text" [(ngModel)]="editName" class="text-input" placeholder="Your name" />
            </div>

            <div class="field-group">
              <label class="field-label">Username</label>
              <input type="text" [(ngModel)]="editUsername" class="text-input" placeholder="username" />
            </div>

            <div class="modal-actions">
              <button class="btn-cancel" (click)="isEditModalOpen = false">Cancel</button>
              <button class="btn-save" [disabled]="isSaving" (click)="saveProfile()">
                {{ isSaving ? 'Saving...' : 'Save' }}
              </button>
            </div>
          </div>
        </div>
      }

      <app-memory-security-modal
        [isOpen]="isSecurityModalOpen"
        (close)="isSecurityModalOpen = false"
      ></app-memory-security-modal>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      width: 100%;
      min-height: 100%;
      background: #000000;
    }

    .profile-container {
      width: 100%;
      min-height: 100%;
      display: flex;
      flex-direction: column;
      background: #000000;
    }

    .profile-header {
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

    .profile-content {
      flex: 1;
      overflow-y: auto;
      padding: 32px 24px 100px;
      max-width: 720px;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      gap: 22px;
    }

    @media (max-width: 767px) {
      .profile-header {
        padding: 0 16px;
      }
      .profile-content {
        padding: 20px 16px 90px;
      }
    }

    .user-hero-card {
      background: #202022;
      border: 1px solid #28282C;
      border-radius: 18px;
      padding: 22px 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }

    .user-avatar-box {
      width: 80px;
      height: 80px;
      border-radius: 50%;
      background: #28282C;
      border: 2px solid #38383E;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 12px;
    }
    .user-avatar-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .user-avatar-fallback {
      font-family: var(--font-brand);
      font-size: 2rem;
      color: #FFFFFF;
    }

    .user-info {
      display: flex;
      flex-direction: column;
      gap: 2px;
      margin-bottom: 16px;
    }
    .user-name {
      font-family: var(--font-brand);
      font-size: 1.35rem;
      color: #FFFFFF;
    }
    .user-username {
      font-size: 0.88rem;
      color: #3B82F6;
      font-weight: 500;
    }
    .user-email {
      font-size: 0.82rem;
      color: #71717A;
    }

    .edit-profile-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 18px;
      border-radius: 9999px;
      background: #28282C;
      border: 1px solid #38383E;
      color: #FFFFFF;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
    }
    .edit-profile-btn:hover {
      background: #323238;
    }

    .settings-group {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .group-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 4px;
    }
    .group-title {
      font-size: 0.8rem;
      font-weight: 700;
      color: #71717A;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .length-options-grid {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .length-card {
      background: #202022;
      border: 1px solid #28282C;
      border-radius: 12px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      text-align: left;
      cursor: pointer;
      transition: all 0.15s;
    }
    .length-card.active {
      background: #242428;
      border-color: #FFFFFF;
    }
    .length-title {
      font-size: 0.92rem;
      font-weight: 600;
      color: #FFFFFF;
      margin-bottom: 2px;
    }
    .length-desc {
      font-size: 0.78rem;
      color: #A1A1AA;
    }

    .menu-item-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 16px;
      background: #202022;
      border: 1px solid #28282C;
      border-radius: 12px;
      text-decoration: none;
      cursor: pointer;
      transition: background 0.15s;
    }
    .menu-item-row:hover {
      background: #242428;
    }

    .menu-item-left {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .menu-item-name {
      font-size: 0.92rem;
      font-weight: 600;
      color: #FFFFFF;
    }
    .menu-item-sub {
      font-size: 0.78rem;
      color: #71717A;
    }

    .danger-row:hover {
      background: rgba(239, 68, 68, 0.08);
    }
    .danger-text {
      color: #EF4444;
    }
    .danger-sub {
      color: rgba(239, 68, 68, 0.7);
    }

    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 6000;
      background: rgba(0, 0, 0, 0.82);
      backdrop-filter: blur(10px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }

    .modal-card {
      background: #1C1C1F;
      border: 1px solid #2E2E32;
      border-radius: 20px;
      max-width: 380px;
      width: 100%;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .modal-title {
      font-family: var(--font-brand);
      font-size: 1.25rem;
      color: #FFFFFF;
      text-align: center;
    }

    .avatar-edit-box {
      display: flex;
      justify-content: center;
    }
    .avatar-edit-label {
      width: 80px;
      height: 80px;
      border-radius: 50%;
      background: #28282C;
      border: 2px solid #38383E;
      position: relative;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }
    .avatar-edit-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .avatar-edit-char {
      font-family: var(--font-brand);
      font-size: 2rem;
      color: #FFFFFF;
    }
    .camera-badge {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 24px;
      background: rgba(0, 0, 0, 0.6);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .file-hidden {
      display: none;
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
    .text-input {
      background: #242428;
      border: 1px solid #2E2E32;
      border-radius: 10px;
      padding: 10px 14px;
      color: #FFFFFF;
      font-size: 0.92rem;
      outline: none;
    }

    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      margin-top: 8px;
    }
    .btn-cancel {
      padding: 10px 16px;
      border-radius: 10px;
      background: #28282C;
      color: #D4D4D8;
      font-weight: 600;
    }
    .btn-save {
      padding: 10px 20px;
      border-radius: 10px;
      background: #FFFFFF;
      color: #000000;
      font-weight: 700;
    }
  `]
})
export class ProfileScreenComponent implements OnInit {
  private authService = inject(AuthService);
  private alertService = inject(AlertService);
  private router = inject(Router);

  user: GoogleUser | null = null;
  selectedReplyLength: 'default' | 'short' | 'long' = 'default';

  isEditModalOpen = false;
  isSecurityModalOpen = false;
  isSaving = false;

  editName = '';
  editUsername = '';
  editAvatarUri: string | null = null;
  editAvatarBase64: string | null = null;

  ngOnInit(): void {
    this.user = this.authService.currentUser();
    this.selectedReplyLength = this.authService.getReplyLengthPreference();
  }

  setReplyLength(length: 'default' | 'short' | 'long'): void {
    this.selectedReplyLength = length;
    this.authService.setReplyLengthPreference(length);
    this.authService.updateProfile({ reply_length: length });
  }

  openEditProfileModal(): void {
    this.editName = this.user?.name || '';
    this.editUsername = this.user?.username || '';
    this.editAvatarUri = this.user?.picture || null;
    this.editAvatarBase64 = null;
    this.isEditModalOpen = true;
  }

  onAvatarSelected(event: any): void {
    const file = event.target?.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      this.editAvatarUri = result;
      this.editAvatarBase64 = result.split(',')[1];
    };
    reader.readAsDataURL(file);
  }

  async saveProfile(): Promise<void> {
    this.isSaving = true;

    let pictureUrl = this.user?.picture;
    if (this.editAvatarBase64) {
      const upRes = await this.authService.uploadProfilePicture({ base64: this.editAvatarBase64 });
      if (upRes.url) {
        pictureUrl = upRes.url;
      }
    }

    const res = await this.authService.updateProfile({
      name: this.editName.trim(),
      username: this.editUsername.trim().toLowerCase(),
      picture: pictureUrl,
    });

    this.isSaving = false;

    if (res.success) {
      this.user = res.user || this.authService.currentUser();
      this.isEditModalOpen = false;
      this.alertService.showAlert('Profile Updated', 'Your profile changes have been saved.', [{ text: 'OK', style: 'primary' }], 'success');
    } else {
      this.alertService.showAlert('Update Failed', res.error || 'Could not update profile', [{ text: 'OK', style: 'primary' }], 'danger');
    }
  }

  handleLogout(): void {
    this.alertService.showAlert(
      'Sign Out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Sign Out',
          style: 'destructive',
          onPress: () => {
            this.authService.logout();
            this.router.navigate(['/login']);
          },
        },
      ],
      'danger'
    );
  }

  confirmDeleteAccount(): void {
    this.alertService.showAlert(
      'Delete Account',
      'Permanently delete your account, companion customizations, and memory graphs? This action cannot be reversed.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Forever',
          style: 'destructive',
          onPress: async () => {
            await this.authService.deleteAccount();
            this.router.navigate(['/login']);
          },
        },
      ],
      'danger'
    );
  }
}
