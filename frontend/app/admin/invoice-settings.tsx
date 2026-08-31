import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api/client";
import { Button, GlassHeader, TextField, useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const GST_MODES = [
  { key: "cgst_sgst", label: "CGST + SGST", hint: "Intra-state" },
  { key: "igst", label: "IGST", hint: "Inter-state" },
  { key: "none", label: "No GST", hint: "Unregistered" },
];

export default function InvoiceSettingsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [s, setS] = useState<any>({});

  const load = useCallback(async () => {
    try {
      const res = await api.get("/invoice-settings");
      setS(res);
    } catch {
      toast.show("Could not load settings", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const set = (k: string, v: any) => setS((prev: any) => ({ ...prev, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/invoice-settings", {
        legal_name: s.legal_name,
        address: s.address,
        gstin: s.gstin,
        state: s.state,
        phone: s.phone,
        email: s.email,
        invoice_prefix: s.invoice_prefix,
        default_gst_rate: Number(s.default_gst_rate) || 0,
        default_gst_mode: s.default_gst_mode,
        default_terms: s.default_terms,
        place_of_supply_default: s.place_of_supply_default,
      });
      toast.show("Invoice settings saved", "success");
      router.back();
    } catch {
      toast.show("Could not save settings", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.container} testID="admin-invoice-settings-screen">
      <GlassHeader title="Invoice Settings" subtitle="Your billing details" topInset={insets.top} onBack={() => router.back()} />
      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>
      ) : (
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
          <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 120 }} keyboardShouldPersistTaps="handled">
            <Text style={styles.hint}>Next invoice number: <Text style={{ color: colors.brand, fontWeight: "700" }}>{s.next_number_preview}</Text></Text>

            <Text style={styles.section}>Seller (your studio)</Text>
            <TextField label="Legal / studio name" value={s.legal_name || ""} onChangeText={(t) => set("legal_name", t)} placeholder="PK Photography" />
            <TextField label="GSTIN" value={s.gstin || ""} onChangeText={(t) => set("gstin", t)} placeholder="29ABCDE1234F1Z5" autoCapitalize="characters" />
            <TextField label="Address" value={s.address || ""} onChangeText={(t) => set("address", t)} placeholder="Street, City, PIN" multiline />
            <TextField label="State" value={s.state || ""} onChangeText={(t) => set("state", t)} placeholder="Karnataka" />
            <TextField label="Phone" value={s.phone || ""} onChangeText={(t) => set("phone", t)} keyboardType="phone-pad" />
            <TextField label="Email" value={s.email || ""} onChangeText={(t) => set("email", t)} keyboardType="email-address" autoCapitalize="none" />

            <Text style={styles.section}>Defaults</Text>
            <TextField label="Invoice prefix" value={s.invoice_prefix || ""} onChangeText={(t) => set("invoice_prefix", t)} placeholder="INV-" />
            <Text style={styles.fieldLabel}>Default GST type</Text>
            <View style={styles.modeRow}>
              {GST_MODES.map((m) => (
                <Pressable key={m.key} onPress={() => set("default_gst_mode", m.key)} style={[styles.modeBtn, s.default_gst_mode === m.key && styles.modeBtnActive]}>
                  <Text style={[styles.modeLabel, s.default_gst_mode === m.key && styles.modeLabelActive]}>{m.label}</Text>
                  <Text style={[styles.modeHint, s.default_gst_mode === m.key && { color: colors.onBrand }]}>{m.hint}</Text>
                </Pressable>
              ))}
            </View>
            <TextField label="Default GST rate (%)" value={String(s.default_gst_rate ?? "")} onChangeText={(t) => set("default_gst_rate", t)} keyboardType="numeric" placeholder="18" />
            <TextField label="Default place of supply" value={s.place_of_supply_default || ""} onChangeText={(t) => set("place_of_supply_default", t)} placeholder="Karnataka (29)" />
            <TextField label="Default terms / notes" value={s.default_terms || ""} onChangeText={(t) => set("default_terms", t)} multiline placeholder="Thank you for your business." />

            <Button testID="save-invoice-settings" title="Save settings" icon="save-outline" loading={saving} onPress={save} style={{ marginTop: spacing.lg }} />
          </ScrollView>
        </KeyboardAvoidingView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  hint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, marginBottom: spacing.lg },
  section: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing.md, marginBottom: spacing.md },
  fieldLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600", marginBottom: spacing.sm },
  modeRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.lg },
  modeBtn: { flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border, alignItems: "center" },
  modeBtnActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  modeLabel: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  modeLabelActive: { color: colors.onBrand },
  modeHint: { color: colors.muted, fontFamily: fonts.text, fontSize: 10, marginTop: 2 },
});
