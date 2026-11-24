import { Injectable, inject, signal } from '@angular/core';
import { API_CONFIG } from './config';
import { KeyService } from './key.service';
import { PersonaItem } from './persona.service';

export interface ConversationLastMessage {
  id: string;
  sender: 'user' | 'bot' | string;
  text: string;
  created_at: string;
}

export interface ConversationItem {
  persona: PersonaItem;
  last_message: ConversationLastMessage;
}

@Injectable({
  providedIn: 'root'
})
export class ConversationService {
  private keyService = inject(KeyService);
  readonly conversations = signal<ConversationItem[]>([]);
  readonly isLoading = signal<boolean>(false);

  async fetchUserConversations(userId: string, token?: string): Promise<ConversationItem[]> {
    if (!userId) return [];
    this.isLoading.set(true);

    const userKey = this.keyService.getOrCreateUserKey();
    const url = `${API_CONFIG.baseUrl}/memory/conversations/?user_id=${encodeURIComponent(userId)}&user_key=${encodeURIComponent(userKey)}`;
    try {
      const res = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      if (res.ok) {
        const data = await res.json();
        const list: ConversationItem[] = data.conversations || [];
        this.conversations.set(list);
        this.isLoading.set(false);
        return list;
      } else {
        console.warn(`[ConversationService] HTTP ${res.status}`);
      }
    } catch (err) {
      console.error('[ConversationService] network error:', err);
    }

    this.isLoading.set(false);
    return [];
  }
}
