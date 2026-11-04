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

/**
 * Fetch all persona conversations for the given user ID.
 * Returns sorted list of conversation threads with decrypted latest messages and timestamps.
 */
export async function fetchUserConversations(
  userId: string,
  token?: string
): Promise<ConversationItem[]> {
  if (!userId) return [];
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);

  try {
    const userKey = await getOrCreateUserKey();
    const baseUrl = API_CONFIG.baseUrl || 'https://amour-ai-d6a8.onrender.com/api';
    const res = await fetch(`${baseUrl}/memory/conversations/?user_id=${encodeURIComponent(userId)}`, {
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
      console.warn(`[conversationService] fetchUserConversations HTTP ${res.status}`);
      return [];
    }
    const data = await res.json();
    return (data.conversations || []) as ConversationItem[];
  } catch (err: any) {
    clearTimeout(timer);
    console.warn('[conversationService] fetchUserConversations error:', err?.message || err);
    return [];
  }
}
