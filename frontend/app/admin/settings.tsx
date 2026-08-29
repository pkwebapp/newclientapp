import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { PhoneField } from "@/src/components/PhoneField";
import { NotificationPrefs } from "@/src/components/NotificationPrefs";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { goBackOr } from "@/src/navigation/back";


export default function StudioSettings() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [phone, setPhone] = useState("");
  const [reviewUrl, setReviewUrl] = useState("");
  const [bookingEmail, setBookingEmail] = useState("");

  const load = useCallback(async () => {
    try {
      const p = await api.get("/studio/profile");
      setName(p.name || "");
      setWhatsapp(p.whatsapp || "");
      setPhone(p.phone || "");
      setReviewUrl(p.google_review_url || "");
      setBookingEmail(p.booking_email || "");
    } catch {
      toast.show("Could not load settings", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const save = async () => {
    setSaving(true);
    try {
      await api.patch("/studio/profile", {
        name: name.trim(),
        whatsapp: whatsapp.trim(),
        phone: phone.trim(),
        google_review_url: reviewUrl.trim(),
        booking_email: bookingEmail.trim(),
      });
      toast.show("Settings saved", "success");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not save", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.container} testID="studio-settings-screen">
      <GlassHeader title="Studio Settings" onBack={() => goBackOr(router, "/admin")} topInset={insets.top} />
      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>
      ) : (
        <KeyboardAwareScrollView contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing["2xl"] }]} bottomOffset={24} keyboardShouldPersistTaps="handled">
          <View style={styles.info}>
            <Ionicons name="information-circle-outline" size={16} color={colors.muted} />
            <Text style={styles.infoText}>These details power the client Quick Actions — Message (WhatsApp), Call, and the Google review link.</Text>
          </View>
          <TextField testID="studio-name" label="Studio name" value={name} onChangeText={setName} placeholder="PK Photography" />
          <PhoneField testID="studio-whatsapp" label="WhatsApp number" value={whatsapp} onChangeText={setWhatsapp} placeholder="Enter mobile number" required={false} />
          <PhoneField testID="studio-phone" label="Call number" value={phone} onChangeText={setPhone} placeholder="Enter mobile number" required={false} />
          <TextField testID="studio-review-url" label="Google review link" value={reviewUrl} onChangeText={setReviewUrl} placeholder="https://g.page/r/…" autoCapitalize="none" />
          <TextField testID="studio-booking-email" label="Booking email" value={bookingEmail} onChangeText={setBookingEmail} placeholder="studio@email.com" autoCapitalize="none" keyboardType="email-address" />
          <Button testID="save-settings-btn" title="Save settings" loading={saving} onPress={save} icon="checkmark" />

          {/* ---- Broadcast tile ---- */}
          <Text style={styles.sectionTitle}>Announcements</Text>
          <Pressable
            testID="open-notify-page"
            onPress={() => router.push("/admin/notify")}
            style={styles.tile}
          >
            <View style={styles.tileIcon}>
              <Ionicons name="megaphone-outline" size={20} color={colors.brand} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.tileTitle}>Send an announcement</Text>
              <Text style={styles.tileSub}>Notify a single gallery, all your clients, or specific people.</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </Pressable>

          {/* ---- Notification preferences ---- */}
          <Text style={styles.sectionTitle}>Notification preferences</Text>
          <NotificationPrefs testID="admin-notification-prefs" />
        </KeyboardAwareScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  body: { padding: spacing.xl },
  info: { flexDirection: "row", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.xl, borderWidth: 1, borderColor: colors.brandTertiary },
  infoText: { flex: 1, color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18 },
  sectionTitle: {
    color: colors.onSurface,
    fontFamily: fonts.display,
    fontSize: fontSize.xl,
    marginTop: spacing["2xl"],
    marginBottom: spacing.md,
  },
  tile: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
    minHeight: 68,
    marginBottom: spacing.xl,
  },
  tileIcon: { width: 40, height: 40, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.brandTertiary },
  tileTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  tileSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginTop: 3 },
});
