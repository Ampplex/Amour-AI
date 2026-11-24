import { Injectable, signal, computed } from '@angular/core';
import { API_CONFIG } from './config';

export interface GoogleUser {
  id: string;
  email: string;
  name: string;
  username?: string;
  given_name?: string;
  family_name?: string;
  picture?: string;
  verified_email?: boolean;
  namespace?: string;
  token?: string;
  reply_length?: 'default' | 'short' | 'long';
}

const LOCAL_SESSION_KEY = '@amour_user_session';
const REPLY_LENGTH_KEY = '@amour_reply_length';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  readonly currentUser = signal<GoogleUser | null>(null);
  readonly isLoading = signal<boolean>(false);
  readonly error = signal<string | null>(null);
  readonly isAuthReady = signal<boolean>(false);

  readonly isLoggedIn = computed(() => !!this.currentUser());

  constructor() {
    this.restoreSession();
  }

  private async tryServerFetch(path: string, options: RequestInit = {}): Promise<Response | null> {
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 10000);
        const res = await fetch(`${base}${path}`, { ...options, signal: controller.signal });
        clearTimeout(timer);
        if (res.ok) return res;
      } catch {
        // try next candidate
      }
    }
    return null;
  }

  private restoreSession(): void {
    try {
      const stored = localStorage.getItem(LOCAL_SESSION_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed && parsed.id) {
          this.currentUser.set(parsed);
          this.refreshProfile();
        }
      }
    } catch (e) {
      console.warn('[AuthService] Error reading local session:', e);
    } finally {
      this.isAuthReady.set(true);
    }
  }

  async loginWithEmail(
    email: string,
    password: string
  ): Promise<{ success: boolean; error?: string; unverified?: boolean }> {
    this.isLoading.set(true);
    this.error.set(null);
    let lastError = 'Unable to connect to server. Please check your network connection.';
    let isUnverified = false;

    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
        });

        const data = await res.json();
        if (res.ok && data.user) {
          const bUser = data.user;
          const authedUser: GoogleUser = {
            id: bUser.id,
            name: bUser.name || 'User',
            email: bUser.email,
            picture: bUser.picture || undefined,
            given_name: bUser.given_name || undefined,
            family_name: bUser.family_name || undefined,
            verified_email: bUser.verified_email,
            namespace: bUser.namespace || bUser.id,
            username: bUser.username,
            token: data.access_token,
            reply_length: bUser.reply_length || 'default',
          };
          this.setUser(authedUser);
          this.isLoading.set(false);
          return { success: true };
        } else {
          lastError = data.error || data.detail || 'Login failed';
          if (data.unverified) {
            isUnverified = true;
          }
          break;
        }
      } catch (err: any) {
        lastError = err?.message || 'Network error';
      }
    }

    this.isLoading.set(false);
    this.error.set(lastError);
    return { success: false, error: lastError, unverified: isUnverified };
  }

  async signUpWithEmail(
    name: string,
    email: string,
    password: string
  ): Promise<{ success: boolean; requiresVerification?: boolean; error?: string; message?: string }> {
    this.isLoading.set(true);
    this.error.set(null);
    let lastError = 'Unable to connect to server.';

    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/auth/signup/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: name.trim(), email: email.trim().toLowerCase(), password }),
        });

        const data = await res.json();
        if (res.ok) {
          this.isLoading.set(false);
          return {
            success: true,
            requiresVerification: data.requires_verification ?? true,
            message: data.message,
          };
        } else {
          lastError = data.error || (data.email ? data.email[0] : null) || 'Registration failed';
          break;
        }
      } catch (err: any) {
        lastError = err?.message || 'Network error';
      }
    }

    this.isLoading.set(false);
    this.error.set(lastError);
    return { success: false, error: lastError };
  }

  async confirmEmail(
    email: string,
    code: string
  ): Promise<{ success: boolean; error?: string; user?: GoogleUser }> {
    this.isLoading.set(true);
    this.error.set(null);
    let lastError = 'Unable to connect to server.';

    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/auth/confirm-email/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.trim().toLowerCase(), code: code.trim() }),
        });

        const data = await res.json();
        if (res.ok && data.user) {
          const bUser = data.user;
          const authedUser: GoogleUser = {
            id: bUser.id,
            name: bUser.name || 'User',
            email: bUser.email,
            picture: bUser.picture || undefined,
            given_name: bUser.given_name || undefined,
            family_name: bUser.family_name || undefined,
            verified_email: bUser.verified_email,
            namespace: bUser.namespace || bUser.id,
            username: bUser.username,
            token: data.access_token,
          };
          this.setUser(authedUser);
          this.isLoading.set(false);
          return { success: true, user: authedUser };
        } else {
          lastError = data.error || 'Confirmation failed';
          break;
        }
      } catch (err: any) {
        lastError = err?.message || 'Network error';
      }
    }

    this.isLoading.set(false);
    this.error.set(lastError);
    return { success: false, error: lastError };
  }

  async resendVerification(email: string): Promise<{ success: boolean; error?: string; message?: string }> {
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/auth/resend-verification/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.trim().toLowerCase() }),
        });
        const data = await res.json();
        if (res.ok) {
          return { success: true, message: data.message };
        }
      } catch {}
    }
    return { success: false, error: 'Could not resend verification email' };
  }

  async forgotPassword(email: string): Promise<{ success: boolean; error?: string; message?: string }> {
    this.isLoading.set(true);
    let lastError = 'Failed to send reset email';
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/auth/forgot-password/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.trim().toLowerCase() }),
        });
        const data = await res.json();
        if (res.ok) {
          this.isLoading.set(false);
          return { success: true, message: data.message };
        } else {
          lastError = data.error || lastError;
          break;
        }
      } catch (err: any) {
        lastError = err?.message || 'Network error';
      }
    }
    this.isLoading.set(false);
    return { success: false, error: lastError };
  }

  async resetPassword(
    email: string,
    code: string,
    newPassword: string
  ): Promise<{ success: boolean; error?: string; message?: string }> {
    this.isLoading.set(true);
    let lastError = 'Password reset failed';
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/auth/reset-password/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: email.trim().toLowerCase(),
            code: code.trim(),
            new_password: newPassword,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          this.isLoading.set(false);
          return { success: true, message: data.message };
        } else {
          lastError = data.error || lastError;
          break;
        }
      } catch (err: any) {
        lastError = err?.message || 'Network error';
      }
    }
    this.isLoading.set(false);
    return { success: false, error: lastError };
  }

  devSessionLogin(email?: string, name?: string): void {
    const devUser: GoogleUser = {
      id: 'usr_dev_' + Date.now().toString(36),
      email: email || 'alex@amour.ai',
      name: name || 'Alex Vance',
      given_name: 'Alex',
      picture: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=400&q=80',
      verified_email: true,
      username: 'alex_amour',
      reply_length: 'default',
    };
    this.setUser(devUser);
  }

  setUser(user: GoogleUser | null): void {
    this.currentUser.set(user);
    if (user) {
      try {
        localStorage.setItem(LOCAL_SESSION_KEY, JSON.stringify(user));
      } catch {}
    } else {
      try {
        localStorage.removeItem(LOCAL_SESSION_KEY);
      } catch {}
    }
  }

  async updateProfile(data: {
    username?: string;
    name?: string;
    picture?: string;
    reply_length?: 'default' | 'short' | 'long';
  }): Promise<{ success: boolean; error?: string; user?: GoogleUser }> {
    const user = this.currentUser();
    if (!user) return { success: false, error: 'No authenticated user' };

    if (data.reply_length) {
      this.setReplyLengthPreference(data.reply_length);
    }

    let lastError = 'Network request failed';
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/auth/profile/`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            ...(user.token ? { Authorization: `Bearer ${user.token}` } : {}),
          },
          body: JSON.stringify({
            user_id: user.id,
            username: data.username,
            name: data.name,
            picture: data.picture,
            reply_length: data.reply_length,
          }),
        });

        const resData = await res.json();
        if (res.ok) {
          const resolvedName = resData.name ?? user.name;
          const updatedUser: GoogleUser = {
            ...user,
            username: resData.username ?? user.username,
            name: resolvedName,
            given_name: (resolvedName ? resolvedName.trim().split(' ')[0] : '') || resData.given_name || user.given_name,
            picture: resData.picture ?? user.picture,
            reply_length: resData.reply_length ?? data.reply_length ?? user.reply_length,
          };
          this.setUser(updatedUser);
          return { success: true, user: updatedUser };
        } else {
          return {
            success: false,
            error: resData.error || resData.detail || 'Failed to update profile',
          };
        }
      } catch (err: any) {
        lastError = err?.message || 'Connection error';
      }
    }
    return { success: false, error: lastError };
  }

  async uploadProfilePicture(options: { base64?: string }): Promise<{ success: boolean; url?: string; error?: string }> {
    const user = this.currentUser();
    if (!user) return { success: false, error: 'No authenticated user' };
    if (!options.base64) return { success: false, error: 'No image data provided' };

    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/auth/profile/upload-picture/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(user.token ? { Authorization: `Bearer ${user.token}` } : {}),
          },
          body: JSON.stringify({
            user_id: user.id,
            image_base64: options.base64,
          }),
        });

        const resData = await res.json();
        if (res.ok && resData.url) {
          const updatedUser: GoogleUser = {
            ...user,
            picture: resData.url,
            username: resData.user?.username ?? user.username,
          };
          this.setUser(updatedUser);
          return { success: true, url: resData.url };
        }
      } catch {}
    }
    return { success: false, error: 'Failed to upload picture' };
  }

  async refreshProfile(): Promise<void> {
    const user = this.currentUser();
    if (!user) return;
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/auth/profile/?user_id=${encodeURIComponent(user.id)}`);
        if (res.ok) {
          const profile = await res.json();
          const updated: GoogleUser = {
            ...user,
            username: profile.username || user.username,
            name: profile.name || user.name,
            picture: profile.picture || user.picture,
            reply_length: profile.reply_length || user.reply_length || 'default',
          };
          this.setUser(updated);
          break;
        }
      } catch {}
    }
  }

  getReplyLengthPreference(): 'default' | 'short' | 'long' {
    const user = this.currentUser();
    if (user?.reply_length) return user.reply_length;
    try {
      const val = localStorage.getItem(REPLY_LENGTH_KEY);
      if (val === 'short' || val === 'long' || val === 'default') return val;
    } catch {}
    return 'default';
  }

  setReplyLengthPreference(length: 'default' | 'short' | 'long'): void {
    try {
      localStorage.setItem(REPLY_LENGTH_KEY, length);
    } catch {}
    const user = this.currentUser();
    if (user) {
      this.currentUser.set({ ...user, reply_length: length });
    }
  }

  async deleteAccount(): Promise<{ success: boolean; error?: string }> {
    const user = this.currentUser();
    if (!user) return { success: false, error: 'No user to delete' };

    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/auth/delete-account/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(user.token ? { Authorization: `Bearer ${user.token}` } : {}),
            'X-User-Id': user.id,
          },
          body: JSON.stringify({ user_id: user.id }),
        });
        if (res.ok) {
          this.logout();
          return { success: true };
        }
      } catch {}
    }
    return { success: false, error: 'Could not delete account' };
  }

  logout(): void {
    this.setUser(null);
  }
}
