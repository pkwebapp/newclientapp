import React, { useEffect, useState } from "react";
import { useRouter, useLocalSearchParams } from "expo-router";
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

import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

type PhoneStep = "phone" | "password" | "verify" | "setup" | "reset";

export default function AdminLogin() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ mode?: string }>();
  const isRegister = params.mode === "register";
  const { user, signInWithToken } = useAuth();
  const toast = useToast();
  const { isDesktop } = useResponsive();
  const google = useGoogleSignIn("admin");

  // Phone smart flow: password for returning studios, OTP + setup for new ones
  const [phoneStep, setPhoneStep] = useState<PhoneStep>("phone");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [phoneLoading, setPhoneLoading] = useState(false);
  const [forgotFlow, setForgotFlow] = useState(false);
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  // Phone password sign-in (returning studios)
  const [phonePw, setPhonePw] = useState("");
  const [showPhonePw, setShowPhonePw] = useState(false);
  // First-time studio setup via phone
  const [setupName, setSetupName] = useState("");
  const [setupEmail, setSetupEmail] = useState("");
  const [setupPw, setSetupPw] = useState("");
  const [showSetupPw, setShowSetupPw] = useState(false);
  // Reset password (forgot → OTP)
  const [resetPw, setResetPw] = useState("");
  const [resetPwConfirm, setResetPwConfirm] = useState("");
  const [showResetPw, setShowResetPw] = useState(false);

  // Auto-redirect once signed in (a client account that signs in here goes to
  // its own area instead of dead-ending on this screen).
  useEffect(() => {
    if (user?.role === "admin") router.replace("/admin");
    else if (user?.role === "client") router.replace("/client");
    else if (user?.role === "superadmin") router.replace("/superadmin");
  }, [user, router]);

  const fail = (where: string, e: any, fallback: string) => {
    console.error(`[admin-login] ${where} failed`, e);
    toast.show(e?.message || fallback, "error");
  };

  // ── Phone OTP handlers (smart flow) ───────────────────────────────────────
  const resetPhoneToStart = () => {
    setAuthToken(null);
    setPendingToken(null);
    setForgotFlow(false);
    setOtp("");
    setDevCode(null);
    setPhonePw("");
    setPhoneStep("phone");
  };

  const sendOtp = async () => {
    const res = await sendPhoneOtp(phone, "admin");
    setDevCode(res.dev_code ?? null);
    setOtp("");
    toast.show("OTP sent to your mobile", "success");
  };

  // Step 1: phone → decide password vs OTP
  const continueFromPhone = async () => {
    if (!isPhoneNumberValid(phone)) {
      toast.show("Enter a valid mobile number", "error");
      return;
    }
    setPhoneLoading(true);
    try {
      const res = await checkPhone(phone);
      if (res.exists && res.has_password) {
        setPhonePw("");
        setPhoneStep("password");
      } else {
        setForgotFlow(false);
        await sendOtp();
        setPhoneStep("verify");
      }
    } catch (e: any) {
      fail("check-phone", e, "Something went wrong. Please try again.");
    } finally {
      setPhoneLoading(false);
    }
  };

  // Step 2a: returning studio → password
  const loginPhonePassword = async () => {
    if (!phonePw) {
      toast.show("Enter your password", "error");
      return;
    }
    setPhoneLoading(true);
    try {
      const res = await loginWithPhonePassword(phone, phonePw);
      const u = await signInWithToken(res.token);
      if (!u) throw new Error("Authentication failed. Please try again.");
    } catch (e: any) {
      fail("password-login", e, "Incorrect password");
    } finally {
      setPhoneLoading(false);
    }
  };

  const forgotPhonePassword = async () => {
    setPhoneLoading(true);
    try {
      setForgotFlow(true);
      await sendOtp();
      setPhoneStep("verify");
    } catch (e: any) {
      setForgotFlow(false);
      fail("forgot-password", e, "Could not send OTP");
    } finally {
      setPhoneLoading(false);
    }
  };

  const resendPhoneOtp = async () => {
    setPhoneLoading(true);
    try {
      await sendOtp();
    } catch (e: any) {
      fail("resend-otp", e, "Could not send OTP");
    } finally {
      setPhoneLoading(false);
    }
  };

  // Step 2b: verify OTP → setup / reset / sign in
  const verifyPhoneOtpHandler = async () => {
    if (otp.length < 6) {
      toast.show("Enter the 6-digit OTP", "error");
      return;
    }
    setPhoneLoading(true);
    try {
      const res = await verifyPhoneOtp(phone, otp, "admin");
      if (res.is_new) {
        setPendingToken(res.token);
        setAuthToken(res.token);
        setSetupName("");
        setSetupEmail("");
        setSetupPw("");
        setPhoneStep("setup");
        return;
      }
      if (forgotFlow) {
        setPendingToken(res.token);
        setAuthToken(res.token);
        setResetPw("");
        setResetPwConfirm("");
        setPhoneStep("reset");
        return;
      }
      const u = await signInWithToken(res.token);
      if (!u) throw new Error("Authentication failed. Please try again.");
    } catch (e: any) {
      fail("verify-otp", e, "Verification failed");
    } finally {
      setPhoneLoading(false);
    }
  };

  // Step 3a: first-time studio setup (name + email + password)
  const finishPhoneSetup = async () => {
    if (!setupName.trim()) {
      toast.show("Please enter your name", "error");
      return;
    }
    if (!setupEmail.trim() || !/^\S+@\S+\.\S+$/.test(setupEmail.trim())) {
      toast.show("Enter a valid email address", "error");
      return;
    }
    if (setupPw.length < 4) {
      toast.show("Password must be at least 4 characters", "error");
      return;
    }
    if (!pendingToken) {
      toast.show("Session expired. Please sign in again.", "error");
      resetPhoneToStart();
      return;
    }
    setPhoneLoading(true);
    try {
      await completePhoneSetup(setupName.trim(), setupPw, setupEmail.trim());
      const u = await signInWithToken(pendingToken);
      if (!u) throw new Error("Your session expired. Please sign in again.");
    } catch (e: any) {
      fail("complete-setup", e, "Could not save your details");
    } finally {
      setPhoneLoading(false);
    }
  };

  // Step 3b: reset password (forgot → OTP)
  const finishPhoneReset = async () => {
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
      resetPhoneToStart();
      return;
    }
    setPhoneLoading(true);
    try {
      await setPhonePassword(resetPw);
      const u = await signInWithToken(pendingToken);
      if (!u) throw new Error("Your session expired. Please sign in again.");
      toast.show("Password updated", "success");
    } catch (e: any) {
      fail("reset-password", e, "Could not reset your password");
    } finally {
      setPhoneLoading(false);
    }
  };

  const titles: Record<PhoneStep, [string, string]> = {
    phone: isRegister
      ? ["Start your studio, free", "Create your studio workspace in under a minute — no card required."]
      : ["Welcome back", "Sign in with your mobile number or Google to manage galleries, uploads and clients."],
    password: ["Welcome back", `Signing in as ${phone}`],
    verify: ["Verify your number", `A 6-digit code was sent to ${phone}`],
    setup: ["Set up your studio", "Add your details and a password to finish."],
    reset: ["Reset password", `Choose a new password for ${phone}`],
  };
  const [title, subtitle] = titles[phoneStep];

  return (
    <View style={styles.container} testID="admin-login-screen">
      <GlassHeader
        title="Studio Sign In"
        onBack={() => {
          if (phoneStep !== "phone") resetPhoneToStart();
          else goBackOr(router, "/");
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
        {/* Brand header */}
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
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.sub}>{subtitle}</Text>
        </View>

        <View style={{ marginTop: spacing.xl }}>
              {/* Step: phone */}
              {phoneStep === "phone" && (
                <>
                  <PhoneField
                    testID="admin-phone-input"
                    label="Mobile number"
                    value={phone}
                    onChangeText={setPhone}
                  />
                  <Button
                    testID="admin-continue-btn"
                    title="Continue"
                    loading={phoneLoading}
                    onPress={continueFromPhone}
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
                    loading={google.loading}
                    onPress={google.start}
                  />
                  <Text style={styles.hintCenter}>
                    {isRegister
                      ? "Already have a studio? Just sign in with the same number or Google account."
                      : "New studio? Sign in with your number or Google to start free — no card required."}
                  </Text>
                </>
              )}


              {/* Step: password (returning studios) */}
              {phoneStep === "password" && (
                <>
                  <TextField
                    testID="admin-phone-password-input"
                    label="Password"
                    value={phonePw}
                    onChangeText={setPhonePw}
                    placeholder="Your password"
                    secureTextEntry={!showPhonePw}
                    autoCapitalize="none"
                    autoFocus
                    onSubmitEditing={loginPhonePassword}
                    returnKeyType="go"
                  />
                  <View style={styles.pwMetaRow}>
                    <Pressable testID="admin-change-number" onPress={resetPhoneToStart} hitSlop={8}>
                      <Text style={styles.hintLink}>Use a different number</Text>
                    </Pressable>
                    <Pressable testID="admin-toggle-phone-password" onPress={() => setShowPhonePw((v) => !v)} hitSlop={8}>
                      <Text style={styles.toggle}>{showPhonePw ? "Hide" : "Show"}</Text>
                    </Pressable>
                  </View>
                  <Button
                    testID="admin-phone-login-btn"
                    title="Sign in"
                    loading={phoneLoading}
                    onPress={loginPhonePassword}
                  />
                  <Pressable
                    testID="admin-forgot-phone-password"
                    onPress={forgotPhonePassword}
                    style={{ marginTop: spacing.lg, alignItems: "center" }}
                  >
                    <Text style={styles.toggle}>Forgot password? Sign in with OTP</Text>
                  </Pressable>
                </>
              )}

              {/* Step: verify OTP */}
              {phoneStep === "verify" && (
                <>
                  {devCode ? (
                    <View style={styles.devCodeBox}>
                      <Text style={styles.devCodeLabel}>DEV MODE — OTP Code</Text>
                      <Text style={styles.devCodeValue}>{devCode}</Text>
                    </View>
                  ) : null}
                  <TextField
                    testID="admin-otp-input"
                    label="6-digit OTP"
                    value={otp}
                    onChangeText={setOtp}
                    placeholder="000000"
                    keyboardType="number-pad"
                    maxLength={6}
                  />
                  <Button
                    testID="admin-verify-otp-btn"
                    title="Verify & continue"
                    loading={phoneLoading}
                    onPress={verifyPhoneOtpHandler}
                  />
                  <Pressable
                    testID="admin-resend-otp"
                    onPress={resendPhoneOtp}
                    style={{ marginTop: spacing.lg, alignItems: "center" }}
                  >
                    <Text style={styles.toggle}>Resend OTP</Text>
                  </Pressable>
                </>
              )}

              {/* Step: first-time setup (name + email + password) */}
              {phoneStep === "setup" && (
                <>
                  <TextField
                    testID="admin-setup-name"
                    label="Your name"
                    value={setupName}
                    onChangeText={setSetupName}
                    placeholder="e.g. Priya's Studio"
                    autoCapitalize="words"
                    autoFocus
                  />
                  <TextField
                    testID="admin-setup-email"
                    label="Email"
                    value={setupEmail}
                    onChangeText={setSetupEmail}
                    placeholder="you@studio.com"
                    autoCapitalize="none"
                    keyboardType="email-address"
                  />
                  <TextField
                    testID="admin-setup-password"
                    label="Create a password"
                    value={setupPw}
                    onChangeText={setSetupPw}
                    placeholder="Min. 4 characters"
                    secureTextEntry={!showSetupPw}
                    autoCapitalize="none"
                  />
                  <View style={styles.pwMetaRow}>
                    <Text style={styles.hint}>You&apos;ll use these to sign in next time.</Text>
                    <Pressable testID="admin-toggle-setup-password" onPress={() => setShowSetupPw((v) => !v)} hitSlop={8}>
                      <Text style={styles.toggle}>{showSetupPw ? "Hide" : "Show"}</Text>
                    </Pressable>
                  </View>
                  <Button
                    testID="admin-setup-continue-btn"
                    title="Continue"
                    loading={phoneLoading}
                    onPress={finishPhoneSetup}
                  />
                </>
              )}

              {/* Step: reset password (forgot → OTP) */}
              {phoneStep === "reset" && (
                <>
                  <TextField
                    testID="admin-reset-password"
                    label="New password"
                    value={resetPw}
                    onChangeText={setResetPw}
                    placeholder="Min. 4 characters"
                    secureTextEntry={!showResetPw}
                    autoCapitalize="none"
                    autoFocus
                  />
                  <TextField
                    testID="admin-reset-password-confirm"
                    label="Confirm password"
                    value={resetPwConfirm}
                    onChangeText={setResetPwConfirm}
                    placeholder="Re-enter password"
                    secureTextEntry={!showResetPw}
                    autoCapitalize="none"
                  />
                  <View style={styles.pwMetaRow}>
                    <Text style={styles.hint}>Keep it simple — even a 4-digit PIN works.</Text>
                    <Pressable testID="admin-toggle-reset-password" onPress={() => setShowResetPw((v) => !v)} hitSlop={8}>
                      <Text style={styles.toggle}>{showResetPw ? "Hide" : "Show"}</Text>
                    </Pressable>
                  </View>
                  <Button
                    testID="admin-reset-continue-btn"
                    title="Save & sign in"
                    loading={phoneLoading}
                    disabled={resetPw.length < 4 || resetPw !== resetPwConfirm}
                    onPress={finishPhoneReset}
                  />
                </>
              )}
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  body: { paddingHorizontal: spacing.xl, paddingTop: spacing.xl },
  bodyDesktop: {
    maxWidth: 460,
    width: "100%",
    alignSelf: "center",
    paddingTop: spacing["2xl"],
  },
  brandHeader: {
    backgroundColor: colors.brandTertiary,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.xl,
    overflow: "hidden",
  },
  brandGlow: {
    position: "absolute",
    top: -60,
    right: -40,
    width: 180,
    height: 180,
    borderRadius: 90,
    backgroundColor: "rgba(226,98,60,0.14)",
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  brandLogoDot: {
    width: 40,
    height: 40,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  brandName: {
    color: colors.onSurface,
    fontFamily: fonts.text,
    fontSize: fontSize.sm,
    fontWeight: "700",
    letterSpacing: 3,
    flex: 1,
  },
  brandBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
  },
  brandBadgeText: {
    color: colors.onBrand,
    fontFamily: fonts.text,
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 1.5,
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
  },
  divider: { flexDirection: "row", alignItems: "center", marginVertical: spacing.xl },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.borderStrong },
  or: {
    color: colors.muted,
    marginHorizontal: spacing.md,
    fontFamily: fonts.text,
    fontSize: fontSize.sm,
  },
  toggle: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base },
  pwMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: -spacing.sm,
    marginBottom: spacing.lg,
  },
  hint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, flex: 1 },
  hintCenter: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, textAlign: "center", marginTop: spacing.lg, lineHeight: 20 },
  hintLink: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  // Dev code hint
  devCodeBox: {
    marginBottom: spacing.lg,
    backgroundColor: "rgba(226,98,60,0.12)",
    borderRadius: radius.md,
    padding: spacing.md,
    borderLeftWidth: 4,
    borderLeftColor: colors.brand,
  },
  devCodeLabel: {
    color: colors.brand,
    fontFamily: fonts.text,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.8,
  },
  devCodeValue: {
    color: colors.onSurface,
    fontFamily: fonts.text,
    fontSize: 28,
    fontWeight: "800",
    letterSpacing: 6,
    marginTop: 4,
  },
});
