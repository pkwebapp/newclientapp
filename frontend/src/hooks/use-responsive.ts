import { useWindowDimensions } from "react-native";

/**
 * Central breakpoint helper so the app can adapt between a mobile (phone /
 * Expo Go) layout and a desktop / wide-web layout.
 *
 * Desktop chrome (sidebar shell, multi-column panels) only activates at
 * `isDesktop` so the native mobile experience stays exactly as before.
 */
export const DESKTOP_BREAKPOINT = 900;
export const TABLET_BREAKPOINT = 600;

// Width of the persistent desktop sidebar + the capped main content column.
export const SIDEBAR_WIDTH = 264;
export const CONTENT_MAX_WIDTH = 768;

export function useResponsive() {
  const { width, height } = useWindowDimensions();
  return {
    width,
    height,
    isDesktop: width >= DESKTOP_BREAKPOINT,
    isTablet: width >= TABLET_BREAKPOINT && width < DESKTOP_BREAKPOINT,
    isPhone: width < TABLET_BREAKPOINT,
  };
}
