import { useState } from "react";
import { useRouter } from "expo-router";
import { KeyboardAvoidingView, Linking, Platform, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, ApiError } from "@/src/api/client";
import { useAuth } from "@/src/context/AuthContext";
import { Button, TextField, LuxeLoader, useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

import { APP_DOMAIN, getAppSurface } from "@/src/navigation/host-routing";
export default function SuperAdminLogin() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { signInWithLegacyToken } = useAuth();
  const toast = useToast();
  const surface = getAppSurface();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    try {
      const result = await api.post("/superadmin/login", { email: email.trim(), password });
      await signInWithLegacyToken(result.session_token);
      router.replace("/superadmin");
    } catch (error: any) {
      toast.show(error instanceof ApiError ? error.message : "Could not sign in", "error");
    } finally {
      setLoading(false);
    }
  };

  if (surface === "client" || surface === "studio") {
    return (
      <View style={styles.restrictedContainer}>
        <View style={styles.card}>
          <View style={styles.logo}><Text style={styles.logoText}>P</Text></View>
          <Text style={styles.eyebrow}>PIK CONNECT</Text>
          <Text style={styles.title}>Platform control is restricted</Text>
          <Text style={styles.subtitle}>Super Admin access is available only from the secure platform workspace.</Text>
          <Button title="Open Super Admin workspace" onPress={() => Linking.openURL(`${APP_DOMAIN.superadmin}/superadmin-login`)} icon="shield-checkmark-outline" />
        </View>
      </View>
    );
  }

  if (loading) return <LuxeLoader title="Signing in" subtitle="Opening platform controls…" />;

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : "height"}>
      <View style={[styles.card, { paddingTop: insets.top + spacing["2xl"] }]}>
        <View style={styles.logo}><Text style={styles.logoText}>P</Text></View>
        <Text style={styles.eyebrow}>PIK CONNECT</Text>
        <Text style={styles.title}>Platform control</Text>
        <Text style={styles.subtitle}>Sign in to manage photographers, galleries and platform usage.</Text>
        <View style={styles.form}>
          <TextField label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
          <TextField label="Password" value={password} onChangeText={setPassword} secureTextEntry />
          <Button title="Sign in as Super Admin" onPress={submit} icon="shield-checkmark-outline" />
        </View>
        <Text style={styles.note}>Restricted platform access</Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F7F8FA", alignItems: "center", justifyContent: "center" },
  restrictedContainer: { flex: 1, backgroundColor: "#F7F8FA", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  card: { width: "100%", maxWidth: 460, padding: spacing.xl },
  logo: { width: 52, height: 52, borderRadius: radius.lg, backgroundColor: colors.brand, alignItems: "center", justifyContent: "center", marginBottom: spacing.lg },
  logoText: { color: colors.onBrand, fontFamily: fonts.display, fontSize: 30, fontWeight: "700" },
  eyebrow: { color: colors.brand, fontFamily: fonts.text, fontSize: 11, fontWeight: "800", letterSpacing: 2 },
  title: { color: "#101828", fontFamily: fonts.display, fontSize: 32, fontWeight: "700", marginTop: spacing.sm },
  subtitle: { color: "#667085", fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 21, marginTop: spacing.sm },
  form: { marginTop: spacing["2xl"] },
  note: { color: "#98A2B3", fontFamily: fonts.text, fontSize: 12, textAlign: "center", marginTop: spacing.xl },
});
