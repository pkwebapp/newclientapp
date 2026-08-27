import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Modal,
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
import { NotificationBell } from "@/src/components/NotificationBell";
import { HeaderMenuButton } from "@/src/components/MobileShell";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

export default function AdminDashboard() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const toast = useToast();
  const [events, setEvents] = useState<any[]>([]);
  const [clientCount, setClientCount] = useState<number>(0);
  const [plan, setPlan] = useState<any>(null);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [selectedBooking, setSelectedBooking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [ev, cl, pl, notificationData] = await Promise.all([
        api.get("/events"),
        api.get("/clients").catch(() => []),
        api.get("/billing/status").catch(() => null),
        api.get("/notifications").catch(() => ({ items: [], unread_count: 0 })),
      ]);
      setEvents(ev);
      setClientCount(Array.isArray(cl) ? cl.length : 0);
      setPlan(pl);
      setNotifications(notificationData.items || []);
      setUnreadNotifications(notificationData.unread_count || 0);
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

  const openNotification = async (notification: any) => {
    if (!notification.read) {
      try {
        await api.patch(`/notifications/${notification.notification_id}/read`, {});
        setNotifications((prev) => prev.map((item) => item.notification_id === notification.notification_id ? { ...item, read: true } : item));
        setUnreadNotifications((count) => Math.max(0, count - 1));
      } catch {}
    }
    setSelectedBooking(notification);
  };

  return (
    <View style={styles.container} testID="admin-dashboard-screen">
      <GlassHeader
        title="Studio Console"
        subtitle={user?.email}
        topInset={insets.top}
        left={<HeaderMenuButton />}
        right={<NotificationBell audience="admin" testID="admin-notification-bell" onNotificationPress={openNotification} />}
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
            <Stat label="Galleries" value={events.length} icon="images-outline" />
            <Stat label="Photos" value={totalPhotos} icon="image-outline" />
            <Stat label="Clients" value={clientCount} icon="people-outline" />
          </View>

          {plan && (plan.plan === "trial" || plan.locked) && (
            <Pressable
              testID="plan-banner"
              onPress={() => router.push("/admin/billing")}
              style={[styles.planBanner, plan.locked && styles.planBannerLocked]}
            >
              <Ionicons name={plan.locked ? "lock-closed" : "sparkles"} size={18} color={plan.locked ? colors.onError : colors.brand} />
              <View style={{ flex: 1 }}>
                <Text style={[styles.planBannerTitle, plan.locked && { color: colors.onError }]}>
                  {plan.locked
                    ? "Your trial has ended"
                    : `You're on the Trial plan${plan.days_left != null ? ` · ${plan.days_left} day${plan.days_left === 1 ? "" : "s"} left` : ""}`}
                </Text>
                <Text style={[styles.planBannerSub, plan.locked && { color: colors.onError }]}>
                  {plan.locked ? "Subscribe to restore your galleries" : "Upgrade to Standard or Pro for more galleries & storage"}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={plan.locked ? colors.onError : colors.brand} />
            </Pressable>
          )}

          {user?.uploads_disabled && (
            <View style={styles.uploadDisabledBanner} testID="upload-disabled-banner">
              <Ionicons name="cloud-offline-outline" size={20} color={colors.onError} />
              <View style={{ flex: 1 }}>
                <Text style={styles.uploadDisabledTitle}>Your upload feature is disabled</Text>
                <Text style={styles.uploadDisabledSub}>Upgrade to continue or contact admin.</Text>
              </View>
            </View>
          )}

          {notifications.length > 0 && (
            <View style={styles.notificationsSection} testID="admin-notifications">
              <View style={styles.notificationHeader}>
                <Text style={styles.sectionTitle}>Notifications</Text>
                {unreadNotifications > 0 && <View style={styles.unreadBadge}><Text style={styles.unreadBadgeText}>{unreadNotifications} new</Text></View>}
              </View>
              {notifications.slice(0, 3).map((notification) => (
                <Pressable
                  key={notification.notification_id}
                  testID={`notification-${notification.notification_id}`}
                  onPress={() => openNotification(notification)}
                  style={[styles.notificationRow, !notification.read && styles.notificationUnread]}
                >
                  <View style={styles.notificationIcon}><Ionicons name="calendar-outline" size={18} color={colors.brand} /></View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.notificationTitle}>{notification.title}</Text>
                    <Text style={styles.notificationBody}>{notification.body}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                </Pressable>
              ))}
            </View>
          )}

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
              style={{ marginTop: spacing.md }}
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
      <Modal visible={!!selectedBooking} transparent animationType="fade" onRequestClose={() => setSelectedBooking(null)}>
        <Pressable style={styles.bookingModalBackdrop} onPress={() => setSelectedBooking(null)}>
          <Pressable style={styles.bookingModalCard} testID="booking-details-modal" onPress={() => {}}>
            <View style={styles.bookingModalHeader}>
              <View style={styles.notificationIcon}><Ionicons name="calendar-outline" size={20} color={colors.brand} /></View>
              <View style={{ flex: 1 }}>
                <Text style={styles.bookingModalTitle}>Booking request</Text>
                <Text style={styles.bookingModalSub}>{selectedBooking?.service_type || "Session inquiry"}</Text>
              </View>
              <Pressable testID="close-booking-details" onPress={() => setSelectedBooking(null)} hitSlop={8}><Ionicons name="close" size={22} color={colors.muted} /></Pressable>
            </View>
            <View style={styles.bookingDetails}>
              <Text style={styles.bookingPerson}>{selectedBooking?.contact_name || "Unknown client"}</Text>
              {selectedBooking?.contact_phone ? <Text style={styles.bookingDetailText}>Phone: {selectedBooking.contact_phone}</Text> : null}
              {selectedBooking?.contact_email ? <Text style={styles.bookingDetailText}>Email: {selectedBooking.contact_email}</Text> : null}
              {selectedBooking?.preferred_date ? <Text style={styles.bookingDetailText}>Preferred date: {selectedBooking.preferred_date}</Text> : null}
              {selectedBooking?.location ? <Text style={styles.bookingDetailText}>Location: {selectedBooking.location}</Text> : null}
              {selectedBooking?.message ? <Text style={styles.bookingMessage}>“{selectedBooking.message}”</Text> : null}
            </View>
            <Button testID="booking-details-clients-btn" title="Open client CRM" variant="secondary" onPress={() => { setSelectedBooking(null); router.push("/admin/clients"); }} />
          </Pressable>
        </Pressable>
      </Modal>
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
  planBanner: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.brandTertiary, borderWidth: 1, borderColor: colors.brand, borderRadius: radius.lg, padding: spacing.lg, marginBottom: spacing.xl },
  planBannerLocked: { backgroundColor: colors.error, borderColor: colors.error },
  uploadDisabledBanner: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.error, borderWidth: 1, borderColor: colors.error, borderRadius: radius.lg, padding: spacing.lg, marginBottom: spacing.xl },
  uploadDisabledTitle: { color: colors.onError, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  uploadDisabledSub: { color: colors.onError, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  notificationsSection: { marginBottom: spacing.xl },
  notificationHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  unreadBadge: { backgroundColor: colors.brandTertiary, borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: 4 },
  unreadBadgeText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  notificationRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border },
  notificationUnread: { borderColor: colors.brand, backgroundColor: colors.brandTertiary },
  notificationIcon: { width: 38, height: 38, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
  notificationTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  notificationBody: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 3 },
  bookingModalBackdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.72)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  bookingModalCard: { width: "100%", maxWidth: 520, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, padding: spacing.xl, borderWidth: 1, borderColor: colors.borderStrong },
  bookingModalHeader: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginBottom: spacing.xl },
  bookingModalTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  bookingModalSub: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 3 },
  bookingDetails: { backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.xl, gap: spacing.sm },
  bookingPerson: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "700" },
  bookingDetailText: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base },
  bookingMessage: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 21, marginTop: spacing.sm },
  planBannerTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  planBannerSub: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
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
