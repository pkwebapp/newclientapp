import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
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

  const pickQr = async () => {
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        toast.show("Photo permission needed to add a QR", "error");
        return;
      }
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: 0.8,
        base64: true,
      });
      if (res.canceled || !res.assets?.[0]?.base64) return;
      const asset = res.assets[0];
      const mime = asset.mimeType || "image/png";
      set("qr_base64", `data:${mime};base64,${asset.base64}`);
      toast.show("QR added", "success");
    } catch {
      toast.show("Could not load image", "error");
    }
  };

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
        proforma_prefix: s.proforma_prefix,
        number_format: s.number_format,
        number_padding: Number(s.number_padding) || 4,
        default_gst_rate: Number(s.default_gst_rate) || 0,
        default_gst_mode: s.default_gst_mode,
        default_terms: s.default_terms,
        place_of_supply_default: s.place_of_supply_default,
        bank_account_name: s.bank_account_name,
        bank_name: s.bank_name,
        bank_account_number: s.bank_account_number,
        bank_ifsc: s.bank_ifsc,
        upi: s.upi,
        qr_base64: s.qr_base64,
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

            <Text style={styles.section}>Numbering</Text>
            <Text style={styles.hint}>GST-approved serial formats (Rule 46(b): ≤16 chars, unique per financial year).</Text>
            <View style={styles.formatWrap}>
              {(s.number_format_options || []).map((opt: any) => (
                <Pressable
                  key={opt.key}
                  testID={`numfmt-${opt.key}`}
                  onPress={() => set("number_format", opt.key)}
                  style={[styles.formatBtn, s.number_format === opt.key && styles.modeBtnActive]}
                >
                  <Text style={[styles.formatLabel, s.number_format === opt.key && styles.modeLabelActive]}>{opt.label}</Text>
                </Pressable>
              ))}
            </View>
            <View style={styles.two}>
              <View style={{ flex: 1 }}><TextField label="Invoice prefix" value={s.invoice_prefix || ""} onChangeText={(t) => set("invoice_prefix", t)} placeholder="INV-" /></View>
              <View style={{ flex: 1 }}><TextField label="Proforma prefix" value={s.proforma_prefix || ""} onChangeText={(t) => set("proforma_prefix", t)} placeholder="PRO-" /></View>
            </View>
            <TextField label="Number padding (digits)" value={String(s.number_padding ?? "")} onChangeText={(t) => set("number_padding", t)} keyboardType="numeric" placeholder="4" />
            <Text style={styles.hint}>Tip: for formats with slashes (e.g. INV/25-26/0001), set the prefix without a trailing dash.</Text>

            <Text style={styles.section}>Defaults</Text>
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

            <Text style={styles.section}>Transfer / Payment details</Text>
            <Text style={styles.hint}>Shown on invoices so clients can pay you directly.</Text>
            <TextField label="Account holder name" value={s.bank_account_name || ""} onChangeText={(t) => set("bank_account_name", t)} placeholder="Prabhakar Kumar" />
            <View style={styles.two}>
              <View style={{ flex: 1 }}><TextField label="Bank name" value={s.bank_name || ""} onChangeText={(t) => set("bank_name", t)} placeholder="Kotak Mahindra Bank" /></View>
              <View style={{ flex: 1 }}><TextField label="IFSC" value={s.bank_ifsc || ""} onChangeText={(t) => set("bank_ifsc", t)} placeholder="KKBK0000668" autoCapitalize="characters" /></View>
            </View>
            <TextField label="Account number" value={s.bank_account_number || ""} onChangeText={(t) => set("bank_account_number", t)} keyboardType="numeric" placeholder="3012516828" />
            <TextField label="UPI ID / number" value={s.upi || ""} onChangeText={(t) => set("upi", t)} autoCapitalize="none" placeholder="name@upi or 9876543210" />

            <Text style={styles.fieldLabel}>Payment QR code</Text>
            <View style={styles.qrRow}>
              {s.qr_base64 ? (
                <Image source={{ uri: s.qr_base64 }} style={styles.qrPreview} contentFit="contain" />
              ) : (
                <View style={[styles.qrPreview, styles.qrPlaceholder]}>
                  <Text style={styles.qrPlaceholderText}>No QR</Text>
                </View>
              )}
              <View style={{ flex: 1, gap: spacing.sm }}>
                <Button testID="pick-qr" title={s.qr_base64 ? "Replace QR" : "Upload QR"} icon="qr-code-outline" variant="secondary" onPress={pickQr} />
                {s.qr_base64 ? (
                  <Pressable testID="remove-qr" onPress={() => set("qr_base64", "")} style={styles.removeQr}>
                    <Text style={styles.removeQrText}>Remove QR</Text>
                  </Pressable>
                ) : null}
              </View>
            </View>

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
  two: { flexDirection: "row", gap: spacing.sm },
  formatWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.md },
  formatBtn: { paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderRadius: radius.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  formatLabel: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  qrRow: { flexDirection: "row", alignItems: "center", gap: spacing.lg, marginTop: spacing.sm },
  qrPreview: { width: 96, height: 96, borderRadius: radius.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  qrPlaceholder: { alignItems: "center", justifyContent: "center" },
  qrPlaceholderText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  removeQr: { alignItems: "center", paddingVertical: spacing.sm },
  removeQrText: { color: colors.onError, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
});
