import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { api } from "@/src/api/client";
import { SuperAdminHeader, StatusBadge } from "@/src/components/SuperAdminShell";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

export default function SuperadminAlbums() {
  const [rows, setRows] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await api.get(`/superadmin/albums${query.trim() ? `?q=${encodeURIComponent(query.trim())}` : ""}`));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [query]);

  useFocusEffect(useCallback(() => { load().catch(() => setRows([])); }, [load]));

  return (
    <ScrollView
      testID="superadmin-albums"
      contentContainerStyle={styles.page}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load().catch(() => setRefreshing(false)); }} />}
    >
      <SuperAdminHeader title="Albums" subtitle="Every flipbook album across the platform" />
      <TextInput
        testID="superadmin-album-search"
        value={query}
        onChangeText={setQuery}
        onSubmitEditing={() => load()}
        placeholder="Search album, client or photographer"
        placeholderTextColor="#98A2B3"
        style={styles.search}
      />
      {loading ? (
        <View style={styles.loading}><ActivityIndicator color={colors.brand} /></View>
      ) : rows.length === 0 ? (
        <View style={styles.emptyCard}><Text style={styles.emptyTitle}>No albums found</Text><Text style={styles.emptyText}>Albums created by photographers will appear here.</Text></View>
      ) : (
        <View style={styles.list}>
          {rows.map((row) => (
            <View key={row.album_id} style={styles.row}>
              <View style={styles.albumIcon}><Text style={styles.albumIconText}>A</Text></View>
              <View style={{ flex: 1 }}>
                <Text style={styles.name} numberOfLines={1}>{row.title}</Text>
                <Text style={styles.sub} numberOfLines={1}>{row.photographer}</Text>
                <Text style={styles.meta} numberOfLines={1}>{[row.client_name, row.event_name].filter(Boolean).join(" · ") || "No client or event linked"}</Text>
              </View>
              <View style={styles.stats}>
                <StatusBadge status={row.archived ? "Archived" : row.status} />
                <Text style={styles.stat}>{row.pages} pages · {row.spreads} spreads</Text>
              </View>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { paddingBottom: spacing["3xl"] },
  search: { height: 48, marginHorizontal: spacing["2xl"], paddingHorizontal: spacing.md, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#D0D5DD", borderRadius: radius.md, color: "#344054", fontFamily: fonts.text },
  list: { margin: spacing["2xl"], backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.lg, overflow: "hidden" },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, borderBottomWidth: 1, borderBottomColor: "#F2F4F7" },
  albumIcon: { width: 42, height: 42, borderRadius: radius.md, backgroundColor: "#FFF1EC", alignItems: "center", justifyContent: "center" },
  albumIconText: { color: colors.brand, fontFamily: fonts.display, fontSize: 20, fontWeight: "800" },
  name: { color: "#101828", fontFamily: fonts.text, fontSize: 14, fontWeight: "700" },
  sub: { color: "#475467", fontFamily: fonts.text, fontSize: 12, marginTop: 4 },
  meta: { color: "#98A2B3", fontFamily: fonts.text, fontSize: 11, marginTop: 3 },
  stats: { alignItems: "flex-end", gap: spacing.sm },
  stat: { color: "#667085", fontFamily: fonts.text, fontSize: 12 },
  loading: { padding: spacing["3xl"], alignItems: "center" },
  emptyCard: { margin: spacing["2xl"], padding: spacing["2xl"], backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.lg, alignItems: "center" },
  emptyTitle: { color: "#101828", fontFamily: fonts.display, fontSize: fontSize.xl, fontWeight: "700" },
  emptyText: { color: "#667085", fontFamily: fonts.text, fontSize: 14, marginTop: spacing.sm },
});
