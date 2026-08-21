import { Redirect, Stack } from "expo-router";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/src/context/AuthContext";
import { useResponsive } from "@/src/hooks/use-responsive";
import { DesktopShell } from "@/src/components/DesktopShell";
import { MobileShell } from "@/src/components/MobileShell";
import { colors, fonts, fontSize } from "@/src/theme";

/**
 * Auth gate for all /admin/* routes.
 *
 * Protected screens fetch data in their focus effects and load images with the
 * bearer token from the API client. On a hard browser refresh the AuthProvider
 * bootstrap (reading the token from storage) is async, so without this gate the
 * screen can fire requests before the token is applied -> 401 "Not authenticated"
 * and empty/broken photos. Gating on `loading`/`user` guarantees the token is
 * restored and validated before any admin screen mounts.
 */
export default function AdminLayout() {
  const { user, loading } = useAuth();
  const { isDesktop } = useResponsive();

  if (loading) {
    return (
      <View style={styles.container} testID="admin-auth-loading">
        <Text style={styles.brand}>PK Photography</Text>
        <ActivityIndicator color={colors.brand} style={{ marginTop: 16 }} />
      </View>
    );
  }

  if (!user) return <Redirect href="/admin-login" />;
  if (user.role !== "admin") return <Redirect href="/" />;

  const stack = <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface } }} />;

  if (isDesktop) return <DesktopShell role="admin">{stack}</DesktopShell>;
  return <MobileShell role="admin">{stack}</MobileShell>;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  brand: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize.hero, letterSpacing: 2 },
});
