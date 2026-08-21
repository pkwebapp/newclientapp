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
