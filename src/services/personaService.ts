import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_CONFIG } from '../constants/authConfig';

export interface PersonaItem {
  id: string;
  name: string;
  tagline: string;
  age?: number;
  border_color: string;
  image_url: string;
  greeting: string;
  memory_prompt: string;
  visibility: string;
  is_community?: boolean;
  likes_count?: number;
  chats_count?: number;
  publisher_name?: string;
  publisher_handle?: string;
  publisher_avatar?: string;
  creator_name?: string;
  creator_id?: string;
  created_at: string;
  updated_at?: string;
}

const BASE_STORAGE_KEY = '@amour_personas_roster_v4';

function getStorageKey(userId?: string): string {
  return userId ? `${BASE_STORAGE_KEY}_${userId}` : BASE_STORAGE_KEY;
}

type PersonaListener = (personas: PersonaItem[]) => void;
const listeners = new Set<PersonaListener>();

/**
 * Subscribe to real-time persona updates (creation, deletion, syncing).
 * Automatically fires when any persona changes anywhere in the app.
 */
export function subscribePersonas(listener: PersonaListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function notifyListeners(personas: PersonaItem[]) {
  listeners.forEach((listener) => {
    try {
      listener(personas);
    } catch (e) {
      console.warn('[PersonaService] Listener error:', e);
    }
  });
}

// Dummy legacy IDs to always filter out
const DUMMY_IDS = new Set<string>([
  '26c93a17-ab27-43e0-adb8-470dc15ab3bd',
  '230c2da9-9082-4d70-a0c7-eca4a869c739',
  'df442f6d-998d-4448-8cf1-ed58085e076c',
]);

// Helper to attempt fetch across candidate endpoints (adb reverse or local Wi-Fi)
const CANDIDATE_URLS = [
  API_CONFIG.baseUrl,
  'http://127.0.0.1:8000/api',
  'http://192.168.1.4:8000/api',
  'http://10.104.217.217:8000/api',
  'http://192.168.1.2:8000/api',
];

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 10000): Promise<Response> {
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

export async function getStoredPersonas(userId?: string): Promise<PersonaItem[]> {
  const storageKey = getStorageKey(userId);
  try {
    const raw = await AsyncStorage.getItem(storageKey);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.filter(
          (p) => !DUMMY_IDS.has(p.id) && p.creator_name !== 'Amour Core'
        );
      }
    }
  } catch (err) {
    console.warn('[PersonaService] Read error:', err);
  }
  return [];
}

/**
 * Retrieves personas stored with corresponding user ID in PostgreSQL database (Neon).
 */
export async function fetchAndSyncPersonas(userId?: string): Promise<PersonaItem[]> {
  const storageKey = getStorageKey(userId);
  // 1. Load local cache first
  const localList = await getStoredPersonas(userId);

  // 2. Query PostgreSQL strictly for this user ID
  try {
    const endpoint = userId
      ? `/memory/personas/?creator_id=${userId}`
      : '/memory/personas/?scope=my_personas';
    const res = await tryServerFetch(endpoint);
    if (res && res.ok) {
      const serverList: PersonaItem[] = await res.json();
      if (Array.isArray(serverList)) {
        const validServer = serverList.filter(
          (p) => !DUMMY_IDS.has(p.id) && p.creator_name !== 'Amour Core'
        );
        // Persist real user personas in local storage
        await AsyncStorage.setItem(storageKey, JSON.stringify(validServer));
        notifyListeners(validServer);
        return validServer;
      }
    }
  } catch (err) {
    console.warn('[PersonaService] Server sync notice:', err);
  }

  return localList;
}

/**
 * Stores persona with corresponding user ID in PostgreSQL database (Neon).
 */
export async function savePersonaToRoster(
  item: Omit<PersonaItem, 'id' | 'created_at'>,
  userId?: string
): Promise<PersonaItem> {
  const storageKey = getStorageKey(userId);
  const newId = 'persona-' + Date.now().toString(36) + '-' + Math.random().toString(36).substring(2, 6);
  const nowIso = new Date().toISOString();

  const newPersona: PersonaItem = {
    ...item,
    id: newId,
    creator_id: userId,
    created_at: nowIso,
  };

  // 1. Store in user's local roster immediately (0ms instant UI update)
  const current = await getStoredPersonas(userId);
  const updated = [newPersona, ...current.filter((p) => p.name.toLowerCase() !== newPersona.name.toLowerCase())];
  await AsyncStorage.setItem(storageKey, JSON.stringify(updated));
  notifyListeners(updated);

  // 2. Store in PostgreSQL with corresponding user ID
  try {
    const res = await tryServerFetch('/memory/personas/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: item.name,
        tagline: item.tagline,
        border_color: item.border_color,
        image_url: item.image_url,
        greeting: item.greeting,
        memory_prompt: item.memory_prompt,
        visibility: item.visibility,
        user_id: userId,
        publisher_name: item.publisher_name,
        publisher_handle: item.publisher_handle,
        publisher_avatar: item.publisher_avatar,
      }),
    });
    if (res && res.ok) {
      const savedFromServer: PersonaItem = await res.json();
      if (savedFromServer && savedFromServer.id) {
        const finalUpdated = updated.map((p) => (p.id === newId ? savedFromServer : p));
        await AsyncStorage.setItem(storageKey, JSON.stringify(finalUpdated));
        notifyListeners(finalUpdated);
        return savedFromServer;
      }
    }
  } catch (err) {
    console.warn('[PersonaService] Background server save notice:', err);
  }

  return newPersona;
}

export async function updatePersonaMemory(
  id: string,
  updates: { memory_prompt?: string; greeting?: string; name?: string; tagline?: string },
  userId?: string
): Promise<PersonaItem | null> {
  const storageKey = getStorageKey(userId);
  const current = await getStoredPersonas(userId);
  let updatedPersona: PersonaItem | null = null;

  const updatedList = current.map((p) => {
    if (p.id === id) {
      updatedPersona = {
        ...p,
        ...updates,
        updated_at: new Date().toISOString(),
      };
      return updatedPersona;
    }
    return p;
  });

  if (updatedPersona) {
    await AsyncStorage.setItem(storageKey, JSON.stringify(updatedList));
    notifyListeners(updatedList);
  }

  // Sync update with backend & Reeve
  try {
    const res = await tryServerFetch(`/memory/personas/${id}/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...updates,
        user_id: userId,
      }),
    });
    if (res && res.ok) {
      const serverUpdated: PersonaItem = await res.json();
      if (serverUpdated && serverUpdated.id) {
        const finalUpdated = updatedList.map((p) => (p.id === id ? serverUpdated : p));
        await AsyncStorage.setItem(storageKey, JSON.stringify(finalUpdated));
        notifyListeners(finalUpdated);
        return serverUpdated;
      }
    }
  } catch (err) {
    console.warn('[PersonaService] Server memory update notice:', err);
  }

  return updatedPersona;
}

export async function deletePersonaFromRoster(id: string, userId?: string): Promise<void> {
  const storageKey = getStorageKey(userId);
  const current = await getStoredPersonas(userId);
  const updated = current.filter((p) => p.id !== id);
  await AsyncStorage.setItem(storageKey, JSON.stringify(updated));
  notifyListeners(updated);

  // Sync delete with PostgreSQL database
  try {
    await tryServerFetch(`/memory/personas/${id}/`, {
      method: 'DELETE',
    });
  } catch (err) {
    console.warn('[PersonaService] Server delete notice:', err);
  }
}
