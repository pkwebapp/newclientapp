import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import { AppState, Platform } from "react-native";
import type { Session } from "@supabase/supabase-js";

import { api, setAuthToken } from "@/src/api/client";
import { LuxeLoader } from "@/src/components/ui";
import { storage } from "@/src/utils/storage";
import { supabase } from "@/src/lib/supabase";
import { signOut as supabaseSignOut } from "@/src/lib/auth-actions";

// Legacy opaque token — used ONLY for the super admin login.
const LEGACY_TOKEN_KEY = "pik_legacy_session_token";

export type User = {
  user_id: string;
  role: "admin" | "client" | "superadmin";
  name?: string;
  email?: string;
  phone?: string;
  picture?: string;
  profile_complete?: boolean;
  studio_profile?: Record<string, any> | null;
  uploads_disabled?: boolean;
};

type AuthState = {
  user: User | null;
  session: Session | null; // Supabase session for admin/client, null for superadmin
  token: string | null;    // The bearer we attach to backend calls
  loading: boolean;
  /** Superadmin sign-in helper — accepts the legacy opaque token. */
  signInWithLegacyToken: (token: string) => Promise<User | null>;
  /** Called after any Supabase auth event to refresh local user profile. */
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState>({} as AuthState);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const legacyTokenRef = useRef<string | null>(null);

  /** Compute the effective bearer token. Supabase JWT wins over legacy. */
  const applyEffectiveToken = useCallback((sb: Session | null) => {
    const t = sb?.access_token || legacyTokenRef.current || null;
    setAuthToken(t);
    setToken(t);
  }, []);

  const fetchMe = useCallback(async (): Promise<User | null> => {
    try {
      const res = await api.get("/auth/me");
      setUser(res.user);
      return res.user;
    } catch {
      return null;
    }
  }, []);

  // Bootstrap: load legacy token (for superadmin) + hydrate Supabase session
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        legacyTokenRef.current = (await storage.secureGet<string>(LEGACY_TOKEN_KEY, "")) || null;
        const { data } = await supabase.auth.getSession();
        if (!mounted) return;
        setSession(data.session);
        applyEffectiveToken(data.session);
        // If we have any token, fetch the local user profile.
        if (data.session?.access_token || legacyTokenRef.current) {
          await fetchMe();
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();

    // Auth state changes (sign-in, sign-out, token refresh, magic link)
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      // Avoid awaiting async work synchronously inside the callback
      setTimeout(async () => {
        setSession(next);
        applyEffectiveToken(next);
        if (next?.access_token) {
          // A Supabase login supersedes any stale legacy session.
          if (legacyTokenRef.current) {
            legacyTokenRef.current = null;
            await storage.secureRemove(LEGACY_TOKEN_KEY);
          }
          await fetchMe();
        } else if (!legacyTokenRef.current) {
          setUser(null);
        }
      }, 0);
    });

    // AppState background/foreground auto-refresh (native only)
    let appStateSub: { remove: () => void } | null = null;
    if (Platform.OS !== "web") {
      appStateSub = AppState.addEventListener("change", (state) => {
        if (state === "active") supabase.auth.startAutoRefresh();
        else supabase.auth.stopAutoRefresh();
      });
    }

    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
      appStateSub?.remove();
    };
  }, [applyEffectiveToken, fetchMe]);

  const signInWithLegacyToken = useCallback(async (t: string): Promise<User | null> => {
    legacyTokenRef.current = t;
    await storage.secureSet(LEGACY_TOKEN_KEY, t);
    // Clear any stale Supabase session so we don't accidentally send the wrong token.
    try { await supabase.auth.signOut(); } catch {}
    setAuthToken(t);
    setToken(t);
    const u = await fetchMe();
    if (!u) {
      legacyTokenRef.current = null;
      await storage.secureRemove(LEGACY_TOKEN_KEY);
      setAuthToken(null);
      setToken(null);
    }
    return u;
  }, [fetchMe]);

  const refresh = useCallback(async () => {
    await fetchMe();
  }, [fetchMe]);

  const signOut = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch {}
    try { await supabaseSignOut(); } catch {}
    legacyTokenRef.current = null;
    await storage.secureRemove(LEGACY_TOKEN_KEY);
    setAuthToken(null);
    setToken(null);
    setSession(null);
    setUser(null);
  }, []);

  if (loading) {
    return <LuxeLoader title="Loading PIK Connect" subtitle="Preparing your galleries…" />;
  }

  return (
    <AuthContext.Provider
      value={{ user, session, token, loading, signInWithLegacyToken, refresh, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}
