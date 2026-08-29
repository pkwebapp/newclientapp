import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { api } from "@/src/api/client";
import { Button, GlassHeader, Pill, TextField, useToast } from "@/src/components/ui";
import DatePickerField, { isValidIsoDate } from "@/src/components/DatePickerField";
import { lightColors as colors, fonts, fontSize, spacing } from "@/src/theme";
export default function ClientBookingDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const [b, setB] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [eventName, setEventName] = useState("");
  const [preferredDate, setPreferredDate] = useState("");
  const [location, setLocation] = useState("");
  const [requirement, setRequirement] = useState("");
  const [changeMessage, setChangeMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const data = await api.get(`/me/bookings/${id}`);
      setB(data);
      setEventName(data.event_name || "");
      setPreferredDate(isValidIsoDate(data.preferred_date || "") ? data.preferred_date : "");
      setLocation(data.location || "");
      setRequirement(data.requirement || "");
    } finally { setLoading(false); }
  }, [id]);
  useFocusEffect(useCallback(() => { load().catch(() => {}); }, [load]));
  const accept = async () => {
    setBusy(true);
    try { await api.post(`/me/bookings/${id}/quote/accept`, {}); toast.show("Quotation accepted — payment pending", "success"); await load(); }
    catch (e: any) { toast.show(e.message || "Could not accept quotation", "error"); }
    finally { setBusy(false); }
  };
  const saveEdits = async () => {
    if (!changeMessage.trim() && eventName === (b?.event_name || "") && preferredDate === (b?.preferred_date || "") && location === (b?.location || "") && requirement === (b?.requirement || "")) {
      toast.show("Add a change or message for the studio", "error"); return;
    }
    setBusy(true);
    try {
      await api.patch(`/me/bookings/${id}`, { event_name: eventName, preferred_date: preferredDate || null, location: location || null, requirement: requirement || null, message: changeMessage || null });
      toast.show("Changes sent to the studio", "success"); setEditing(false); setChangeMessage(""); await load();
    } catch (e: any) { toast.show(e.message || "Could not send changes", "error"); }
    finally { setBusy(false); }
  };
  if (loading) return <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>;
  return (
    <View style={styles.container}>
      <GlassHeader title="Booking details" onBack={() => router.back()} />
      <KeyboardAwareScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled" bottomOffset={24}>
        {b ? <>
          <View style={styles.heroRow}><View style={{ flex: 1 }}><Text style={styles.title}>{b.event_name || b.service_type}</Text><Text style={styles.sub}>{b.preferred_date || "Date pending"} · {b.location || "Location pending"}</Text></View><Pill label={b.status.replaceAll("_", " ")} tone={b.status === "scheduled" || b.status === "confirmed" ? "success" : "neutral"} /></View>
          <View style={styles.card}><Text style={styles.heading}>Your enquiry</Text><Text style={styles.sub}>{b.service_type}</Text><Text style={styles.sub}>{b.message || b.requirement || "No additional requirements"}</Text></View>
          {b.total_amount != null ? <View style={styles.card}><Text style={styles.heading}>Quotation {b.quote_revision ? `v${b.quote_revision}` : ""}</Text><Text style={styles.total}>₹{b.total_amount}</Text><Text style={styles.sub}>Booking amount: ₹{b.advance_amount || 0}</Text><Text style={styles.sub}>Paid: ₹{b.paid_amount || 0} · Balance: ₹{b.remaining_amount || 0}</Text>{b.offerings?.length ? <View style={styles.offerings}>{b.offerings.map((item: any, index: number) => <View key={`${item.title}-${index}`} style={styles.offerRow}><View style={{ flex: 1 }}><Text style={styles.offerTitle}>{item.title}</Text>{item.description ? <Text style={styles.sub}>{item.description}</Text> : null}</View>{item.amount ? <Text style={styles.offerAmount}>₹{item.amount}</Text> : null}</View>)}</View> : null}{b.payment_terms ? <Text style={styles.terms}>{b.payment_terms}</Text> : null}{b.status === "quotation" ? <View style={styles.actionRow}><Button testID="edit-booking-btn" title="Edit enquiry" variant="secondary" onPress={() => setEditing((value) => !value)} style={styles.actionButton} /><Button testID="accept-quotation-btn" title="Accept quote" loading={busy} onPress={accept} style={styles.actionButton} /></View> : null}</View> : null}
          {b.status === "payment_pending" ? <View style={styles.infoBox}><Text style={styles.infoTitle}>Booking amount pending</Text><Text style={styles.sub}>The studio will confirm your date after your booking payment is received.</Text></View> : null}
          {b.status === "scheduled" ? <View style={styles.card}><Text style={styles.heading}>Upcoming shoot</Text><Text style={styles.sub}>{b.schedule?.date || b.preferred_date} · {b.schedule?.start_time || b.start_time}–{b.schedule?.end_time || b.end_time}</Text><Text style={styles.sub}>{b.schedule?.venue || b.location}</Text></View> : null}
          {editing ? <View style={styles.card}><Text style={styles.heading}>Request changes</Text><TextField label="Event / booking name" value={eventName} onChangeText={setEventName} placeholder="Event name" /><DatePickerField testID="client-booking-preferred-date" label="Preferred date" value={preferredDate} onChange={setPreferredDate} emptyLabel="Choose preferred date" /><TextField label="Location" value={location} onChangeText={setLocation} placeholder="Venue / city" /><TextField label="Requirements" value={requirement} onChangeText={setRequirement} placeholder="What would you like changed?" /><TextInput testID="booking-change-message" value={changeMessage} onChangeText={setChangeMessage} multiline placeholder="Add a message for the studio" placeholderTextColor={colors.muted} style={styles.multiline} /><Button testID="save-booking-changes-btn" title="Send changes to studio" loading={busy} onPress={saveEdits} /></View> : null}
        </> : null}
      </KeyboardAwareScrollView>
    </View>
  );
}
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
  body: { padding: spacing.lg, paddingBottom: spacing["3xl"] },
  heroRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md, marginBottom: spacing.lg },
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], flex: 1 },
  sub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 20, marginTop: spacing.sm },
  card: { backgroundColor: colors.surfaceSecondary, padding: spacing.lg, borderRadius: 12, marginBottom: spacing.lg, borderWidth: 1, borderColor: colors.border },
  heading: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "700", marginBottom: spacing.md },
  total: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize["3xl"], marginBottom: spacing.sm },
  offerings: { marginTop: spacing.lg, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  offerRow: { flexDirection: "row", gap: spacing.md, paddingVertical: spacing.md, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  offerTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  offerAmount: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  terms: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginTop: spacing.lg },
  actionRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg },
  actionButton: { flex: 1 },
  infoBox: { backgroundColor: colors.brandTertiary, padding: spacing.lg, borderRadius: 12, marginBottom: spacing.lg },
  infoTitle: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  multiline: { minHeight: 100, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 10, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, padding: spacing.md, textAlignVertical: "top", marginBottom: spacing.lg },
});
