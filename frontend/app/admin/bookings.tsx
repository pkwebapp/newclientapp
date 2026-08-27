import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { api } from "@/src/api/client";
import { GlassHeader, Pill } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const FILTERS = [["all", "All"], ["new_request", "New Request"], ["quotation", "Quotation"], ["payment_pending", "Payment Pending"], ["confirmed", "Confirmed"], ["completed", "Completed"], ["cancelled", "Cancelled"]] as const;

export default function AdminBookings() {
  const router = useRouter();
  const [filter, setFilter] = useState("all");
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => { setLoading(true); try { setRows(await api.get(`/bookings${filter === "all" ? "" : `?status=${filter}`}`)); } finally { setLoading(false); } }, [filter]);
  useFocusEffect(useCallback(() => { load().catch(() => setRows([])); }, [load]));
  return <View style={styles.container} testID="admin-bookings-screen">
    <GlassHeader title="Bookings" subtitle="Requests, quotations and confirmed shoots" onBack={() => router.back()} />
    <ScrollView contentContainerStyle={styles.body} horizontal={false}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>{FILTERS.map(([key, label]) => <Pressable key={key} testID={`booking-filter-${key}`} onPress={() => setFilter(key)} style={[styles.filter, filter === key && styles.filterActive]}><Text style={[styles.filterText, filter === key && styles.filterTextActive]}>{label}</Text></Pressable>)}</ScrollView>
      {loading ? <ActivityIndicator color={colors.brand} style={{ marginTop: spacing.xl }} /> : rows.length === 0 ? <Text style={styles.empty}>No bookings in this view.</Text> : rows.map((booking) => <Pressable key={booking.request_id} testID={`booking-row-${booking.request_id}`} onPress={() => router.push(`/admin/booking/${booking.request_id}`)} style={styles.card}><View style={{ flex: 1 }}><Text style={styles.title}>{booking.event_name || booking.service_type}</Text><Text style={styles.sub}>{booking.contact_name || "Client"} · {booking.preferred_date || "Date not set"}</Text><Text style={styles.meta}>{booking.requirement || booking.service_type} {booking.expected_budget ? `· ₹${booking.expected_budget}` : ""}</Text></View><Pill label={booking.status} tone={booking.status === "confirmed" ? "success" : "neutral"} /></Pressable>)}
    </ScrollView>
  </View>;
}
const styles = StyleSheet.create({ container: { flex: 1, backgroundColor: colors.surface }, body: { padding: spacing.lg, paddingBottom: spacing["3xl"] }, filters: { gap: spacing.sm, paddingBottom: spacing.lg }, filter: { paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border }, filterActive: { backgroundColor: colors.brand, borderColor: colors.brand }, filterText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm }, filterTextActive: { color: colors.onBrand }, card: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, marginBottom: spacing.md, borderRadius: radius.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border }, title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.lg }, sub: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: 4 }, meta: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 4 }, empty: { color: colors.muted, fontFamily: fonts.text, textAlign: "center", marginTop: spacing["2xl"] } });
