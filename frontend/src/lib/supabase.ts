import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';
import { Platform } from 'react-native';

const url = process.env.EXPO_PUBLIC_SUPABASE_URL as string;
const key = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY as string;

if (!url || !key) {
  // eslint-disable-next-line no-console
  console.warn('[supabase] Missing EXPO_PUBLIC_SUPABASE_URL / EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY');
}

// On web the URL fragment holds tokens after magic-link / OAuth. Let the SDK
// parse it (it does so once) so getSession() returns the fresh session.
const detectSessionInUrl = Platform.OS === 'web';

export const supabase = createClient(url ?? '', key ?? '', {
  auth: {
    storage: Platform.OS === 'web' ? undefined : (AsyncStorage as any),
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl,
    flowType: 'implicit',
  },
});
