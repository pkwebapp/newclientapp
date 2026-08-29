import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Platform } from "react-native";
import * as WebBrowser from "expo-web-browser";
import * as Linking from "expo-linking";

import { api, setAuthToken } from "@/src/api/client";
import { LuxeLoader } from "@/src/components/ui";
import { storage } from "@/src/utils/storage";

WebBrowser.maybeCompleteAuthSession();

const TOKEN_KEY = "lumiere_session_token";
const GOOGLE_ROLE_KEY = "pik_google_role";

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
  token: string | null;
  loading: boolean;
  signInWithToken: (token: string) => Promise<User | null>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
  startGoogleLogin: (role?: "admin" | "client") => Promise<void>;
};

const AuthContext = createContext<AuthState>({} as AuthState);
export const useAuth = () => useContext(AuthContext);

const exchanged = new Set<string>();

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const applyToken = useCallback(async (t: string): Promise<User | null> => {
    setAuthToken(t);
    await storage.secureSet(TOKEN_KEY, t);
    setToken(t);
    try {
      const res = await api.get("/auth/me");
      setUser(res.user);
      return res.user;
    } catch {
      setAuthToken(null);
      await storage.secureRemove(TOKEN_KEY);
      setToken(null);
      setUser(null);
      return null;
    }
  }, []);

  const exchangeGoogle = useCallback(
    async (sessionId: string, role: "admin" | "client" = "admin") => {
      if (exchanged.has(sessionId)) return;
      exchanged.add(sessionId);
      const res = await api.post("/auth/session", { session_id: sessionId, role });
      await applyToken(res.session_token);
    },
    [applyToken]
  );

  // Bootstrap
  useEffect(() => {
    (async () => {
      try {
        // Web: handle Google OAuth redirect (session_id in url) FIRST.
        if (Platform.OS === "web" && typeof window !== "undefined") {
          const raw = window.location.hash + " " + window.location.search;
          const m = raw.match(/session_id=([^&#\s]+)/);
          if (m) {
            try {
              const savedRole = await storage.getItem<string>(GOOGLE_ROLE_KEY, "admin");
              await exchangeGoogle(decodeURIComponent(m[1]), savedRole === "client" ? "client" : "admin");
              await storage.removeItem(GOOGLE_ROLE_KEY);
              window.history.replaceState(window.history.state, "", window.location.pathname);
            } catch {}
            setLoading(false);
            return;
          }
        }
        const stored = await storage.secureGet<string>(TOKEN_KEY, "");
        if (stored) {
          setAuthToken(stored);
          setToken(stored);
          try {
            const res = await api.get("/auth/me");
            setUser(res.user);
          } catch {
            setAuthToken(null);
            await storage.secureRemove(TOKEN_KEY);
            setToken(null);
          }
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [exchangeGoogle]);

  const signInWithToken = useCallback((t: string) => applyToken(t), [applyToken]);

  const signOut = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {}
    setAuthToken(null);
    await storage.secureRemove(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const res = await api.get("/auth/me");
      setUser(res.user);
    } catch {}
  }, []);

  const startGoogleLogin = useCallback(async (role: "admin" | "client" = "admin") => {
    await storage.setItem(GOOGLE_ROLE_KEY, role);
    if (Platform.OS === "web") {
      const redirect = window.location.origin + "/";
      window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirect)}`;
      return;
    }
    const redirectUrl = Linking.createURL("");
    const authUrl = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;

    let captured: string | null = null;
    const sub = Linking.addEventListener("url", (e) => {
      if (e.url) captured = e.url;
    });
    try {
      const result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUrl);
      let url: string | null = result.type === "success" ? result.url : null;
      if (!url) url = captured;
      if (!url) url = await Linking.getInitialURL();
      if (url) {
        const m = url.match(/[?#&]session_id=([^&#]+)/);
        if (m) await exchangeGoogle(decodeURIComponent(m[1]), role);
      }
    } finally {
      sub.remove();
      await storage.removeItem(GOOGLE_ROLE_KEY);
    }
  }, [exchangeGoogle]);

  if (loading) return <LuxeLoader title="Loading PIK Connect" subtitle="Preparing your galleries…" />;


  return (
    <AuthContext.Provider
      value={{ user, token, loading, signInWithToken, signOut, refresh, startGoogleLogin }}
    >
      {children}
    </AuthContext.Provider>
  );
}
