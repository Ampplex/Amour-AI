import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_CONFIG } from '../constants/authConfig';
import { PersonaItem } from './personaService';

export interface FeedPersonaItem extends PersonaItem {
  likes_count: number;
  chats_count: number;
  publisher_name: string;
  publisher_handle: string;
  publisher_avatar: string;
  is_liked?: boolean;
  is_following?: boolean;
}

export interface PaginatedFeedResponse {
  results: FeedPersonaItem[];
  count: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

const LIKED_STORAGE_KEY = '@amour_liked_persona_ids';
const FOLLOWED_STORAGE_KEY = '@amour_followed_publishers';
const FEED_CACHE_KEY = '@amour_feed_cache_window_v4';
const OLD_FEED_CACHE_KEY = '@amour_feed_cache_window';
const ANON_DEVICE_ID_KEY = '@amour_anon_device_id';

let cachedDeviceId: string | null = null;

export async function getAnonymousDeviceId(): Promise<string> {
  if (cachedDeviceId) return cachedDeviceId;
  try {
    const stored = await AsyncStorage.getItem(ANON_DEVICE_ID_KEY);
    if (stored) {
      cachedDeviceId = stored;
      return stored;
    }
    const newId = 'anon-' + Date.now().toString(36) + '-' + Math.random().toString(36).substring(2, 9);
    await AsyncStorage.setItem(ANON_DEVICE_ID_KEY, newId);
    cachedDeviceId = newId;
    return newId;
  } catch {
    return 'anon-device';
  }
}

// Candidate URLs for reliable connection over USB, wireless ADB, or local network
const CANDIDATE_URLS = [
  API_CONFIG.baseUrl,
  'http://127.0.0.1:8000/api',
  'http://192.168.1.4:8000/api',
  'http://10.104.217.217:8000/api',
  'http://192.168.1.2:8000/api',
];

// Helper to format counts: e.g. 12400 -> "12.4K", 12000 -> "12K", 700 -> "700"
export function formatCount(count: number): string {
  if (!count || count <= 0) return '0';
  if (count >= 1000000) {
    const val = (count / 1000000).toFixed(1).replace(/\.0$/, '');
    return `${val}M`;
  }
  if (count >= 1000) {
    const val = (count / 1000).toFixed(1).replace(/\.0$/, '');
    return `${val}K`;
  }
  return count.toString();
}

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 3000): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    return res;
  } catch (e) {
    clearTimeout(id);
    throw e;
  }
}

async function tryServerFetch(path: string, options: RequestInit = {}): Promise<Response | null> {
  for (const base of CANDIDATE_URLS) {
    try {
      const url = `${base}${path}`;
      const res = await fetchWithTimeout(url, options, 10000);
      if (res.ok) return res;
    } catch {
      // try next candidate
    }
  }
  return null;
}

// Multi-Account Isolated Memory & Local Cache of Liked IDs & Followed Handles
const userLikedCache = new Map<string, Set<string>>();
const userFollowedCache = new Map<string, Set<string>>();

function getUserCacheKey(userId?: string): string {
  return userId ? userId.trim() : 'anonymous';
}

export async function getLikedIds(userId?: string): Promise<Set<string>> {
  const cacheKey = getUserCacheKey(userId);
  if (userLikedCache.has(cacheKey)) {
    return userLikedCache.get(cacheKey)!;
  }

  const storageKey = userId ? `${LIKED_STORAGE_KEY}_${userId}` : LIKED_STORAGE_KEY;
  try {
    const raw = await AsyncStorage.getItem(storageKey);
    if (raw) {
      const set = new Set<string>(JSON.parse(raw));
      userLikedCache.set(cacheKey, set);
      return set;
    }
  } catch (e) {
    console.warn('[FeedService] Error reading liked IDs:', e);
  }
  const emptySet = new Set<string>();
  userLikedCache.set(cacheKey, emptySet);
  return emptySet;
}

export async function getFollowedHandles(userId?: string): Promise<Set<string>> {
  const cacheKey = getUserCacheKey(userId);
  if (userFollowedCache.has(cacheKey)) {
    return userFollowedCache.get(cacheKey)!;
  }

  const storageKey = userId ? `${FOLLOWED_STORAGE_KEY}_${userId}` : FOLLOWED_STORAGE_KEY;
  try {
    const raw = await AsyncStorage.getItem(storageKey);
    if (raw) {
      const set = new Set<string>(JSON.parse(raw));
      userFollowedCache.set(cacheKey, set);
      return set;
    }
  } catch (e) {
    console.warn('[FeedService] Error reading followed handles:', e);
  }
  const emptySet = new Set<string>();
  userFollowedCache.set(cacheKey, emptySet);
  return emptySet;
}

/**
 * Synchronize real user interactions (likes and follows) directly with PostgreSQL database.
 */
