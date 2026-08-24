import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "@/src/api/client";
import { SuperAdminHeader, StatusBadge, formatBytes } from "@/src/components/SuperAdminShell";
import { colors, fonts, radius, spacing } from "@/src/theme";

const FILTERS = ["all", "active", "trial", "expired", "suspended", "upload_disabled"];

export default function SuperadminPhotographers() {
  const router = useRouter();
  const [rows, setRows] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.get(`/superadmin/photographers?${filter !== "all" ? `status=${filter}` : ""}`)); } finally { setLoading(false); }
  }, [filter]);
  useFocusEffect(useCallback(() => { load().catch(() => setRows([])); }, [load]));

  const shown = rows.filter((row) => !query.trim() || row.name.toLowerCase().includes(query.trim().toLowerCase()) || (row.email || "").toLowerCase().includes(query.trim().toLowerCase()));

  return (
    <ScrollView testID="superadmin-photographers" contentContainerStyle={styles.page}>
      <SuperAdminHeader title="Photographers" subtitle="Manage every studio on the platform" />
      <View style={styles.controls}><View style={styles.search}><Ionicons name="search-outline" size={18} color="#98A2B3" /><TextInput testID="superadmin-photographer-search" value={query} onChangeText={setQuery} placeholder="Search name or email" placeholderTextColor="#98A2B3" style={styles.input} /></View><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>{FILTERS.map((item) => <Pressable key={item} testID={`superadmin-filter-${item}`} onPress={() => setFilter(item)} style={[styles.filter, filter === item && styles.filterActive]}><Text style={[styles.filterText, filter === item && styles.filterTextActive]}>{item.replace("_", " ")}</Text></Pressable>)}</ScrollView></View>
      {loading ? <View style={styles.loading}><ActivityIndicator color={colors.brand} /></View> : <View style={styles.list}>{shown.map((row) => <Pressable key={row.photographer_id} testID={`superadmin-photographer-${row.photographer_id}`} onPress={() => router.push(`/superadmin/photographer/${row.photographer_id}`)} style={styles.row}><View style={styles.avatar}><Text style={styles.avatarText}>{row.name.charAt(0).toUpperCase()}</Text></View><View style={styles.main}><Text style={styles.name} numberOfLines={1}>{row.name}</Text><Text style={styles.email} numberOfLines={1}>{row.email}</Text><View style={styles.meta}><Text style={styles.metaText}>{row.membership}</Text><Text style={styles.metaText}>{row.galleries} galleries</Text><Text style={styles.metaText}>{row.images.toLocaleString("en-IN")} images</Text><Text style={styles.metaText}>{formatBytes(row.storage_bytes)}</Text></View></View><View style={styles.right}><StatusBadge status={row.uploads_disabled ? "Uploads disabled" : row.status} /><Ionicons name="chevron-forward" size={18} color="#98A2B3" /></View></Pressable>)}</View>}
      {!loading && shown.length === 0 ? <Text style={styles.empty}>No photographers match this search.</Text> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({ page: { paddingBottom: spacing["3xl"] }, controls: { paddingHorizontal: spacing["2xl"] }, search: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#D0D5DD", borderRadius: radius.md, height: 48, paddingHorizontal: spacing.md }, input: { flex: 1, color: "#344054", fontFamily: fonts.text, fontSize: 14 }, filters: { gap: spacing.sm, paddingVertical: spacing.md }, filter: { paddingHorizontal: spacing.md, height: 36, alignItems: "center", justifyContent: "center", borderRadius: radius.pill, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0" }, filterActive: { backgroundColor: colors.brand, borderColor: colors.brand }, filterText: { color: "#667085", fontFamily: fonts.text, fontSize: 12, textTransform: "capitalize" }, filterTextActive: { color: colors.onBrand, fontWeight: "700" }, list: { marginHorizontal: spacing["2xl"], borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.lg, backgroundColor: "#FFFFFF", overflow: "hidden" }, row: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, borderBottomWidth: 1, borderBottomColor: "#F2F4F7", minHeight: 92 }, avatar: { width: 42, height: 42, borderRadius: radius.pill, backgroundColor: "#FFF1EC", alignItems: "center", justifyContent: "center" }, avatarText: { color: colors.brand, fontFamily: fonts.display, fontSize: 19, fontWeight: "700" }, main: { flex: 1, minWidth: 0 }, name: { color: "#101828", fontFamily: fonts.text, fontSize: 15, fontWeight: "700" }, email: { color: "#667085", fontFamily: fonts.text, fontSize: 12, marginTop: 3 }, meta: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: 8 }, metaText: { color: "#98A2B3", fontFamily: fonts.text, fontSize: 11 }, right: { alignItems: "flex-end", gap: spacing.sm }, loading: { padding: spacing["3xl"], alignItems: "center" }, empty: { color: "#667085", fontFamily: fonts.text, textAlign: "center", padding: spacing["2xl"] },});
