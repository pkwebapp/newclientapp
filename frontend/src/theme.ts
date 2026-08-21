import { Platform } from "react-native";

// Palette from design_guidelines.json — Glass / Luxe (DARK)
export const colors = {
  surface: "#0D0D0D",
  onSurface: "#F5F5F5",
  surfaceSecondary: "#1A1A1A",
  onSurfaceSecondary: "#E0E0E0",
  surfaceTertiary: "#262626",
  onSurfaceTertiary: "#CCCCCC",
  surfaceInverse: "#F5F5F5",
  onSurfaceInverse: "#0D0D0D",
  brand: "#D4AF37",
  brandSecondary: "#E5C76B",
  onBrand: "#0D0D0D",
  brandTertiary: "#332D1C",
  onBrandTertiary: "#D4AF37",
  success: "#2E4D36",
  onSuccess: "#84C298",
  warning: "#5C431A",
  onWarning: "#E8BA71",
  error: "#591C1C",
  onError: "#E88282",
  border: "#262626",
  borderStrong: "#404040",
  divider: "#1A1A1A",
  muted: "#8A8A8A",
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
