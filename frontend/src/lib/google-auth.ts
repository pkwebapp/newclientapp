/**
 * Google sign-in via Emergent Auth.
 *
 * 1. `startGoogleSignIn(role)` sends the user to Emergent's Google login.
 * 2. Google drops them back on our login route with `#session_id=<one-time id>`.
 * 3. The login screen (see `useGoogleSignIn`) POSTs it to our backend
 *    `/api/auth/session`, which returns a normal bearer `session_token`.
 *
 * The frontend never talks to Emergent's API directly — only the backend does.
 */
import { Platform } from "react-native";
import * as WebBrowser from "expo-web-browser";
import * as Linking from "expo-linking";

WebBrowser.maybeCompleteAuthSession();

export type GoogleRole = "admin" | "client";

const AUTH_URL = "https://auth.emergentagent.com/";
/** Route we land back on — must exist in expo-router. */
const RETURN_ROUTE: Record<GoogleRole, string> = { admin: "admin-login", client: "client-login" };

/** Emergent returns the id in the hash fragment; match the raw string so both
 * `#session_id=` and `?session_id=` work everywhere. */
export function extractSessionId(url?: string | null): string | null {
  if (!url) return null;
  const m = url.match(/[?#&]session_id=([^&#]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

function redirectUrl(role: GoogleRole): string {
  if (Platform.OS === "web" && typeof window !== "undefined") {
    return `${window.location.origin}/${RETURN_ROUTE[role]}`;
  }
  return Linking.createURL(RETURN_ROUTE[role]);
}

/**
 * Kick off Google sign-in.
 * - Web: full-page redirect (this promise never meaningfully resolves).
 * - Native: opens the system auth session and resolves with the `session_id`,
 *   or `null` if the user really cancelled.
 */
export async function startGoogleSignIn(role: GoogleRole): Promise<string | null> {
  const redirect = redirectUrl(role);
  const authUrl = `${AUTH_URL}?redirect=${encodeURIComponent(redirect)}`;

  if (Platform.OS === "web") {
    window.location.href = authUrl;
    return null;
  }

  // Android Custom Tabs often report "dismiss" even when the deep link was
  // delivered — capture it from every source before deciding it was cancelled.
  let captured: string | null = null;
  const sub = Linking.addEventListener("url", (e) => {
    captured = captured ?? extractSessionId(e.url);
  });
  try {
    const result = await WebBrowser.openAuthSessionAsync(authUrl, redirect);
    let sid = result.type === "success" ? extractSessionId(result.url) : null;
    if (!sid) sid = captured;
    if (!sid) sid = extractSessionId(await Linking.getInitialURL());
    return sid;
  } finally {
    sub.remove();
  }
}

/** Web only: read a `session_id` off the current page URL (hash or query). */
export function readWebSessionId(): string | null {
  if (Platform.OS !== "web" || typeof window === "undefined") return null;
  return extractSessionId(window.location.hash) ?? extractSessionId(window.location.search);
}

/** Web only: strip just the `session_id` param, keeping everything else. */
export function clearWebSessionId(): void {
  if (Platform.OS !== "web" || typeof window === "undefined") return;
  const strip = (s: string, lead: string) => {
    const params = new URLSearchParams(s.replace(/^[?#]/, ""));
    params.delete("session_id");
    const rest = params.toString();
    return rest ? `${lead}${rest}` : "";
  };
  const search = strip(window.location.search, "?");
  const hash = strip(window.location.hash, "#");
  window.history.replaceState(window.history.state, "", `${window.location.pathname}${search}${hash}`);
}

// A session_id is single-use. Re-mounts, hot deep links and the auth-session
// result can all surface the same one — only the first caller may exchange it.
const consumed = new Set<string>();
export function claimSessionId(id: string): boolean {
  if (consumed.has(id)) return false;
  consumed.add(id);
  return true;
}
