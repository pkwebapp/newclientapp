import { Platform } from 'react-native';
import { makeRedirectUri } from 'expo-auth-session';

/**
 * Redirect URI used for magic-link / password-reset / Google OAuth.
 *
 * - Web: https://<host>/auth/callback
 * - Native (Expo Go): exp://<host>/--/auth/callback
 * - Native (standalone): pikconnect://auth/callback (matches app.json scheme)
 *
 * All returned values MUST be added to Supabase Auth -> URL Configuration.
 */
export function getRedirectUri(): string {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    return `${window.location.origin}/auth/callback`;
  }
  return makeRedirectUri({ path: 'auth/callback', scheme: 'pikconnect' });
}
