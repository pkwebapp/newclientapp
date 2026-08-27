import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { api } from "@/src/api/client";
import { SuperAdminHeader, StatCard, StatusBadge, formatBytes } from "@/src/components/SuperAdminShell";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const number = (value: number) => new Intl.NumberFormat("en-IN", { notation: value > 999999 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value || 0);

export default function SuperAdminDashboard() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try { setData(await api.get("/superadmin/overview")); } finally { setRefreshing(false); }
  }, []);
  useFocusEffect(useCallback(() => { load().catch(() => setData(null)); }, [load]));

  if (!data) return <View style={styles.loading}><ActivityIndicator color={colors.brand} /></View>;
  const stats = data.stats || {};
  const cards = [
    ["Total Photographers", number(stats.total_photographers), "people-outline"],
    ["Active Photographers", number(stats.active_photographers), "checkmark-circle-outline"],
    ["Total Galleries", number(stats.total_galleries), "images-outline"],
    ["Total Albums", number(stats.total_albums), "book-outline"],
    ["Total Images", number(stats.total_images), "image-outline"],
    ["Storage Used", formatBytes(stats.storage_bytes), "cloud-outline"],
    ["Uploads Today", number(stats.uploads_today), "cloud-upload-outline"],
  ];

  return (
    <ScrollView testID="superadmin-dashboard" contentContainerStyle={styles.page} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load().catch(() => setRefreshing(false)); }} />}>
      <SuperAdminHeader title="Dashboard" subtitle="A quick view of platform health" />
      <View style={styles.statsGrid}>{cards.map(([label, value, icon], index) => <StatCard key={label} label={label} value={value} icon={icon as any} accent={index === 1} />)}</View>

      <View style={styles.sectionHeader}><Text style={styles.sectionTitle}>Recent photographer activity</Text><Pressable onPress={() => router.push("/superadmin/activity")}><Text style={styles.link}>View all</Text></Pressable></View>
      <View style={styles.panel}>
        {(data.recent_activity || []).length === 0 ? <Text style={styles.empty}>Activity will appear here as studios use the platform.</Text> : (data.recent_activity || []).slice(0, 6).map((item: any, index: number) => (
          <View key={`${item.date}-${index}`} style={styles.activityRow}>
            <View style={styles.activityDot} />
            <View style={{ flex: 1 }}><Text style={styles.activityName}>{item.photographer}</Text><Text style={styles.activityDescription}>{item.action} · {item.description}</Text></View>
            <View style={styles.activityRight}><StatusBadge status={item.status || "Success"} /><Text style={styles.activityDate}>{item.date ? new Date(item.date).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—"}</Text></View>
          </View>
        ))}
      </View>

      <Text style={[styles.sectionTitle, { marginTop: spacing["2xl"] }]}>Accounts requiring attention</Text>
      <View style={styles.attentionGrid}>
        <Pressable style={styles.attentionRow} onPress={() => router.push("/superadmin/storage")}><View style={styles.attentionIcon}><Text style={styles.attentionNumber}>{data.attention?.storage_warnings || 0}</Text></View><View style={{ flex: 1 }}><Text style={styles.attentionTitle}>Storage warnings</Text><Text style={styles.attentionSub}>Photographers near their limit</Text></View><Text style={styles.link}>View</Text></Pressable>
        <Pressable style={styles.attentionRow} onPress={() => router.push("/superadmin/photographers?status=upload_disabled")}><View style={styles.attentionIcon}><Text style={styles.attentionNumber}>{data.attention?.uploads_disabled || 0}</Text></View><View style={{ flex: 1 }}><Text style={styles.attentionTitle}>Uploads disabled</Text><Text style={styles.attentionSub}>Accounts currently restricted</Text></View><Text style={styles.link}>View</Text></Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { paddingBottom: spacing["3xl"] },
  loading: { flex: 1, backgroundColor: "#F7F8FA", alignItems: "center", justifyContent: "center" },
  statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, paddingHorizontal: spacing["2xl"] },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: spacing["2xl"], marginTop: spacing["2xl"], marginBottom: spacing.md },
  sectionTitle: { color: "#101828", fontFamily: fonts.display, fontSize: fontSize.xl, fontWeight: "700", paddingHorizontal: spacing["2xl"] },
  link: { color: colors.brand, fontFamily: fonts.text, fontSize: 13, fontWeight: "700" },
  panel: { backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.lg, marginHorizontal: spacing["2xl"], paddingHorizontal: spacing.lg },
  empty: { color: "#667085", fontFamily: fonts.text, fontSize: 14, paddingVertical: spacing.xl },
  activityRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.lg, borderBottomWidth: 1, borderBottomColor: "#F2F4F7" },
  activityDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.brand },
  activityName: { color: "#344054", fontFamily: fonts.text, fontSize: 14, fontWeight: "700" },
  activityDescription: { color: "#667085", fontFamily: fonts.text, fontSize: 12, marginTop: 4 },
  activityRight: { alignItems: "flex-end", gap: 5 },
  activityDate: { color: "#98A2B3", fontFamily: fonts.text, fontSize: 11 },
  attentionGrid: { gap: spacing.sm, paddingHorizontal: spacing["2xl"], marginTop: spacing.md },
  attentionRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.md, padding: spacing.md, minHeight: 72 },
  attentionIcon: { width: 38, height: 38, borderRadius: radius.md, backgroundColor: "#FFF1EC", alignItems: "center", justifyContent: "center" },
  attentionNumber: { color: colors.brand, fontFamily: fonts.text, fontSize: 16, fontWeight: "800" },
  attentionTitle: { color: "#344054", fontFamily: fonts.text, fontSize: 14, fontWeight: "700" },
  attentionSub: { color: "#667085", fontFamily: fonts.text, fontSize: 12, marginTop: 3 },
});
