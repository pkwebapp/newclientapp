import { Platform } from "react-native";

export type AppSurface = "client" | "studio" | "superadmin" | "preview";

/**
 * Web host routing is intentionally conservative: unknown hosts remain on the
 * shared preview surface, while production role domains get isolated entry
 * points and route guards. Native builds use the shared preview behavior.
 */
export function getAppSurface(): AppSurface {
  if (Platform.OS !== "web" || typeof window === "undefined") return "preview";
  const hostname = window.location.hostname.toLowerCase().replace(/^www\./, "");
  if (hostname === "pikconnect.com") return "client";
  if (hostname === "studio.pikconnect.com") return "studio";
  if (hostname === "myspace.pikconnect.com") return "superadmin";
  return "preview";
}

export const APP_DOMAIN = {
  client: "https://pikconnect.com",
  studio: "https://studio.pikconnect.com",
  superadmin: "https://myspace.pikconnect.com",
} as const;
