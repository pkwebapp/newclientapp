import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, imgUrl } from "@/src/api/client";
import { useAuth } from "@/src/context/AuthContext";
import { EmptyState, Pill, GlassHeader, useToast } from "@/src/components/ui";
import { NotificationBell } from "@/src/components/NotificationBell";
import { HeaderMenuButton } from "@/src/components/MobileShell";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

const dialDigits = (num?: string) => {
  const digits = (num || "").replace(/\D/g, "");
  return digits.length === 10 ? `91${digits}` : digits;
};

function groupByYear(memories: any[]) {
  const map: Record<string, any[]> = {};
  for (const m of memories) {
    const y = m.year || "Earlier";
    (map[y] = map[y] || []).push(m);
  }
  return Object.entries(map).sort((a, b) => (a[0] < b[0] ? 1 : -1));
}

export default function ClientDashboard() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, signOut } = useAuth();
  const toast = useToast();
  const [dash, setDash] = useState<any>(null);
  const [albums, setAlbums] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [d, al] = await Promise.all([
        api.get("/me/dashboard"),
        api.get("/albums/client/mine").catch(() => []),
      ]);
      setDash(d);
      setAlbums(al);
    } catch {
      toast.show("Could not load your memories", "error");
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

  const studio = dash?.studio || {};
  const memories = dash?.memories || [];
  const upcoming = dash?.upcoming || [];
  const upcomingShoots = dash?.upcoming_shoots || [];
  const firstName = dash?.profile?.first_name || user?.name || "there";

  const openWhatsApp = () => {
    Linking.openURL(`https://wa.me/${dialDigits(studio.whatsapp)}`).catch(() =>
      toast.show("Could not open WhatsApp", "error")
    );
  };
  const call = () => {
    const digits = (studio.phone || "").replace(/\D/g, "");
    Linking.openURL(`tel:${digits}`).catch(() => toast.show("Could not start call", "error"));
  };

  const ACTIONS = [
    { key: "book", label: "Book", icon: "calendar", onPress: () => router.push("/client/book") },
    { key: "message", label: "Message", icon: "logo-whatsapp", onPress: openWhatsApp },
    { key: "call", label: "Call", icon: "call", onPress: call },
    { key: "review", label: "Review", icon: "star", onPress: () => router.push("/client/review") },
  ];

  const openClientNotification = (notification: any) => {
    if (notification.event_id) {
      router.push(`/client/event/${notification.event_id}`);
    } else if (notification.type === "payment_reminder") {
      router.push("/client/services");
    } else {
      router.push("/client");
    }
  };

  return (
    <View style={styles.container} testID="client-dashboard-screen">
      <GlassHeader
        title="Your Memories"
        subtitle={`Welcome, ${firstName}`}
        topInset={insets.top}
        left={<HeaderMenuButton />}
        right={
          <View style={styles.headerActions}>
            <NotificationBell audience="client" testID="client-notification-bell" onNotificationPress={openClientNotification} />
            <Pressable testID="signout-btn" onPress={signOut} hitSlop={10} style={{ padding: 6 }}>
              <Ionicons name="log-out-outline" size={22} color={colors.onSurfaceTertiary} />
            </Pressable>
          </View>
        }
      />
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing["3xl"] }}
          refreshControl={
            <RefreshControl
              tintColor={colors.brand}
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                load();
              }}
            />
          }
        >
          {/* Quick actions */}
          <View style={styles.actionsRow}>
            {ACTIONS.map((a) => (
              <Pressable key={a.key} testID={`qa-${a.key}`} onPress={a.onPress} style={styles.action}>
                <View style={styles.actionIcon}>
                  <Ionicons name={a.icon as any} size={20} color={colors.brand} />
                </View>
                <Text style={styles.actionLabel}>{a.label}</Text>
              </Pressable>
            ))}
          </View>

          {upcomingShoots.length > 0 && (
            <>
              <View style={styles.sectionHead}><Text style={styles.sectionTitle}>Upcoming shoots</Text><Pressable testID="view-client-bookings" onPress={() => router.push("/client/bookings")}><Text style={styles.viewAll}>View all</Text></Pressable></View>
              <View style={styles.upcomingBox}>
                {upcomingShoots.map((shoot: any) => (
                  <Pressable key={shoot.request_id} testID={`upcoming-shoot-${shoot.request_id}`} onPress={() => router.push(`/client/booking/${shoot.request_id}`)} style={styles.upcomingRow}>
                    <View style={styles.upcomingIcon}><Ionicons name="calendar" size={16} color={colors.brand} /></View>
                    <View style={{ flex: 1 }}><Text style={styles.upcomingTitle}>{shoot.event_name || shoot.service_type}</Text><Text style={styles.upcomingSub}>{shoot.preferred_date} · {shoot.start_time || "Time pending"} · {shoot.location || "Venue pending"}</Text></View>
                    <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                  </Pressable>
                ))}
              </View>
            </>
          )}

          {/* Upcoming */}
          {upcoming.length > 0 && (
            <>
              <Text style={styles.sectionTitle}>Upcoming</Text>
              <View style={styles.upcomingBox}>
                {upcoming.map((u: any) => (
                  <View key={u.date_id} style={styles.upcomingRow}>
                    <View style={styles.upcomingIcon}>
                      <Ionicons name={/anniv/i.test(u.occasion) ? "heart" : "gift"} size={16} color={colors.brand} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.upcomingTitle}>{u.person_label} · {u.occasion}</Text>
                      <Text style={styles.upcomingSub}>{u.next_date}</Text>
                    </View>
                    <Text style={styles.upcomingDays}>
                      {u.days_until === 0 ? "Today" : u.days_until === 1 ? "Tomorrow" : `in ${u.days_until}d`}
                    </Text>
                  </View>
                ))}
              </View>
            </>
          )}

          {/* Albums */}
          {albums.length > 0 && (
            <>
              <Text style={styles.sectionTitle}>Your Albums</Text>
              {albums.map((a) => (
                <Pressable
                  key={a.album_id}
                  testID={`client-album-${a.album_id}`}
                  onPress={() => router.push(`/a/${a.share_token}` as any)}
                  style={styles.albumCard}
                >
                  <View style={styles.albumThumb}>
                    {a.cover_url ? (
                      <Image source={{ uri: a.cover_url }} style={StyleSheet.absoluteFill} contentFit="cover" transition={200} />
                    ) : (
                      <Ionicons name="book" size={22} color={colors.brand} />
                    )}
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.albumTitle} numberOfLines={1}>{a.title}</Text>
                    <Text style={styles.albumMeta} numberOfLines={1}>
                      {[a.event_name, `${a.total_spreads} spreads`].filter(Boolean).join(" · ")}
                    </Text>
                  </View>
                  {a.has_music && <Ionicons name="musical-notes" size={16} color={colors.brand} />}
                  <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} />
                </Pressable>
              ))}
            </>
          )}

          {/* Memories grouped by year */}
          {memories.length === 0 && albums.length === 0 ? (
            <EmptyState
              icon="mail-open-outline"
              title="No memories yet"
              subtitle="When your studio shares an event or album, it will appear here. Pull down to refresh."
            />
          ) : (
            groupByYear(memories).map(([year, list]) => (
              <View key={year}>
                <Text style={styles.yearHead}>{year}</Text>
                {(list as any[]).map((e) => (
                  <Pressable
                    key={e.event_id}
                    testID={`memory-card-${e.event_id}`}
                    onPress={() => router.push(`/client/event/${e.event_id}`)}
                    style={styles.card}
                  >
                    <Image
                      source={(e.cover_url || imgUrl(null, e.cover_path)) ? { uri: e.cover_url || imgUrl(null, e.cover_path) } : undefined}
                      style={StyleSheet.absoluteFill}
                      contentFit="cover"
                      transition={250}
                    />
                    <LinearGradient
                      colors={["transparent", "rgba(13,13,13,0.35)", "rgba(13,13,13,0.92)"]}
                      locations={[0, 0.45, 1]}
                      style={StyleSheet.absoluteFill}
                    />
                    <View style={styles.cardTop}>
                      <Pill label={categoryMeta[e.category]?.label || e.category} tone="gold" />
                      {e.my_photos_count > 0 && (
                        <Pill label={`${e.my_photos_count} of you`} tone="success" icon="sparkles" />
                      )}
                    </View>
                    <View style={styles.cardBottom}>
                      <Text style={styles.cardTitle} numberOfLines={1}>{e.name}</Text>
                      <View style={styles.metaRow}>
                        <Text style={styles.meta}>
                          <Ionicons name="image-outline" size={12} /> {e.photo_count} photos
                        </Text>
                        {e.date ? <Text style={styles.meta}>  •  {e.date}</Text> : null}
                      </View>
                    </View>
                  </Pressable>
                ))}
              </View>
            ))
          )}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  headerActions: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: {
    width: "100%",
    height: 220,
    borderRadius: radius.lg,
    overflow: "hidden",
    marginBottom: spacing.lg,
    backgroundColor: colors.surfaceSecondary,
  },
  cardTop: {
    position: "absolute",
    top: spacing.md,
    left: spacing.md,
    right: spacing.md,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  cardBottom: { position: "absolute", left: spacing.lg, right: spacing.lg, bottom: spacing.lg },
  cardTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  sectionTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginBottom: spacing.md, marginTop: spacing.lg },
  sectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  viewAll: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600", marginTop: spacing.lg, marginBottom: spacing.md },
  yearHead: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize.lg, marginBottom: spacing.md, marginTop: spacing.lg, letterSpacing: 1 },
  actionsRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.sm },
  action: { flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, paddingVertical: spacing.lg, alignItems: "center", gap: spacing.sm, borderWidth: 1, borderColor: colors.border },
  actionIcon: { width: 40, height: 40, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  actionLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm },
  upcomingBox: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.sm, borderWidth: 1, borderColor: colors.border },
  upcomingRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md },
  upcomingIcon: { width: 34, height: 34, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  upcomingTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  upcomingSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  upcomingDays: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
  albumCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  albumThumb: { width: 44, height: 58, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center", overflow: "hidden" },
  albumTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.lg },
  albumMeta: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  metaRow: { flexDirection: "row", alignItems: "center", marginTop: spacing.xs },
  meta: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm },
});
