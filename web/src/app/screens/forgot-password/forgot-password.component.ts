import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AmourLogoComponent } from '../../components/amour-logo/amour-logo.component';
import { AuthService } from '../../services/auth.service';
import { AlertService } from '../../services/alert.service';

@Component({
  selector: 'app-forgot-password-screen',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, AmourLogoComponent],
  template: `
    <div class="auth-screen">
      <div class="auth-card">
        <div class="logo-header">
          <app-amour-logo [size]="120" [showText]="false" [animated]="false"></app-amour-logo>
        </div>

        @if (!codeSent) {
          <div class="title-header">
            <h1 class="auth-title">Reset Password</h1>
            <p class="auth-subtitle">Enter your registered email and we'll send a password recovery code.</p>
          </div>

          @if (error) {
            <div class="error-banner">{{ error }}</div>
          }

          <form (ngSubmit)="handleSendCode()" class="form-container">
            <div class="input-group">
              <label class="input-label">Email Address</label>
              <input type="email" [(ngModel)]="email" name="email" class="auth-input" placeholder="name@example.com" required />
            </div>

            <button type="submit" class="submit-btn" [disabled]="loading">
              {{ loading ? 'Sending code...' : 'Send Recovery Code' }}
            </button>
          </form>
        } @else {
          <div class="title-header">
            <h1 class="auth-title">Set New Password</h1>
            <p class="auth-subtitle">Enter the 6-digit code sent to {{ email }} and your new password.</p>
          </div>

          @if (error) {
            <div class="error-banner">{{ error }}</div>
          }

          <form (ngSubmit)="handleResetPassword()" class="form-container">
            <div class="input-group">
              <label class="input-label">Verification Code</label>
              <input type="text" [(ngModel)]="code" name="code" class="auth-input code-input" placeholder="123456" maxlength="6" required />
            </div>

            <div class="input-group">
              <label class="input-label">New Password</label>
              <input type="password" [(ngModel)]="newPassword" name="newPassword" class="auth-input" placeholder="Enter new password" required />
            </div>

            <button type="submit" class="submit-btn" [disabled]="loading">
              {{ loading ? 'Updating password...' : 'Reset Password' }}
            </button>
          </form>
        }

        <div class="bottom-footer">
          <a routerLink="/login" class="back-link">Return to Sign In</a>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .auth-screen {
      width: 100%;
      height: 100vh;
      background: #171717;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }

    .auth-card {
      background: #202022;
      border: 1px solid #2E2E32;
      border-radius: 20px;
      max-width: 400px;
      width: 100%;
      padding: 32px 28px;
      display: flex;
      flex-direction: column;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
    }

    .logo-header {
      display: flex;
      justify-content: center;
      margin-bottom: 20px;
    }

    .title-header {
      text-align: center;
      margin-bottom: 24px;
    }

    .auth-title {
      font-family: var(--font-brand);
      font-size: 1.6rem;
      color: #FFFFFF;
      margin-bottom: 6px;
    }

    .auth-subtitle {
      font-size: 0.88rem;
      color: #A1A1AA;
      line-height: 1.45;
    }

    .error-banner {
      background: rgba(239, 68, 68, 0.12);
      border: 1px solid rgba(239, 68, 68, 0.3);
      border-radius: 10px;
      padding: 10px 14px;
      color: #EF4444;
      font-size: 0.85rem;
      margin-bottom: 16px;
    }

    .form-container {
      display: flex;
      flex-direction: column;
      gap: 16px;
      margin-bottom: 24px;
    }

    .input-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .input-label {
      font-size: 0.8rem;
      font-weight: 600;
      color: #D4D4D8;
    }

    .auth-input {
      width: 100%;
      background: #28282C;
      border: 1px solid #323238;
      border-radius: 12px;
      padding: 12px 14px;
      color: #FFFFFF;
      font-size: 0.92rem;
      outline: none;
      transition: border-color 0.15s;
    }
    .auth-input:focus {
      border-color: #52525B;
    }

    .code-input {
      text-align: center;
      letter-spacing: 4px;
      font-size: 1.2rem;
      font-weight: 700;
    }

    .submit-btn {
      width: 100%;
      padding: 13px;
      border-radius: 12px;
      background: #FFFFFF;
      color: #000000;
      font-weight: 700;
      font-size: 0.95rem;
      transition: all 0.15s;
    }
    .submit-btn:disabled {
      opacity: 0.5;
    }
    .submit-btn:not(:disabled):hover {
      background: #E4E4E7;
    }

    .bottom-footer {
      text-align: center;
      font-size: 0.85rem;
    }

    .back-link {
      color: #A1A1AA;
      text-decoration: none;
    }
    .back-link:hover {
      color: #FFFFFF;
      text-decoration: underline;
    }
  `]
})
export class ForgotPasswordScreenComponent {
  private authService = inject(AuthService);
  private alertService = inject(AlertService);
  private router = inject(Router);

  email = '';
  code = '';
  newPassword = '';
  codeSent = false;
  loading = false;
  error: string | null = null;

  async handleSendCode(): Promise<void> {
    this.error = null;
    if (!this.email.trim()) {
      this.error = 'Please enter your email address.';
      return;
    }

    this.loading = true;
    const res = await this.authService.forgotPassword(this.email);
    this.loading = false;

    if (res.success) {
      this.codeSent = true;
    } else {
      this.error = res.error || 'Failed to send recovery code';
    }
  }

  async handleResetPassword(): Promise<void> {
    this.error = null;
    if (!this.code.trim() || !this.newPassword.trim()) {
      this.error = 'Please enter both the code and your new password.';
      return;
    }

    this.loading = true;
    const res = await this.authService.resetPassword(this.email, this.code, this.newPassword);
    this.loading = false;

    if (res.success) {
      this.alertService.showAlert('Password Reset Successful', 'Your password has been updated. You can now sign in with your new credentials.', [{ text: 'Sign In', style: 'primary', onPress: () => this.router.navigate(['/login']) }], 'success');
    } else {
      this.error = res.error || 'Password reset failed';
    }
  }
}
