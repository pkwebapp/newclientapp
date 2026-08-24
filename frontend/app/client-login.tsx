import { useState } from "react";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { useAuth } from "@/src/context/AuthContext";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { useResponsive } from "@/src/hooks/use-responsive";
import { goBackOr } from "@/src/navigation/back";

import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

export default function ClientLogin() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { signInWithToken } = useAuth();
  const toast = useToast();
  const { isDesktop } = useResponsive();

  const [channel, setChannel] = useState<"email" | "phone">("email");
  const [step, setStep] = useState<"identify" | "verify">("identify");
  const [value, setValue] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);

  const requestOtp = async () => {
    if (!value.trim()) {
      toast.show(channel === "email" ? "Enter your email" : "Enter your phone number", "error");
      return;
    }
    setLoading(true);
    try {
      const body: any = { channel };
      if (channel === "email") body.email = value.trim();
      else body.phone = value.trim();
      const res = await api.post("/auth/client/request-otp", body);
      setStep("verify");
      if (res.dev_code) {
        toast.show(`Demo code: ${res.dev_code}`, "info");
        setCode(res.dev_code);
      } else {
        toast.show("Code sent. Check your inbox.", "success");
      }
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not send code", "error");
    } finally {
      setLoading(false);
    }
  };

  const verify = async () => {
    if (code.length < 4) {
      toast.show("Enter the 6-digit code", "error");
      return;
    }
    setLoading(true);
    try {
      const body: any = { channel, code: code.trim(), name: name.trim() || undefined };
      if (channel === "email") body.email = value.trim();
      else body.phone = value.trim();
      const res = await api.post("/auth/client/verify-otp", body);
      await signInWithToken(res.session_token);
      router.replace("/client");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Verification failed", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
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

        {step === "identify" ? (
          <>
            <Text style={styles.title}>Find your photos</Text>
            <Text style={styles.sub}>We’ll send a one-time code to verify it’s you.</Text>

            <View style={styles.tabs}>
              {(["email", "phone"] as const).map((c) => (
                <Pressable
                  key={c}
                  testID={`channel-${c}`}
                  onPress={() => {
                    setChannel(c);
                    setValue("");
                  }}
                  style={[styles.tab, channel === c && styles.tabActive]}
                >
                  <Ionicons
                    name={c === "email" ? "mail-outline" : "call-outline"}
                    size={16}
                    color={channel === c ? colors.onBrand : colors.onSurfaceTertiary}
                  />
                  <Text style={[styles.tabText, channel === c && styles.tabTextActive]}>
                    {c === "email" ? "Email" : "Phone"}
                  </Text>
                </Pressable>
              ))}
            </View>

            <View style={{ marginTop: spacing.xl }}>
              <TextField
                testID="client-identifier-input"
                label={channel === "email" ? "Email address" : "Mobile number"}
                value={value}
                onChangeText={setValue}
                placeholder={channel === "email" ? "you@example.com" : "+1 555 000 1234"}
                autoCapitalize="none"
                keyboardType={channel === "email" ? "email-address" : "phone-pad"}
              />
              <Button testID="request-otp-btn" title="Send code" loading={loading} onPress={requestOtp} />
            </View>
          </>
        ) : (
          <>
            <Text style={styles.title}>Enter your code</Text>
            <Text style={styles.sub}>Sent to {value}</Text>
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
              <TextField
                testID="client-name-input"
                label="Your name (optional)"
                value={name}
                onChangeText={setName}
                placeholder="e.g. Priya"
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
  );
}

const styles = StyleSheet.create({
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
  tabs: {
    flexDirection: "row",
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.xs,
    marginTop: spacing.xl,
  },
  tab: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    paddingVertical: spacing.md,
    borderRadius: radius.sm,
  },
  tabActive: { backgroundColor: colors.brand },
  tabText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  tabTextActive: { color: colors.onBrand, fontWeight: "600" },
  toggle: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base },
});
