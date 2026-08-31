import { useEffect, useState } from "react";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View, Linking, Platform } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "@/src/context/AuthContext";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { useResponsive } from "@/src/hooks/use-responsive";
import { goBackOr } from "@/src/navigation/back";
import {
  sendEmailOtp, verifyEmailOtp, sendMagicLink, signInWithGoogle,
} from "@/src/lib/auth-actions";

import { lightColors as colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { ThemeProvider } from "@/src/theme-context";
import { APP_DOMAIN, getAppSurface } from "@/src/navigation/host-routing";

export default function ClientLogin() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, signInAsMock, mockMode } = useAuth();
  const toast = useToast();
  const { isDesktop } = useResponsive();
  const surface = getAppSurface();

  const [step, setStep] = useState<"identify" | "verify">("identify");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [magicLoading, setMagicLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  // Auto-route once the Supabase session lands + backend confirms the role.
  useEffect(() => {
    if (user?.role === "client") router.replace("/client");
  }, [user, router]);

  const requestOtp = async () => {
    if (!email.trim()) {
      toast.show("Enter your email", "error");
      return;
    }
    setLoading(true);
    try {
      const { error } = await sendEmailOtp(email, "client");
      if (error) throw error;
      setStep("verify");
      toast.show("6-digit code sent. Check your inbox.", "success");
    } catch (e: any) {
      toast.show(e?.message || "Could not send code", "error");
    } finally {
      setLoading(false);
    }
  };

  const verify = async () => {
    if (code.length < 6) {
      toast.show("Enter the 6-digit code", "error");
      return;
    }
    setLoading(true);
    try {
      const { error } = await verifyEmailOtp(email, code);
      if (error) throw error;
      // AuthContext.onAuthStateChange picks up the new session.
    } catch (e: any) {
      toast.show(e?.message || "Verification failed", "error");
    } finally {
      setLoading(false);
    }
  };

  const magic = async () => {
    if (!email.trim()) { toast.show("Enter your email first", "error"); return; }
    setMagicLoading(true);
    try {
      const { error } = await sendMagicLink(email, "client");
      if (error) throw error;
      toast.show("Magic link sent — open it on this device.", "success");
    } catch (e: any) {
      toast.show(e?.message || "Could not send magic link", "error");
    } finally {
      setMagicLoading(false);
    }
  };

  const google = async () => {
    setGoogleLoading(true);
    try {
      await signInWithGoogle("client");
      if (Platform.OS !== "web") router.replace("/client");
    } catch (e: any) {
      toast.show(e?.message || "Google sign-in failed", "error");
    } finally {
      setGoogleLoading(false);
    }
  };

  if (surface === "studio" || surface === "superadmin") {
    return (
      <ThemeProvider scheme="light">
        <View style={styles.restrictedContainer} testID="client-login-restricted">
          <Text style={styles.restrictedTitle}>Client sign-in is on its own website</Text>
          <Text style={styles.restrictedText}>Use the client domain to access your galleries and bookings.</Text>
          <Button title="Open client website" onPress={() => Linking.openURL(`${APP_DOMAIN.client}/client-login`)} icon="sparkles-outline" />
        </View>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider scheme="light">
    <View style={styles.container} testID="client-login-screen">
      <GlassHeader
        title={step === "identify" ? "Sign in" : "Verify"}
        onBack={() => (step === "verify" ? setStep("identify") : goBackOr(router, "/"))}
        topInset={insets.top}
      />
      <KeyboardAwareScrollView
        contentContainerStyle={[styles.body, isDesktop && styles.bodyDesktop, { paddingBottom: insets.bottom + spacing["2xl"] }]}
        bottomOffset={24}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.iconWrap}>
          <Ionicons name="sparkles" size={28} color={colors.brand} />
        </View>

        {mockMode && (
          <View style={styles.demoBox}>
            <Text style={styles.demoLabel}>DEMO MODE · Supabase not configured</Text>
            <Text style={styles.demoHint}>Preview the client gallery without signing in.</Text>
            <Button
              testID="client-demo-btn"
              title="Enter Client Gallery (Demo)"
              icon="sparkles-outline"
              onPress={async () => {
                await signInAsMock("client");
                router.replace("/client");
              }}
            />
          </View>
        )}

        {step === "identify" ? (
          <>
            <Text style={styles.title}>Find your photos</Text>
            <Text style={styles.sub}>We’ll send a one-time code to verify it’s you.</Text>

            <View style={{ marginTop: spacing.xl }}>
              <TextField
                testID="client-identifier-input"
                label="Email address"
                value={email}
                onChangeText={setEmail}
                placeholder="you@example.com"
                autoCapitalize="none"
                keyboardType="email-address"
              />
              <Button testID="request-otp-btn" title="Send 6-digit code" loading={loading} onPress={requestOtp} />

              <Button
                testID="client-magic-btn"
                title="Send magic link instead"
                variant="secondary"
                icon="mail-outline"
                loading={magicLoading}
                onPress={magic}
              />

              <View style={styles.divider}>
                <View style={styles.line} />
                <Text style={styles.or}>OR</Text>
                <View style={styles.line} />
              </View>

              <Button
                testID="client-google-btn"
                title="Continue with Google"
                variant="secondary"
                icon="logo-google"
                loading={googleLoading}
                onPress={google}
              />
            </View>
          </>
        ) : (
          <>
            <Text style={styles.title}>Enter your code</Text>
            <Text style={styles.sub}>Sent to {email}</Text>
            <View style={{ marginTop: spacing.xl }}>
              <TextField
                testID="otp-code-input"
                label="6-digit code"
                value={code}
                onChangeText={setCode}
                placeholder="000000"
                keyboardType="number-pad"
                maxLength={6}
              />
              <Button testID="verify-otp-btn" title="Verify & continue" loading={loading} onPress={verify} />
              <Pressable testID="resend-otp" onPress={requestOtp} style={{ marginTop: spacing.lg, alignItems: "center" }}>
                <Text style={styles.toggle}>Resend code</Text>
              </Pressable>
            </View>
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
    </ThemeProvider>
  );
}

const styles = StyleSheet.create({
  restrictedContainer: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  restrictedTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], textAlign: "center" },
  restrictedText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 21, textAlign: "center", marginVertical: spacing.lg, maxWidth: 420 },
  container: { flex: 1, backgroundColor: colors.surface },
  body: { paddingHorizontal: spacing.xl, paddingTop: spacing["2xl"] },
  bodyDesktop: { maxWidth: 460, width: "100%", alignSelf: "center", paddingTop: spacing["3xl"] },
  iconWrap: {
    width: 60,
    height: 60,
    borderRadius: radius.pill,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  sub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: spacing.xs },
  divider: { flexDirection: "row", alignItems: "center", marginVertical: spacing.xl },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.borderStrong },
  or: { color: colors.muted, marginHorizontal: spacing.md, fontFamily: fonts.text, fontSize: fontSize.sm },
  toggle: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base },
  demoBox: { backgroundColor: colors.brandTertiary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.lg, marginBottom: spacing.xl },
  demoLabel: { color: colors.brand, fontFamily: fonts.text, fontSize: 11, fontWeight: "800", letterSpacing: 1.2, marginBottom: 4 },
  demoHint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginBottom: spacing.md },
});
