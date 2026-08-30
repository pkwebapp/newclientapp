import { Platform } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';

import { supabase } from './supabase';
import { getRedirectUri } from './redirect';

WebBrowser.maybeCompleteAuthSession();

export type Role = 'admin' | 'client';

/** Sign up with email+password. Role is set in user_metadata so the backend
 * knows whether to create a studio or client account on first login. */
export async function signUpWithPassword(params: {
  email: string; password: string; role: Role; name?: string;
}) {
  const { email, password, role, name } = params;
  return supabase.auth.signUp({
    email: email.trim().toLowerCase(),
    password,
    options: {
      emailRedirectTo: getRedirectUri(),
      data: {
        role,
        ...(name ? { name } : {}),
      },
    },
  });
}

export async function signInWithPassword(email: string, password: string) {
  return supabase.auth.signInWithPassword({
    email: email.trim().toLowerCase(),
    password,
  });
}

/** Send a magic link. The email template must contain {{ .ConfirmationURL }}. */
export async function sendMagicLink(email: string, role: Role) {
  return supabase.auth.signInWithOtp({
    email: email.trim().toLowerCase(),
    options: {
      emailRedirectTo: getRedirectUri(),
      shouldCreateUser: true,
      data: { role },
    },
  });
}

/** Send a 6-digit email OTP. The email template must contain {{ .Token }}. */
export async function sendEmailOtp(email: string, role: Role) {
  return supabase.auth.signInWithOtp({
    email: email.trim().toLowerCase(),
    options: {
      shouldCreateUser: true,
      data: { role },
    },
  });
}

export async function verifyEmailOtp(email: string, token: string) {
  return supabase.auth.verifyOtp({
    email: email.trim().toLowerCase(),
    token: token.trim(),
    type: 'email',
  });
}

export async function sendPasswordReset(email: string) {
  return supabase.auth.resetPasswordForEmail(email.trim().toLowerCase(), {
    redirectTo: getRedirectUri(),
  });
}

export async function updatePassword(newPassword: string) {
  return supabase.auth.updateUser({ password: newPassword });
}

/** Google OAuth. On web it does a full-page redirect. On native it opens the
 * system browser and returns via deep link into /auth/callback. */
export async function signInWithGoogle(role: Role) {
  const redirectTo = getRedirectUri();
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo,
      skipBrowserRedirect: Platform.OS !== 'web',
      queryParams: { role },
    },
  });
  if (error) throw error;
  if (Platform.OS === 'web') return; // SDK triggers window.location redirect

  if (data?.url) {
    // Capture the deep-link back before returning from the browser.
    let deepLinkUrl: string | null = null;
    const sub = Linking.addEventListener('url', (e) => { deepLinkUrl = e.url; });
    try {
      const result = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
      let hit: string | null = result.type === 'success' ? result.url : null;
      if (!hit) hit = deepLinkUrl;
      if (!hit) hit = await Linking.getInitialURL();
      if (hit) {
        // Extract tokens from the URL fragment/query and set the session
        // manually (the SDK doesn't auto-detect on native).
        const m = hit.split('#')[1] || hit.split('?')[1] || '';
        const params = new URLSearchParams(m);
        const access_token = params.get('access_token');
        const refresh_token = params.get('refresh_token');
        if (access_token) {
          await supabase.auth.setSession({
            access_token,
            refresh_token: refresh_token ?? '',
          });
        }
      }
    } finally {
      sub.remove();
    }
  }
}

export async function signOut() {
  return supabase.auth.signOut();
}
