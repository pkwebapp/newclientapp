import React, { useEffect, useState } from "react";
import { useRouter } from "expo-router";
import {
  Pressable, StyleSheet, Text, View, Linking,
} from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "@/src/context/AuthContext";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { PhoneField, isPhoneNumberValid } from "@/src/components/PhoneField";
import { useResponsive } from "@/src/hooks/use-responsive";
import { goBackOr } from "@/src/navigation/back";
import { sendPhoneOtp, verifyPhoneOtp, loginWithPhonePassword, completePhoneSetup } from "@/src/lib/phone-auth";
import { setAuthToken } from "@/src/api/client";

import { lightColors as colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { ThemeProvider } from "@/src/theme-context";
import { APP_DOMAIN, getAppSurface } from "@/src/navigation/host-routing";

type LoginTab = "otp" | "password";

export default function ClientLogin() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, signInWithLegacyToken } = useAuth();
  const toast = useToast();
  const { isDesktop } = useResponsive();
  const surface = getAppSurface();

  const [loginTab, setLoginTab] = useState<LoginTab>("otp");
  const [step, setStep] = useState<"phone" | "verify" | "setup">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [pwPhone, setPwPhone] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  // One-time setup step (new users): name asked at sign-in + optional password.
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);

  // Auto-route once the backend confirms role.
  useEffect(() => {
    if (user?.role === "client") router.replace("/client");
  }, [user, router]);

  // ── OTP flow ──────────────────────────────────────────────────────────────
  const requestOtp = async () => {
    if (!isPhoneNumberValid(phone)) {
      toast.show("Enter a valid mobile number", "error");
      return;
    }
    setLoading(true);
    try {
      const res = await sendPhoneOtp(phone, "client");
      setDevCode(res.dev_code ?? null);
      setStep("verify");
      toast.show("OTP sent to your mobile", "success");
    } catch (e: any) {
      toast.show(e?.message || "Could not send OTP", "error");
    } finally {
      setLoading(false);
    }
  };

  const verifyOtp = async () => {
    if (code.length < 6) {
      toast.show("Enter the 6-digit OTP", "error");
      return;
    }
    setLoading(true);
    try {
      const res = await verifyPhoneOtp(phone, code, "client");
      if (res.is_new) {
        // First-time user — collect their name (and an optional password) before
        // dropping them into the app. Authenticate the setup call with the phone
        // JWT WITHOUT completing sign-in yet (so we don't redirect prematurely).
        setPendingToken(res.token);
        setAuthToken(res.token);
        setName("");
        setNewPassword("");
        setStep("setup");
        return;
      }
      // Returning user — sign in straight away.
      const u = await signInWithLegacyToken(res.token);
      if (!u) throw new Error("Authentication failed. Please try again.");
    } catch (e: any) {
      toast.show(e?.message || "Verification failed", "error");
    } finally {
      setLoading(false);
    }
  };

  // ── First-time setup: name (required) + password (min 4, optional) ──────────
  const finishSetup = async () => {
    if (!name.trim()) {
      toast.show("Please enter your name", "error");
      return;
    }
    if (newPassword && newPassword.length < 4) {
      toast.show("Password must be at least 4 characters", "error");
      return;
    }
    if (!pendingToken) {
      toast.show("Session expired. Please sign in again.", "error");
      setStep("phone");
      return;
    }
    setLoading(true);
    try {
      await completePhoneSetup(name.trim(), newPassword || undefined);
      const u = await signInWithLegacyToken(pendingToken);
      if (!u) throw new Error("Could not finish setup. Please try again.");
    } catch (e: any) {
      toast.show(e?.message || "Could not save your details", "error");
    } finally {
      setLoading(false);
    }
  };

  // ── Password flow ─────────────────────────────────────────────────────────
  const loginPassword = async () => {
    if (!isPhoneNumberValid(pwPhone)) {
      toast.show("Enter a valid mobile number", "error");
      return;
    }
    if (!password) {
      toast.show("Enter your password", "error");
      return;
    }
    setLoading(true);
    try {
      const res = await loginWithPhonePassword(pwPhone, password);
      const u = await signInWithLegacyToken(res.token);
      if (!u) throw new Error("Authentication failed. Please try again.");
    } catch (e: any) {
      toast.show(e?.message || "Sign-in failed", "error");
    } finally {
      setLoading(false);
    }
  };

  if (surface === "studio" || surface === "superadmin") {
    return (
      <ThemeProvider scheme="light">
        <View style={styles.restrictedContainer} testID="client-login-restricted">
          <Text style={styles.restrictedTitle}>Client sign-in is on its own website</Text>
          <Text style={styles.restrictedText}>
            Use the client domain to access your galleries and bookings.
          </Text>
          <Button
            title="Open client website"
            onPress={() => Linking.openURL(`${APP_DOMAIN.client}/client-login`)}
            icon="sparkles-outline"
          />
        </View>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider scheme="light">
      <View style={styles.container} testID="client-login-screen">
        <GlassHeader
          title={step === "phone" ? "Sign in" : step === "setup" ? "Almost there" : "Verify"}
          onBack={() => {
            if (step === "setup") {
              // Abandon the half-finished setup: drop the pending token and
              // start over from the phone step.
              setAuthToken(null);
              setPendingToken(null);
              setStep("phone");
              setCode("");
            } else if (step === "verify") {
              setStep("phone");
            } else {
              goBackOr(router, "/");
            }
          }}
          topInset={insets.top}
        />
        <KeyboardAwareScrollView
          contentContainerStyle={[
            styles.body,
            isDesktop && styles.bodyDesktop,
            { paddingBottom: insets.bottom + spacing["2xl"] },
          ]}
          bottomOffset={24}
          keyboardShouldPersistTaps="handled"
        >
          {/* Brand icon */}
          <View style={styles.iconWrap}>
            <Ionicons name="sparkles" size={28} color={colors.brand} />
          </View>

          {/* Login method tabs (hidden during first-time setup) */}
          {step !== "setup" && (
          <View style={styles.tabs}>
            <Pressable
              testID="tab-otp"
              style={[styles.tab, loginTab === "otp" && styles.tabActive]}
              onPress={() => { setLoginTab("otp"); setStep("phone"); setDevCode(null); }}
            >
              <Ionicons
                name="phone-portrait-outline"
                size={15}
                color={loginTab === "otp" ? colors.brand : colors.muted}
              />
              <Text style={[styles.tabText, loginTab === "otp" && styles.tabTextActive]}>
                OTP
              </Text>
            </Pressable>
            <Pressable
              testID="tab-password"
              style={[styles.tab, loginTab === "password" && styles.tabActive]}
              onPress={() => setLoginTab("password")}
            >
              <Ionicons
                name="lock-closed-outline"
                size={15}
                color={loginTab === "password" ? colors.brand : colors.muted}
              />
              <Text style={[styles.tabText, loginTab === "password" && styles.tabTextActive]}>
                Password
              </Text>
            </Pressable>
          </View>
          )}

          {/* ── OTP tab ─────────────────────────────────────────────── */}
          {loginTab === "otp" && step !== "setup" && (
            <>
              {step === "phone" ? (
                <>
                  <Text style={styles.title}>Find your photos</Text>
                  <Text style={styles.sub}>
                    Enter your mobile number — we&apos;ll send a verification code via SMS.
                  </Text>
                  <View style={{ marginTop: spacing.xl }}>
                    <PhoneField
                      testID="client-phone-input"
                      label="Mobile number"
                      value={phone}
                      onChangeText={setPhone}
                    />
                    <Button
                      testID="request-otp-btn"
                      title="Send OTP"
                      loading={loading}
                      onPress={requestOtp}
                    />
                  </View>
                </>
              ) : (
                <>
                  <Text style={styles.title}>Enter your code</Text>
                  <Text style={styles.sub}>Sent via SMS to {phone}</Text>

                  {/* Dev mode: show the code automatically */}
                  {devCode ? (
                    <View style={styles.devCodeBox}>
                      <Text style={styles.devCodeLabel}>DEV MODE — OTP Code</Text>
                      <Text style={styles.devCodeValue}>{devCode}</Text>
                    </View>
                  ) : null}

                  <View style={{ marginTop: spacing.xl }}>
                    <TextField
                      testID="otp-code-input"
                      label="6-digit OTP"
                      value={code}
                      onChangeText={setCode}
                      placeholder="000000"
                      keyboardType="number-pad"
                      maxLength={6}
                    />
                    <Button
                      testID="verify-otp-btn"
                      title="Verify & sign in"
                      loading={loading}
                      onPress={verifyOtp}
                    />
                    <Pressable
                      testID="resend-otp"
                      onPress={requestOtp}
                      style={{ marginTop: spacing.lg, alignItems: "center" }}
                    >
                      <Text style={styles.link}>Resend OTP</Text>
                    </Pressable>
                  </View>
                </>
              )}
            </>
          )}

          {/* ── Password tab ─────────────────────────────────────────── */}
          {loginTab === "password" && (
            <>
              <Text style={styles.title}>Sign in with password</Text>
              <Text style={styles.sub}>Use your mobile number and password.</Text>
              <View style={{ marginTop: spacing.xl }}>
                <PhoneField
                  testID="pw-phone-input"
                  label="Mobile number"
                  value={pwPhone}
                  onChangeText={setPwPhone}
                />
                <TextField
                  testID="pw-password-input"
                  label="Password"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry
                />
                <Button
                  testID="pw-login-btn"
                  title="Sign in"
                  loading={loading}
                  onPress={loginPassword}
                />
                <Pressable
                  onPress={() => setLoginTab("otp")}
                  style={{ marginTop: spacing.lg, alignItems: "center" }}
                >
                  <Text style={styles.link}>Sign in with OTP instead</Text>
                </Pressable>
              </View>
            </>
          )}

          {/* ── First-time setup (new users after OTP) ─────────────────── */}
          {step === "setup" && (
            <>
              <Text style={styles.title}>Welcome! 👋</Text>
              <Text style={styles.sub}>
                Tell us your name and set a password so you can sign in faster next time.
              </Text>
              <View style={{ marginTop: spacing.xl }}>
                <TextField
                  testID="setup-name-input"
                  label="Your name"
                  value={name}
                  onChangeText={setName}
                  placeholder="e.g. Riya Sharma"
                  autoCapitalize="words"
                  autoFocus
                  returnKeyType="next"
                />
                <TextField
                  testID="setup-password-input"
                  label="Create a password"
                  value={newPassword}
                  onChangeText={setNewPassword}
                  placeholder="Min. 4 characters"
                  secureTextEntry={!showNewPassword}
                  autoCapitalize="none"
                />
                <View style={styles.pwMetaRow}>
                  <Text style={styles.hint}>Optional — you can always add it later.</Text>
                  <Pressable
                    testID="setup-toggle-password"
                    onPress={() => setShowNewPassword((v) => !v)}
                    hitSlop={8}
                  >
                    <Text style={styles.link}>{showNewPassword ? "Hide" : "Show"}</Text>
                  </Pressable>
                </View>
                <Button
                  testID="setup-continue-btn"
                  title="Continue"
                  loading={loading}
                  onPress={finishSetup}
                  style={{ marginTop: spacing.sm }}
                />
              </View>
            </>
          )}
        </KeyboardAwareScrollView>
      </View>
    </ThemeProvider>
  );
}

