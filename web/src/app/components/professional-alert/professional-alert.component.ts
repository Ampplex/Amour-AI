import { Component, inject, ElementRef, viewChild, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AlertService, AlertButton } from '../../services/alert.service';

@Component({
  selector: 'app-professional-alert',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (alertService.isVisible() && alertService.alertConfig(); as config) {
      <div class="alert-overlay" (click)="onBackdropClick($event)">
        <div class="alert-card" role="dialog" aria-modal="true" [attr.aria-labelledby]="'alert-title'">
          <!-- Icon Header indicator based on alert type -->
          <div class="alert-indicator" [attr.data-type]="config.type || 'info'">
            @switch (config.type) {
              @case ('danger') {
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="#EF4444" stroke-width="2" stroke-linecap="round"/>
                </svg>
              }
              @case ('success') {
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" stroke="#10B981" stroke-width="2" stroke-linecap="round"/>
                </svg>
              }
              @case ('warning') {
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" stroke="#F59E0B" stroke-width="2" stroke-linecap="round"/>
                </svg>
              }
              @default {
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="#3B82F6" stroke-width="2" stroke-linecap="round"/>
                </svg>
              }
            }
          </div>

          <h3 id="alert-title" class="alert-title">{{ config.title }}</h3>
          
          @if (config.message) {
            <p class="alert-message">{{ config.message }}</p>
          }

          <div class="alert-actions">
            @for (btn of config.buttons; track $index) {
              <button
                type="button"
                class="alert-btn"
                [attr.data-style]="btn.style || 'default'"
                (click)="onButtonClick(btn)"
              >
                {{ btn.text }}
              </button>
            }
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .alert-overlay {
      position: fixed;
      inset: 0;
      z-index: 9999;
      background: rgba(0, 0, 0, 0.78);
      backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      animation: fadeIn 0.15s ease-out;
    }

    .alert-card {
      background: #202022;
      border: 1px solid #2E2E32;
      border-radius: 16px;
      max-width: 360px;
      width: 100%;
      padding: 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
      animation: popIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .alert-indicator {
      width: 48px;
      height: 48px;
      border-radius: 50%;
      background: #28282A;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
      border: 1px solid #333338;
    }

    .alert-title {
      font-family: var(--font-brand);
      font-size: 1.25rem;
      color: #FFFFFF;
      margin-bottom: 8px;
      letter-spacing: 0.2px;
    }

    .alert-message {
      font-size: 0.92rem;
      color: #A1A1AA;
      line-height: 1.5;
      margin-bottom: 22px;
    }

    .alert-actions {
      display: flex;
      width: 100%;
      gap: 10px;
    }

    .alert-btn {
      flex: 1;
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 0.92rem;
      font-weight: 600;
      transition: all 0.15s ease;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .alert-btn[data-style="primary"] {
      background: #FFFFFF;
      color: #000000;
    }
    .alert-btn[data-style="primary"]:hover {
      background: #E4E4E7;
    }

    .alert-btn[data-style="destructive"] {
      background: rgba(239, 68, 68, 0.15);
      color: #EF4444;
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .alert-btn[data-style="destructive"]:hover {
      background: rgba(239, 68, 68, 0.25);
    }

    .alert-btn[data-style="cancel"],
    .alert-btn[data-style="default"] {
      background: #28282A;
      color: #D4D4D8;
      border: 1px solid #38383D;
    }
    .alert-btn[data-style="cancel"]:hover,
    .alert-btn[data-style="default"]:hover {
      background: #323236;
      color: #FFFFFF;
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
export class ProfessionalAlertComponent {
  readonly alertService = inject(AlertService);

  onBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.alertService.hideAlert();
    }
  }

  onButtonClick(btn: AlertButton): void {
    this.alertService.handleButtonClick(btn);
  }
}
