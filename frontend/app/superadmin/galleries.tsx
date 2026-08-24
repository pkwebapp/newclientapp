import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { api } from "@/src/api/client";
import { SuperAdminHeader, StatusBadge } from "@/src/components/SuperAdminShell";
import { colors, fonts, radius, spacing } from "@/src/theme";

export default function Galleries() {
  const [rows, setRows] = useState<any[]>([]); const [query, setQuery] = useState(""); const [loading, setLoading] = useState(true);
  const load = useCallback(async () => { setLoading(true); try { setRows(await api.get(`/superadmin/galleries${query ? `?q=${encodeURIComponent(query)}` : ""}`)); } finally { setLoading(false); } }, [query]);
  useFocusEffect(useCallback(() => { load().catch(() => setRows([])); }, [load]));
  return <ScrollView testID="superadmin-galleries" contentContainerStyle={styles.page}><SuperAdminHeader title="Galleries" subtitle="Every gallery across the platform" /><TextInput testID="superadmin-gallery-search" value={query} onChangeText={setQuery} onSubmitEditing={() => load()} placeholder="Search gallery or photographer" placeholderTextColor="#98A2B3" style={styles.search} />{loading ? <View style={styles.loading}><ActivityIndicator color={colors.brand} /></View> : <View style={styles.list}>{rows.map((row) => <View key={row.event_id} style={styles.row}><View style={{ flex: 1 }}><Text style={styles.name}>{row.name}</Text><Text style={styles.sub}>{row.photographer || "Unknown photographer"}</Text></View><View style={styles.stats}><Text style={styles.stat}>{row.images.toLocaleString("en-IN")} images</Text><StatusBadge status={row.status} /></View></View>)}</View>}</ScrollView>;
}
const styles = StyleSheet.create({ page: { paddingBottom: spacing["3xl"] }, search: { height: 48, marginHorizontal: spacing["2xl"], paddingHorizontal: spacing.md, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#D0D5DD", borderRadius: radius.md, color: "#344054", fontFamily: fonts.text }, list: { margin: spacing["2xl"], backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.lg, overflow: "hidden" }, row: { flexDirection: "row", alignItems: "center", padding: spacing.lg, borderBottomWidth: 1, borderBottomColor: "#F2F4F7" }, name: { color: "#101828", fontFamily: fonts.text, fontSize: 14, fontWeight: "700" }, sub: { color: "#667085", fontFamily: fonts.text, fontSize: 12, marginTop: 4 }, stats: { alignItems: "flex-end", gap: spacing.sm }, stat: { color: "#667085", fontFamily: fonts.text, fontSize: 12 }, loading: { padding: spacing["3xl"], alignItems: "center" } });