const styles = StyleSheet.create({
  restrictedContainer: {
    flex: 1,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
  },
  restrictedTitle: {
    color: colors.onSurface,
    fontFamily: fonts.display,
    fontSize: fontSize["2xl"],
    textAlign: "center",
  },
  restrictedText: {
    color: colors.muted,
    fontFamily: fonts.text,
    fontSize: fontSize.base,
    lineHeight: 21,
    textAlign: "center",
    marginVertical: spacing.lg,
    maxWidth: 420,
  },
  container: { flex: 1, backgroundColor: colors.surface },
  body: { paddingHorizontal: spacing.xl, paddingTop: spacing["2xl"] },
  bodyDesktop: {
    maxWidth: 460,
    width: "100%",
    alignSelf: "center",
    paddingTop: spacing["3xl"],
  },
  iconWrap: {
    width: 60,
    height: 60,
    borderRadius: radius.pill,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  // Tabs
  tabs: {
    flexDirection: "row",
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: 4,
    marginBottom: spacing.xl,
    gap: 4,
  },
  tab: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    minHeight: 44,
  },
  tabActive: { backgroundColor: colors.surface },
  tabText: {
    color: colors.muted,
    fontFamily: fonts.text,
    fontSize: fontSize.sm,
    fontWeight: "600",
  },
  tabTextActive: { color: colors.brand },
  // Form
  title: {
    color: colors.onSurface,
    fontFamily: fonts.display,
    fontSize: fontSize["2xl"],
  },
  sub: {
    color: colors.muted,
    fontFamily: fonts.text,
    fontSize: fontSize.base,
    marginTop: spacing.xs,
    lineHeight: 22,
  },
  link: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base },
  pwMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: -spacing.sm,
    marginBottom: spacing.lg,
  },
  hint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, flex: 1 },
  // Dev code hint
  devCodeBox: {
    marginTop: spacing.lg,
    backgroundColor: "#FFF3CD",
    borderRadius: radius.md,
    padding: spacing.md,
    borderLeftWidth: 4,
    borderLeftColor: "#F5A623",
  },
  devCodeLabel: {
    color: "#856404",
    fontFamily: fonts.text,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.8,
  },
  devCodeValue: {
    color: "#533F03",
    fontFamily: fonts.text,
    fontSize: 28,
    fontWeight: "800",
    letterSpacing: 6,
    marginTop: 4,
  },
});
