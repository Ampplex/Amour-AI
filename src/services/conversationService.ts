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
  page?: number;
  page_size?: number;
  has_more?: boolean;
}

export interface ConversationsFetchResult {
  ok: boolean;
  conversations: ConversationItem[];
  page: number;
  hasMore: boolean;
  error?: string;
}

export const CONVERSATIONS_PAGE_SIZE = 20;
export const MAX_CACHED_CONVERSATIONS = 20;

const CONVERSATIONS_CACHE_PREFIX = '@amour_conversations_cache_v1_';
const MAX_INLINE_DATA_URI_LENGTH = 2048;

const memoryCache = new Map<string, ConversationItem[]>();
const inFlightRequests = new Map<string, Promise<ConversationsFetchResult>>();

function cacheStorageKey(userId: string): string {
  return `${CONVERSATIONS_CACHE_PREFIX}${userId.trim()}`;
}

function sanitizeImageForDiskCache(value?: string): string {
  if (!value) return '';
  // Skip oversized base64 data URIs so AsyncStorage stays well under Android's 2MB row limit.
  if (value.startsWith('data:') && value.length > MAX_INLINE_DATA_URI_LENGTH) {
    return '';
  }
  return value;
}

function prepareDiskCacheItems(list: ConversationItem[]): ConversationItem[] {
  return list.slice(0, MAX_CACHED_CONVERSATIONS).map((item) => ({
    ...item,
    persona: {
      ...item.persona,
      image_url: sanitizeImageForDiskCache(item.persona?.image_url),
      publisher_avatar: sanitizeImageForDiskCache(item.persona?.publisher_avatar),
    },
  }));
}

/**
 * Returns the latest cached conversations (up to MAX_CACHED_CONVERSATIONS)
 * from memory or AsyncStorage for instant Frame-1 render.
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
        const capped = parsed.slice(0, MAX_CACHED_CONVERSATIONS) as ConversationItem[];
        memoryCache.set(userId, capped);
        return capped;
      }
    }
  } catch {
    // ignore storage read errors
  }
  return null;
}

async function saveCachedConversations(userId: string, list: ConversationItem[]): Promise<void> {
  if (!userId) return;
  const capped = list.slice(0, MAX_CACHED_CONVERSATIONS);
  memoryCache.set(userId, capped);
  try {
    await AsyncStorage.setItem(
      cacheStorageKey(userId),
      JSON.stringify(prepareDiskCacheItems(capped))
    );
  } catch {
    // ignore storage write errors
  }
}

export async function clearConversationCache(userId?: string): Promise<void> {
  if (userId) {
    memoryCache.delete(userId);
    for (const key of Array.from(inFlightRequests.keys())) {
      if (key.startsWith(`${userId}:`)) {
        inFlightRequests.delete(key);
      }
    }
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
  page: number,
  pageSize: number,
  token?: string
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  try {
    const baseUrl = API_CONFIG.baseUrl || 'https://amour-ai-v3e4.onrender.com/api';
    const url = `${baseUrl}/memory/conversations/?user_id=${encodeURIComponent(userId)}&page=${page}&page_size=${pageSize}`;
    return await fetch(url, {
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
 * Fetch paginated persona conversations with explicit status and in-flight deduplication.
 * Caches only Page 1 (latest conversations, capped at MAX_CACHED_CONVERSATIONS) locally.
 * Never masks network/timeout/HTTP errors as an empty conversation list.
 */
export async function fetchUserConversationsWithStatus(
  userId: string,
  token?: string,
  page: number = 1,
  pageSize: number = CONVERSATIONS_PAGE_SIZE
): Promise<ConversationsFetchResult> {
  if (!userId) {
    return { ok: true, conversations: [], page: 1, hasMore: false };
  }

  const safePage = Math.max(1, page);
  const safePageSize = Math.min(100, Math.max(1, pageSize));
  const dedupKey = `${userId}:${safePage}:${safePageSize}`;

  const existing = inFlightRequests.get(dedupKey);
  if (existing) {
    return existing;
  }

  const requestPromise = (async (): Promise<ConversationsFetchResult> => {
    try {
      const userKey = await getOrCreateUserKey();
      let res = await performConversationsRequest(userId, userKey, safePage, safePageSize, token);

      // If a stale/expired JWT triggers 401 on an AllowAny endpoint, retry once using user_id + user_key
      if (res.status === 401 && token) {
        res = await performConversationsRequest(userId, userKey, safePage, safePageSize, undefined);
      }

      if (!res.ok) {
        const errMsg = `HTTP ${res.status}`;
        console.warn(`[conversationService] fetchUserConversations ${errMsg}`);
        return { ok: false, conversations: [], page: safePage, hasMore: false, error: errMsg };
      }

      const data = await res.json();
      const list = Array.isArray(data?.conversations) ? (data.conversations as ConversationItem[]) : [];
      const hasMore = Boolean(data?.has_more);

      if (safePage === 1) {
        await saveCachedConversations(userId, list);
      }

      return { ok: true, conversations: list, page: safePage, hasMore };
    } catch (err: any) {
      const errMsg = err?.name === 'AbortError' ? 'Request timed out' : err?.message || 'Network error';
      console.warn('[conversationService] fetchUserConversations error:', errMsg);
      return { ok: false, conversations: [], page: safePage, hasMore: false, error: errMsg };
    } finally {
      inFlightRequests.delete(dedupKey);
    }
  })();

  inFlightRequests.set(dedupKey, requestPromise);
  return requestPromise;
}

/**
 * Fetch the first page of persona conversations for the given user ID.
 * Returns sorted list of conversation threads with decrypted latest messages and timestamps.
 */
export async function fetchUserConversations(
  userId: string,
  token?: string
): Promise<ConversationItem[]> {
  const result = await fetchUserConversationsWithStatus(userId, token, 1, CONVERSATIONS_PAGE_SIZE);
  return result.conversations;
}
