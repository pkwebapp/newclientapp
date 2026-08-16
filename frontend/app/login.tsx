import { useRouter } from "expo-router";
import { StyleSheet, Text, View, Dimensions } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { Button } from "@/src/components/ui";
import { colors, fonts, fontSize, spacing } from "@/src/theme";

const HERO =
  "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwxfHxjaW5lbWF0aWMlMjBkYXJrJTIwcGhvdG9ncmFwaHklMjBzdHVkaW8lMjBjYW1lcmF8ZW58MHx8fHwxNzg2ODIzMDE5fDA&ixlib=rb-4.1.0&q=85";

export default function Landing() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const h = Dimensions.get("window").height;

  return (
    <View style={styles.container} testID="landing-screen">
      <Image source={{ uri: HERO }} style={StyleSheet.absoluteFill} contentFit="cover" />
      <LinearGradient
        colors={["rgba(13,13,13,0.2)", "rgba(13,13,13,0.75)", "rgba(13,13,13,0.98)"]}
        locations={[0, 0.5, 1]}
        style={StyleSheet.absoluteFill}
      />
      <View style={[styles.content, { paddingTop: insets.top + spacing["3xl"], paddingBottom: insets.bottom + spacing.xl }]}>
        <View style={styles.top}>
          <View style={styles.logoRow}>
            <Ionicons name="aperture-outline" size={26} color={colors.brand} />
            <Text style={styles.logo}>PIK CONNECT</Text>
          </View>
        </View>

        <View style={{ flex: 1, justifyContent: "flex-end" }}>
          <Text style={styles.title}>Your moments,{"\n"}found in an instant.</Text>
          <Text style={styles.subtitle}>
            Take a selfie and we'll surface every photo of you from the event gallery.
          </Text>

          <View style={{ marginTop: spacing["2xl"], gap: spacing.md }}>
            <Button
              testID="continue-client-btn"
              title="Find my photos"
              icon="sparkles"
              onPress={() => router.push("/client-login")}
            />
            <Button
              testID="continue-admin-btn"
              title="Studio sign in"
              variant="ghost"
              icon="briefcase-outline"
              onPress={() => router.push("/admin-login")}
            />
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  content: { flex: 1, paddingHorizontal: spacing.xl },
  top: { alignItems: "flex-start" },
  logoRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  logo: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, letterSpacing: 4, fontWeight: "600" },
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.hero, lineHeight: 46 },
  subtitle: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.lg, marginTop: spacing.md, lineHeight: 24, maxWidth: 320 },
});
