import { useState } from "react";
import { useRouter, useLocalSearchParams } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { publicApi, ApiError } from "@/src/api/client";
import { useAuth } from "@/src/context/AuthContext";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { useResponsive } from "@/src/hooks/use-responsive";
import { goBackOr } from "@/src/navigation/back";

import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

type Step = "email" | "reset";

export default function ForgotPassword() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ email?: string }>();
  const { signInWithToken } = useAuth();
  const toast = useToast();
  const { isDesktop } = useResponsive();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState(params.email || "");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [sending, setSending] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [devCode, setDevCode] = useState<string | null>(null);

  const requestCode = async () => {
    if (!email.trim()) {
      toast.show("Enter your studio email", "error");
      return;
    }
    setSending(true);
    try {
      const res: any = await publicApi.post("/auth/admin/forgot-password", {
        email: email.trim(),
      });
      // Backend is deliberately vague to avoid leaking account existence.
      toast.show(
        res?.delivered
          ? "Reset code sent — check your email"
          : "If this email is registered, a code was sent",
        "success"
      );
      if (res?.dev_code) setDevCode(res.dev_code);
      setStep("reset");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not send code", "error");
    } finally {
      setSending(false);
    }
  };

  const resendCode = async () => {
    setDevCode(null);
    await requestCode();
  };

  const submitReset = async () => {
    if (!code.trim()) {
      toast.show("Enter the 6-digit code", "error");
      return;
    }
    if (newPassword.length < 6) {
      toast.show("Password must be at least 6 characters", "error");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.show("Passwords do not match", "error");
      return;
    }
    setResetting(true);
    try {
      const res: any = await publicApi.post("/auth/admin/reset-password", {
        email: email.trim(),
        code: code.trim(),
        new_password: newPassword,
      });
      if (res?.session_token) {
        await signInWithToken(res.session_token);
        toast.show("Password reset — you're signed in", "success");
        router.replace("/admin");
      } else {
        toast.show("Password reset. Please sign in.", "success");
        router.replace("/admin-login");
      }
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Reset failed", "error");
    } finally {
      setResetting(false);
    }
  };

  return (
    <View style={styles.container} testID="forgot-password-screen">
      <GlassHeader
        title={step === "email" ? "Forgot password" : "Enter reset code"}
        onBack={() => (step === "reset" ? setStep("email") : goBackOr(router, "/admin-login"))}
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
        <View style={styles.brandHeader}>
          <View style={styles.brandGlow} pointerEvents="none" />
          <View style={styles.brandRow}>
            <View style={styles.brandLogoDot}>
              <Ionicons name="lock-open" size={20} color={colors.brand} />
            </View>
            <Text style={styles.brandName}>PIK CONNECT</Text>
            <View style={styles.brandBadge}>
              <Text style={styles.brandBadgeText}>STUDIO</Text>
            </View>
          </View>
          <Text style={styles.title}>
            {step === "email" ? "Reset your password" : "Almost there"}
          </Text>
          <Text style={styles.sub}>
            {step === "email"
              ? "Enter your studio email. We'll send you a 6-digit code to reset your password."
              : `We sent a 6-digit code to ${email}. It expires in 15 minutes.`}
          </Text>
        </View>

        {step === "email" ? (
          <View style={{ marginTop: spacing.xl }}>
            <TextField
              testID="forgot-email-input"
              label="Studio email"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              keyboardType="email-address"
              autoFocus
            />
            <Button
              testID="forgot-send-btn"
              title="Send reset code"
              icon="mail-outline"
              loading={sending}
              onPress={requestCode}
            />
            <Pressable
              testID="forgot-back-to-login"
              onPress={() => router.replace("/admin-login")}
              style={styles.linkRow}
            >
              <Ionicons name="chevron-back" size={14} color={colors.brand} />
              <Text style={styles.link}>Back to sign in</Text>
            </Pressable>
          </View>
        ) : (
          <View style={{ marginTop: spacing.xl }}>
            {devCode ? (
              <View style={styles.devCodeBox}>
                <Ionicons name="information-circle" size={16} color={colors.brand} />
                <Text style={styles.devCodeText}>
                  Preview mode — your code is{" "}
                  <Text style={styles.devCodeStrong}>{devCode}</Text>
                </Text>
              </View>
            ) : null}
            <TextField
              testID="reset-code-input"
              label="6-digit code"
              value={code}
              onChangeText={(t) => setCode(t.replace(/[^0-9]/g, "").slice(0, 6))}
              keyboardType="number-pad"
              autoFocus
            />
            <TextField
              testID="reset-new-password"
              label="New password"
              value={newPassword}
              onChangeText={setNewPassword}
              secureTextEntry
            />
            <TextField
              testID="reset-confirm-password"
              label="Confirm password"
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              secureTextEntry
            />
            <Button
              testID="reset-submit-btn"
              title="Reset password"
              icon="checkmark"
              loading={resetting}
              onPress={submitReset}
            />
            <Pressable testID="reset-resend" onPress={resendCode} style={styles.linkRow}>
              <Ionicons name="refresh" size={14} color={colors.brand} />
              <Text style={styles.link}>Resend code</Text>
            </Pressable>
          </View>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
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
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  sub: {
    color: colors.muted,
    fontFamily: fonts.text,
    fontSize: fontSize.base,
    marginTop: spacing.xs,
    lineHeight: 21,
  },
  linkRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    marginTop: spacing.xl,
    minHeight: 44,
  },
  link: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  devCodeBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: "rgba(226,98,60,0.35)",
    backgroundColor: "rgba(226,98,60,0.08)",
  },
  devCodeText: {
    flex: 1,
    color: colors.onSurface,
    fontFamily: fonts.text,
    fontSize: fontSize.sm,
    lineHeight: 20,
  },
  devCodeStrong: { fontWeight: "800", letterSpacing: 2, color: colors.brand },
});
