import { Injectable } from '@angular/core';
import { API_CONFIG } from './config';

const SECURE_STORE_KEY = 'amour_reeve_user_memory_key';

const WORDLIST = [
  'abandon', 'ability', 'able', 'about', 'above', 'absent', 'absorb', 'abstract',
  'absurd', 'abuse', 'access', 'accident', 'account', 'accuse', 'achieve', 'acid',
  'acoustic', 'acquire', 'across', 'act', 'action', 'actor', 'actress', 'actual',
  'adapt', 'add', 'addict', 'address', 'adjust', 'admit', 'adult', 'advance',
  'advice', 'aerobic', 'affair', 'afford', 'afraid', 'again', 'age', 'agent',
  'agree', 'ahead', 'aim', 'air', 'airport', 'aisle', 'alarm', 'album',
  'alcohol', 'alert', 'alien', 'all', 'alley', 'allow', 'almost', 'alone',
  'alpha', 'already', 'also', 'alter', 'always', 'amateur', 'amazing', 'among',
  'amount', 'amused', 'analyst', 'anchor', 'ancient', 'anger', 'angle', 'angry',
  'animal', 'ankle', 'announce', 'annual', 'another', 'answer', 'antenna', 'antique',
  'anxiety', 'any', 'apart', 'apology', 'appear', 'apple', 'approve', 'april',
  'arch', 'arctic', 'area', 'arena', 'argue', 'arm', 'armed', 'armor',
  'army', 'around', 'arrange', 'arrest', 'arrive', 'arrow', 'art', 'artefact',
  'artist', 'artwork', 'ask', 'aspect', 'assault', 'asset', 'assist', 'assume',
  'asthma', 'athlete', 'atom', 'attack', 'attend', 'attitude', 'attract', 'auction',
  'audit', 'august', 'aunt', 'author', 'auto', 'autumn', 'average', 'avocado',
];

