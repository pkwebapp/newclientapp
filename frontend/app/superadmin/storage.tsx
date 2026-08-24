import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { api } from "@/src/api/client";
import { SuperAdminHeader, ProgressBar, StatusBadge, formatBytes } from "@/src/components/SuperAdminShell";
import { colors, fonts, radius, spacing } from "@/src/theme";

export default function Storage() {
  const [data, setData] = useState<any>(null);
  const load = useCallback(async () => setData(await api.get("/superadmin/storage")), []);
  useFocusEffect(useCallback(() => { load().catch(() => setData(null)); }, [load]));
  if (!data) return <View style={styles.loading}><ActivityIndicator color={colors.brand} /></View>;
  const totalPercent = data.platform_limit_gb ? (data.total_bytes / (1024 ** 3) / data.platform_limit_gb) * 100 : 0;
  return <ScrollView testID="superadmin-storage" contentContainerStyle={styles.page}><SuperAdminHeader title="Storage" subtitle="Platform usage by photographer" /><View style={styles.panel}><View style={styles.head}><Text style={styles.title}>Total storage</Text><Text style={styles.value}>{formatBytes(data.total_bytes)} / 20 TB</Text></View><ProgressBar value={totalPercent} /></View><View style={styles.list}>{data.photographers.map((row: any) => { const used = row.storage_bytes / (1024 ** 3); const percent = row.storage_limit_gb ? (used / row.storage_limit_gb) * 100 : 0; return <View key={row.photographer_id} style={styles.row}><View style={{ flex: 1 }}><Text style={styles.name}>{row.name}</Text><Text style={styles.sub}>{row.membership} · {formatBytes(row.storage_bytes)} / {row.storage_limit_gb} GB</Text><View style={{ marginTop: spacing.sm }}><ProgressBar value={percent} /></View></View><StatusBadge status={percent >= 85 ? "Warning" : "Healthy"} /></View>; })}</View></ScrollView>;
}
const styles = StyleSheet.create({ page: { paddingBottom: spacing["3xl"] }, panel: { backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.lg, marginHorizontal: spacing["2xl"], padding: spacing.xl }, head: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.md }, title: { color: "#344054", fontFamily: fonts.text, fontSize: 15, fontWeight: "700" }, value: { color: colors.brand, fontFamily: fonts.text, fontSize: 14, fontWeight: "700" }, list: { margin: spacing["2xl"], gap: spacing.sm }, row: { flexDirection: "row", alignItems: "center", gap: spacing.lg, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.md, padding: spacing.lg }, name: { color: "#101828", fontFamily: fonts.text, fontSize: 14, fontWeight: "700" }, sub: { color: "#667085", fontFamily: fonts.text, fontSize: 12, marginTop: 4 }, loading: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#F7F8FA" } });
