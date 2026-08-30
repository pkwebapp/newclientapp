import { useEffect } from 'react';
import { ActivityIndicator, StyleSheet, View, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import * as Linking from 'expo-linking';

import { supabase } from '@/src/lib/supabase';
import { colors } from '@/src/theme';

/**
 * Auth redirect handler for Supabase magic links / OAuth / password reset.
 *
 * On web: detectSessionInUrl=true in the Supabase client processes the URL
 * automatically; we just wait for the session to appear and route out.
 *
 * On native: we parse the deep link explicitly and hand tokens to setSession.
 */
export default function AuthCallback() {
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;

    const finish = () => {
      if (cancelled) return;
      // Route based on the role in user_metadata. Falls back to /client.
      supabase.auth.getSession().then(({ data }) => {
        const role = (data.session?.user?.user_metadata as any)?.role;
        if (role === 'admin') router.replace('/admin');
        else router.replace('/client');
      });
    };

    const parseAndSet = async (url: string | null) => {
      if (!url) return;
      // Recovery links: land on a screen that lets the user pick a new password.
      if (url.includes('type=recovery') || url.includes('reset')) {
        router.replace('/forgot-password?stage=set');
        return;
      }
      const hash = url.includes('#') ? url.split('#')[1] : '';
      const query = url.includes('?') ? url.split('?')[1].split('#')[0] : '';
      const p = new URLSearchParams(hash || query);
      const access_token = p.get('access_token');
      const refresh_token = p.get('refresh_token');
      const token_hash = p.get('token_hash');
      const type = p.get('type');
      if (access_token) {
        await supabase.auth.setSession({
          access_token,
          refresh_token: refresh_token ?? '',
        });
      } else if (token_hash && type) {
        // OTP link flow (rare on native)
        await supabase.auth.verifyOtp({ token_hash, type: type as any });
      }
    };

    if (Platform.OS === 'web') {
      // Wait a tick for detectSessionInUrl to process the fragment.
      const t = setTimeout(finish, 400);
      return () => { cancelled = true; clearTimeout(t); };
    }

    (async () => {
      const initial = await Linking.getInitialURL();
      await parseAndSet(initial);
      finish();
    })();

    const sub = Linking.addEventListener('url', ({ url }) => {
      parseAndSet(url).then(finish);
    });
    return () => { cancelled = true; sub.remove(); };
  }, [router]);

  return (
    <View style={styles.wrap}>
      <ActivityIndicator color={colors.brand} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
});
