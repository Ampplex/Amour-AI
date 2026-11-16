import * as Crypto from 'expo-crypto';
import { API_CONFIG } from '../constants/authConfig';
import { getOrCreateUserKey } from './keyService';
import { getReplyLengthPreference, ReplyLengthOption } from './settingsService';

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
  reply_length?: ReplyLengthOption;
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

const CANDIDATE_URLS = [
  API_CONFIG.baseUrl,
  'http://192.168.1.4:8000/api',
  'http://127.0.0.1:8000/api',
];

let activeBaseUrl = API_CONFIG.baseUrl || 'https://amour-ai-d6a8.onrender.com/api';

async function resolveActiveBaseUrl(): Promise<string> {
  const probeController = new AbortController();
  const probeTimer = setTimeout(() => probeController.abort(), 1200);
  try {
    const probe = await fetch(`${activeBaseUrl}/memory/status/`, {
      method: 'GET',
      signal: probeController.signal,
    });
    clearTimeout(probeTimer);
    if (probe.ok) return activeBaseUrl;
  } catch {
    clearTimeout(probeTimer);
  }

  for (const candidate of CANDIDATE_URLS) {
    if (candidate === activeBaseUrl) continue;
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 1200);
    try {
      const probe = await fetch(`${candidate}/memory/status/`, {
        method: 'GET',
        signal: ctrl.signal,
      });
      clearTimeout(t);
      if (probe.ok) {
        activeBaseUrl = candidate;
        return candidate;
      }
    } catch {
      clearTimeout(t);
    }
  }

  return activeBaseUrl;
}

/**
 * Fetch paginated chat history for a specific persona and user.
 * Direct single-endpoint GET with 12s timeout.
 */
export async function fetchChatHistory(
  personaId: string,
  userId: string,
  page: number = 1,
  pageSize: number = 30,
  token?: string
): Promise<ChatHistoryResponse | null> {
  const query = `persona_id=${encodeURIComponent(personaId)}&user_id=${encodeURIComponent(userId)}&page=${page}&page_size=${pageSize}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);

  try {
    const userKey = await getOrCreateUserKey();
    const baseUrl = await resolveActiveBaseUrl();
    const res = await fetch(`${baseUrl}/memory/chat/?${query}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Memory-User-Key': userKey,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) {
      console.warn(`[chatService] fetchChatHistory HTTP ${res.status}`);
      return null;
    }
    return await res.json();
  } catch (err: any) {
    clearTimeout(timer);
    console.warn('[chatService] fetchChatHistory error:', err?.message || err);
    return null;
  }
}

/**
 * Send a chat message with a unique client_message_id for guaranteed idempotency.
 * Single request with 45s timeout to allow full LLM inference + Reeve memory indexing.
 * Never loops over candidate URLs for state-mutating requests.
 */
export async function sendChatMessage(
  payload: SendMessagePayload,
  token?: string
): Promise<SendMessageResponse | null> {
  const clientMessageId = payload.client_message_id || Crypto.randomUUID();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45000);

  try {
    const userKey = await getOrCreateUserKey();
    const replyLength = payload.reply_length || (await getReplyLengthPreference());
    const baseUrl = await resolveActiveBaseUrl();
    const res = await fetch(`${baseUrl}/memory/chat/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Memory-User-Key': userKey,
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
    if (!res.ok) {
      console.warn(`[chatService] sendChatMessage HTTP ${res.status}`);
      return null;
    }
    return await res.json();
  } catch (err: any) {
    clearTimeout(timer);
    console.warn('[chatService] sendChatMessage error:', err?.message || err);
    return null;
  }
}

/**
 * Permanently delete a chat message from PostgreSQL.
 */
export async function deleteChatMessage(
  messageId: string,
  userId: string,
  token?: string
): Promise<{ success: boolean; deleted_id?: string; error?: string }> {
  const query = `message_id=${encodeURIComponent(messageId)}&user_id=${encodeURIComponent(userId)}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);

  try {
    const userKey = await getOrCreateUserKey();
    const baseUrl = await resolveActiveBaseUrl();
    const res = await fetch(`${baseUrl}/memory/chat/?${query}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-Memory-User-Key': userKey,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      return { success: false, error: errData?.error || `HTTP ${res.status}` };
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timer);
    return { success: false, error: err?.message || 'Network error' };
  }
}

/**
 * Switch active variant for a regenerated bot response.
 * Updates PostgreSQL DB so that message id reply is set to the current selected one.
 */
export async function switchChatMessageVariant(
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
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);

  try {
    const userKey = await getOrCreateUserKey();
    const baseUrl = await resolveActiveBaseUrl();
    const res = await fetch(`${baseUrl}/memory/chat/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-Memory-User-Key': userKey,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        message_id: messageId,
        variant_index: variantIndex,
        user_id: userId,
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      return { success: false, error: errData?.error || `HTTP ${res.status}` };
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timer);
    return { success: false, error: err?.message || 'Network error' };
  }
}
