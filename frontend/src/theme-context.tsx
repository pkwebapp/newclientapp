import React, { createContext, useContext, useMemo } from "react";

import { colors as darkColors, lightColors, Palette } from "@/src/theme";

type Scheme = "dark" | "light";
type ThemeValue = { colors: Palette; scheme: Scheme };

const ThemeContext = createContext<ThemeValue>({ colors: darkColors, scheme: "dark" });

/** Scopes a palette to a subtree. Shared components read it via usePalette().
 *  Default (no provider) is the dark studio theme, so admin surfaces are untouched. */
export function ThemeProvider({ scheme, children }: { scheme: Scheme; children: React.ReactNode }) {
  const value = useMemo<ThemeValue>(
    () => ({ colors: scheme === "light" ? lightColors : darkColors, scheme }),
    [scheme]
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function usePalette(): ThemeValue {
  return useContext(ThemeContext);
}

/** Memoized palette-aware StyleSheet factory. */
export function useThemedStyles<T>(factory: (colors: Palette) => T): T {
  const { colors } = usePalette();
  return useMemo(() => factory(colors), [factory, colors]);
}
