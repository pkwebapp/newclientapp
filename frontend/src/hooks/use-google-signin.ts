import { useCallback, useEffect, useRef, useState } from "react";
import { Platform } from "react-native";
import * as Linking from "expo-linking";

import { api } from "@/src/api/client";
import { useAuth } from "@/src/context/AuthContext";
import { useToast } from "@/src/components/ui";
import {
  claimSessionId,
  clearWebSessionId,
  extractSessionId,
  readWebSessionId,
  startGoogleSignIn,
  type GoogleRole,
} from "@/src/lib/google-auth";

/**
 * "Continue with Google" for a login screen.
 *
 * Returns `start()` for the button and `loading`. On mount it also looks for a
 * `session_id` (web URL / native deep link) and finishes the sign-in, so the
 * same screen handles both the outbound click and the inbound redirect.
 */
export function useGoogleSignIn(role: GoogleRole) {
  const { signInWithToken } = useAuth();
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const roleRef = useRef(role);
  roleRef.current = role;

  const exchange = useCallback(
    async (sessionId: string) => {
      if (!claimSessionId(sessionId)) return;
      setLoading(true);
      try {
        const res = await api.post("/auth/session", { session_id: sessionId, role: roleRef.current });
        const u = await signInWithToken(res.session_token);
        if (!u) throw new Error("Could not complete Google sign-in. Please try again.");
        clearWebSessionId();
      } catch (e: any) {
        console.error("[google-auth] session exchange failed", e);
        toast.show(e?.message || "Google sign-in failed", "error");
        clearWebSessionId();
      } finally {
        setLoading(false);
      }
    },
    [signInWithToken, toast]
  );

  // Inbound: finish a sign-in that redirected back to this screen.
  useEffect(() => {
    const fromWeb = readWebSessionId();
    if (fromWeb) {
      exchange(fromWeb);
      return;
    }
    if (Platform.OS === "web") return;
    Linking.getInitialURL().then((url) => {
      const sid = extractSessionId(url);
      if (sid) exchange(sid);
    });
    const sub = Linking.addEventListener("url", (e) => {
      const sid = extractSessionId(e.url);
      if (sid) exchange(sid);
    });
    return () => sub.remove();
  }, [exchange]);

  // Outbound: the button.
  const start = useCallback(async () => {
    setLoading(true);
    try {
      const sid = await startGoogleSignIn(roleRef.current);
      if (Platform.OS === "web") return; // page is navigating away
      if (sid) await exchange(sid);
      else toast.show("Google sign-in was cancelled", "info");
    } catch (e: any) {
      console.error("[google-auth] start failed", e);
      toast.show(e?.message || "Could not open Google sign-in", "error");
    } finally {
      if (Platform.OS !== "web") setLoading(false);
    }
  }, [exchange, toast]);

  return { start, loading };
}
