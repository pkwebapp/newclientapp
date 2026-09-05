import React, { useEffect, useState } from "react";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "@/src/context/AuthContext";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { PhoneField, isPhoneNumberValid } from "@/src/components/PhoneField";
import { useResponsive } from "@/src/hooks/use-responsive";
import { useGoogleSignIn } from "@/src/hooks/use-google-signin";
import { goBackOr } from "@/src/navigation/back";
import {
  sendPhoneOtp,
  verifyPhoneOtp,
  loginWithPhonePassword,
  completePhoneSetup,
  setPhonePassword,
  checkPhone,
} from "@/src/lib/phone-auth";
import { setAuthToken } from "@/src/api/client";

import { lightColors as colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { ThemeProvider } from "@/src/theme-context";

type Step = "phone" | "password" | "verify" | "setup" | "reset";

export default function ClientLogin() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, signInWithToken } = useAuth();
  const toast = useToast();
  const { isDesktop } = useResponsive();
  const google = useGoogleSignIn("client");

  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);

  // Password sign-in (returning users)
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // OTP verify
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  // True when the user reached OTP via "Forgot password" — they'll set a new one.
  const [forgotFlow, setForgotFlow] = useState(false);

  // First-time setup (new users): name + optional password
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);

  // Reset password (after forgot → OTP)
  const [resetPw, setResetPw] = useState("");
  const [resetPwConfirm, setResetPwConfirm] = useState("");
  const [showResetPw, setShowResetPw] = useState(false);

  // Auto-route once the backend confirms role (a studio account that signs in
  // here goes to its own area instead of dead-ending on this screen).
  useEffect(() => {
    if (user?.role === "client") router.replace("/client");
    else if (user?.role === "admin") router.replace("/admin");
    else if (user?.role === "superadmin") router.replace("/superadmin");
  }, [user, router]);

  const fail = (where: string, e: any, fallback: string) => {
    console.error(`[client-login] ${where} failed`, e);
    toast.show(e?.message || fallback, "error");
  };

  const resetToPhone = () => {
    setAuthToken(null);
    setPendingToken(null);
    setForgotFlow(false);
    setCode("");
    setDevCode(null);
    setPassword("");
    setStep("phone");
  };

  // ── Step 1: phone → decide password vs OTP ────────────────────────────────
  const continueFromPhone = async () => {
    if (!isPhoneNumberValid(phone)) {
      toast.show("Enter a valid mobile number", "error");
      return;
    }
    setLoading(true);
    try {
      const res = await checkPhone(phone);
      if (res.exists && res.has_password) {
        setPassword("");
        setStep("password");
      } else {
        // New user, or existing user who never set a password → OTP.
        setForgotFlow(false);
        await requestOtp();
        setStep("verify");
      }
    } catch (e: any) {
      fail("check-phone", e, "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── OTP helpers ────────────────────────────────────────────────────────────
  const requestOtp = async () => {
    const res = await sendPhoneOtp(phone, "client");
    setDevCode(res.dev_code ?? null);
    setCode("");
    toast.show("OTP sent to your mobile", "success");
  };

  const resendOtp = async () => {
    setLoading(true);
    try {
      await requestOtp();
    } catch (e: any) {
      fail("resend-otp", e, "Could not send OTP");
    } finally {
      setLoading(false);
    }
  };

  // ── Step 2a: password sign-in (returning users) ────────────────────────────
  const loginPassword = async () => {
    if (!password) {
      toast.show("Enter your password", "error");
      return;
    }
    setLoading(true);
    try {
      const res = await loginWithPhonePassword(phone, password);
      const u = await signInWithToken(res.token);
      if (!u) throw new Error("Authentication failed. Please try again.");
    } catch (e: any) {
      fail("password-login", e, "Incorrect password");
    } finally {
      setLoading(false);
    }
  };

  const forgotPassword = async () => {
    setLoading(true);
    try {
      setForgotFlow(true);
      await requestOtp();
      setStep("verify");
    } catch (e: any) {
      setForgotFlow(false);
      fail("forgot-password", e, "Could not send OTP");
    } finally {
      setLoading(false);
    }
  };

  // ── Step 2b: verify OTP ─────────────────────────────────────────────────────
  const verifyOtp = async () => {
    if (code.length < 6) {
      toast.show("Enter the 6-digit OTP", "error");
      return;
    }
    setLoading(true);
    try {
      const res = await verifyPhoneOtp(phone, code, "client");
      if (res.is_new) {
        // Brand-new user (or existing user with no password/name) → setup.
        setPendingToken(res.token);
        setAuthToken(res.token);
        setName("");
        setNewPassword("");
        setStep("setup");
        return;
      }
      if (forgotFlow) {
        // Returning user recovering access → let them set a new password.
        setPendingToken(res.token);
        setAuthToken(res.token);
        setResetPw("");
        setResetPwConfirm("");
        setStep("reset");
        return;
      }
      // Fallback: just sign in.
      const u = await signInWithToken(res.token);
      if (!u) throw new Error("Authentication failed. Please try again.");
    } catch (e: any) {
      fail("verify-otp", e, "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  // ── Step 3a: first-time setup (name required, password optional) ────────────
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
      resetToPhone();
      return;
    }
    setLoading(true);
    try {
      await completePhoneSetup(name.trim(), newPassword || undefined);
      const u = await signInWithToken(pendingToken);
      if (!u) throw new Error("Your session expired. Please sign in again.");
    } catch (e: any) {
      fail("complete-setup", e, "Could not save your details");
    } finally {
      setLoading(false);
    }
  };

  // ── Step 3b: reset password (after forgot → OTP) ────────────────────────────
  const finishReset = async () => {
    if (resetPw.length < 4) {
      toast.show("Password must be at least 4 characters", "error");
      return;
    }
    if (resetPw !== resetPwConfirm) {
      toast.show("Passwords do not match", "error");
      return;
    }
    if (!pendingToken) {
      toast.show("Session expired. Please sign in again.", "error");
      resetToPhone();
      return;
    }
    setLoading(true);
    try {
      await setPhonePassword(resetPw);
      const u = await signInWithToken(pendingToken);
      if (!u) throw new Error("Your session expired. Please sign in again.");
      toast.show("Password updated", "success");
    } catch (e: any) {
      fail("reset-password", e, "Could not reset your password");
    } finally {
      setLoading(false);
    }
  };

  const onBack = () => {
    if (step === "phone") return goBackOr(router, "/");
    if (step === "password" || step === "verify") return resetToPhone();
    // setup / reset → abandon and start over
    return resetToPhone();
  };

  const headerTitle =
    step === "phone" ? "Sign in"
      : step === "password" ? "Welcome back"
        : step === "verify" ? "Verify"
          : step === "setup" ? "Almost there"
            : "Reset password";

  return (
    <ThemeProvider scheme="light">
      <View style={styles.container} testID="client-login-screen">
        <GlassHeader title={headerTitle} onBack={onBack} topInset={insets.top} />
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

          {/* ── Step: phone ─────────────────────────────────────────── */}
          {step === "phone" && (
            <>
              <Text style={styles.title}>Find your photos</Text>
              <Text style={styles.sub}>
                Enter your mobile number to continue. New here? We&apos;ll verify you with an OTP.
              </Text>
              <View style={{ marginTop: spacing.xl }}>
                <PhoneField
                  testID="client-phone-input"
                  label="Mobile number"
                  value={phone}
                  onChangeText={setPhone}
                />
                <Button
                  testID="continue-btn"
                  title="Continue"
                  loading={loading}
                  onPress={continueFromPhone}
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
                  loading={google.loading}
                  onPress={google.start}
                />
              </View>
            </>
          )}

          {/* ── Step: password (returning users) ────────────────────── */}
          {step === "password" && (
            <>
              <Text style={styles.title}>Enter your password</Text>
              <Text style={styles.sub}>Signing in as {phone}</Text>
              <View style={{ marginTop: spacing.xl }}>
                <TextField
                  testID="pw-password-input"
                  label="Password"
                  value={password}
                  onChangeText={setPassword}
                  placeholder="Your password"
                  secureTextEntry={!showPassword}
                  autoCapitalize="none"
                  autoFocus
                  onSubmitEditing={loginPassword}
                  returnKeyType="go"
                />
                <View style={styles.pwMetaRow}>
                  <Pressable testID="change-number" onPress={resetToPhone} hitSlop={8}>
                    <Text style={styles.hintLink}>Use a different number</Text>
                  </Pressable>
                  <Pressable testID="toggle-password" onPress={() => setShowPassword((v) => !v)} hitSlop={8}>
                    <Text style={styles.link}>{showPassword ? "Hide" : "Show"}</Text>
                  </Pressable>
                </View>
                <Button
                  testID="pw-login-btn"
                  title="Sign in"
                  loading={loading}
                  onPress={loginPassword}
                />
                <Pressable
                  testID="forgot-password"
                  onPress={forgotPassword}
                  style={{ marginTop: spacing.lg, alignItems: "center" }}
                >
                  <Text style={styles.link}>Forgot password? Sign in with OTP</Text>
                </Pressable>
              </View>
            </>
          )}

          {/* ── Step: verify OTP ────────────────────────────────────── */}
          {step === "verify" && (
            <>
              <Text style={styles.title}>Enter your code</Text>
              <Text style={styles.sub}>Sent via SMS to {phone}</Text>

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
                  title="Verify & continue"
                  loading={loading}
                  onPress={verifyOtp}
                />
                <Pressable
                  testID="resend-otp"
                  onPress={resendOtp}
                  style={{ marginTop: spacing.lg, alignItems: "center" }}
                >
                  <Text style={styles.link}>Resend OTP</Text>
                </Pressable>
              </View>
            </>
          )}

          {/* ── Step: first-time setup ──────────────────────────────── */}
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

          {/* ── Step: reset password (forgot flow) ──────────────────── */}
          {step === "reset" && (
            <>
              <Text style={styles.title}>Set a new password</Text>
              <Text style={styles.sub}>
                You&apos;re verified. Choose a new password for {phone}.
              </Text>
              <View style={{ marginTop: spacing.xl }}>
                <TextField
                  testID="reset-password-input"
                  label="New password"
                  value={resetPw}
                  onChangeText={setResetPw}
                  placeholder="Min. 4 characters"
                  secureTextEntry={!showResetPw}
                  autoCapitalize="none"
                  autoFocus
                />
                <TextField
                  testID="reset-password-confirm"
                  label="Confirm password"
                  value={resetPwConfirm}
                  onChangeText={setResetPwConfirm}
                  placeholder="Re-enter password"
                  secureTextEntry={!showResetPw}
                  autoCapitalize="none"
                />
                <View style={styles.pwMetaRow}>
                  <Text style={styles.hint}>Keep it simple — even a 4-digit PIN works.</Text>
                  <Pressable
                    testID="reset-toggle-password"
                    onPress={() => setShowResetPw((v) => !v)}
                    hitSlop={8}
                  >
                    <Text style={styles.link}>{showResetPw ? "Hide" : "Show"}</Text>
                  </Pressable>
                </View>
                <Button
                  testID="reset-continue-btn"
                  title="Save & sign in"
                  loading={loading}
                  disabled={resetPw.length < 4 || resetPw !== resetPwConfirm}
                  onPress={finishReset}
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
  divider: { flexDirection: "row", alignItems: "center", marginVertical: spacing.lg },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.borderStrong },
  or: { color: colors.muted, marginHorizontal: spacing.md, fontFamily: fonts.text, fontSize: fontSize.sm },
  link: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  hintLink: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
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
