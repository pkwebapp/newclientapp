import { Platform } from "react-native";

// Palette aligned with pkphotography.in — warm charcoal + signature orange.
export const colors = {
  surface: "#0E0D0C",
  onSurface: "#F5F1EA",
  surfaceSecondary: "#161514",
  onSurfaceSecondary: "#E4DFD6",
  surfaceTertiary: "#242220",
  onSurfaceTertiary: "#CFC9BE",
  surfaceInverse: "#EEEAE1",
  onSurfaceInverse: "#161514",
  brand: "#E2623C",
  brandSecondary: "#EF8055",
  onBrand: "#FFFFFF",
  brandTertiary: "#2B201A",
  onBrandTertiary: "#E2623C",
  success: "#24402C",
  onSuccess: "#8FD1A2",
  warning: "#5C431A",
  onWarning: "#E8BA71",
  error: "#5A1E1A",
  onError: "#E88A7E",
  border: "#2A2724",
  borderStrong: "#403B35",
  divider: "#161514",
  muted: "#8A857D",
  shellBlur: "rgba(14,13,12,0.82)",
};

export type Palette = typeof colors;

// Warm mid-tone light palette — used by the public marketing pages and the
// client-facing surface (see src/theme-context.tsx). Same semantic keys.
export const lightColors: Palette = {
  surface: "#D8D0C4",
  onSurface: "#241D16",
  surfaceSecondary: "#EDE7DC",
  onSurfaceSecondary: "#4A4238",
  surfaceTertiary: "#E0D8CA",
  onSurfaceTertiary: "#5C544A",
  surfaceInverse: "#241D16",
  onSurfaceInverse: "#F5F1EA",
  brand: "#E2623C",
  brandSecondary: "#C8532F",
  onBrand: "#FFFFFF",
  brandTertiary: "#F0DACB",
  onBrandTertiary: "#C8532F",
  success: "#DCE8DA",
  onSuccess: "#2F6B40",
  warning: "#F0E3C4",
  onWarning: "#7E5C12",
  error: "#F1D6CF",
  onError: "#B03A2A",
  border: "#C7BEB0",
  borderStrong: "#B0A695",
  divider: "#CFC7B9",
  muted: "#7C7365",
  shellBlur: "rgba(233,226,214,0.88)",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, "2xl": 32, "3xl": 48 };
export const radius = { sm: 6, md: 12, lg: 20, pill: 999 };
export const fontSize = { sm: 12, base: 14, lg: 16, xl: 20, "2xl": 24, "3xl": 32, hero: 40 };

// Robust system fonts: serif for premium display, system sans for body.
export const fonts = {
  display: Platform.select({ ios: "Georgia", android: "serif", default: "Georgia" }) as string,
  text: Platform.select({ ios: "System", android: "sans-serif", default: "System" }) as string,
};

export const categoryMeta: Record<string, { label: string; icon: string }> = {
  portrait: { label: "Portrait", icon: "person" },
  wedding: { label: "Wedding", icon: "heart" },
  event: { label: "Events", icon: "star" },
  corporate: { label: "Corporate", icon: "briefcase" },
  school: { label: "School", icon: "school" },
  studio: { label: "Studio", icon: "camera" },
  nightlife: { label: "Nightlife", icon: "moon" },
};
