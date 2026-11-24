import { Injectable, inject, signal } from '@angular/core';
import { API_CONFIG } from './config';
import { KeyService } from './key.service';
import { AuthService } from './auth.service';

export interface ChatResponseMetadata {
  narrative_decision: string | null;
  story_state: {
    available: boolean;
    schema_version: number | null;
    revision: number | null;
    updated: boolean;
  };
}

export interface ChatHistoryItem {
  id: string;
  client_message_id?: string;
  user_id: string;
  persona_id: string;
  namespace: string;
  sender: 'user' | 'bot';
  text: string;
  conflict_stage?: number;
  conflict_level?: number;
  response_metadata?: any;
  variants?: string[];
  active_variant_index?: number;
  created_at: string;
}

export interface ChatHistoryResponse {
  results: ChatHistoryItem[];
  count: number;
  page: number;
  page_size: number;
  has_more: boolean;
  conflict_stage?: number;
  conflict_level?: number;
}

export interface SendMessagePayload {
  client_message_id?: string;
  edit_message_id?: string;
  regenerate_bot_message_id?: string;
  message: string;
  persona_id: string;
  persona_name: string;
  greeting?: string;
  memory_prompt?: string;
  client_time: string;
  client_timezone: string;
  user_id?: string;
  user_name?: string;
  reply_length?: 'default' | 'short' | 'long';
  is_autonomous_continue?: boolean;
}

export interface SendMessageResponse {
  id: string;
  client_message_id?: string;
  user_message_id?: string;
  reply: string;
  conflict_stage?: number;
  conflict_level?: number;
  context?: string;
  namespace: string;
  persona_id: string;
  user_id: string;
  metadata?: ChatResponseMetadata;
  variants?: string[];
  active_variant_index?: number;
}

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  private keyService = inject(KeyService);
  private authService = inject(AuthService);

  readonly messages = signal<ChatHistoryItem[]>([]);
  readonly isSending = signal<boolean>(false);
  readonly isLoadingHistory = signal<boolean>(false);

  private generateUUID(): string {
    if (typeof window !== 'undefined' && window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return 'msg-' + Date.now().toString(36) + '-' + Math.random().toString(36).substring(2, 9);
  }

  async fetchChatHistory(
    personaId: string,
    userId: string,
    page: number = 1,
    pageSize: number = 30,
    token?: string
  ): Promise<ChatHistoryResponse | null> {
    this.isLoadingHistory.set(true);
    const userKey = this.keyService.getOrCreateUserKey();
    const query = `persona_id=${encodeURIComponent(personaId)}&user_id=${encodeURIComponent(userId)}&page=${page}&page_size=${pageSize}&user_key=${encodeURIComponent(userKey)}`;

    const url = `${API_CONFIG.baseUrl}/memory/chat/?${query}`;
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 20000);
      const res = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (res.ok) {
        const data: ChatHistoryResponse = await res.json();
        this.isLoadingHistory.set(false);
        return data;
      } else {
        console.warn(`[ChatService] fetchChatHistory HTTP ${res.status}`);
      }
    } catch (err) {
      console.error('[ChatService] fetchChatHistory network error:', err);
    }

    this.isLoadingHistory.set(false);
    return null;
  }

  async sendChatMessage(
    payload: SendMessagePayload,
    token?: string
  ): Promise<SendMessageResponse | null> {
    this.isSending.set(true);
    const clientMessageId = payload.client_message_id || this.generateUUID();
    const userKey = this.keyService.getOrCreateUserKey();
    const replyLength = payload.reply_length || this.authService.getReplyLengthPreference();
    const url = `${API_CONFIG.baseUrl}/memory/chat/?user_key=${encodeURIComponent(userKey)}`;

    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 60000);
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          ...payload,
          reply_length: replyLength,
          client_message_id: clientMessageId,
          user_key: userKey,
        }),
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (res.ok) {
        const data: SendMessageResponse = await res.json();
        this.isSending.set(false);
        return data;
      } else {
        const errText = await res.text().catch(() => '');
        console.error(`[ChatService] sendChatMessage HTTP ${res.status}:`, errText);
      }
    } catch (err) {
      console.error('[ChatService] sendChatMessage network/CORS error:', err);
    }

    this.isSending.set(false);
    return null;
  }

  async deleteChatMessage(
    messageId: string,
    userId: string,
    token?: string
  ): Promise<{ success: boolean; deleted_id?: string; error?: string }> {
    const userKey = this.keyService.getOrCreateUserKey();
    const query = `message_id=${encodeURIComponent(messageId)}&user_id=${encodeURIComponent(userId)}&user_key=${encodeURIComponent(userKey)}`;
    const url = `${API_CONFIG.baseUrl}/memory/chat/?${query}`;

    try {
      const res = await fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message_id: messageId,
          user_id: userId,
          user_key: userKey,
        }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.error('[ChatService] deleteChatMessage error:', err);
    }
    return { success: false, error: 'Could not delete message' };
  }

  async switchChatMessageVariant(
    messageId: string,
    variantIndex: number,
    userId: string,
    token?: string
  ): Promise<{
    success: boolean;
    message_id?: string;
    text?: string;
    active_variant_index?: number;
    variants?: string[];
    error?: string;
  }> {
    const userKey = this.keyService.getOrCreateUserKey();
    const url = `${API_CONFIG.baseUrl}/memory/chat/?user_key=${encodeURIComponent(userKey)}`;

    try {
      const res = await fetch(url, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message_id: messageId,
          variant_index: variantIndex,
          user_id: userId,
          user_key: userKey,
        }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.error('[ChatService] switchChatMessageVariant error:', err);
    }
    return { success: false, error: 'Failed to switch variant' };
  }

  async editBotChatMessage(
    messageId: string,
    newText: string,
    userId: string,
    token?: string
  ): Promise<{
    success: boolean;
    message_id?: string;
    text?: string;
    variants?: string[];
    error?: string;
  }> {
    const userKey = this.keyService.getOrCreateUserKey();
    const url = `${API_CONFIG.baseUrl}/memory/chat/?user_key=${encodeURIComponent(userKey)}`;

    try {
      const res = await fetch(url, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message_id: messageId,
          text: newText,
          user_id: userId,
          user_key: userKey,
        }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.error('[ChatService] editBotChatMessage error:', err);
    }
    return { success: false, error: 'Failed to update message' };
  }
}
