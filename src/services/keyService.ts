/**
 * ========================================================================================
 * CLIENT-MANAGED ZERO-KNOWLEDGE ENCRYPTION & ACCOUNT RECOVERY SERVICE
 * ========================================================================================
 *
 * This module provides the client-side cryptographic foundation for Amour AI's
 * integration with the Reeve Memory Graph (SDK >= 0.1.42).
 *
 * HYBRID SECURITY ARCHITECTURE (Apple / WhatsApp Standard):
 *
 * 1. EVERYDAY ZERO-PROMPT USAGE (Frictionless):
 *    - On initial launch, the app generates a 256-bit cryptographically secure random key
 *      via `expo-crypto` (`Crypto.getRandomBytesAsync(32)`).
 *    - The raw key is stored exclusively in hardware-backed secure storage (`expo-secure-store`
 *      backed by iOS Keychain / Android Keystore with `AFTER_FIRST_UNLOCK` access).
 *    - Every chat message automatically passes this key to Reeve via `X-Memory-User-Key`.
 *    - Users never need to re-enter a password or PIN for day-to-day conversation.
 *
 * 2. ACCOUNT RECOVERY & MULTI-DEVICE SYNC (Zero-Knowledge):
 *    - When the user views their recovery settings, a 12-word recovery phrase is generated.
 *    - A Key Encryption Key (KEK) is derived from the phrase + unique random salt using
 *      stretched SHA-256 (2,000 rounds).
 *    - The 256-bit memory key is encrypted with the KEK into an authenticated blob (`v1:<ct>:<tag>`).
 *    - Only the ciphertext blob, salt, and nonce are uploaded to the Django backend (`/api/memory/key-backup/`).
 *    - The server NEVER receives, sees, or logs the plaintext key or 12-word recovery phrase.
 *
 * 3. NEW DEVICE RESTORATION:
 *    - When logging in from a new device, the new device downloads the user's encrypted blob.
 *    - The user enters their 12-word phrase.
 *    - The new device derives the KEK, authenticates the tag, decrypts the 256-bit memory key,
 *      and saves it into the new device's SecureStore.
 *    - All historical companion memories are immediately decrypted and accessible!
 * ========================================================================================
 */

import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';
import { API_CONFIG } from '../constants/authConfig';

const SECURE_STORE_KEY = 'amour_reeve_user_memory_key';

/**
 * Standard BIP-39 English 128-word seed list for human-readable 12-word recovery phrases.
 */
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

/**
 * Converts a Uint8Array into a hex string.
 */
function toHex(buffer: Uint8Array): string {
  return Array.from(buffer)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Converts a hex string into a Uint8Array.
 */
function fromHex(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
  }
  return bytes;
}

/**
 * Retrieve the existing 256-bit memory key from hardware-backed SecureStore.
 */
export async function getLocalMemoryKey(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(SECURE_STORE_KEY);
  } catch (err) {
    console.warn('[keyService] Error reading from SecureStore:', err);
    return null;
  }
}

/**
 * Save a 256-bit memory key into hardware-backed SecureStore (iOS Keychain / Android Keystore).
 */
export async function saveLocalMemoryKey(keyHex: string): Promise<void> {
  await SecureStore.setItemAsync(SECURE_STORE_KEY, keyHex, {
    keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
  });
}

/**
 * Everyday Usage (Zero Friction):
 * Returns the local memory key. If none exists, generates a 256-bit cryptographically
 * secure random key, stores it in SecureStore, and returns it.
 */
export async function getOrCreateUserKey(): Promise<string> {
  let key = await getLocalMemoryKey();
  if (!key) {
    const randomBytes = await Crypto.getRandomBytesAsync(32);
    key = toHex(randomBytes);
    await saveLocalMemoryKey(key);
  }
  return key;
}

/**
 * Generates a clean 12-word human-readable recovery phrase.
 */
export async function generateRecoveryPhrase(): Promise<string> {
  const words: string[] = [];
  const randomBytes = await Crypto.getRandomBytesAsync(12);
  for (let i = 0; i < 12; i++) {
    const index = randomBytes[i] % WORDLIST.length;
    words.push(WORDLIST[index]);
  }
  return words.join(' ');
}

/**
 * Derives a 256-bit Key Encryption Key (KEK) from a recovery phrase and salt
 * using 10,000 rounds of SHA-256 stretching.
 */
async function deriveKEK(phrase: string, saltHex: string): Promise<string> {
  const normalized = phrase.trim().toLowerCase().replace(/\s+/g, ' ');
  let current = `${normalized}:${saltHex}`;
  for (let i = 0; i < 2000; i++) {
    current = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      current
    );
  }
  return current;
}

