import AsyncStorage from '@react-native-async-storage/async-storage';
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

export const CHAT_HISTORY_PAGE_SIZE = 30;
export const MAX_CACHED_MESSAGES_PER_CHAT = 30;
export const MAX_CACHED_MESSAGE_THREADS = 25;

const CHAT_MSGS_CACHE_PREFIX = '@amour_chat_msgs_v1_';
const CHAT_MSGS_INDEX_PREFIX = '@amour_chat_msgs_index_v1_';
const BASE_URL_PROBE_TTL_MS = 60000;

const chatHistoryMemoryCache = new Map<string, ChatHistoryResponse>();
let lastBaseUrlVerifiedAt = 0;

const CANDIDATE_URLS = [
  API_CONFIG.baseUrl,
  'http://192.168.1.4:8000/api',
  'http://127.0.0.1:8000/api',
];

let activeBaseUrl = API_CONFIG.baseUrl || 'https://amour-ai-v3e4.onrender.com/api';

function chatCacheKey(userId: string, personaId: string): string {
  return `${userId.trim()}:${personaId.trim()}`;
}

function chatStorageKey(userId: string, personaId: string): string {
  return `${CHAT_MSGS_CACHE_PREFIX}${userId.trim()}_${personaId.trim()}`;
}

function chatIndexKey(userId: string): string {
  return `${CHAT_MSGS_INDEX_PREFIX}${userId.trim()}`;
}

async function touchThreadLruIndex(userId: string, personaId: string): Promise<void> {
  const cleanUser = userId.trim();
  const cleanPersona = personaId.trim();
  const idxKey = chatIndexKey(cleanUser);
  try {
    const raw = await AsyncStorage.getItem(idxKey);
    const parsed: string[] = raw ? JSON.parse(raw) : [];
    const current = Array.isArray(parsed) ? parsed.filter((id) => typeof id === 'string' && id !== cleanPersona) : [];
    const next = [cleanPersona, ...current];
    const evicted = next.slice(MAX_CACHED_MESSAGE_THREADS);
    const kept = next.slice(0, MAX_CACHED_MESSAGE_THREADS);

    await AsyncStorage.setItem(idxKey, JSON.stringify(kept));
    if (evicted.length > 0) {
      for (const oldPid of evicted) {
        chatHistoryMemoryCache.delete(chatCacheKey(cleanUser, oldPid));
      }
      await AsyncStorage.multiRemove(evicted.map((oldPid) => chatStorageKey(cleanUser, oldPid))).catch(() => {});
    }
  } catch {
    // ignore index update errors
  }
}

/**
 * Synchronous memory-cache lookup for instant zero-spinner render when available.
 */
export function getMemoryCachedChatHistory(
  personaId: string,
  userId: string
): ChatHistoryResponse | null {
  if (!personaId || !userId) return null;
  return chatHistoryMemoryCache.get(chatCacheKey(userId, personaId)) || null;
}

/**
 * Returns the latest cached messages (up to MAX_CACHED_MESSAGES_PER_CHAT = 30)
 * for a single (userId, personaId) chat thread.
 */
export async function getCachedChatHistory(
  personaId: string,
  userId: string
): Promise<ChatHistoryResponse | null> {
  if (!personaId || !userId) return null;
  const memKey = chatCacheKey(userId, personaId);
  const mem = chatHistoryMemoryCache.get(memKey);
  if (mem) return mem;

  try {
    const raw = await AsyncStorage.getItem(chatStorageKey(userId, personaId));
    if (raw) {
      const parsed = JSON.parse(raw) as ChatHistoryResponse;
      if (parsed && Array.isArray(parsed.results)) {
        const capped: ChatHistoryResponse = {
          ...parsed,
          results: parsed.results.slice(-MAX_CACHED_MESSAGES_PER_CHAT),
          page: 1,
          page_size: MAX_CACHED_MESSAGES_PER_CHAT,
        };
        chatHistoryMemoryCache.set(memKey, capped);
        return capped;
      }
    }
  } catch {
    // ignore cache read errors
  }
  return null;
}

/**
 * Persists only the latest MAX_CACHED_MESSAGES_PER_CHAT (30) messages for this thread
 * and enforces the LRU cap across threads in AsyncStorage.
 */
