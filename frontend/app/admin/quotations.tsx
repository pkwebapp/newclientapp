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
import { QUOTE_STATUS_META } from "@/src/api/quotations";
import { formatINR } from "@/src/utils/format";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const FILTERS = [
  { key: "", label: "All" },
  { key: "sent", label: "Sent" },
  { key: "accepted", label: "Accepted" },
  { key: "revision_requested", label: "Revision" },
  { key: "draft", label: "Draft" },
];

export default function QuotationsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const [filter, setFilter] = useState("");
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get("/quotations");
      setItems(Array.isArray(res.items) ? res.items : []);
    } catch {
      toast.show("Could not load quotations", "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [toast]);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      load();
    }, [load])
  );

  const filtered = filter ? items.filter((q) => q.status === filter) : items;

  return (
    <View style={styles.container} testID="admin-quotations-screen">
      <GlassHeader
        title="Quotations"
        topInset={insets.top}
        onBack={() => router.back()}
        right={
          <Pressable testID="new-quotation-btn" onPress={() => router.push("/admin/quotation/new")} hitSlop={10}>
            <Ionicons name="add" size={26} color={colors.brand} />
          </Pressable>
        }
      />
      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 96 }}
          refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        >
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: spacing.lg }} contentContainerStyle={{ gap: spacing.sm }}>
            {FILTERS.map((f) => (
              <Pressable key={f.key || "all"} onPress={() => setFilter(f.key)} style={[styles.chip, filter === f.key && styles.chipActive]}>
                <Text style={[styles.chipText, filter === f.key && styles.chipTextActive]}>{f.label}</Text>
              </Pressable>
            ))}
          </ScrollView>

          {filtered.length === 0 ? (
            <EmptyState
              icon="reader-outline"
              title="No quotations yet"
              subtitle="Send premium quotes on your studio letterhead. Clients can accept or request changes."
              action={<Button testID="empty-new-quotation" title="New quotation" icon="add" onPress={() => router.push("/admin/quotation/new")} />}
              style={{ marginTop: spacing.md }}
            />
          ) : (
            filtered.map((q) => {
              const meta = QUOTE_STATUS_META[q.status] || QUOTE_STATUS_META.sent;
              return (
                <Pressable key={q.quotation_id} testID={`quotation-${q.quotation_id}`} onPress={() => router.push(`/admin/quotation/${q.quotation_id}`)} style={styles.row}>
                  <View style={styles.rowIcon}><Ionicons name="reader-outline" size={20} color={colors.brand} /></View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.rowTitle} numberOfLines={1}>{q.subject || q.client?.name || "Quotation"}</Text>
                    <Text style={styles.rowSub} numberOfLines={1}>{q.quotation_number} · {q.client?.name || "—"} · {q.issue_date}</Text>
                  </View>
                  <View style={{ alignItems: "flex-end", gap: 4 }}>
                    {q.show_pricing ? <Text style={styles.rowAmount}>{formatINR(q.total)}</Text> : null}
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
