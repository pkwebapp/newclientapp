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
import { useAuth } from "@/src/context/AuthContext";
import { EmptyState, Pill, GlassHeader, useToast } from "@/src/components/ui";
import { useResponsive } from "@/src/hooks/use-responsive";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

export default function AdminDashboard() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, signOut } = useAuth();
  const toast = useToast();
  const { isDesktop } = useResponsive();
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setEvents(await api.get("/events"));
    } catch {
      toast.show("Could not load events", "error");
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

  const statusTone = (s: string) => (s === "ready" ? "success" : s === "empty" ? "neutral" : "warning");

  return (
    <View style={styles.container} testID="admin-dashboard-screen">
      <GlassHeader
        title="Studio Console"
        subtitle={user?.email}
        topInset={insets.top}
        left={
          <Pressable testID="admin-home-btn" onPress={() => router.push("/login")} hitSlop={10} style={{ padding: 6 }}>
            <Ionicons name="home-outline" size={22} color={colors.onSurfaceTertiary} />
          </Pressable>
        }
        right={
          <Pressable testID="admin-signout-btn" onPress={signOut} hitSlop={10} style={{ padding: 6 }}>
            <Ionicons name="log-out-outline" size={22} color={colors.onSurfaceTertiary} />
          </Pressable>
        }
      />
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
          <View style={styles.statsRow}>
            <Stat label="Events" value={events.length} icon="albums-outline" />
            <Stat label="Photos" value={events.reduce((a, e) => a + (e.photo_count || 0), 0)} icon="image-outline" />
          </View>

          <Pressable
            testID="admin-clients-card"
            onPress={() => router.push("/admin/clients")}
            style={styles.albumsCard}
          >
            <View style={styles.rowIcon}>
              <Ionicons name="people-outline" size={20} color={colors.brand} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>Clients</Text>
              <Text style={styles.rowSub}>Families, contacts, important dates & lifetime relationships</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </Pressable>

          <Pressable
            testID="admin-albums-card"
            onPress={() => router.push("/admin/albums")}
            style={styles.albumsCard}
          >
            <View style={styles.rowIcon}>
              <Ionicons name="book-outline" size={20} color={colors.brand} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>Album Flipbooks</Text>
              <Text style={styles.rowSub}>Upload a designed PDF album and share a premium 3D viewer</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </Pressable>

          <Pressable
            testID="admin-settings-card"
            onPress={() => router.push("/admin/settings")}
            style={styles.albumsCard}
          >
            <View style={styles.rowIcon}>
              <Ionicons name="settings-outline" size={20} color={colors.brand} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>Studio Settings</Text>
              <Text style={styles.rowSub}>WhatsApp, call number & review link for client Quick Actions</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </Pressable>

          {events.length === 0 ? (
            <EmptyState icon="add-circle-outline" title="Create your first event" subtitle="Set up a gallery, upload photos, and invite your clients." />
          ) : (
            <View style={isDesktop ? styles.gridWrap : undefined}>
              {events.map((e) => (
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

      <Pressable testID="new-event-fab" onPress={() => router.push("/admin/new-event")} style={[styles.fab, { bottom: insets.bottom + spacing.lg }]}>
        <Ionicons name="add" size={26} color={colors.onBrand} />
        <Text style={styles.fabText}>New Event</Text>
      </Pressable>
    </View>
  );
}

function Stat({ label, value, icon }: { label: string; value: number; icon: any }) {
  return (
    <View style={styles.stat}>
      <Ionicons name={icon} size={20} color={colors.brand} />
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  statsRow: { flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg },
  albumsCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.brandTertiary,
  },
  gridWrap: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between" },
  rowDesktop: { width: "48.5%" },
  stat: { flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, alignItems: "flex-start" },
  statValue: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], marginTop: spacing.sm },
  statLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
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
