import React, { createContext, useContext, useEffect, useMemo, useRef, useState, useCallback } from "react";
import { AppState, Platform } from "react-native";
import type { Session } from "@supabase/supabase-js";

import { api, setAuthToken } from "@/src/api/client";
import { LuxeLoader } from "@/src/components/ui";
import { storage } from "@/src/utils/storage";
import { supabase, isSupabaseConfigured } from "@/src/lib/supabase";
import { signOut as supabaseSignOut } from "@/src/lib/auth-actions";

// Legacy opaque token — used ONLY for the super admin login.
const LEGACY_TOKEN_KEY = "pik_legacy_session_token";

// DEV/mock mode: when Supabase keys are not configured we let admin/client into
// their dashboards with a fake session so the UI can be built/reviewed without
// a backend auth wired up. Data calls still 401 (empty states) until the real
// API is added. Persisted so a browser refresh keeps you signed in.
const MOCK_ROLE_KEY = "pik_mock_role";
const MOCK_USERS: Record<"admin" | "client", User> = {
  admin: {
    user_id: "mock_admin",
    role: "admin",
    name: "Demo Studio",
    email: "demo@studio.test",
    profile_complete: true,
    studio_profile: { studio_name: "Demo Studio", contact_name: "Demo Admin" },
  },
  client: {
    user_id: "mock_client",
    role: "client",
    name: "Demo Client",
    email: "demo@client.test",
  },
};

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
  /** DEV/mock: true when Supabase is not configured (demo dashboards allowed). */
  mockMode: boolean;
  /** DEV/mock: enter an admin/client dashboard without Supabase configured. */
  signInAsMock: (role: "admin" | "client") => Promise<User | null>;
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
  const mockRoleRef = useRef<"admin" | "client" | null>(null);

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

  // Bootstrap: load legacy token (for superadmin) + hydrate Supabase session.
  // When Supabase is NOT configured we run in DEV/mock mode: restore a saved
  // mock admin/client session so the dashboards stay reachable for UI work.
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        legacyTokenRef.current = (await storage.secureGet<string>(LEGACY_TOKEN_KEY, "")) || null;

        if (!isSupabaseConfigured) {
          if (legacyTokenRef.current) {
            // Real demo session (dev-login token) OR super admin — has backend data.
            if (!mounted) return;
            setAuthToken(legacyTokenRef.current);
            setToken(legacyTokenRef.current);
            await fetchMe();
          } else {
            const mockRole = (await storage.secureGet<string>(MOCK_ROLE_KEY, "")) || "";
            if (!mounted) return;
            if (mockRole === "admin" || mockRole === "client") {
              mockRoleRef.current = mockRole;
              setUser(MOCK_USERS[mockRole]);
            }
          }
          return;
        }

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

    // Auth state changes — only meaningful when Supabase is configured.
    let sub: { subscription: { unsubscribe: () => void } } | null = null;
    if (isSupabaseConfigured) {
      const res = supabase.auth.onAuthStateChange((_event, next) => {
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
      sub = res.data;
    }

    // AppState background/foreground auto-refresh (native only)
    let appStateSub: { remove: () => void } | null = null;
    if (Platform.OS !== "web" && isSupabaseConfigured) {
      appStateSub = AppState.addEventListener("change", (state) => {
        if (state === "active") supabase.auth.startAutoRefresh();
        else supabase.auth.stopAutoRefresh();
      });
    }

    return () => {
      mounted = false;
      sub?.subscription.unsubscribe();
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

  const signInAsMock = useCallback(async (role: "admin" | "client"): Promise<User | null> => {
    mockRoleRef.current = role;
    // Preferred: get a REAL backend session token from the dev-only endpoint so
    // demo mode exercises the full API with real data. This mirrors the final
    // (Supabase) flow exactly — same screens, same data path.
    try {
      const res: any = await api.post("/auth/dev/mock-login", { role });
      if (res?.token) {
        const u = await signInWithLegacyToken(res.token);
        if (u) {
          await storage.secureRemove(MOCK_ROLE_KEY);
          return u;
        }
      }
    } catch {
      // dev endpoint disabled (e.g. production) — fall through to a UI-only mock
    }
    // Fallback: render the dashboards with a fake user (no backend token → empty data).
    await storage.secureSet(MOCK_ROLE_KEY, role);
    setAuthToken(null);
    setToken(null);
    setSession(null);
    setUser(MOCK_USERS[role]);
    setLoading(false);
    return MOCK_USERS[role];
  }, [signInWithLegacyToken]);

  const refresh = useCallback(async () => {
    await fetchMe();
  }, [fetchMe]);

  const signOut = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch {}
    try { await supabaseSignOut(); } catch {}
    legacyTokenRef.current = null;
    mockRoleRef.current = null;
    await storage.secureRemove(LEGACY_TOKEN_KEY);
    await storage.secureRemove(MOCK_ROLE_KEY);
    setAuthToken(null);
    setToken(null);
    setSession(null);
    setUser(null);
  }, []);

  // Memoized for the same reason the toast context is (see ui.tsx): useAuth() is read by
  // nearly every screen, often inside an effect that reloads data on mount, so a fresh object
  // here on every unrelated re-render of AuthProvider would retrigger those effects constantly.
  const value = useMemo(
    () => ({ user, session, token, loading, mockMode: !isSupabaseConfigured, signInWithLegacyToken, signInAsMock, refresh, signOut }),
    [user, session, token, loading, signInWithLegacyToken, signInAsMock, refresh, signOut]
  );

  if (loading) {
    return <LuxeLoader title="Loading PIK Connect" subtitle="Preparing your galleries…" />;
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
