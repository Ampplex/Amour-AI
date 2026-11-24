import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { AmourLogoComponent } from '../../components/amour-logo/amour-logo.component';
import { MemorySecurityModalComponent } from '../../components/memory-security-modal/memory-security-modal.component';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-tabs-shell',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    AmourLogoComponent,
    MemorySecurityModalComponent
  ],
  template: `
    <div class="app-layout">
      <!-- Desktop Instagram-Style Left Sidebar Navigation (screens >= 768px) -->
      <aside class="desktop-sidebar">
        <!-- Top Logo Lockup -->
        <div class="sidebar-header">
          <a routerLink="home" class="sidebar-logo-link" title="Amour AI">
            <app-amour-logo [size]="155" [showText]="true" [animated]="false"></app-amour-logo>
          </a>
        </div>

        <!-- Main Navigation Links -->
        <nav class="sidebar-nav">
          <!-- 1. Home -->
          <a routerLink="home" routerLinkActive="active" class="nav-item">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" class="nav-icon">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <polyline points="9 22 9 12 15 12 15 22" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="nav-label">Home</span>
          </a>

          <!-- 2. Personas -->
          <a routerLink="personas" routerLinkActive="active" class="nav-item">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" class="nav-icon">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <circle cx="9" cy="7" r="4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="nav-label">Personas</span>
          </a>

          <!-- 3. Chats -->
          <a routerLink="chats" routerLinkActive="active" class="nav-item">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" class="nav-icon">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="nav-label">Chats</span>
          </a>

          <!-- 4. Create Studio -->
          <a routerLink="create" routerLinkActive="active" class="nav-item">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" class="nav-icon">
              <rect x="3" y="3" width="18" height="18" rx="5" stroke="currentColor" stroke-width="2"/>
              <line x1="12" y1="8" x2="12" y2="16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              <line x1="8" y1="12" x2="16" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span class="nav-label">Create</span>
          </a>

          <!-- 5. Profile -->
          <a routerLink="profile" routerLinkActive="active" class="nav-item">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" class="nav-icon">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="nav-label">Profile</span>
          </a>
        </nav>

        <!-- Bottom Sidebar Actions (Memory Vault & Status) -->
        <div class="sidebar-footer">
          <button class="nav-item vault-btn" (click)="isSecurityModalOpen = true" title="Reeve Zero-Knowledge Memory Vault">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" class="nav-icon">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" stroke="#60A5FA" stroke-width="2" stroke-linecap="round"/>
              <circle cx="12" cy="11" r="2" stroke="#60A5FA" stroke-width="2"/>
              <path d="M12 13v3" stroke="#60A5FA" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span class="nav-label vault-label">Memory Vault</span>
          </button>

          @if (currentUser(); as user) {
            <a routerLink="profile" class="user-pill">
              @if (user.picture) {
                <img [src]="user.picture" [alt]="user.name" class="user-avatar" />
              } @else {
                <div class="user-fallback">{{ (user.name || 'U').charAt(0).toUpperCase() }}</div>
              }
              <div class="user-meta">
                <span class="user-name">{{ user.name || 'Amour User' }}</span>
                <span class="user-badge">Encrypted Session</span>
              </div>
            </a>
          }
        </div>
      </aside>

      <!-- Main Full Screen Content Viewport -->
      <main class="main-viewport">
        <router-outlet></router-outlet>
      </main>

      <!-- Mobile Bottom Tab Bar (< 768px) -->
      <nav class="bottom-tab-bar">
        <a routerLink="home" routerLinkActive="active" class="tab-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" class="tab-icon">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <polyline points="9 22 9 12 15 12 15 22" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="tab-label">Home</span>
        </a>

        <a routerLink="personas" routerLinkActive="active" class="tab-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" class="tab-icon">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="9" cy="7" r="4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="tab-label">Personas</span>
        </a>

        <a routerLink="chats" routerLinkActive="active" class="tab-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" class="tab-icon">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="tab-label">Chats</span>
        </a>

        <a routerLink="create" routerLinkActive="active" class="tab-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" class="tab-icon">
            <rect x="3" y="3" width="18" height="18" rx="5" stroke="currentColor" stroke-width="2"/>
            <line x1="12" y1="8" x2="12" y2="16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            <line x1="8" y1="12" x2="16" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <span class="tab-label">Create</span>
        </a>

        <a routerLink="profile" routerLinkActive="active" class="tab-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" class="tab-icon">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="tab-label">Profile</span>
        </a>
      </nav>
    </div>

    <!-- Zero-Knowledge Memory Security Modal -->
    <app-memory-security-modal
      [isOpen]="isSecurityModalOpen"
      (close)="isSecurityModalOpen = false"
    ></app-memory-security-modal>
  `,
  styles: [`
    :host {
      display: block;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
    }

    .app-layout {
      width: 100%;
      height: 100%;
      display: flex;
      background: #000000;
      color: #FFFFFF;
      overflow: hidden;
    }

    /* Desktop Left Sidebar (Clean Instagram Web style) */
    .desktop-sidebar {
      width: 245px;
      height: 100vh;
      background: #000000;
      border-right: 1px solid #262626;
      display: flex;
      flex-direction: column;
      padding: 24px 16px 20px;
      box-sizing: border-box;
      flex-shrink: 0;
      z-index: 100;
    }

    .sidebar-header {
      padding: 10px 12px 28px;
    }
    .sidebar-logo-link {
      display: inline-block;
      text-decoration: none;
    }

    .sidebar-nav {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 12px 14px;
      border-radius: 8px;
      color: #F5F5F5;
      text-decoration: none;
      font-family: var(--font-body);
      font-size: 15px;
      font-weight: 500;
      letter-spacing: -0.1px;
      transition: background 0.15s ease;
      cursor: pointer;
      border: none;
      background: transparent;
      width: 100%;
      text-align: left;
      box-sizing: border-box;
    }

    .nav-item:hover {
      background: rgba(255, 255, 255, 0.08);
      color: #FFFFFF;
    }

    .nav-item.active {
      font-weight: 700;
      color: #FFFFFF;
    }

    .nav-icon {
      flex-shrink: 0;
    }
    .nav-item.active .nav-icon {
      stroke-width: 2.5;
    }

    .sidebar-footer {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding-top: 14px;
      border-top: 1px solid #262626;
    }

    .vault-btn {
      color: #60A5FA;
    }
    .vault-btn:hover {
      background: rgba(96, 165, 250, 0.12);
      color: #93C5FD;
    }
    .vault-label {
      font-size: 14px;
      font-weight: 600;
    }

    .user-pill {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 12px;
      border-radius: 8px;
      text-decoration: none;
      color: inherit;
      transition: background 0.15s;
    }
    .user-pill:hover {
      background: rgba(255, 255, 255, 0.08);
    }
    .user-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      object-fit: cover;
      border: 1.5px solid #F43F5E;
    }
    .user-fallback {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: #F43F5E;
      color: #FFFFFF;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
    }
    .user-meta {
      display: flex;
      flex-direction: column;
      min-width: 0;
    }
    .user-name {
      font-family: var(--font-body);
      font-size: 14px;
      font-weight: 600;
      color: #FFFFFF;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .user-badge {
      font-size: 11px;
      color: #60A5FA;
    }

    /* Main Full-Screen Viewport */
    .main-viewport {
      flex: 1;
      height: 100vh;
      overflow-y: auto;
      overflow-x: hidden;
      background: #000000;
      position: relative;
    }

    /* Mobile Bottom Tab Bar (hidden on desktop) */
    .bottom-tab-bar {
      display: none;
    }

    /* Responsive: Mobile viewports (< 768px) */
    @media (max-width: 767px) {
      .app-layout {
        flex-direction: column;
      }
      .desktop-sidebar {
        display: none;
      }
      .main-viewport {
        height: calc(100vh - 56px);
      }
      .bottom-tab-bar {
        display: flex;
        height: 56px;
        background: #000000;
        border-top: 1px solid #262626;
        align-items: center;
        justify-content: space-around;
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 100;
      }
      .tab-item {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-decoration: none;
        color: #A8A8A8;
        padding: 4px 0;
        transition: color 0.15s ease;
      }
      .tab-label {
        font-family: var(--font-body);
        font-size: 10px;
        letter-spacing: 0.2px;
      }
      .tab-item.active {
        color: #FFFFFF;
      }
    }

    /* Medium screens (768px - 1160px): Instagram-style slim icon sidebar */
    @media (min-width: 768px) and (max-width: 1160px) {
      .desktop-sidebar {
        width: 72px;
        padding: 24px 8px;
        align-items: center;
      }
      .sidebar-header {
        padding: 8px 0 24px;
      }
      .nav-label, .vault-label, .user-meta {
        display: none;
      }
      .nav-item {
        justify-content: center;
        padding: 12px;
      }
      .user-pill {
        padding: 6px;
        justify-content: center;
      }
    }
  `]
})
export class TabsShellComponent {
  private authService = inject(AuthService);
  readonly currentUser = this.authService.currentUser;
  isSecurityModalOpen = false;
}
