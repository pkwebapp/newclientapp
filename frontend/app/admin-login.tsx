import { useState } from "react";
import { useRouter, useLocalSearchParams } from "expo-router";
import { Pressable, StyleSheet, Text, View, Platform, Linking } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { useAuth } from "@/src/context/AuthContext";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { useResponsive } from "@/src/hooks/use-responsive";
import { goBackOr } from "@/src/navigation/back";

import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { APP_DOMAIN, getAppSurface } from "@/src/navigation/host-routing";

export default function AdminLogin() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ mode?: string }>();
  const { signInWithToken, startGoogleLogin } = useAuth();
  const toast = useToast();
  const { isDesktop } = useResponsive();
  const surface = getAppSurface();

  const [mode, setMode] = useState<"login" | "register">(params.mode === "register" ? "register" : "login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const submit = async () => {
    if (!email.trim() || !password) {
      toast.show("Enter your email and password", "error");
      return;
    }
    setLoading(true);
    try {
      const path = mode === "login" ? "/auth/admin/login" : "/auth/admin/register";
      const body =
        mode === "login"
          ? { email: email.trim(), password }
          : { name: name.trim() || "Studio Admin", email: email.trim(), password };
      const res = await api.post(path, body);
      await signInWithToken(res.session_token);
      router.replace("/admin");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Login failed", "error");
    } finally {
      setLoading(false);
    }
  };

  const google = async () => {
    setGoogleLoading(true);
    try {
      await startGoogleLogin();
      if (Platform.OS !== "web") router.replace("/");
    } catch {
      toast.show("Google sign-in failed", "error");
    } finally {
      setGoogleLoading(false);
    }
  };

  if (surface === "client" || surface === "superadmin") {
    return (
      <View style={styles.restrictedContainer} testID="admin-login-restricted">
        <Text style={styles.restrictedTitle}>Studio sign-in is on its own workspace</Text>
        <Text style={styles.restrictedText}>Use the dedicated studio domain to keep client and platform access separate.</Text>
        <Button title="Open studio workspace" onPress={() => Linking.openURL(`${APP_DOMAIN.studio}/admin-login`)} icon="briefcase-outline" />
      </View>
    );
  }

  return (
    <View style={styles.container} testID="admin-login-screen">
      <GlassHeader title="Studio Sign In" onBack={() => goBackOr(router, "/")} topInset={insets.top} />
      <KeyboardAwareScrollView
        contentContainerStyle={[styles.body, isDesktop && styles.bodyDesktop, { paddingBottom: insets.bottom + spacing["2xl"] }]}
        bottomOffset={24}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.brandHeader}>
          <View style={styles.brandGlow} pointerEvents="none" />
          <View style={styles.brandRow}>
            <View style={styles.brandLogoDot}>
              <Ionicons name="aperture" size={20} color={colors.brand} />
            </View>
            <Text style={styles.brandName}>PIK CONNECT</Text>
            <View style={styles.brandBadge}>
              <Text style={styles.brandBadgeText}>STUDIO</Text>
            </View>
          </View>
          <Text style={styles.title}>{mode === "login" ? "Welcome back" : "Start your studio, free"}</Text>
          <Text style={styles.sub}>
            {mode === "login"
              ? "Sign in to manage galleries, uploads and client access."
              : "Create your studio workspace in under a minute — no card required."}
          </Text>
        </View>

        <View style={{ marginTop: spacing.xl }}>
          {mode === "register" && (
            <TextField
              testID="admin-name-input"
              label="Studio name"
              value={name}
              onChangeText={setName}
            />
          )}
          <TextField
            testID="admin-email-input"
            label="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
          />
          <TextField
            testID="admin-password-input"
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />
          {mode === "login" ? (
            <Pressable
              testID="forgot-password-link"
              onPress={() => router.push({ pathname: "/forgot-password", params: { email } })}
              style={styles.forgotRow}
              accessibilityRole="link"
            >
              <Text style={styles.forgotText}>Forgot password?</Text>
            </Pressable>
          ) : null}
          <Button
            testID="admin-submit-btn"
            title={mode === "login" ? "Sign in" : "Create account"}
            loading={loading}
            onPress={submit}
          />

          <View style={styles.divider}>
            <View style={styles.line} />
            <Text style={styles.or}>OR</Text>
            <View style={styles.line} />
          </View>

          <Button
            testID="admin-google-btn"
            title="Continue with Google"
            variant="secondary"
            icon="logo-google"
            loading={googleLoading}
            onPress={google}
          />

          <Pressable
            testID="admin-toggle-mode"
            onPress={() => setMode(mode === "login" ? "register" : "login")}
            style={{ marginTop: spacing.xl, alignItems: "center" }}
          >
            <Text style={styles.toggle}>
              {mode === "login" ? "New studio? Create an account" : "Already have an account? Sign in"}
            </Text>
          </Pressable>
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  restrictedContainer: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  restrictedTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], textAlign: "center" },
  restrictedText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 21, textAlign: "center", marginVertical: spacing.lg, maxWidth: 420 },
  container: { flex: 1, backgroundColor: colors.surface },
  body: { paddingHorizontal: spacing.xl, paddingTop: spacing.xl },
  bodyDesktop: { maxWidth: 460, width: "100%", alignSelf: "center", paddingTop: spacing["2xl"] },
  brandHeader: {
    backgroundColor: colors.brandTertiary,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.xl,
    overflow: "hidden",
  },
  brandGlow: { position: "absolute", top: -60, right: -40, width: 180, height: 180, borderRadius: 90, backgroundColor: "rgba(226,98,60,0.14)" },
  brandRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.lg },
  brandLogoDot: { width: 40, height: 40, borderRadius: radius.pill, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  brandName: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700", letterSpacing: 3, flex: 1 },
  brandBadge: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.pill, backgroundColor: colors.brand },
  brandBadgeText: { color: colors.onBrand, fontFamily: fonts.text, fontSize: 10, fontWeight: "800", letterSpacing: 1.5 },
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  sub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: spacing.xs },
  divider: { flexDirection: "row", alignItems: "center", marginVertical: spacing.xl },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.borderStrong },
  or: { color: colors.muted, marginHorizontal: spacing.md, fontFamily: fonts.text, fontSize: fontSize.sm },
  toggle: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base },
  superadminLink: { color: "#98A2B3", fontFamily: fonts.text, fontSize: fontSize.sm },
  forgotRow: { alignSelf: "flex-end", minHeight: 44, justifyContent: "center", marginTop: -spacing.sm, marginBottom: spacing.md, paddingHorizontal: spacing.xs },
  forgotText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
});
