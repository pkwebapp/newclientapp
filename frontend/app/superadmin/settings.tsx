import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { api } from "@/src/api/client";
import { Button, useToast } from "@/src/components/ui";
import { SuperAdminHeader } from "@/src/components/SuperAdminShell";
import { NotificationPrefs } from "@/src/components/NotificationPrefs";
import { fonts, radius, spacing } from "@/src/theme";

export default function Settings() {
  const [name, setName] = useState("PIK Connect");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      const data = await api.get("/superadmin/settings");
      setName(data.platform_name || "PIK Connect");
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load().catch(() => setLoading(false));
    }, [load])
  );

  const save = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      toast.show("Platform name can't be empty", "error");
      return;
    }
    setSaving(true);
    try {
      await api.patch("/superadmin/settings", { platform_name: trimmed });
      setName(trimmed);
      setMessage("Settings saved");
    } catch {
      toast.show("Could not save settings", "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <ScrollView testID="superadmin-settings" contentContainerStyle={styles.page}>
      <SuperAdminHeader title="Settings" subtitle="Basic platform settings" />
      <View style={styles.panel}>
        <Text style={styles.label}>Admin profile</Text>
        <Text style={styles.value}>prabhakar@pkphotography.in</Text>
        <Text style={[styles.label, { marginTop: spacing.xl }]}>Platform name</Text>
        <TextInput value={name} onChangeText={setName} style={styles.input} />
        <Button title="Save settings" loading={saving} onPress={save} />
        {message ? <Text style={styles.note}>{message}</Text> : null}
      </View>
      <View style={styles.panel}>
        <Text style={styles.sectionTitle}>Notification preferences</Text>
        <NotificationPrefs testID="superadmin-notification-prefs" />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { paddingBottom: spacing["3xl"] },
  loading: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#F7F8FA" },
  panel: {
    marginHorizontal: spacing["2xl"],
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#EAECF0",
    borderRadius: radius.lg,
    padding: spacing.xl,
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    color: "#101828",
    fontFamily: fonts.display,
    fontSize: 20,
    marginBottom: spacing.md,
  },
  label: { color: "#667085", fontFamily: fonts.text, fontSize: 12, fontWeight: "700", marginBottom: spacing.sm },
  value: { color: "#101828", fontFamily: fonts.text, fontSize: 15 },
  input: { height: 48, borderWidth: 1, borderColor: "#D0D5DD", borderRadius: radius.md, paddingHorizontal: spacing.md, color: "#344054", fontFamily: fonts.text, fontSize: 14, marginBottom: spacing.lg },
  note: { color: "#667085", fontFamily: fonts.text, fontSize: 12, marginTop: spacing.md },
});
