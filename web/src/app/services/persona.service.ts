import { Injectable, signal, inject } from '@angular/core';
import { API_CONFIG } from './config';
import { KeyService } from './key.service';

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
const CUSTOM_STORAGE_KEY = '@amour_persona_user_customizations_v1';

const DUMMY_IDS = new Set<string>([
  '26c93a17-ab27-43e0-adb8-470dc15ab3bd',
  '230c2da9-9082-4d70-a0c7-eca4a869c739',
  'df442f6d-998d-4448-8cf1-ed58085e076c',
]);

@Injectable({
  providedIn: 'root'
})
export class PersonaService {
  private keyService = inject(KeyService);
  readonly personas = signal<PersonaItem[]>([]);
  readonly isLoading = signal<boolean>(false);

  private getStorageKey(userId?: string): string {
    return userId ? `${BASE_STORAGE_KEY}_${userId}` : BASE_STORAGE_KEY;
  }

  private getCustomStorageKey(userId?: string): string {
    return userId ? `${CUSTOM_STORAGE_KEY}_${userId}` : CUSTOM_STORAGE_KEY;
  }

  getStoredPersonas(userId?: string): PersonaItem[] {
    const key = this.getStorageKey(userId);
    try {
      const raw = localStorage.getItem(key);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          return parsed.filter(p => !DUMMY_IDS.has(p.id) && p.creator_name !== 'Amour Core');
        }
      }
    } catch {}
    return [];
  }

  async fetchAndSyncPersonas(userId?: string): Promise<PersonaItem[]> {
    this.isLoading.set(true);
    const local = this.getStoredPersonas(userId);
    if (local.length > 0) {
      this.personas.set(local);
    }

    try {
      const endpoint = userId
        ? `/memory/personas/?creator_id=${encodeURIComponent(userId)}`
        : '/memory/personas/?scope=my_personas';

      for (const base of API_CONFIG.candidateUrls) {
        try {
          const res = await fetch(`${base}${endpoint}`);
          if (res.ok) {
            const serverList: PersonaItem[] = await res.json();
            if (Array.isArray(serverList)) {
              const valid = serverList.filter(p => !DUMMY_IDS.has(p.id) && p.creator_name !== 'Amour Core');
              this.personas.set(valid);
              try {
                localStorage.setItem(this.getStorageKey(userId), JSON.stringify(valid));
              } catch {}
              this.isLoading.set(false);
              return valid;
            }
          }
        } catch {}
      }
    } finally {
      this.isLoading.set(false);
    }

    return local;
  }

  async uploadPersonaAvatarToS3(base64Data: string, filename = 'avatar.jpg'): Promise<string | null> {
    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/memory/upload-image/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image_base64: base64Data, filename }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data?.url) return data.url;
        }
      } catch {}
    }
    return null;
  }

  async savePersonaToRoster(
    item: Omit<PersonaItem, 'id' | 'created_at'>,
    userId?: string
  ): Promise<PersonaItem> {
    const newId = 'persona-' + Date.now().toString(36) + '-' + Math.random().toString(36).substring(2, 6);
    const nowIso = new Date().toISOString();

    const newPersona: PersonaItem = {
      ...item,
      id: newId,
      creator_id: userId,
      created_at: nowIso,
    };

    const current = this.getStoredPersonas(userId);
    const updated = [newPersona, ...current.filter((p) => p.name.toLowerCase() !== newPersona.name.toLowerCase())];
    this.personas.set(updated);
    try {
      localStorage.setItem(this.getStorageKey(userId), JSON.stringify(updated));
    } catch {}

    // Post to backend
    const userKey = this.keyService.getOrCreateUserKey();
    const url = `${API_CONFIG.baseUrl}/memory/personas/?user_key=${encodeURIComponent(userKey)}`;
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: item.name,
          tagline: item.tagline,
          age: item.age,
          border_color: item.border_color,
          image_url: item.image_url,
          greeting: item.greeting,
          memory_prompt: item.memory_prompt,
          visibility: item.visibility,
          user_id: userId,
          user_key: userKey,
          publisher_name: item.publisher_name,
          publisher_handle: item.publisher_handle,
          publisher_avatar: item.publisher_avatar,
        }),
      });

      if (res.ok) {
        const savedFromServer: PersonaItem = await res.json();
        if (savedFromServer && savedFromServer.id) {
          const finalUpdated = updated.map((p) => (p.id === newId ? savedFromServer : p));
          this.personas.set(finalUpdated);
          try {
            localStorage.setItem(this.getStorageKey(userId), JSON.stringify(finalUpdated));
          } catch {}
          return savedFromServer;
        }
      }
    } catch (err) {
      console.error('[PersonaService] savePersonaToRoster error:', err);
    }

    return newPersona;
  }

  async updatePersonaMemory(
    id: string,
    updates: { memory_prompt?: string; greeting?: string; name?: string; tagline?: string },
    userId?: string
  ): Promise<PersonaItem | null> {
    this.savePersonaCustomization(id, updates, userId);

    const current = this.getStoredPersonas(userId);
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
      this.personas.set(updatedList);
      try {
        localStorage.setItem(this.getStorageKey(userId), JSON.stringify(updatedList));
      } catch {}
    }

    const userKey = this.keyService.getOrCreateUserKey();
    const patchUrl = `${API_CONFIG.baseUrl}/memory/personas/${encodeURIComponent(id)}/?user_key=${encodeURIComponent(userKey)}`;
    try {
      const res = await fetch(patchUrl, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...updates,
          user_id: userId,
          user_key: userKey,
        }),
      });
      if (res.ok) {
        const serverUpdated: PersonaItem = await res.json();
        if (serverUpdated && serverUpdated.id) {
          const finalUpdated = updatedList.map((p) => (p.id === id ? serverUpdated : p));
          this.personas.set(finalUpdated);
          try {
            localStorage.setItem(this.getStorageKey(userId), JSON.stringify(finalUpdated));
          } catch {}
          return serverUpdated;
        }
      }
    } catch (err) {
      console.error('[PersonaService] updatePersonaMemory error:', err);
    }
    return updatedPersona;
  }

  async deletePersonaFromRoster(personaId: string, userId?: string): Promise<boolean> {
    const current = this.getStoredPersonas(userId);
    const updated = current.filter((p) => p.id !== personaId);
    this.personas.set(updated);
    try {
      localStorage.setItem(this.getStorageKey(userId), JSON.stringify(updated));
    } catch {}

    for (const base of API_CONFIG.candidateUrls) {
      try {
        const res = await fetch(`${base}/memory/personas/${encodeURIComponent(personaId)}/`, {
          method: 'DELETE',
        });
        if (res.ok) return true;
      } catch {}
    }
    return true;
  }

  getPersonaCustomizations(userId?: string): Record<string, Partial<PersonaItem>> {
    try {
      const raw = localStorage.getItem(this.getCustomStorageKey(userId));
      if (raw) return JSON.parse(raw);
    } catch {}
    return {};
  }

  getPersonaCustomization(personaId: string, userId?: string): Partial<PersonaItem> | null {
    const customs = this.getPersonaCustomizations(userId);
    return customs[personaId] || null;
  }

  savePersonaCustomization(
    personaId: string,
    updates: Partial<PersonaItem>,
    userId?: string
  ): void {
    try {
      const customs = this.getPersonaCustomizations(userId);
      customs[personaId] = {
        ...(customs[personaId] || {}),
        ...updates,
        updated_at: new Date().toISOString(),
      };
      localStorage.setItem(this.getCustomStorageKey(userId), JSON.stringify(customs));
    } catch {}
  }
}
