import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_CONFIG } from '../constants/authConfig';

export interface PersonaItem {
  id: string;
  name: string;
  tagline: string;
  border_color: string;
  image_url: string;
  greeting: string;
  memory_prompt: string;
  visibility: string;
  creator_name?: string;
  created_at: string;
  updated_at?: string;
}

const STORAGE_KEY = '@amour_personas_roster';

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

// Default seeded personas if storage and network are both empty
const SEED_PERSONAS: PersonaItem[] = [
  {
    id: '26c93a17-ab27-43e0-adb8-470dc15ab3bd',
    name: 'Lyra',
    tagline: 'Cyberpunk Hologram Architect',
    border_color: '#10B981',
    image_url: '',
    greeting: '*adjusts glowing optic visor and flicks an iridescent data stream aside* Caught you admiring the neon grid. Ready to build something impossible?',
    memory_prompt: 'Lyra is a fast-talking synth-wave engineer with a brilliant analytical mind and witty banter. Loves hacking interfaces and talking about synthetic philosophy.',
    visibility: 'public',
    creator_name: 'Amour Core',
    created_at: '2026-10-30T16:50:51.214198+05:30',
  },
  {
    id: '230c2da9-9082-4d70-a0c7-eca4a869c739',
    name: 'Kaelen',
    tagline: 'Wanderer of Forgotten Realms',
    border_color: '#8B5CF6',
    image_url: '',
    greeting: '*leans back against the stone hearth, carving a rune into weathered cedar* Pull up a stool, friend. You have the look of someone who has walked through storms.',
    memory_prompt: 'Kaelen is an intrepid wanderer with memories of distant ruined kingdoms and quiet campfires. Loyal, slightly cynical, deeply grounded.',
    visibility: 'public',
    creator_name: 'Amour Core',
    created_at: '2026-10-30T16:50:51.157244+05:30',
  },
  {
    id: 'df442f6d-998d-4448-8cf1-ed58085e076c',
    name: 'Seraphina',
    tagline: 'Nocturnal Astrologer & Enigmatic Confidant',
    border_color: '#F43F5E',
    image_url: '',
    greeting: '*gently looks up from an ancient celestial chart as you approach* The stars hinted at a curious traveler tonight. What question brings you into my observatory?',
    memory_prompt: 'Seraphina is an observant, serene nocturnal astrologer who reads deep cosmic alignments. Speaks in measured, warm tones with poetic turns of phrase.',
    visibility: 'public',
    creator_name: 'Amour Core',
    created_at: '2026-10-30T16:50:51.100228+05:30',
  },
];

// Helper to attempt fetch across candidate endpoints (adb reverse or local Wi-Fi)
const CANDIDATE_URLS = [
  API_CONFIG.baseUrl,
  'http://192.168.1.2:8000/api',
];

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 2500): Promise<Response> {
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
      const res = await fetchWithTimeout(url, options, 2500);
      if (res.ok) return res;
    } catch {
      // try next candidate
    }
  }
  return null;
}

export async function getStoredPersonas(): Promise<PersonaItem[]> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    }
  } catch (err) {
    console.warn('[PersonaService] Read error:', err);
  }
  return SEED_PERSONAS;
}

export async function fetchAndSyncPersonas(): Promise<PersonaItem[]> {
  // 1. Load local cache first
  const localList = await getStoredPersonas();

  // 2. Try fetching from server
  try {
    const res = await tryServerFetch('/memory/personas/');
    if (res && res.ok) {
      const serverList: PersonaItem[] = await res.json();
      if (Array.isArray(serverList)) {
        // Merge: server items take precedence, but keep any local-only created items
        const map = new Map<string, PersonaItem>();
        for (const p of serverList) {
          map.set(p.name.toLowerCase(), p);
        }
        for (const p of localList) {
          if (!map.has(p.name.toLowerCase())) {
            map.set(p.name.toLowerCase(), p);
          }
        }
        const merged = Array.from(map.values());
        await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
        notifyListeners(merged);
        return merged;
      }
    }
  } catch (err) {
    console.warn('[PersonaService] Server sync notice:', err);
  }

  return localList;
}

export async function savePersonaToRoster(item: Omit<PersonaItem, 'id' | 'created_at'>): Promise<PersonaItem> {
  const newId = 'persona-' + Date.now().toString(36) + '-' + Math.random().toString(36).substring(2, 6);
  const nowIso = new Date().toISOString();

  const newPersona: PersonaItem = {
    ...item,
    id: newId,
    created_at: nowIso,
  };

  // 1. Immediately store in local AsyncStorage and notify all subscribers (INSTANT UI UPDATE)
  const current = await getStoredPersonas();
  const updated = [newPersona, ...current.filter((p) => p.name.toLowerCase() !== newPersona.name.toLowerCase())];
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  notifyListeners(updated);

  // 2. Fire server POST in parallel
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
      }),
    });
    if (res && res.ok) {
      const savedFromServer: PersonaItem = await res.json();
      if (savedFromServer && savedFromServer.id) {
        // Replace temp ID with backend UUID
        const finalUpdated = updated.map((p) => (p.id === newId ? savedFromServer : p));
        await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(finalUpdated));
        notifyListeners(finalUpdated);
        return savedFromServer;
      }
    }
  } catch (err) {
    console.warn('[PersonaService] Background server save notice:', err);
  }

  return newPersona;
}

export async function deletePersonaFromRoster(id: string): Promise<boolean> {
  // 1. Remove from local AsyncStorage and notify all subscribers immediately (INSTANT 0ms UI UPDATE)
  try {
    const current = await getStoredPersonas();
    const updated = current.filter((p) => p.id !== id);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    notifyListeners(updated);
  } catch (err) {
    console.warn('[PersonaService] Local delete error:', err);
  }

  // 2. Attempt server delete in parallel
  try {
    await tryServerFetch(`/memory/personas/${id}/`, {
      method: 'DELETE',
    });
  } catch (err) {
    console.warn('[PersonaService] Server delete notice:', err);
  }

  return true;
}
