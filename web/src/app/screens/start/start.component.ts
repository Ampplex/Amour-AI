import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { AmourLogoComponent } from '../../components/amour-logo/amour-logo.component';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-start-screen',
  standalone: true,
  imports: [CommonModule, AmourLogoComponent],
  template: `
    <div class="start-container" (click)="navigateNext()">
      <div class="logo-box">
        <app-amour-logo [size]="300" [showText]="true" [animated]="true"></app-amour-logo>
        <p class="tagline">Zero-Knowledge Encrypted Companions</p>
      </div>
    </div>
  `,
  styles: [`
    .start-container {
      width: 100%;
      height: 100vh;
      background: #171717;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      user-select: none;
    }
    .logo-box {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      padding: 24px;
    }
    .tagline {
      font-size: 0.88rem;
      color: #71717A;
      margin-top: 18px;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      font-weight: 500;
      animation: pulse 2s infinite ease-in-out;
    }
    @keyframes pulse {
      0%, 100% { opacity: 0.4; }
      50% { opacity: 0.9; }
    }
  `]
})
export class StartScreenComponent implements OnInit {
  private router = inject(Router);
  private authService = inject(AuthService);

  ngOnInit(): void {
    setTimeout(() => {
      this.navigateNext();
    }, 1800);
  }

  navigateNext(): void {
    if (this.authService.isLoggedIn()) {
      this.router.navigate(['/tabs']);
    } else {
      this.router.navigate(['/login']);
    }
  }
}
