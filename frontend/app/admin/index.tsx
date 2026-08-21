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
import { EmptyState, Button, GlassHeader, useToast } from "@/src/components/ui";
import { HeaderMenuButton } from "@/src/components/MobileShell";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

export default function AdminDashboard() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const toast = useToast();
  const [events, setEvents] = useState<any[]>([]);
  const [clientCount, setClientCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [ev, cl] = await Promise.all([
        api.get("/events"),
        api.get("/clients").catch(() => []),
      ]);
      setEvents(ev);
      setClientCount(Array.isArray(cl) ? cl.length : 0);
    } catch {
      toast.show("Could not load your studio", "error");
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

  const totalPhotos = events.reduce((a, e) => a + (e.photo_count || 0), 0);
  const recent = events.slice(0, 5);

  const QUICK: { key: string; label: string; icon: any; onPress: () => void }[] = [
    { key: "gallery", label: "New Gallery", icon: "add-circle", onPress: () => router.push("/admin/new-event") },
    { key: "client", label: "Add Client", icon: "person-add", onPress: () => router.push("/admin/new-client") },
    { key: "album", label: "New Album", icon: "book", onPress: () => router.push("/admin/albums") },
    { key: "settings", label: "Settings", icon: "settings", onPress: () => router.push("/admin/settings") },
  ];

  return (
    <View style={styles.container} testID="admin-dashboard-screen">
      <GlassHeader
        title="Studio Console"
        subtitle={user?.email}
        topInset={insets.top}
        left={<HeaderMenuButton />}
      />
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing["3xl"] }}
          refreshControl={
            <RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />
          }
        >
          <View style={styles.statsRow}>
            <Stat label="Galleries" value={events.length} icon="images-outline" />
            <Stat label="Photos" value={totalPhotos} icon="image-outline" />
            <Stat label="Clients" value={clientCount} icon="people-outline" />
          </View>

          <Text style={styles.sectionTitle}>Quick actions</Text>
          <View style={styles.quickGrid}>
            {QUICK.map((a) => (
              <Pressable key={a.key} testID={`quick-${a.key}`} onPress={a.onPress} style={styles.quickCard}>
                <View style={styles.quickIcon}>
                  <Ionicons name={a.icon} size={22} color={colors.brand} />
                </View>
                <Text style={styles.quickLabel}>{a.label}</Text>
              </Pressable>
            ))}
          </View>

          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitle}>Recent galleries</Text>
            {events.length > 0 ? (
              <Pressable testID="view-all-galleries" onPress={() => router.push("/admin/galleries")} hitSlop={8} style={styles.viewAll}>
                <Text style={styles.viewAllText}>View all</Text>
                <Ionicons name="chevron-forward" size={14} color={colors.brand} />
              </Pressable>
            ) : null}
          </View>

          {recent.length === 0 ? (
            <EmptyState
              icon="add-circle-outline"
              title="Create your first gallery"
              subtitle="Set up an event gallery, upload photos, and invite your clients."
              action={<Button testID="empty-new-gallery" title="New gallery" icon="add" onPress={() => router.push("/admin/new-event")} />}
            />
          ) : (
            recent.map((e) => (
              <Pressable
                key={e.event_id}
                testID={`admin-event-${e.event_id}`}
                onPress={() => router.push(`/admin/event/${e.event_id}`)}
                style={styles.row}
              >
                <View style={styles.rowIcon}>
                  <Ionicons name={(categoryMeta[e.category]?.icon as any) || "star"} size={20} color={colors.brand} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.rowTitle} numberOfLines={1}>{e.name}</Text>
                  <Text style={styles.rowSub} numberOfLines={1}>
                    {categoryMeta[e.category]?.label} · {e.photo_count} photos
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.muted} />
              </Pressable>
            ))
          )}
        </ScrollView>
      )}
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
  statsRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.xl },
  stat: { flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, alignItems: "flex-start", borderWidth: 1, borderColor: colors.border },
  statValue: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], marginTop: spacing.sm },
  statLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  sectionTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginBottom: spacing.md },
  sectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.xl },
  viewAll: { flexDirection: "row", alignItems: "center", gap: 2, marginBottom: spacing.md },
  viewAllText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  quickGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  quickCard: {
    width: "48.5%",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.brandTertiary,
  },
  quickIcon: { width: 40, height: 40, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  quickLabel: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600", flexShrink: 1 },
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
});
