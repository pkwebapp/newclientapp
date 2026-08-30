import { useEffect, useState } from "react";
import { useRouter, useLocalSearchParams } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { useResponsive } from "@/src/hooks/use-responsive";
import { goBackOr } from "@/src/navigation/back";
import { sendPasswordReset, updatePassword } from "@/src/lib/auth-actions";
import { supabase } from "@/src/lib/supabase";

import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const PASSWORD_MIN = 8;
const PASSWORD_HINT = "At least 8 characters, with a letter and a number.";

function scorePassword(pw: string): { ok: boolean; msg: string | null } {
  if (!pw) return { ok: false, msg: null };
  if (pw.length < PASSWORD_MIN) {
    return { ok: false, msg: `Too short — needs ${PASSWORD_MIN - pw.length} more character${pw.length === PASSWORD_MIN - 1 ? "" : "s"}.` };
  }
  const hasLetter = /[A-Za-z]/.test(pw);
  const hasDigit = /[0-9]/.test(pw);
  if (!hasLetter || !hasDigit) return { ok: false, msg: "Add at least one letter and one number." };
  return { ok: true, msg: "Looks good." };
}

type Stage = "email" | "set";

/**
 * Password reset via Supabase:
 * 1. User enters their email → Supabase emails a magic link.
 * 2. Link opens /auth/callback which forwards here with ?stage=set once the
 *    PASSWORD_RECOVERY session is active. User picks a new password → updateUser.
 */
export default function ForgotPassword() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ email?: string; stage?: string }>();
  const toast = useToast();
  const { isDesktop } = useResponsive();

  const [stage, setStage] = useState<Stage>(params.stage === "set" ? "set" : "email");
  const [email, setEmail] = useState(params.email || "");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [sending, setSending] = useState(false);
  const [resetting, setResetting] = useState(false);

  // If we land here from a recovery link, Supabase fires PASSWORD_RECOVERY.
  useEffect(() => {
    const { data: sub } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") setStage("set");
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const requestLink = async () => {
    if (!email.trim()) { toast.show("Enter your studio email", "error"); return; }
    setSending(true);
    try {
      const { error } = await sendPasswordReset(email);
      if (error) throw error;
      toast.show("If this email is registered, a reset link was sent.", "success");
    } catch (e: any) {
      toast.show(e?.message || "Could not send reset link", "error");
    } finally {
      setSending(false);
    }
  };

  const submitReset = async () => {
    const strength = scorePassword(newPassword);
    if (!strength.ok) { toast.show(strength.msg || PASSWORD_HINT, "error"); return; }
    if (newPassword !== confirmPassword) { toast.show("Passwords do not match", "error"); return; }
    setResetting(true);
    try {
      const { error } = await updatePassword(newPassword);
      if (error) throw error;
      toast.show("Password updated — you're signed in.", "success");
      router.replace("/admin");
    } catch (e: any) {
      toast.show(e?.message || "Reset failed", "error");
    } finally {
      setResetting(false);
    }
  };

  return (
    <View style={styles.container} testID="forgot-password-screen">
      <GlassHeader
        title={stage === "email" ? "Forgot password" : "Set a new password"}
        onBack={() => (stage === "set" ? setStage("email") : goBackOr(router, "/admin-login"))}
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
            {stage === "email" ? "Reset your password" : "Choose a new password"}
          </Text>
          <Text style={styles.sub}>
            {stage === "email"
              ? "Enter your studio email. We'll send you a secure reset link."
              : `Set a new password for ${email || "your account"}. You'll stay signed in.`}
          </Text>
        </View>

        {stage === "email" ? (
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
              title="Send reset link"
              icon="mail-outline"
              loading={sending}
              onPress={requestLink}
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
            <TextField
              testID="reset-new-password"
              label="New password"
              value={newPassword}
              onChangeText={setNewPassword}
              secureTextEntry
              autoFocus
            />
            {(() => {
              const s = scorePassword(newPassword);
              const color = !newPassword ? colors.muted : s.ok ? "#2E7D32" : "#C0392B";
              const icon = !newPassword ? "information-circle-outline" : s.ok ? "checkmark-circle" : "alert-circle";
              return (
                <View style={styles.pwHintRow}>
                  <Ionicons name={icon as any} size={14} color={color} />
                  <Text style={[styles.pwHintText, { color }]}>
                    {newPassword ? s.msg : PASSWORD_HINT}
                  </Text>
                </View>
              );
            })()}
            <TextField
              testID="reset-confirm-password"
              label="Confirm password"
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              secureTextEntry
            />
            {confirmPassword && confirmPassword !== newPassword ? (
              <View style={styles.pwHintRow}>
                <Ionicons name="alert-circle" size={14} color="#C0392B" />
                <Text style={[styles.pwHintText, { color: "#C0392B" }]}>Passwords do not match.</Text>
              </View>
            ) : null}
            <Button
              testID="reset-submit-btn"
              title="Update password"
              icon="checkmark"
              loading={resetting}
              onPress={submitReset}
            />
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
  brandGlow: { position: "absolute", top: -60, right: -40, width: 180, height: 180, borderRadius: 90, backgroundColor: "rgba(226,98,60,0.14)" },
  brandRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.lg },
  brandLogoDot: { width: 40, height: 40, borderRadius: radius.pill, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  brandName: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700", letterSpacing: 3, flex: 1 },
  brandBadge: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.pill, backgroundColor: colors.brand },
  brandBadgeText: { color: colors.onBrand, fontFamily: fonts.text, fontSize: 10, fontWeight: "800", letterSpacing: 1.5 },
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  sub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: spacing.xs, lineHeight: 21 },
  linkRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 4, marginTop: spacing.xl, minHeight: 44 },
  link: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  pwHintRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: -spacing.sm, marginBottom: spacing.md, paddingHorizontal: spacing.xs },
  pwHintText: { flex: 1, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18 },
});