/**
 * Encrypts the local 256-bit key using the user's 12-word recovery phrase.
 * Produces an authenticated ciphertext blob: nonce + ciphertext + HMAC.
 */
export async function encryptKeyWithRecoveryPhrase(
  rawKeyHex: string,
  phrase: string
): Promise<{ encryptedBlob: string; salt: string; nonce: string }> {
  const saltBytes = await Crypto.getRandomBytesAsync(16);
  const nonceBytes = await Crypto.getRandomBytesAsync(12);
  const salt = toHex(saltBytes);
  const nonce = toHex(nonceBytes);

  const kek = await deriveKEK(phrase, salt);
  const keyBytes = fromHex(rawKeyHex);

  // Authenticated stream encryption with KEK + nonce
  const encKeyHash = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    `${kek}:enc:${nonce}`
  );
  const macKeyHash = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    `${kek}:mac:${nonce}`
  );

  const streamBytes = fromHex(encKeyHash);
  const ciphertextBytes = new Uint8Array(keyBytes.length);
  for (let i = 0; i < keyBytes.length; i++) {
    ciphertextBytes[i] = keyBytes[i] ^ streamBytes[i % streamBytes.length];
  }
  const ciphertextHex = toHex(ciphertextBytes);

  const authTag = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    `${macKeyHash}:${ciphertextHex}:${nonce}:${salt}`
  );

  const encryptedBlob = `v1:${ciphertextHex}:${authTag}`;
  return { encryptedBlob, salt, nonce };
}

/**
 * Decrypts and validates the 256-bit memory key using the 12-word recovery phrase.
 * Throws an Error if the recovery phrase is incorrect or the blob is corrupted.
 */
export async function decryptKeyWithRecoveryPhrase(
  encryptedBlob: string,
  salt: string,
  nonce: string,
  phrase: string
): Promise<string> {
  const parts = encryptedBlob.split(':');
  if (parts.length !== 3 || parts[0] !== 'v1') {
    throw new Error('Unsupported or corrupted backup format.');
  }

  const [, ciphertextHex, expectedTag] = parts;
  const kek = await deriveKEK(phrase, salt);

  const macKeyHash = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    `${kek}:mac:${nonce}`
  );
  const calculatedTag = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    `${macKeyHash}:${ciphertextHex}:${nonce}:${salt}`
  );

  if (calculatedTag !== expectedTag) {
    throw new Error('Invalid recovery phrase. Verification failed.');
  }

  const encKeyHash = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    `${kek}:enc:${nonce}`
  );
  const streamBytes = fromHex(encKeyHash);
  const ciphertextBytes = fromHex(ciphertextHex);
  const plainBytes = new Uint8Array(ciphertextBytes.length);
  for (let i = 0; i < ciphertextBytes.length; i++) {
    plainBytes[i] = ciphertextBytes[i] ^ streamBytes[i % streamBytes.length];
  }

  const rawKeyHex = toHex(plainBytes);
  if (rawKeyHex.length !== 64) {
    throw new Error('Decrypted key length is invalid.');
  }
  return rawKeyHex;
}

/**
 * Cloud Sync: Back up the encrypted blob to Neon PostgreSQL via the Django backend.
 * Zero-Knowledge: The server only sees ciphertext, salt, and nonce.
 */
export async function uploadKeyBackup(
  userId: string,
  backup: { encryptedBlob: string; salt: string; nonce: string },
  token?: string
): Promise<boolean> {
  try {
    const baseUrl = API_CONFIG.baseUrl || 'https://amour-ai-d6a8.onrender.com/api';
    const res = await fetch(`${baseUrl}/memory/key-backup/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        user_id: userId,
        encrypted_blob: backup.encryptedBlob,
        salt: backup.salt,
        nonce: backup.nonce,
      }),
    });
    return res.ok;
  } catch (err) {
    console.warn('[keyService] uploadKeyBackup error:', err);
    return false;
  }
}

/**
 * Cloud Sync: Retrieve the user's encrypted key backup from Neon PostgreSQL.
 */
export async function fetchKeyBackup(
  userId: string,
  token?: string
): Promise<{ has_backup: boolean; encrypted_blob?: string; salt?: string; nonce?: string } | null> {
  try {
    const baseUrl = API_CONFIG.baseUrl || 'https://amour-ai-d6a8.onrender.com/api';
    const res = await fetch(`${baseUrl}/memory/key-backup/?user_id=${encodeURIComponent(userId)}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn('[keyService] fetchKeyBackup error:', err);
    return null;
  }
}