export async function syncUserInteractions(userId?: string): Promise<{ liked: Set<string>; followed: Set<string> }> {
  const cacheKey = getUserCacheKey(userId);
  if (!userId) {
    const l = await getLikedIds();
    const f = await getFollowedHandles();
    return { liked: l, followed: f };
  }

  try {
    const res = await tryServerFetch(`/memory/interactions/?user_id=${userId}`);
    if (res && res.ok) {
      const data = await res.json();
      const likedArr: string[] = data.liked_ids || [];
      const followedArr: string[] = data.followed_handles || [];
      const likedSet = new Set<string>(likedArr);
      const followedSet = new Set<string>(followedArr);
      userLikedCache.set(cacheKey, likedSet);
      userFollowedCache.set(cacheKey, followedSet);
      AsyncStorage.setItem(`${LIKED_STORAGE_KEY}_${userId}`, JSON.stringify(likedArr)).catch(() => {});
      AsyncStorage.setItem(`${FOLLOWED_STORAGE_KEY}_${userId}`, JSON.stringify(followedArr)).catch(() => {});
      return { liked: likedSet, followed: followedSet };
    }
  } catch (e) {
    console.warn('[FeedService] Interactions sync notice:', e);
  }

  const l = await getLikedIds(userId);
  const f = await getFollowedHandles(userId);
  return { liked: l, followed: f };
}

// In-Memory Page Cache to avoid unnecessary re-renders and network thrashing
const inMemoryPageCache = new Map<number, FeedPersonaItem[]>();

export function clearFeedMemoryCache() {
  inMemoryPageCache.clear();
  userLikedCache.clear();
  userFollowedCache.clear();
}

/**
 * Fetch a page of public community personas with pagination.
 */
export async function fetchFeedPage(
  page: number = 1,
  pageSize: number = 4,
  forceRefresh: boolean = false,
  userId?: string
): Promise<PaginatedFeedResponse> {
  const { liked: likedSet, followed: followedSet } = await syncUserInteractions(userId);

  const isFollowingHandle = (handle?: string, name?: string) => {
    if (!handle && !name) return false;
    const hClean = handle ? handle.replace(/^@/, '').toLowerCase() : '';
    const hAt = `@${hClean}`;
    return (
      (handle ? followedSet.has(handle) : false) ||
      (hClean ? followedSet.has(hClean) : false) ||
      (hAt ? followedSet.has(hAt) : false) ||
      (name ? followedSet.has(name) : false)
    );
  };

  if (forceRefresh) {
    inMemoryPageCache.clear();
    AsyncStorage.removeItem(FEED_CACHE_KEY).catch(() => {});
    AsyncStorage.removeItem(OLD_FEED_CACHE_KEY).catch(() => {});
  } else if (inMemoryPageCache.has(page)) {
    const cachedItems = inMemoryPageCache.get(page)!;
    return {
      results: cachedItems.map((item) => ({
        ...item,
        is_liked: likedSet.has(item.id),
        is_following: isFollowingHandle(item.publisher_handle, item.publisher_name),
      })),
      count: cachedItems.length,
      page,
      page_size: pageSize,
      has_more: true,
    };
  }

  try {
    const res = await tryServerFetch(
      `/memory/personas/?visibility=public&page=${page}&page_size=${pageSize}`
    );

    if (res && res.ok) {
      const data = await res.json();
      const rawResults: any[] = Array.isArray(data) ? data : data.results || [];
      const count: number = data.count || rawResults.length;
      const hasMore: boolean = typeof data.has_more === 'boolean' ? data.has_more : rawResults.length >= pageSize;

      const items: FeedPersonaItem[] = rawResults.map((p) => ({
        id: p.id,
        name: p.name,
        tagline: p.tagline || '',
        border_color: p.border_color || '#F43F5E',
        image_url: p.image_url || '',
        greeting: p.greeting || '',
        memory_prompt: p.memory_prompt || '',
        visibility: p.visibility || 'public',
        likes_count: typeof p.likes_count === 'number' ? p.likes_count : 0,
        chats_count: typeof p.chats_count === 'number' ? p.chats_count : 0,
        publisher_name: p.publisher_name || p.creator_name || 'Creator',
        publisher_handle: p.publisher_handle || `@${(p.publisher_name || 'creator').toLowerCase().replace(/\s+/g, '_')}`,
        publisher_avatar: p.publisher_avatar || '',
        creator_name: p.creator_name || 'Anonymous',
        created_at: p.created_at,
        updated_at: p.updated_at,
        is_liked: likedSet.has(p.id),
        is_following: isFollowingHandle(p.publisher_handle, p.publisher_name),
      }));

      inMemoryPageCache.set(page, items);

      // Save page 1 in AsyncStorage for instant offline/initial cold start
      if (page === 1) {
        AsyncStorage.setItem(FEED_CACHE_KEY, JSON.stringify(items)).catch(() => {});
      }

      return {
        results: items,
        count,
        page,
        page_size: pageSize,
        has_more: hasMore,
      };
    }
  } catch (err) {
    console.warn('[FeedService] Fetch error:', err);
  }

  // Fallback to local cache on cold start network delay
  if (page === 1) {
    try {
      const cached = await AsyncStorage.getItem(FEED_CACHE_KEY);
      if (cached) {
        const parsed: FeedPersonaItem[] = JSON.parse(cached);
        return {
          results: parsed.map((item) => ({
            ...item,
            is_liked: likedSet.has(item.id),
            is_following: followedSet.has(item.publisher_handle || item.publisher_name),
          })),
          count: parsed.length,
          page: 1,
          page_size: pageSize,
          has_more: false,
        };
      }
    } catch {}
  }

  return {
    results: [],
    count: 0,
    page,
    page_size: pageSize,
    has_more: false,
  };
}

