import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AmourLogoComponent } from '../../components/amour-logo/amour-logo.component';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-signup-screen',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, AmourLogoComponent],
  template: `
    <div class="auth-screen">
      <div class="auth-card">
        <div class="logo-header">
          <app-amour-logo [size]="120" [showText]="false" [animated]="false"></app-amour-logo>
        </div>

        @if (!stepVerification) {
          <div class="title-header">
            <h1 class="auth-title">Create Account</h1>
            <p class="auth-subtitle">Experience intelligent companions with private memory.</p>
          </div>

          @if (error) {
            <div class="error-banner">{{ error }}</div>
          }

          <form (ngSubmit)="handleSignup()" class="form-container">
            <div class="input-group">
              <label class="input-label">Full Name</label>
              <input type="text" [(ngModel)]="name" name="name" class="auth-input" placeholder="Your name" required />
            </div>

            <div class="input-group">
              <label class="input-label">Email Address</label>
              <input type="email" [(ngModel)]="email" name="email" class="auth-input" placeholder="name@example.com" required />
            </div>

            <div class="input-group">
              <label class="input-label">Password</label>
              <input type="password" [(ngModel)]="password" name="password" class="auth-input" placeholder="Create a password" required />
            </div>

            <button type="submit" class="submit-btn" [disabled]="loading">
              {{ loading ? 'Creating account...' : 'Create Account' }}
            </button>
          </form>
        } @else {
          <!-- Step 2: Verification Code -->
          <div class="title-header">
            <h1 class="auth-title">Verify Email</h1>
            <p class="auth-subtitle">We sent a 6-digit verification code to <strong>{{ email }}</strong></p>
          </div>

          @if (error) {
            <div class="error-banner">{{ error }}</div>
          }

          <form (ngSubmit)="handleConfirmCode()" class="form-container">
            <div class="input-group">
              <label class="input-label">Verification Code</label>
              <input type="text" [(ngModel)]="code" name="code" class="auth-input code-input" placeholder="123456" maxlength="6" required />
            </div>

            <button type="submit" class="submit-btn" [disabled]="loading">
              {{ loading ? 'Verifying...' : 'Confirm & Continue' }}
            </button>

            <button type="button" class="resend-btn" (click)="handleResend()">
              Resend verification code
            </button>
          </form>
        }

        <div class="bottom-footer">
          <span>Already have an account? </span>
          <a routerLink="/login" class="login-link">Sign In</a>
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

    .resend-btn {
      background: none;
      border: none;
      color: #60A5FA;
      font-size: 0.85rem;
      font-weight: 500;
      cursor: pointer;
      text-align: center;
    }
    .resend-btn:hover {
      text-decoration: underline;
    }

    .bottom-footer {
      text-align: center;
      font-size: 0.85rem;
      color: #71717A;
    }

    .login-link {
      color: #FFFFFF;
      font-weight: 600;
      text-decoration: none;
    }
    .login-link:hover {
      text-decoration: underline;
    }
  `]
})
export class SignupScreenComponent {
  private authService = inject(AuthService);
  private router = inject(Router);

  name = '';
  email = '';
  password = '';
  code = '';
  loading = false;
  error: string | null = null;
  stepVerification = false;

  async handleSignup(): Promise<void> {
    this.error = null;
    if (!this.name.trim() || !this.email.trim() || !this.password.trim()) {
      this.error = 'Please fill out all fields.';
      return;
    }

    this.loading = true;
    const res = await this.authService.signUpWithEmail(this.name, this.email, this.password);
    this.loading = false;

    if (res.success) {
      if (res.requiresVerification) {
        this.stepVerification = true;
      } else {
        this.router.navigate(['/tabs']);
      }
    } else {
      this.error = res.error || 'Registration failed';
    }
  }

  async handleConfirmCode(): Promise<void> {
    this.error = null;
    if (!this.code.trim()) {
      this.error = 'Please enter your verification code.';
      return;
    }

    this.loading = true;
    const res = await this.authService.confirmEmail(this.email, this.code);
    this.loading = false;

    if (res.success) {
      this.router.navigate(['/tabs']);
    } else {
      this.error = res.error || 'Verification code failed';
    }
  }

  async handleResend(): Promise<void> {
    await this.authService.resendVerification(this.email);
  }
}
