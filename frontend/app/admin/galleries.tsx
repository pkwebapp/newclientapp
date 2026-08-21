import { useCallback, useMemo, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api } from "@/src/api/client";
import { EmptyState, Pill, GlassHeader, useToast } from "@/src/components/ui";
import { HeaderMenuButton } from "@/src/components/MobileShell";
import { useResponsive } from "@/src/hooks/use-responsive";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

const FILTERS = [
  { key: "", label: "All" },
  { key: "ready", label: "Ready" },
  { key: "processing", label: "Processing" },
  { key: "archived", label: "Archived" },
];

const statusTone = (s: string) => (s === "ready" ? "success" : s === "empty" ? "neutral" : "warning");

export default function GalleriesScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { isDesktop } = useResponsive();

  const [events, setEvents] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setEvents(await api.get("/events"));
    } catch {
      toast.show("Could not load galleries", "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [toast]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return events.filter((e) => {
      if (needle && !(e.name || "").toLowerCase().includes(needle)) return false;
      if (filter === "archived") return e.status === "archived";
      if (e.status === "archived") return filter === "";
      if (filter === "ready") return e.indexing_status === "ready";
      if (filter === "processing") return e.indexing_status !== "ready" && e.indexing_status !== "empty";
      return true;
    });
  }, [events, q, filter]);

  return (
    <View style={styles.container} testID="admin-galleries-screen">
      <GlassHeader
        title="Client Galleries"
        subtitle={`${events.length} ${events.length === 1 ? "event" : "events"}`}
        topInset={insets.top}
        left={<HeaderMenuButton />}
      />

      <View style={styles.controls}>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput
            testID="gallery-search-input"
            value={q}
            onChangeText={setQ}
            placeholder="Search galleries by name…"
            placeholderTextColor={colors.muted}
            style={styles.searchInput}
            autoCapitalize="none"
          />
          {q ? (
            <Pressable onPress={() => setQ("")} hitSlop={8}>
              <Ionicons name="close-circle" size={18} color={colors.muted} />
            </Pressable>
          ) : null}
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
          {FILTERS.map((f) => (
            <Pressable
              key={f.key || "all"}
              testID={`gallery-filter-${f.label}`}
              onPress={() => setFilter(f.key)}
              style={[styles.filterChip, filter === f.key && styles.filterChipActive]}
            >
              <Text style={[styles.filterText, filter === f.key && styles.filterTextActive]}>{f.label}</Text>
            </Pressable>
          ))}
        </ScrollView>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing["3xl"] + 72 }}
          refreshControl={
            <RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />
          }
        >
          {filtered.length === 0 ? (
            <EmptyState
              icon={q || filter ? "search-outline" : "add-circle-outline"}
              title={q || filter ? "No matching galleries" : "Create your first gallery"}
              subtitle={q || filter ? "Try a different search or filter." : "Set up an event gallery, upload photos, and invite your clients."}
            />
          ) : (
            <View style={isDesktop ? styles.gridWrap : undefined}>
              {filtered.map((e) => (
                <Pressable
                  key={e.event_id}
                  testID={`admin-event-${e.event_id}`}
                  onPress={() => router.push(`/admin/event/${e.event_id}`)}
                  style={[styles.row, isDesktop && styles.rowDesktop]}
                >
                  <View style={styles.rowIcon}>
                    <Ionicons name={(categoryMeta[e.category]?.icon as any) || "star"} size={20} color={colors.brand} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.rowTitle} numberOfLines={1}>{e.name}</Text>
                    <Text style={styles.rowSub}>
                      {categoryMeta[e.category]?.label} · {e.photo_count} photos · {e.similarity_threshold}% threshold
                    </Text>
                  </View>
                  <View style={{ alignItems: "flex-end", gap: 6 }}>
                    {e.source === "gdrive" && <Pill label="Drive" tone="neutral" icon="logo-google" />}
                    {e.status === "archived" ? (
                      <Pill label="Archived" tone="warning" />
                    ) : (
                      <Pill label={e.indexing_status} tone={statusTone(e.indexing_status) as any} />
                    )}
                    <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                  </View>
                </Pressable>
              ))}
            </View>
          )}
        </ScrollView>
      )}

      <Pressable testID="new-event-fab" onPress={() => router.push("/admin/new-event")} style={[styles.fab, { bottom: spacing.lg }]}>
        <Ionicons name="add" size={26} color={colors.onBrand} />
        <Text style={styles.fabText}>New Event</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  controls: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, gap: spacing.md },
  searchBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    height: 46,
  },
  searchInput: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  filterRow: { gap: spacing.sm, paddingRight: spacing.lg },
  filterChip: {
    paddingHorizontal: spacing.lg,
    height: 36,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  filterChipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  filterText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  filterTextActive: { color: colors.onBrand, fontWeight: "600" },
  gridWrap: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between" },
  rowDesktop: { width: "48.5%" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  rowIcon: { width: 42, height: 42, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  rowTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  rowSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  fab: {
    position: "absolute",
    right: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.brand,
    paddingHorizontal: spacing.xl,
    height: 52,
    borderRadius: radius.pill,
    elevation: 6,
    shadowColor: "#000",
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  fabText: { color: colors.onBrand, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "600" },
});
