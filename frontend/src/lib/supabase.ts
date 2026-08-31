import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';
import { Platform } from 'react-native';

const url = process.env.EXPO_PUBLIC_SUPABASE_URL as string;
const key = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY as string;

/** True only when both Supabase env vars are present. */
export const isSupabaseConfigured = Boolean(url && key);

if (!isSupabaseConfigured) {
  // eslint-disable-next-line no-console
  console.warn(
    '[supabase] Missing EXPO_PUBLIC_SUPABASE_URL / EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY — ' +
      'auth is disabled until these are configured. Public pages still render.',
  );
}

// On web the URL fragment holds tokens after magic-link / OAuth. Let the SDK
// parse it (it does so once) so getSession() returns the fresh session.
const detectSessionInUrl = Platform.OS === 'web';

// NOTE: createClient() throws synchronously ("supabaseUrl is required") when the
// URL/key are empty, which would crash the entire JS bundle at import time and
// blank out every screen — including public pages that don't need auth. When the
// env is not configured we fall back to a harmless placeholder so the app still
// boots; real auth calls simply fail (handled by callers) instead of white-screening.
export const supabase = createClient(
  isSupabaseConfigured ? url : 'https://placeholder.supabase.co',
  isSupabaseConfigured ? key : 'placeholder-anon-key',
  {
    auth: {
      storage: Platform.OS === 'web' ? undefined : (AsyncStorage as any),
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl,
      flowType: 'implicit',
    },
  },
);
