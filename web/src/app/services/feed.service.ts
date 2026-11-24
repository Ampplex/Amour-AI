import { Injectable, signal } from '@angular/core';
import { API_CONFIG } from './config';
import { PersonaItem } from './persona.service';

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
const ANON_DEVICE_ID_KEY = '@amour_anon_device_id';

@Injectable({
  providedIn: 'root'
})
export class FeedService {
  readonly feedItems = signal<FeedPersonaItem[]>([]);
  readonly isLoading = signal<boolean>(false);

  private cachedDeviceId: string | null = null;
  private likedIds = new Set<string>();
  private followedHandles = new Set<string>();

  constructor() {
    this.loadCachedInteractions();
  }

  formatCount(count?: number): string {
    if (!count || count <= 0) return '0';
    if (count >= 1000000) {
      return `${(count / 1000000).toFixed(1).replace(/\.0$/, '')}M`;
    }
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1).replace(/\.0$/, '')}K`;
    }
    return count.toString();
  }

  getAnonymousDeviceId(): string {
    if (this.cachedDeviceId) return this.cachedDeviceId;
    try {
      const stored = localStorage.getItem(ANON_DEVICE_ID_KEY);
      if (stored) {
        this.cachedDeviceId = stored;
        return stored;
      }
      const newId = 'anon-' + Date.now().toString(36) + '-' + Math.random().toString(36).substring(2, 9);
      localStorage.setItem(ANON_DEVICE_ID_KEY, newId);
      this.cachedDeviceId = newId;
      return newId;
    } catch {
      return 'anon-device';
    }
  }

  private loadCachedInteractions(userId?: string): void {
    try {
      const likedKey = userId ? `${LIKED_STORAGE_KEY}_${userId}` : LIKED_STORAGE_KEY;
      const rawLiked = localStorage.getItem(likedKey);
      if (rawLiked) {
        this.likedIds = new Set<string>(JSON.parse(rawLiked));
      }

      const followedKey = userId ? `${FOLLOWED_STORAGE_KEY}_${userId}` : FOLLOWED_STORAGE_KEY;
      const rawFollowed = localStorage.getItem(followedKey);
      if (rawFollowed) {
        this.followedHandles = new Set<string>(JSON.parse(rawFollowed));
      }
    } catch {}
  }

  async syncUserInteractions(userId?: string): Promise<{ liked: Set<string>; followed: Set<string> }> {
    this.loadCachedInteractions(userId);
    if (!userId) return { liked: this.likedIds, followed: this.followedHandles };

    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/memory/interactions/?user_id=${encodeURIComponent(userId)}`);
        if (res.ok) {
          const data = await res.json();
          this.likedIds = new Set<string>(data.liked_ids || []);
          this.followedHandles = new Set<string>(data.followed_handles || []);
          localStorage.setItem(`${LIKED_STORAGE_KEY}_${userId}`, JSON.stringify(Array.from(this.likedIds)));
          localStorage.setItem(`${FOLLOWED_STORAGE_KEY}_${userId}`, JSON.stringify(Array.from(this.followedHandles)));
          return { liked: this.likedIds, followed: this.followedHandles };
        }
      } catch {}
    }
    return { liked: this.likedIds, followed: this.followedHandles };
  }

  async fetchFeedPage(
    page: number = 1,
    pageSize: number = 6,
    forceRefresh: boolean = false,
    userId?: string
  ): Promise<PaginatedFeedResponse> {
    this.isLoading.set(true);

    if (page === 1 && !forceRefresh) {
      try {
        const cached = localStorage.getItem(FEED_CACHE_KEY);
        if (cached) {
          const parsed = JSON.parse(cached);
          if (Array.isArray(parsed) && parsed.length > 0) {
            this.feedItems.set(parsed);
          }
        }
      } catch {}
    }

    const { liked, followed } = await this.syncUserInteractions(userId);

    const isFollowingHandle = (handle?: string, name?: string) => {
      if (!handle && !name) return false;
      const hClean = handle ? handle.replace(/^@/, '').toLowerCase() : '';
      const hAt = `@${hClean}`;
      return followed.has(handle || '') || followed.has(hClean) || followed.has(hAt) || followed.has(name || '');
    };

    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/memory/personas/?visibility=public&page=${page}&page_size=${pageSize}`);
        if (res.ok) {
          const data = await res.json();
          const rawResults: any[] = Array.isArray(data) ? data : data.results || [];
          const count: number = data.count || rawResults.length;
          const hasMore: boolean = typeof data.has_more === 'boolean' ? data.has_more : rawResults.length >= pageSize;

          const items: FeedPersonaItem[] = rawResults.map((p) => ({
            id: p.id,
            name: p.name,
            tagline: p.tagline || '',
            age: p.age,
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
            is_liked: liked.has(p.id),
            is_following: isFollowingHandle(p.publisher_handle, p.publisher_name),
          }));

          if (page === 1) {
            this.feedItems.set(items);
            try {
              localStorage.setItem(FEED_CACHE_KEY, JSON.stringify(items));
            } catch {}
          } else {
            this.feedItems.update(prev => [...prev, ...items]);
          }

          this.isLoading.set(false);
          return { results: items, count, page, page_size: pageSize, has_more: hasMore };
        }
      } catch {}
    }

    this.isLoading.set(false);
    return { results: this.feedItems(), count: this.feedItems().length, page, page_size: pageSize, has_more: false };
  }

  async togglePersonaLike(
    personaId: string,
    currentLiked: boolean,
    userId?: string
  ): Promise<{ liked: boolean; likes_count_delta: number; server_likes_count?: number }> {
    const effId = userId || this.getAnonymousDeviceId();
    const willBeLiked = !currentLiked;

    if (willBeLiked) {
      this.likedIds.add(personaId);
    } else {
      this.likedIds.delete(personaId);
    }

    try {
      const key = `${LIKED_STORAGE_KEY}_${effId}`;
      localStorage.setItem(key, JSON.stringify(Array.from(this.likedIds)));
    } catch {}

    // Optimistic UI update
    this.feedItems.update(items =>
      items.map(p => {
        if (p.id === personaId) {
          return {
            ...p,
            is_liked: willBeLiked,
            likes_count: Math.max(0, p.likes_count + (willBeLiked ? 1 : -1)),
          };
        }
        return p;
      })
    );

    let serverCount: number | undefined;
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/memory/personas/${encodeURIComponent(personaId)}/like/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: effId }),
        });
        if (res.ok) {
          const data = await res.json();
          if (typeof data.likes_count === 'number') {
            serverCount = data.likes_count;
            this.feedItems.update(items =>
              items.map(p => (p.id === personaId ? { ...p, is_liked: data.liked, likes_count: data.likes_count } : p))
            );
          }
          break;
        }
      } catch {}
    }

    return { liked: willBeLiked, likes_count_delta: willBeLiked ? 1 : -1, server_likes_count: serverCount };
  }

  async togglePublisherFollow(
    publisherHandle: string,
    currentFollowing: boolean,
    userId?: string
  ): Promise<{ following: boolean }> {
    const effId = userId || this.getAnonymousDeviceId();
    const willFollow = !currentFollowing;

    if (willFollow) {
      this.followedHandles.add(publisherHandle);
    } else {
      this.followedHandles.delete(publisherHandle);
    }

    try {
      const key = `${FOLLOWED_STORAGE_KEY}_${effId}`;
      localStorage.setItem(key, JSON.stringify(Array.from(this.followedHandles)));
    } catch {}

    // Update state
    this.feedItems.update(items =>
      items.map(p => {
        if (p.publisher_handle === publisherHandle) {
          return { ...p, is_following: willFollow };
        }
        return p;
      })
    );

    for (const base of API_CONFIG.candidateUrls) {
      try {
        await fetch(`${base}/memory/publishers/${encodeURIComponent(publisherHandle)}/follow/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: effId }),
        });
        break;
      } catch {}
    }

    return { following: willFollow };
  }
}
