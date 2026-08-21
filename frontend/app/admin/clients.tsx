import { useCallback, useEffect, useRef, useState } from "react";
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
import { useResponsive } from "@/src/hooks/use-responsive";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const STATUS_FILTERS = [
  { key: "", label: "All" },
  { key: "active", label: "Active" },
  { key: "lead", label: "Leads" },
  { key: "past", label: "Past" },
];

const TYPE_ICON: Record<string, any> = {
  family: "people",
  individual: "person",
  corporate: "business",
};

const statusTone = (s: string) =>
  s === "active" ? "success" : s === "lead" ? "gold" : "neutral";

export default function ClientsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { isDesktop } = useResponsive();

  const [clients, setClients] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const debounce = useRef<any>(null);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.append("q", q.trim());
      if (status) params.append("status", status);
      const qs = params.toString();
      setClients(await api.get(`/clients${qs ? `?${qs}` : ""}`));
    } catch {
      toast.show("Could not load clients", "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [q, status, toast]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  // Debounced reload on search text change.
  useEffect(() => {
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => load(), 300);
    return () => clearTimeout(debounce.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, status]);

  return (
    <View style={styles.container} testID="admin-clients-screen">
      <GlassHeader
        title="Clients"
        subtitle="Your client & family relationships"
        onBack={() => router.push("/admin")}
        topInset={insets.top}
      />

      <View style={styles.controls}>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput
            testID="client-search-input"
            value={q}
            onChangeText={setQ}
            placeholder="Search name, phone, email…"
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
          {STATUS_FILTERS.map((f) => (
            <Pressable
              key={f.key || "all"}
              testID={`client-filter-${f.label}`}
              onPress={() => setStatus(f.key)}
              style={[styles.filterChip, status === f.key && styles.filterChipActive]}
            >
              <Text style={[styles.filterText, status === f.key && styles.filterTextActive]}>{f.label}</Text>
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
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 96 }}
          refreshControl={
            <RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />
          }
        >
          {clients.length === 0 ? (
            <EmptyState
              icon="people-outline"
              title={q || status ? "No matching clients" : "No clients yet"}
              subtitle={q || status ? "Try a different search or filter." : "Add a client/family to start building lasting relationships."}
            />
          ) : (
            <View style={isDesktop ? styles.gridWrap : undefined}>
              {clients.map((c) => {
                const primary = c.contacts && c.contacts[0];
                return (
                  <Pressable
                    key={c.client_id}
                    testID={`client-card-${c.client_id}`}
                    onPress={() => router.push(`/admin/client/${c.client_id}`)}
                    style={[styles.row, isDesktop && styles.rowDesktop]}
                  >
                    <View style={styles.rowIcon}>
                      <Ionicons name={TYPE_ICON[c.type] || "people"} size={20} color={colors.brand} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.rowTitle} numberOfLines={1}>{c.name}</Text>
                      <Text style={styles.rowSub} numberOfLines={1}>
                        {primary ? `${primary.name}${primary.phone ? ` · ${primary.phone}` : ""}` : "No contacts yet"}
                      </Text>
                      <View style={styles.metaRow}>
                        <Text style={styles.meta}>{c.stats?.event_count || 0} events</Text>
                        <Text style={styles.metaDot}>•</Text>
                        <Text style={styles.meta}>{c.stats?.contact_count || 0} contacts</Text>
                      </View>
                    </View>
                    <View style={{ alignItems: "flex-end", gap: 6 }}>
                      <Pill label={c.status} tone={statusTone(c.status) as any} />
                      <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                    </View>
                  </Pressable>
                );
              })}
            </View>
          )}
        </ScrollView>
      )}

      <Pressable
        testID="new-client-fab"
        onPress={() => router.push("/admin/new-client")}
        style={[styles.fab, { bottom: insets.bottom + spacing.lg }]}
      >
        <Ionicons name="person-add" size={22} color={colors.onBrand} />
        <Text style={styles.fabText}>New Client</Text>
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
  rowSub: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 4 },
  meta: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  metaDot: { color: colors.muted, fontSize: fontSize.sm },
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
