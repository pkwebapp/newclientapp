import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";

import { api, ApiError, setAuthToken } from "@/src/api/client";
import { LuxeLoader } from "@/src/components/ui";
import { storage } from "@/src/utils/storage";

// Bearer token persisted across launches — a phone JWT or an opaque session
// token (Google sign-in / super admin). Same key on both sides (write here,
// read here) so a refresh restores the session.
const TOKEN_KEY = "pik_legacy_session_token";

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
  token: string | null;    // The bearer we attach to backend calls
  loading: boolean;
  /** Persist a backend-issued token (phone JWT / session token) and load the user.
   * Resolves with the user, or null if the token was rejected. */
  signInWithToken: (token: string) => Promise<User | null>;
  /** Re-fetch the local user profile. */
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState>({} as AuthState);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const applyToken = useCallback((t: string | null) => {
    setAuthToken(t);
    setToken(t);
  }, []);

  const clearToken = useCallback(async () => {
    applyToken(null);
    await storage.secureRemove(TOKEN_KEY);
  }, [applyToken]);

  /** Load /auth/me. Returns the user, or null when the token is invalid (401). */
  const fetchMe = useCallback(async (): Promise<User | null> => {
    try {
      const res = await api.get("/auth/me");
      setUser(res.user);
      return res.user;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        await clearToken();
        setUser(null);
        return null;
      }
      // Network / server hiccup: keep the stored token so a retry can succeed.
      console.error("[auth] /auth/me failed", e);
      throw e;
    }
  }, [clearToken]);

  // Bootstrap: restore the stored token and validate it once.
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const stored = (await storage.secureGet<string>(TOKEN_KEY, "")) || null;
        if (!mounted) return;
        if (stored) {
          applyToken(stored);
          try {
            await fetchMe();
          } catch {
            // Offline / backend down — stay logged out for now, token is kept.
          }
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [applyToken, fetchMe]);

  const signInWithToken = useCallback(async (t: string): Promise<User | null> => {
    applyToken(t);
    await storage.secureSet(TOKEN_KEY, t);
    const u = await fetchMe();
    if (!u) await clearToken();
    return u;
  }, [applyToken, clearToken, fetchMe]);

  const refresh = useCallback(async () => {
    try {
      await fetchMe();
    } catch {}
  }, [fetchMe]);

  const signOut = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch {}
    await clearToken();
    setUser(null);
  }, [clearToken]);

  // Memoized for the same reason the toast context is (see ui.tsx): useAuth() is read by
  // nearly every screen, often inside an effect that reloads data on mount, so a fresh object
  // here on every unrelated re-render of AuthProvider would retrigger those effects constantly.
  const value = useMemo(
    () => ({ user, token, loading, signInWithToken, refresh, signOut }),
    [user, token, loading, signInWithToken, refresh, signOut]
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
