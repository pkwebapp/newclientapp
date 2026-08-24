import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { api } from "@/src/api/client";
import { SuperAdminHeader, StatusBadge } from "@/src/components/SuperAdminShell";
import { colors, fonts, radius, spacing } from "@/src/theme";

export default function Activity() {
  const [rows, setRows] = useState<any[]>([]);
  const load = useCallback(async () => setRows(await api.get("/superadmin/activity")), []);
  useFocusEffect(useCallback(() => { load().catch(() => setRows([])); }, [load]));
  return <ScrollView testID="superadmin-activity" contentContainerStyle={styles.page}><SuperAdminHeader title="Activity Logs" subtitle="Recent platform activity" />{rows.length === 0 ? <Text style={styles.empty}>No activity recorded yet.</Text> : <View style={styles.list}>{rows.map((row, index) => <View key={`${row.date}-${index}`} style={styles.row}><View style={styles.dot} /><View style={{ flex: 1 }}><Text style={styles.name}>{row.photographer}</Text><Text style={styles.action}>{row.action}</Text><Text style={styles.description}>{row.description}</Text></View><View style={styles.right}><StatusBadge status={row.status || "Success"} /><Text style={styles.date}>{row.date ? new Date(row.date).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—"}</Text></View></View>)}</View>}</ScrollView>;
}
const styles = StyleSheet.create({ page: { paddingBottom: spacing["3xl"] }, list: { marginHorizontal: spacing["2xl"], backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.lg, paddingHorizontal: spacing.lg }, row: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.lg, borderBottomWidth: 1, borderBottomColor: "#F2F4F7" }, dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.brand }, name: { color: "#101828", fontFamily: fonts.text, fontSize: 14, fontWeight: "700" }, action: { color: "#344054", fontFamily: fonts.text, fontSize: 13, marginTop: 3 }, description: { color: "#667085", fontFamily: fonts.text, fontSize: 12, marginTop: 3 }, right: { alignItems: "flex-end", gap: 4 }, date: { color: "#98A2B3", fontFamily: fonts.text, fontSize: 11 }, empty: { color: "#667085", fontFamily: fonts.text, paddingHorizontal: spacing["2xl"] } });
