import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { api } from "@/src/api/client";
import { Button, GlassHeader, TextField, Pill, useToast } from "@/src/components/ui";
import DatePickerField, { isValidIsoDate } from "@/src/components/DatePickerField";
import { colors, fonts, fontSize, spacing } from "@/src/theme";
import { timeError } from "@/src/utils/validators";
export default function AdminBookingDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const [b, setB] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [total, setTotal] = useState("");
  const [advance, setAdvance] = useState("");
  const [offeringsText, setOfferingsText] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [scheduledDate, setScheduledDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const startTimeErr = timeError(startTime);
  const endTimeErr = timeError(endTime);
  const [venue, setVenue] = useState("");
  const [assignedPhotographer, setAssignedPhotographer] = useState("");
  const [eventName, setEventName] = useState("");
  const [serviceType, setServiceType] = useState("");
  const [preferredDate, setPreferredDate] = useState("");
  const [location, setLocation] = useState("");
  const [requirement, setRequirement] = useState("");

  const load = useCallback(async () => {
    try {
      const x = await api.get(`/bookings/${id}`);
      setB(x);
      setTotal(String(x.total_amount ?? ""));
      setAdvance(String(x.advance_amount ?? ""));
      setPaymentAmount(String(x.advance_amount ?? ""));
      setOfferingsText((x.offerings || []).map((item: any) => `${item.title || ""} | ${item.description || ""} | ${item.amount || 0}`).join("\n"));
      setEventName(x.event_name || "");
      setServiceType(x.service_type || "");
      setPreferredDate(isValidIsoDate(x.preferred_date || "") ? x.preferred_date : "");
      setLocation(x.location || "");
      setRequirement(x.requirement || "");
      setScheduledDate(isValidIsoDate(x.schedule?.date || x.preferred_date || "") ? (x.schedule?.date || x.preferred_date) : "");
      setStartTime(x.schedule?.start_time || x.start_time || "");
      setEndTime(x.schedule?.end_time || x.end_time || "");
      setVenue(x.schedule?.venue || x.location || "");
      setAssignedPhotographer(x.schedule?.assigned_photographer || "");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useFocusEffect(useCallback(() => { load().catch(() => {}); }, [load]));

  const saveEnquiry = async () => {
    setSaving(true);
    try {
      await api.patch(`/bookings/${id}`, { event_name: eventName, service_type: serviceType, preferred_date: preferredDate || null, location: location || null, requirement: requirement || null });
      toast.show("Booking enquiry updated", "success");
      await load();
    } catch (e: any) {
      toast.show(e.message || "Could not update booking", "error");
    } finally { setSaving(false); }
  };

  const parseOfferings = () => offeringsText.split("\n").map((line) => {
    const [title, description, amount] = line.split("|").map((part) => part.trim());
    return { title, description, amount: Number(amount || 0) };
  }).filter((item) => item.title);

  const quote = async () => {
    const totalAmount = Number(total);
    const advanceAmount = Number(advance);
    if (!totalAmount || advanceAmount < 0 || advanceAmount > totalAmount) {
      toast.show("Enter a valid total and booking amount", "error");
      return;
    }
    setSaving(true);
    try {
      await api.post(`/bookings/${id}/quote`, { total_amount: totalAmount, advance_amount: advanceAmount, payment_terms: "Booking amount is due to confirm the date. Remaining balance is due before delivery.", notes: b?.notes || null, offerings: parseOfferings() });
      toast.show("Detailed quotation sent to client", "success");
      await load();
    } catch (e: any) { toast.show(e.message || "Could not send quotation", "error"); }
    finally { setSaving(false); }
  };

  const addPayment = async () => {
    const amount = Number(paymentAmount);
    if (!amount || amount <= 0) { toast.show("Enter a payment amount", "error"); return; }
    try {
      await api.post(`/bookings/${id}/payments`, { label: "Booking payment", amount, method: paymentMethod, status: "paid" });
      toast.show("Payment recorded", "success");
      await load();
    } catch (e: any) { toast.show(e.message || "Could not record payment", "error"); }
  };

  const schedule = async () => {
    if (!scheduledDate || !startTime || !endTime || !venue) { toast.show("Add date, time, and venue before scheduling", "error"); return; } if (startTimeErr || endTimeErr) { toast.show(startTimeErr || endTimeErr || "Fix the time fields", "error"); return; }
    try {
      await api.post(`/bookings/${id}/schedule`, { scheduled_date: scheduledDate, start_time: startTime, end_time: endTime, venue, assigned_photographer: assignedPhotographer || null });
      toast.show("Shoot scheduled and client notified", "success");
      await load();
    } catch (e: any) { toast.show(e.message || "Could not schedule booking", "error"); }
  };

  if (loading) return <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>;
  return (
    <View style={styles.container}>
      <GlassHeader title="Booking workspace" subtitle={b?.contact_name || "Client enquiry"} onBack={() => router.back()} />
      <KeyboardAwareScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled" bottomOffset={24}>
        {b ? <>
          <View style={styles.heroRow}>
            <View style={{ flex: 1 }}><Text style={styles.title}>{b.event_name || b.service_type}</Text><Text style={styles.sub}>{b.contact_phone || b.contact_email || "No contact details"}</Text></View>
            <Pill label={b.status.replaceAll("_", " ")} tone={b.status === "scheduled" || b.status === "confirmed" ? "success" : "neutral"} />
          </View>
          <View style={styles.card}><Text style={styles.heading}>Client & enquiry</Text><Text style={styles.value}>{b.contact_name || "Client"}</Text><Text style={styles.sub}>{b.contact_phone || "Phone not provided"} · {b.contact_email || "Email not provided"}</Text><TextField label="Event / booking name" value={eventName} onChangeText={setEventName} placeholder="Wedding of..." /><TextField label="Service type" value={serviceType} onChangeText={setServiceType} placeholder="Wedding photography" /><DatePickerField testID="booking-preferred-date" label="Preferred date" value={preferredDate} onChange={setPreferredDate} emptyLabel="Choose preferred date" /><TextField label="Location" value={location} onChangeText={setLocation} placeholder="Venue / city" /><TextField label="Requirements" value={requirement} onChangeText={setRequirement} placeholder="Coverage and expectations" /><Button title="Save enquiry changes" loading={saving} variant="secondary" onPress={saveEnquiry} /></View>
          <View style={styles.card}><Text style={styles.heading}>Build quotation</Text><Text style={styles.helper}>Add one inclusion per line: Service | details | amount</Text><TextInput testID="quote-offerings" value={offeringsText} onChangeText={setOfferingsText} multiline placeholder="8 hours photography | Two photographers | 45000\nEdited gallery | 500 edited images | 0" placeholderTextColor={colors.muted} style={styles.multiline} /><View style={styles.row}><View style={{ flex: 1 }}><TextField label="Total price" value={total} onChangeText={setTotal} keyboardType="numeric" placeholder="75000" /></View><View style={{ flex: 1 }}><TextField label="Booking amount" value={advance} onChangeText={setAdvance} keyboardType="numeric" placeholder="25000" /></View></View><Button testID="send-quotation-btn" title={b.quote_revision ? `Send quotation revision ${Number(b.quote_revision) + 1}` : "Submit quotation to client"} loading={saving} onPress={quote} /></View>
          <View style={styles.card}><Text style={styles.heading}>Payments</Text><Text style={styles.sub}>Paid ₹{b.paid_amount || 0} · Balance ₹{b.remaining_amount || 0}</Text><View style={styles.row}><View style={{ flex: 1 }}><TextField label="Amount received" value={paymentAmount} onChangeText={setPaymentAmount} keyboardType="numeric" placeholder={String(b.advance_amount || "0")} /></View><View style={{ flex: 1 }}><TextField label="Method" value={paymentMethod} onChangeText={setPaymentMethod} placeholder="cash / UPI / bank" /></View></View><Button testID="record-payment-btn" title="Record payment received" variant="secondary" onPress={addPayment} /></View>
          <View style={styles.card}><Text style={styles.heading}>Schedule shoot</Text><Text style={styles.helper}>{b.status === "confirmed" ? "Payment received. Choose a date and time to add this shoot to the calendar." : "Scheduling unlocks after the booking amount is received."}</Text><DatePickerField testID="booking-schedule-date" label="Shoot date" value={scheduledDate} onChange={setScheduledDate} emptyLabel="Choose shoot date" /><TextField label="Venue" value={venue} onChangeText={setVenue} placeholder="Venue / address" /><View style={styles.row}><View style={{ flex: 1 }}><TextField label="Start time" value={startTime} onChangeText={setStartTime} placeholder="10:00" error={startTimeErr || undefined} /></View><View style={{ flex: 1 }}><TextField label="End time" value={endTime} onChangeText={setEndTime} placeholder="18:00" error={endTimeErr || undefined} /></View></View><TextField label="Assigned photographer" value={assignedPhotographer} onChangeText={setAssignedPhotographer} placeholder="Photographer name" /><Button testID="schedule-booking-btn" title="Schedule shoot" disabled={b.status !== "confirmed"} onPress={schedule} /></View>
          {b.payments?.length ? <View><Text style={styles.heading}>Payment history</Text>{b.payments.map((p: any) => <Text key={p.payment_id} style={styles.sub}>{p.label}: ₹{p.amount} · {p.method} · {p.status}</Text>)}</View> : null}
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
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], marginBottom: spacing.xs, flex: 1 },
  card: { backgroundColor: colors.surfaceSecondary, padding: spacing.lg, borderRadius: 12, marginBottom: spacing.lg, borderWidth: 1, borderColor: colors.border },
  heading: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "700", marginBottom: spacing.md },
  value: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, marginBottom: spacing.xs },
  sub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: spacing.xs },
  helper: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginBottom: spacing.md },
  multiline: { minHeight: 120, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 10, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, padding: spacing.md, textAlignVertical: "top", marginBottom: spacing.lg },
  row: { flexDirection: "row", gap: spacing.md },
});
