import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AmourLogoComponent } from '../../components/amour-logo/amour-logo.component';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login-screen',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, AmourLogoComponent],
  template: `
    <div class="auth-screen">
      <div class="auth-card">
        <!-- Logo Emblem -->
        <div class="logo-header">
          <app-amour-logo [size]="130" [showText]="false" [animated]="false"></app-amour-logo>
        </div>

        <div class="title-header">
          <h1 class="auth-title">Welcome Back</h1>
          <p class="auth-subtitle">Sign in to continue your private, intelligent sessions.</p>
        </div>

        @if (error) {
          <div class="error-banner">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="#EF4444" stroke-width="2"/>
              <path d="M12 8v4m0 4h.01" stroke="#EF4444" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span>{{ error }}</span>
          </div>
        }

        <form (ngSubmit)="handleLogin()" class="form-container">
          <div class="input-group">
            <label class="input-label">Email Address</label>
            <input
              type="email"
              [(ngModel)]="email"
              name="email"
              class="auth-input"
              placeholder="name@example.com"
              required
            />
          </div>

          <div class="input-group">
            <div class="label-row">
              <label class="input-label">Password</label>
              <a routerLink="/forgot-password" class="forgot-link">Forgot?</a>
            </div>
            <div class="password-wrapper">
              <input
                [type]="showPassword ? 'text' : 'password'"
                [(ngModel)]="password"
                name="password"
                class="auth-input"
                placeholder="Enter your password"
                required
              />
              <button
                type="button"
                class="eye-btn"
                (click)="showPassword = !showPassword"
                [attr.aria-label]="showPassword ? 'Hide password' : 'Show password'"
              >
                @if (showPassword) {
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24M1 1l22 22" stroke="#71717A" stroke-width="2" stroke-linecap="round"/>
                  </svg>
                } @else {
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke="#71717A" stroke-width="2"/>
                    <circle cx="12" cy="12" r="3" stroke="#71717A" stroke-width="2"/>
                  </svg>
                }
              </button>
            </div>
          </div>

          <button type="submit" class="submit-btn" [disabled]="loading">
            {{ loading ? 'Signing in...' : 'Sign In' }}
          </button>
        </form>

        <div class="divider">
          <span>or continue with</span>
        </div>

        <button type="button" class="google-btn" (click)="handleGoogleMock()">
          <svg width="18" height="18" viewBox="0 0 24 24">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
          </svg>
          Google
        </button>

        <!-- Dev Mode Demo Access -->
        <button type="button" class="dev-btn" (click)="handleDevSession()">
          Enter as Demo User
        </button>

        <div class="bottom-footer">
          <span>Don't have an account? </span>
          <a routerLink="/signup" class="signup-link">Create Account</a>
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
      display: flex;
      align-items: center;
      gap: 8px;
      color: #EF4444;
      font-size: 0.85rem;
      margin-bottom: 16px;
    }

    .form-container {
      display: flex;
      flex-direction: column;
      gap: 16px;
      margin-bottom: 20px;
    }

    .input-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .label-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .input-label {
      font-size: 0.8rem;
      font-weight: 600;
      color: #D4D4D8;
    }

    .forgot-link {
      font-size: 0.78rem;
      color: #60A5FA;
      text-decoration: none;
    }
    .forgot-link:hover {
      text-decoration: underline;
    }

    .password-wrapper {
      position: relative;
      display: flex;
      align-items: center;
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
    .password-wrapper .auth-input {
      padding-right: 42px;
    }
    .auth-input:focus {
      border-color: #52525B;
    }

    .eye-btn {
      position: absolute;
      right: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
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

    .divider {
      display: flex;
      align-items: center;
      text-align: center;
      margin-bottom: 16px;
      color: #71717A;
      font-size: 0.78rem;
    }
    .divider::before, .divider::after {
      content: '';
      flex: 1;
      border-bottom: 1px solid #2E2E34;
    }
    .divider span {
      padding: 0 10px;
    }

    .google-btn {
      width: 100%;
      padding: 12px;
      border-radius: 12px;
      background: #28282C;
      border: 1px solid #38383E;
      color: #FFFFFF;
      font-weight: 600;
      font-size: 0.9rem;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      margin-bottom: 10px;
      transition: background 0.15s;
    }
    .google-btn:hover {
      background: #323238;
    }

    .dev-btn {
      width: 100%;
      padding: 10px;
      border-radius: 12px;
      background: rgba(59, 130, 246, 0.12);
      border: 1px dashed rgba(59, 130, 246, 0.35);
      color: #60A5FA;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 22px;
      transition: background 0.15s;
    }
    .dev-btn:hover {
      background: rgba(59, 130, 246, 0.2);
    }

    .bottom-footer {
      text-align: center;
      font-size: 0.85rem;
      color: #71717A;
    }

    .signup-link {
      color: #FFFFFF;
      font-weight: 600;
      text-decoration: none;
    }
    .signup-link:hover {
      text-decoration: underline;
    }
  `]
})
export class LoginScreenComponent implements OnInit {
  private authService = inject(AuthService);
  private router = inject(Router);

  email = '';
  password = '';
  showPassword = false;
  loading = false;
  error: string | null = null;

  ngOnInit(): void {
    if (this.authService.isLoggedIn()) {
      this.router.navigate(['/tabs']);
    }
  }

  async handleLogin(): Promise<void> {
    this.error = null;
    if (!this.email.trim() || !this.password.trim()) {
      this.error = 'Please enter both email and password.';
      return;
    }

    this.loading = true;
    const res = await this.authService.loginWithEmail(this.email, this.password);
    this.loading = false;

    if (res.success) {
      this.router.navigate(['/tabs']);
    } else {
      this.error = res.error || 'Login failed';
    }
  }

  handleGoogleMock(): void {
    // Authenticate demo/google session
    this.authService.devSessionLogin('google.user@amour.ai', 'Google User');
    this.router.navigate(['/tabs']);
  }

  handleDevSession(): void {
    this.authService.devSessionLogin();
    this.router.navigate(['/tabs']);
  }
}