function toHex(buffer: Uint8Array): string {
  return Array.from(buffer)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function fromHex(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.substring(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

@Injectable({
  providedIn: 'root'
})
export class KeyService {
  getLocalMemoryKey(): string | null {
    try {
      return localStorage.getItem(SECURE_STORE_KEY);
    } catch {
      return null;
    }
  }

  saveLocalMemoryKey(keyHex: string): void {
    try {
      localStorage.setItem(SECURE_STORE_KEY, keyHex);
    } catch (e) {
      console.warn('[KeyService] Could not save memory key:', e);
    }
  }

  getOrCreateUserKey(): string {
    let key = this.getLocalMemoryKey();
    if (!key) {
      const randomBytes = new Uint8Array(32);
      window.crypto.getRandomValues(randomBytes);
      key = toHex(randomBytes);
      this.saveLocalMemoryKey(key);
    }
    return key;
  }

  generateRecoveryPhrase(): string {
    const words: string[] = [];
    const randomBytes = new Uint8Array(12);
    window.crypto.getRandomValues(randomBytes);
    for (let i = 0; i < 12; i++) {
      const index = randomBytes[i] % WORDLIST.length;
      words.push(WORDLIST[index]);
    }
    return words.join(' ');
  }

  async sha256Hex(str: string): Promise<string> {
    const encoder = new TextEncoder();
    const data = encoder.encode(str);
    const hashBuffer = await window.crypto.subtle.digest('SHA-256', data);
    return toHex(new Uint8Array(hashBuffer));
  }

  async deriveKEK(phrase: string, saltHex: string): Promise<string> {
    const normalized = phrase.trim().toLowerCase().replace(/\s+/g, ' ');
    let current = `${normalized}:${saltHex}`;
    for (let i = 0; i < 2000; i++) {
      current = await this.sha256Hex(current);
    }
    return current;
  }

  async encryptMemoryKeyWithPhrase(phrase: string): Promise<{
    salt: string;
    nonce: string;
    encryptedBlob: string;
  }> {
    const rawKey = this.getOrCreateUserKey();
    const saltBytes = new Uint8Array(16);
    const nonceBytes = new Uint8Array(12);
    window.crypto.getRandomValues(saltBytes);
    window.crypto.getRandomValues(nonceBytes);

    const saltHex = toHex(saltBytes);
    const nonceHex = toHex(nonceBytes);
    const kek = await this.deriveKEK(phrase, saltHex);
    const keyBytes = fromHex(rawKey);

    // Authenticated stream encryption with KEK + nonce matching mobile keyService
    const encKeyHash = await this.sha256Hex(`${kek}:enc:${nonceHex}`);
    const macKeyHash = await this.sha256Hex(`${kek}:mac:${nonceHex}`);

    const streamBytes = fromHex(encKeyHash);
    const ciphertextBytes = new Uint8Array(keyBytes.length);
    for (let i = 0; i < keyBytes.length; i++) {
      ciphertextBytes[i] = keyBytes[i] ^ streamBytes[i % streamBytes.length];
    }
    const ciphertextHex = toHex(ciphertextBytes);

    const authTag = await this.sha256Hex(`${macKeyHash}:${ciphertextHex}:${nonceHex}:${saltHex}`);
    const encryptedBlob = `v1:${ciphertextHex}:${authTag}`;

    return { salt: saltHex, nonce: nonceHex, encryptedBlob };
  }

  async decryptMemoryKeyWithPhrase(
    phrase: string,
    saltHex: string,
    nonceHex: string,
    encryptedBlob: string
  ): Promise<string | null> {
    try {
      const parts = encryptedBlob.split(':');
      if (parts.length !== 3 || parts[0] !== 'v1') return null;

      const ciphertextHex = parts[1];
      const providedAuthTag = parts[2];
      const kek = await this.deriveKEK(phrase, saltHex);

      const macKeyHash = await this.sha256Hex(`${kek}:mac:${nonceHex}`);
      const computedAuthTag = await this.sha256Hex(`${macKeyHash}:${ciphertextHex}:${nonceHex}:${saltHex}`);

      if (computedAuthTag !== providedAuthTag) {
        return null; // authentication tag mismatch (wrong phrase)
      }

      const encKeyHash = await this.sha256Hex(`${kek}:enc:${nonceHex}`);
      const streamBytes = fromHex(encKeyHash);
      const ciphertextBytes = fromHex(ciphertextHex);
      const keyBytes = new Uint8Array(ciphertextBytes.length);
      for (let i = 0; i < ciphertextBytes.length; i++) {
        keyBytes[i] = ciphertextBytes[i] ^ streamBytes[i % streamBytes.length];
      }

      return toHex(keyBytes);
    } catch {
      return null;
    }
  }

  async backupEncryptedKeyToServer(
    userId: string,
    phrase: string,
    token?: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const rawUserKey = this.getOrCreateUserKey();
      const { salt, nonce, encryptedBlob } = await this.encryptMemoryKeyWithPhrase(phrase);
      const res = await fetch(`${API_CONFIG.baseUrl}/memory/key-backup/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Memory-User-Key': rawUserKey,
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          user_id: userId,
          user_key: rawUserKey,
          encrypted_blob: encryptedBlob,
          salt,
          nonce
        })
      });

      if (res.ok) {
        return { success: true };
      }
      const data = await res.json().catch(() => ({}));
      return { success: false, error: data?.error || `HTTP ${res.status}` };
    } catch (e: any) {
      return { success: false, error: e?.message || 'Network error' };
    }
  }

  async restoreKeyFromServerWithPhrase(
    userId: string,
    phrase: string,
    token?: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const res = await fetch(`${API_CONFIG.baseUrl}/memory/key-backup/?user_id=${encodeURIComponent(userId)}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        }
      });

      if (!res.ok) {
        return { success: false, error: 'No encrypted key backup found for this account.' };
      }

      const data = await res.json();
      if (!data.encrypted_blob || !data.salt || !data.nonce) {
        return { success: false, error: 'Incomplete backup data found.' };
      }

      const plainKey = await this.decryptMemoryKeyWithPhrase(phrase, data.salt, data.nonce, data.encrypted_blob);
      if (!plainKey) {
        return { success: false, error: 'Invalid 12-word recovery phrase. Authentication tag mismatch.' };
      }

      this.saveLocalMemoryKey(plainKey);
      return { success: true };
    } catch (e: any) {
      return { success: false, error: e?.message || 'Network error' };
    }
  }
}
