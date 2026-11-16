import AsyncStorage from '@react-native-async-storage/async-storage';

export type ReplyLengthOption = 'default' | 'short' | 'long';

export const REPLY_LENGTH_KEY = '@amour_reply_length';

/**
 * Retrieve the saved reply length preference.
 * Defaults to 'default' (the original adaptive prompt).
 */
export async function getReplyLengthPreference(): Promise<ReplyLengthOption> {
  try {
    const value = await AsyncStorage.getItem(REPLY_LENGTH_KEY);
    if (value === 'short' || value === 'long' || value === 'default') {
      return value;
    }
  } catch {
    // Fallback gracefully on storage error
  }
  return 'default';
}

/**
 * Persist the user's chosen reply length preference locally.
 */
export async function setReplyLengthPreference(length: ReplyLengthOption): Promise<void> {
  try {
    await AsyncStorage.setItem(REPLY_LENGTH_KEY, length);
  } catch {
    // Non-blocking catch
  }
}
