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
import { GlassHeader, Pill, useToast } from "@/src/components/ui";
import { STATUS_META, monthLabel } from "@/src/api/invoices";
import { formatINR } from "@/src/utils/format";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const PERIODS: { key: string; label: string }[] = [
  { key: "this_month", label: "This month" },
  { key: "this_year", label: "This year" },
  { key: "all", label: "All time" },
];

export default function RevenueScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const [period, setPeriod] = useState("this_month");
  const [summary, setSummary] = useState<any>(null);
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(
    async (p: string) => {
      try {
        const [s, r] = await Promise.all([
          api.get(`/revenue/summary?period=${p}`),
          api.get(`/revenue/records?period=${p}`),
        ]);
        setSummary(s);
        setRecords(r.items || []);
      } catch {
        toast.show("Could not load revenue", "error");
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
      load(period);
    }, [load, period])
  );

  const monthly: any[] = summary?.monthly || [];
  const maxVal = Math.max(1, ...monthly.map((m) => Math.max(m.booked || 0, m.collected || 0)));

  return (
    <View style={styles.container} testID="admin-revenue-screen">
      <GlassHeader title="Revenue" subtitle="Booked vs collected" topInset={insets.top} onBack={() => router.back()} />
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 96 }}
          refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(period); }} />}
        >
          {/* period selector */}
          <View style={styles.segment}>
            {PERIODS.map((p) => (
              <Pressable
                key={p.key}
                testID={`period-${p.key}`}
                onPress={() => setPeriod(p.key)}
                style={[styles.segmentBtn, period === p.key && styles.segmentBtnActive]}
              >
                <Text style={[styles.segmentText, period === p.key && styles.segmentTextActive]}>{p.label}</Text>
              </Pressable>
            ))}
          </View>

          {/* hero: collected */}
          <View style={styles.heroCard}>
            <Text style={styles.heroLabel}>COLLECTED</Text>
            <Text style={styles.heroValue}>{formatINR(summary?.collected)}</Text>
            <View style={styles.heroRow}>
              <View style={styles.heroChip}>
                <Ionicons name="cube-outline" size={14} color={colors.brand} />
                <Text style={styles.heroChipText}>Booked {formatINR(summary?.booked)}</Text>
              </View>
              <View style={styles.heroChip}>
                <Ionicons name="time-outline" size={14} color={colors.onWarning} />
                <Text style={[styles.heroChipText, { color: colors.onWarning }]}>Pending {formatINR(summary?.pending)}</Text>
              </View>
            </View>
          </View>

          {/* monthly trend */}
          <Text style={styles.sectionTitle}>Last 12 months</Text>
          <View style={styles.chartCard}>
            <View style={styles.chart}>
              {monthly.map((m, i) => (
                <View key={m.month} style={styles.barCol}>
                  <View style={styles.barTrack}>
                    <View style={[styles.barBooked, { height: `${Math.round(((m.booked || 0) / maxVal) * 100)}%` }]} />
                    <View style={[styles.barCollected, { height: `${Math.round(((m.collected || 0) / maxVal) * 100)}%` }]} />
                  </View>
                  <Text style={styles.barLabel}>{i % 2 === 0 ? monthLabel(m.month) : ""}</Text>
                </View>
              ))}
            </View>
            <View style={styles.legendRow}>
              <View style={styles.legendItem}><View style={[styles.legendDot, { backgroundColor: colors.brandTertiary }]} /><Text style={styles.legendText}>Booked</Text></View>
              <View style={styles.legendItem}><View style={[styles.legendDot, { backgroundColor: colors.brand }]} /><Text style={styles.legendText}>Collected</Text></View>
            </View>
          </View>

          {/* source breakdown */}
          <Text style={styles.sectionTitle}>By source</Text>
          <View style={styles.sourceRow}>
            <SourceCard icon="receipt-outline" title="Invoices" data={summary?.by_source?.invoices} />
            <SourceCard icon="images-outline" title="Galleries" data={summary?.by_source?.galleries} />
          </View>
          <Text style={styles.assumeNote}>Uninvoiced galleries count their shoot value as received. Linking an invoice to a gallery avoids double-counting.</Text>

          {/* records */}
          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitle}>Transactions</Text>
            <Pressable onPress={() => router.push("/admin/invoices")} hitSlop={8} style={styles.viewAll}>
              <Text style={styles.viewAllText}>Invoices</Text>
              <Ionicons name="chevron-forward" size={14} color={colors.brand} />
            </Pressable>
          </View>
          {records.length === 0 ? (
            <Text style={styles.emptyText}>No revenue in this period yet.</Text>
          ) : (
            records.map((rec) => {
              const meta = STATUS_META[rec.status] || STATUS_META.sent;
              return (
                <Pressable
                  key={`${rec.type}-${rec.ref_id}`}
                  style={styles.recRow}
                  onPress={() => rec.type === "invoice" ? router.push(`/admin/invoice/${rec.ref_id}`) : router.push(`/admin/event/${rec.ref_id}`)}
                >
                  <View style={styles.recIcon}>
                    <Ionicons name={rec.type === "invoice" ? "receipt-outline" : "images-outline"} size={18} color={colors.brand} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.recTitle} numberOfLines={1}>{rec.title}{rec.number ? `  ·  ${rec.number}` : ""}</Text>
                    <Text style={styles.recSub}>{rec.date || "—"}</Text>
                  </View>
                  <View style={{ alignItems: "flex-end", gap: 4 }}>
                    <Text style={styles.recAmount}>{formatINR(rec.collected)}</Text>
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

function SourceCard({ icon, title, data }: { icon: any; title: string; data?: any }) {
  return (
    <View style={styles.sourceCard}>
      <View style={styles.sourceHead}>
        <Ionicons name={icon} size={16} color={colors.brand} />
        <Text style={styles.sourceTitle}>{title}</Text>
        <Text style={styles.sourceCount}>{data?.count || 0}</Text>
      </View>
      <Text style={styles.sourceCollected}>{formatINR(data?.collected)}</Text>
      <Text style={styles.sourceBooked}>of {formatINR(data?.booked)} booked</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  segment: { flexDirection: "row", backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: 4, marginBottom: spacing.xl, borderWidth: 1, borderColor: colors.border },
  segmentBtn: { flex: 1, paddingVertical: spacing.sm, borderRadius: radius.sm, alignItems: "center" },
  segmentBtnActive: { backgroundColor: colors.brand },
  segmentText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
  segmentTextActive: { color: colors.onBrand },
  heroCard: { backgroundColor: colors.brandTertiary, borderRadius: radius.lg, padding: spacing.xl, borderWidth: 1, borderColor: colors.brand, marginBottom: spacing.xl },
  heroLabel: { color: colors.brand, fontFamily: fonts.text, fontSize: 11, fontWeight: "800", letterSpacing: 1.5 },
  heroValue: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.hero, marginTop: spacing.xs },
  heroRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg, flexWrap: "wrap" },
  heroChip: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: colors.surface, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 6 },
  heroChipText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  sectionTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginBottom: spacing.md },
  chartCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, padding: spacing.lg, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.xl },
  chart: { flexDirection: "row", alignItems: "flex-end", height: 140, gap: 4 },
  barCol: { flex: 1, alignItems: "center" },
  barTrack: { width: "70%", height: 120, justifyContent: "flex-end", position: "relative" },
  barBooked: { position: "absolute", bottom: 0, width: "100%", backgroundColor: colors.brandTertiary, borderRadius: 3 },
  barCollected: { position: "absolute", bottom: 0, width: "100%", backgroundColor: colors.brand, borderRadius: 3 },
  barLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: 9, marginTop: 4 },
  legendRow: { flexDirection: "row", gap: spacing.lg, marginTop: spacing.md, justifyContent: "center" },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  legendDot: { width: 10, height: 10, borderRadius: 3 },
  legendText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  sourceRow: { flexDirection: "row", gap: spacing.sm },
  sourceCard: { flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border },
  sourceHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: spacing.sm },
  sourceTitle: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700", flex: 1 },
  sourceCount: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  sourceCollected: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  sourceBooked: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  assumeNote: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.sm, marginBottom: spacing.xl, lineHeight: 18 },
  sectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  viewAll: { flexDirection: "row", alignItems: "center", gap: 2, marginBottom: spacing.md },
  viewAllText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  emptyText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, paddingVertical: spacing.lg },
  recRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border },
  recIcon: { width: 38, height: 38, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  recTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  recSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  recAmount: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
});
