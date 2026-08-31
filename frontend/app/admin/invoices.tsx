import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api } from "@/src/api/client";
import { EmptyState, Button, GlassHeader, Pill, useToast } from "@/src/components/ui";
import { STATUS_META } from "@/src/api/invoices";
import { formatINR } from "@/src/utils/format";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const FILTERS = [
  { key: "", label: "All" },
  { key: "sent", label: "Sent" },
  { key: "partial", label: "Partial" },
  { key: "paid", label: "Paid" },
  { key: "draft", label: "Draft" },
];

export default function InvoicesScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const [filter, setFilter] = useState("");
  const [data, setData] = useState<any>({ items: [], booked: 0, received: 0 });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(
    async (f: string) => {
      try {
        const res = await api.get(`/invoices${f ? `?status=${f}` : ""}`);
        setData(res);
      } catch {
        toast.show("Could not load invoices", "error");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [toast]
  );

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      load(filter);
    }, [load, filter])
  );

  const items: any[] = data.items || [];

  return (
    <View style={styles.container} testID="admin-invoices-screen">
      <GlassHeader
        title="Invoices"
        topInset={insets.top}
        onBack={() => router.back()}
        right={
          <Pressable testID="new-invoice-btn" onPress={() => router.push("/admin/invoice/new")} hitSlop={10}>
            <Ionicons name="add" size={26} color={colors.brand} />
          </Pressable>
        }
      />
      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 96 }}
          refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(filter); }} />}
        >
          <View style={styles.totalsRow}>
            <View style={styles.totalCard}>
              <Text style={styles.totalLabel}>BOOKED</Text>
              <Text style={styles.totalValue}>{formatINR(data.booked)}</Text>
            </View>
            <View style={[styles.totalCard, { backgroundColor: colors.brandTertiary, borderColor: colors.brand }]}>
              <Text style={[styles.totalLabel, { color: colors.brand }]}>RECEIVED</Text>
              <Text style={styles.totalValue}>{formatINR(data.received)}</Text>
            </View>
          </View>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: spacing.lg }} contentContainerStyle={{ gap: spacing.sm }}>
            {FILTERS.map((f) => (
              <Pressable key={f.key || "all"} onPress={() => setFilter(f.key)} style={[styles.chip, filter === f.key && styles.chipActive]}>
                <Text style={[styles.chipText, filter === f.key && styles.chipTextActive]}>{f.label}</Text>
              </Pressable>
            ))}
          </ScrollView>

          {items.length === 0 ? (
            <EmptyState
              icon="receipt-outline"
              title="No invoices yet"
              subtitle="Create GST invoices with HSN codes, share a link and track payments."
              action={<Button testID="empty-new-invoice" title="New invoice" icon="add" onPress={() => router.push("/admin/invoice/new")} />}
              style={{ marginTop: spacing.md }}
            />
          ) : (
            items.map((inv) => {
              const meta = STATUS_META[inv.status] || STATUS_META.sent;
              return (
                <Pressable key={inv.invoice_id} testID={`invoice-${inv.invoice_id}`} onPress={() => router.push(`/admin/invoice/${inv.invoice_id}`)} style={styles.row}>
                  <View style={styles.rowIcon}><Ionicons name="receipt-outline" size={20} color={colors.brand} /></View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.rowTitle} numberOfLines={1}>{inv.client?.name || "Client"}</Text>
                    <Text style={styles.rowSub} numberOfLines={1}>{inv.invoice_number} · {inv.issue_date}</Text>
                  </View>
                  <View style={{ alignItems: "flex-end", gap: 4 }}>
                    <Text style={styles.rowAmount}>{formatINR(inv.total)}</Text>
                    <Pill label={meta.label} tone={meta.tone} />
                  </View>
                </Pressable>
              );
            })
          )}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  totalsRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.lg },
  totalCard: { flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border },
  totalLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  totalValue: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], marginTop: spacing.xs },
  chip: { paddingHorizontal: spacing.lg, paddingVertical: spacing.sm, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
  chipTextActive: { color: colors.onBrand },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border },
  rowIcon: { width: 42, height: 42, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  rowTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "700" },
  rowSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  rowAmount: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
});
