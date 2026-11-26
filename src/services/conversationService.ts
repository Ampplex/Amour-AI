import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_CONFIG } from '../constants/authConfig';
import { getOrCreateUserKey } from './keyService';
import { PersonaItem } from './personaService';

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

export interface ConversationsResponse {
  conversations: ConversationItem[];
}

export interface ConversationsFetchResult {
  ok: boolean;
  conversations: ConversationItem[];
  error?: string;
}

const CONVERSATIONS_CACHE_PREFIX = '@amour_conversations_cache_v1_';
const memoryCache = new Map<string, ConversationItem[]>();
const inFlightRequests = new Map<string, Promise<ConversationsFetchResult>>();

function cacheStorageKey(userId: string): string {
  return `${CONVERSATIONS_CACHE_PREFIX}${userId.trim()}`;
}

/**
 * Returns cached conversations immediately from memory or AsyncStorage for instant Frame-1 UI.
 */
export async function getCachedConversations(userId: string): Promise<ConversationItem[] | null> {
  if (!userId) return null;
  const mem = memoryCache.get(userId);
  if (mem) return mem;

  try {
    const raw = await AsyncStorage.getItem(cacheStorageKey(userId));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        memoryCache.set(userId, parsed);
        return parsed as ConversationItem[];
      }
    }
  } catch {
    // ignore storage read errors
  }
  return null;
}

async function saveCachedConversations(userId: string, list: ConversationItem[]): Promise<void> {
  if (!userId) return;
  memoryCache.set(userId, list);
  try {
    await AsyncStorage.setItem(cacheStorageKey(userId), JSON.stringify(list));
  } catch {
    // ignore storage write errors
  }
}

export async function clearConversationCache(userId?: string): Promise<void> {
  if (userId) {
    memoryCache.delete(userId);
    inFlightRequests.delete(userId);
    try {
      await AsyncStorage.removeItem(cacheStorageKey(userId));
    } catch {}
    return;
  }
  const keys = Array.from(memoryCache.keys());
  memoryCache.clear();
  inFlightRequests.clear();
  try {
    await Promise.all(keys.map((id) => AsyncStorage.removeItem(cacheStorageKey(id))));
  } catch {}
}

async function performConversationsRequest(
  userId: string,
  userKey: string,
  token?: string
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  try {
    const baseUrl = API_CONFIG.baseUrl || 'https://amour-ai-v3e4.onrender.com/api';
    return await fetch(`${baseUrl}/memory/conversations/?user_id=${encodeURIComponent(userId)}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Memory-User-Key': userKey,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Fetch all persona conversations with explicit status and in-flight deduplication.
 * Never masks network/timeout/HTTP errors as an empty conversation list.
 */
export async function fetchUserConversationsWithStatus(
  userId: string,
  token?: string
): Promise<ConversationsFetchResult> {
  if (!userId) {
    return { ok: true, conversations: [] };
  }

  const existing = inFlightRequests.get(userId);
  if (existing) {
    return existing;
  }

  const requestPromise = (async (): Promise<ConversationsFetchResult> => {
    try {
      const userKey = await getOrCreateUserKey();
      let res = await performConversationsRequest(userId, userKey, token);

      // If a stale/expired JWT triggers 401 on an AllowAny endpoint, retry once using user_id + user_key
      if (res.status === 401 && token) {
        res = await performConversationsRequest(userId, userKey, undefined);
      }

      if (!res.ok) {
        const errMsg = `HTTP ${res.status}`;
        console.warn(`[conversationService] fetchUserConversations ${errMsg}`);
        return { ok: false, conversations: [], error: errMsg };
      }

      const data = await res.json();
      const list = Array.isArray(data?.conversations) ? (data.conversations as ConversationItem[]) : [];
      await saveCachedConversations(userId, list);
      return { ok: true, conversations: list };
    } catch (err: any) {
      const errMsg = err?.name === 'AbortError' ? 'Request timed out' : err?.message || 'Network error';
      console.warn('[conversationService] fetchUserConversations error:', errMsg);
      return { ok: false, conversations: [], error: errMsg };
    } finally {
      inFlightRequests.delete(userId);
    }
  })();

  inFlightRequests.set(userId, requestPromise);
  return requestPromise;
}

/**
 * Fetch all persona conversations for the given user ID.
 * Returns sorted list of conversation threads with decrypted latest messages and timestamps.
 */
export async function fetchUserConversations(
  userId: string,
  token?: string
): Promise<ConversationItem[]> {
  const result = await fetchUserConversationsWithStatus(userId, token);
  return result.conversations;
}
