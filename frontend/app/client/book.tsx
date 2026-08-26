import { useState } from "react";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import DatePickerField, { todayIso } from "@/src/components/DatePickerField";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { goBackOr } from "@/src/navigation/back";


const SERVICES = [
  { key: "Wedding", icon: "heart" },
  { key: "Couple Shoot", icon: "people" },
  { key: "Family Portrait", icon: "home" },
  { key: "Birthday", icon: "gift" },
  { key: "Corporate", icon: "business" },
  { key: "Videography", icon: "videocam" },
  { key: "Drone", icon: "airplane" },
  { key: "Other", icon: "ellipsis-horizontal" },
];

export default function BookPhotographer() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [service, setService] = useState("Wedding");
  const [date, setDate] = useState(todayIso());
  const [location, setLocation] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async () => {
    setLoading(true);
    try {
      await api.post("/me/booking-requests", {
        service_type: service,
        preferred_date: date.trim() || undefined,
        location: location.trim() || undefined,
        message: message.trim() || undefined,
      });
      setDone(true);
      toast.show("Inquiry sent — your studio will be in touch", "success");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not send inquiry", "error");
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <View style={styles.container} testID="book-screen">
        <GlassHeader title="Book Photographer" onBack={() => goBackOr(router, "/client")} topInset={insets.top} />
        <View style={styles.doneWrap}>
          <View style={styles.doneIcon}>
            <Ionicons name="checkmark" size={40} color={colors.brand} />
          </View>
          <Text style={styles.doneTitle}>Inquiry sent</Text>
          <Text style={styles.doneSub}>Your studio already knows you — they’ll reach out about your {service.toLowerCase()} soon.</Text>
          <View style={{ width: "100%", marginTop: spacing.xl }}>
            <Button title="Back to memories" onPress={() => router.replace("/client")} />
          </View>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID="book-screen">
      <GlassHeader title="Book Us Again" onBack={() => goBackOr(router, "/client")} topInset={insets.top} />
      <KeyboardAwareScrollView contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing["2xl"] }]} bottomOffset={24} keyboardShouldPersistTaps="handled">
        <Text style={styles.label}>What do you need?</Text>
        <View style={styles.chipWrap}>
          {SERVICES.map((s) => (
            <Pressable key={s.key} testID={`service-${s.key}`} onPress={() => setService(s.key)} style={[styles.chip, service === s.key && styles.chipActive]}>
              <Ionicons name={s.icon as any} size={14} color={service === s.key ? colors.onBrand : colors.onSurfaceTertiary} />
              <Text style={[styles.chipText, service === s.key && styles.chipTextActive]}>{s.key}</Text>
            </Pressable>
          ))}
        </View>
        <View style={{ marginTop: spacing.xl }}>
          <DatePickerField
            testID="book-date"
            label="Preferred date"
            value={date}
            onChange={setDate}
          />
          <TextField testID="book-location" label="Location" value={location} onChangeText={setLocation} placeholder="City / venue" />
          <TextField testID="book-message" label="Message" value={message} onChangeText={setMessage} placeholder="Tell us what you have in mind…" multiline />
          <Button testID="book-submit" title="Submit inquiry" loading={loading} onPress={submit} icon="send" />
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl },
  label: { color: colors.onSurfaceSecondary, fontSize: fontSize.sm, marginBottom: spacing.md, fontFamily: fonts.text, letterSpacing: 0.5, textTransform: "uppercase" },
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: spacing.lg, height: 40, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  chipTextActive: { color: colors.onBrand, fontWeight: "600" },
  doneWrap: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  doneIcon: { width: 84, height: 84, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", marginBottom: spacing.lg },
  doneTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  doneSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, textAlign: "center", marginTop: spacing.sm, lineHeight: 20, maxWidth: 300 },
});
