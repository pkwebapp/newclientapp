import { Redirect, Stack } from "expo-router";
import Head from "expo-router/head";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/src/context/AuthContext";
import { useResponsive } from "@/src/hooks/use-responsive";
import { MobileShell } from "@/src/components/MobileShell";
import { DesktopShell } from "@/src/components/DesktopShell";

import { colors, fonts, fontSize } from "@/src/theme";
import { getAppSurface } from "@/src/navigation/host-routing";

/**
 * Auth gate for all /client/* routes.
 *
 * See app/admin/_layout.tsx for the rationale — this prevents the refresh race
 * where a client screen fetches/loads images before the session token is
 * restored from storage, surfacing as 401 "Not authenticated" + missing photos.
 */
export default function ClientLayout() {
  const { user, loading } = useAuth();
  const { isDesktop } = useResponsive();
  const surface = getAppSurface();

  if (surface === "studio" || surface === "superadmin") return <Redirect href="/" />;

  if (loading) {
    return (
      <View style={styles.container} testID="client-auth-loading">
        <Text style={styles.brand}>PIK Connect</Text>
        <ActivityIndicator color={colors.brand} style={{ marginTop: 16 }} />
      </View>
    );
  }

  if (!user) return <Redirect href="/client-login" />;
  if (user.role !== "client") return <Redirect href="/" />;

  const stack = <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface } }} />;
  const noindex = (
    <Head>
      <meta name="robots" content="noindex, nofollow" />
    </Head>
  );

  if (isDesktop) return <DesktopShell role="client">{noindex}{stack}</DesktopShell>;
  return <MobileShell role="client">{noindex}{stack}</MobileShell>;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  brand: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize.hero, letterSpacing: 2 },
});