/**
 * Toggle like for a persona with instant local persistence and background server sync.
 */
export async function togglePersonaLike(
  personaId: string,
  currentLiked: boolean,
  userId?: string
): Promise<{ liked: boolean; likes_count_delta: number; server_likes_count?: number }> {
  const effectiveUserId = userId || (await getAnonymousDeviceId());
  const cacheKey = getUserCacheKey(effectiveUserId);
  const likedSet = await getLikedIds(effectiveUserId);
  const willBeLiked = !currentLiked;

  if (willBeLiked) {
    likedSet.add(personaId);
  } else {
    likedSet.delete(personaId);
  }
  userLikedCache.set(cacheKey, likedSet);
  const key = `${LIKED_STORAGE_KEY}_${effectiveUserId}`;
  AsyncStorage.setItem(key, JSON.stringify(Array.from(likedSet))).catch(() => {});

  // 1. Update in-memory pagination cache immediately
  for (const [pageNum, items] of inMemoryPageCache.entries()) {
    const updated = items.map((p) => {
      if (p.id === personaId) {
        return {
          ...p,
          is_liked: willBeLiked,
          likes_count: Math.max(0, p.likes_count + (willBeLiked ? 1 : -1)),
        };
      }
      return p;
    });
    inMemoryPageCache.set(pageNum, updated);
  }

  // 2. Update local cold start cache
  AsyncStorage.getItem(FEED_CACHE_KEY).then((cached) => {
    if (cached) {
      try {
        const parsed: FeedPersonaItem[] = JSON.parse(cached);
        const updated = parsed.map((p) =>
          p.id === personaId
            ? {
                ...p,
                is_liked: willBeLiked,
                likes_count: Math.max(0, p.likes_count + (willBeLiked ? 1 : -1)),
              }
            : p
        );
        AsyncStorage.setItem(FEED_CACHE_KEY, JSON.stringify(updated)).catch(() => {});
      } catch {}
    }
  }).catch(() => {});

  // 3. Fire server request and retrieve authoritative database count
  let serverLikesCount: number | undefined;
  try {
    const res = await tryServerFetch(`/memory/personas/${personaId}/like/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: effectiveUserId }),
    });
    if (res && res.ok) {
      const data = await res.json();
      if (typeof data.likes_count === 'number') {
        serverLikesCount = data.likes_count;
        // Update in-memory cache with exact server count
        for (const [pageNum, items] of inMemoryPageCache.entries()) {
          const synced = items.map((p) =>
            p.id === personaId
              ? { ...p, is_liked: data.liked, likes_count: data.likes_count }
              : p
          );
          inMemoryPageCache.set(pageNum, synced);
        }
      }
    }
  } catch (e) {
    console.warn('[FeedService] Like sync notice:', e);
  }

  return {
    liked: willBeLiked,
    likes_count_delta: willBeLiked ? 1 : -1,
    server_likes_count: serverLikesCount,
  };
}

/**
 * Toggle follow/unfollow for a publisher with instant local persistence and background server sync.
 */
export async function togglePublisherFollow(
  publisherHandle: string,
  currentFollowing: boolean,
  userId?: string
): Promise<{ following: boolean }> {
  const effectiveUserId = userId || (await getAnonymousDeviceId());
  const cacheKey = getUserCacheKey(effectiveUserId);
  const followedSet = await getFollowedHandles(effectiveUserId);
  const willBeFollowing = !currentFollowing;

  if (willBeFollowing) {
    followedSet.add(publisherHandle);
  } else {
    followedSet.delete(publisherHandle);
  }
  userFollowedCache.set(cacheKey, followedSet);
  const key = `${FOLLOWED_STORAGE_KEY}_${effectiveUserId}`;
  AsyncStorage.setItem(key, JSON.stringify(Array.from(followedSet))).catch(() => {});

  // Fire server request asynchronously in background with real user ID
  tryServerFetch(`/memory/publishers/${encodeURIComponent(publisherHandle)}/follow/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: effectiveUserId }),
  }).catch((e) => console.log('[FeedService] Follow sync error:', e));

  return {
    following: willBeFollowing,
  };
}