export async function saveCachedChatHistory(
  personaId: string,
  userId: string,
  data: ChatHistoryResponse
): Promise<void> {
  if (!personaId || !userId || !Array.isArray(data?.results)) return;
  const cappedResults = data.results.slice(-MAX_CACHED_MESSAGES_PER_CHAT);
  const capped: ChatHistoryResponse = {
    ...data,
    results: cappedResults,
    page: 1,
    page_size: MAX_CACHED_MESSAGES_PER_CHAT,
    has_more: Boolean(data.has_more || data.results.length > MAX_CACHED_MESSAGES_PER_CHAT),
  };

  chatHistoryMemoryCache.set(chatCacheKey(userId, personaId), capped);
  try {
    await AsyncStorage.setItem(chatStorageKey(userId, personaId), JSON.stringify(capped));
    await touchThreadLruIndex(userId, personaId);
  } catch {
    // ignore storage write errors
  }
}

export async function clearChatHistoryCache(userId?: string): Promise<void> {
  if (userId) {
    const cleanUser = userId.trim();
    for (const key of Array.from(chatHistoryMemoryCache.keys())) {
      if (key.startsWith(`${cleanUser}:`)) {
        chatHistoryMemoryCache.delete(key);
      }
    }
    try {
      const idxKey = chatIndexKey(cleanUser);
      const raw = await AsyncStorage.getItem(idxKey);
      const pids: string[] = raw ? JSON.parse(raw) : [];
      const keysToRemove = [
        idxKey,
        ...(Array.isArray(pids) ? pids.map((pid) => chatStorageKey(cleanUser, pid)) : []),
      ];
      await AsyncStorage.multiRemove(keysToRemove);
    } catch {}
    return;
  }

  chatHistoryMemoryCache.clear();
  try {
    const allKeys = await AsyncStorage.getAllKeys();
    const chatKeys = allKeys.filter(
      (k) => k.startsWith(CHAT_MSGS_CACHE_PREFIX) || k.startsWith(CHAT_MSGS_INDEX_PREFIX)
    );
    if (chatKeys.length > 0) {
      await AsyncStorage.multiRemove(chatKeys);
    }
  } catch {}
}

async function resolveActiveBaseUrl(): Promise<string> {
  if (Date.now() - lastBaseUrlVerifiedAt < BASE_URL_PROBE_TTL_MS) {
    return activeBaseUrl;
  }

  const probeController = new AbortController();
  const probeTimer = setTimeout(() => probeController.abort(), 1200);
  try {
    const probe = await fetch(`${activeBaseUrl}/memory/status/`, {
      method: 'GET',
      signal: probeController.signal,
    });
    clearTimeout(probeTimer);
    if (probe.ok) {
      lastBaseUrlVerifiedAt = Date.now();
      return activeBaseUrl;
    }
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
        lastBaseUrlVerifiedAt = Date.now();
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
 * Caches only Page 1 (latest 30 messages) locally; older pages always load from backend.
 */
export async function fetchChatHistory(
  personaId: string,
  userId: string,
  page: number = 1,
  pageSize: number = CHAT_HISTORY_PAGE_SIZE,
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
    lastBaseUrlVerifiedAt = Date.now();
    const json = (await res.json()) as ChatHistoryResponse;
    if (page === 1 && json && Array.isArray(json.results)) {
      await saveCachedChatHistory(personaId, userId, json);
    }
    return json;
  } catch (err: any) {
    clearTimeout(timer);
    lastBaseUrlVerifiedAt = 0;
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
    lastBaseUrlVerifiedAt = Date.now();
    return await res.json();
  } catch (err: any) {
    clearTimeout(timer);
    lastBaseUrlVerifiedAt = 0;
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

    lastBaseUrlVerifiedAt = Date.now();
    return await res.json();
  } catch (err: any) {
    clearTimeout(timer);
    lastBaseUrlVerifiedAt = 0;
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

    lastBaseUrlVerifiedAt = Date.now();
    return await res.json();
  } catch (err: any) {
    clearTimeout(timer);
    lastBaseUrlVerifiedAt = 0;
    return { success: false, error: err?.message || 'Network error' };
  }
}

/**
 * Edit a bot / persona response in-place.
 * Updates PostgreSQL DB so that the message reply is set to the edited text under the same message ID,
 * and synchronizes Reeve memory graph with the updated dialogue exchange.
 */
export async function editBotChatMessage(
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
        text: newText,
        user_id: userId,
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      return { success: false, error: errData?.error || `HTTP ${res.status}` };
    }

    lastBaseUrlVerifiedAt = Date.now();
    return await res.json();
  } catch (err: any) {
    clearTimeout(timer);
    lastBaseUrlVerifiedAt = 0;
    return { success: false, error: err?.message || 'Network error' };
  }
}
