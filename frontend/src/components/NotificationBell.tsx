import { useCallback, useEffect, useMemo, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "@/src/api/client";
import { Palette, fonts, fontSize, radius, spacing } from "@/src/theme";
import { usePalette, useThemedStyles } from "@/src/theme-context";

export function NotificationBell({ audience, testID, onNotificationPress }: { audience: "admin" | "client"; testID?: string; onNotificationPress?: (item: any) => void }) {
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const [items, setItems] = useState<any[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const isAdmin = audience === "admin";
  const listPath = isAdmin ? "/notifications" : "/me/notifications";

  const load = useCallback(async () => {
    try {
      const response = await api.get(listPath);
      setItems(response.items || []);
      setUnread(response.unread_count || 0);
    } catch {
      // The bell stays quiet when a session is still bootstrapping.
    }
  }, [listPath]);

  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 30_000);
    return () => clearInterval(timer);
  }, [load]);

  const markRead = async (item: any) => {
    if (item.read) return;
    const path = isAdmin ? `/notifications/${item.notification_id}/read` : `/me/notifications/${item.notification_id}/read`;
    try {
      await api.patch(path, {});
      setItems((current) => current.map((entry) => entry.notification_id === item.notification_id ? { ...entry, read: true } : entry));
      setUnread((count) => Math.max(0, count - 1));
    } catch {}
  };

  const handleNotificationPress = async (item: any) => {
    await markRead(item);
    setOpen(false);
    onNotificationPress?.({ ...item, read: true });
  };

  const icon = useMemo(() => (audience === "admin" ? "calendar-outline" : "megaphone-outline"), [audience]);

  return (
    <>
      <Pressable testID={testID || `${audience}-notification-bell`} onPress={() => setOpen(true)} style={styles.bell} hitSlop={8} accessibilityLabel="Notifications">
        <Ionicons name="notifications-outline" size={22} color={colors.onSurface} />
        {unread > 0 && <View style={styles.badge}><Text style={styles.badgeText}>{unread > 9 ? "9+" : unread}</Text></View>}
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.panel} testID={`${audience}-notification-panel`} onPress={() => {}}>
            <View style={styles.panelHeader}>
              <View>
                <Text style={styles.panelTitle}>Notifications</Text>
                <Text style={styles.panelSub}>{unread ? `${unread} unread` : "You're all caught up"}</Text>
              </View>
              <Pressable testID={`${audience}-notification-close`} onPress={() => setOpen(false)} style={styles.close}><Ionicons name="close" size={20} color={colors.muted} /></Pressable>
            </View>
            <ScrollView style={styles.list} contentContainerStyle={items.length ? undefined : styles.emptyList}>
              {items.length === 0 ? (
                <View><Ionicons name="notifications-off-outline" size={28} color={colors.muted} /><Text style={styles.emptyTitle}>No notifications yet</Text><Text style={styles.emptyText}>{isAdmin ? "New bookings and client activity will appear here." : "Offers, gallery notices and payment reminders will appear here."}</Text></View>
              ) : items.map((item) => (
                <Pressable key={item.notification_id} testID={`bell-notification-${item.notification_id}`} onPress={() => handleNotificationPress(item)} style={[styles.item, !item.read && styles.itemUnread]}>
                  <View style={styles.itemIcon}><Ionicons name={item.type === "booking_request" ? icon : "information-circle-outline"} size={18} color={colors.brand} /></View>
                  <View style={{ flex: 1 }}><Text style={styles.itemTitle}>{item.title}</Text><Text style={styles.itemBody}>{item.body}</Text></View>
                  {!item.read && <View style={styles.dot} />}
                </Pressable>
              ))}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const makeStyles = (colors: Palette) => StyleSheet.create({
  bell: { width: 44, height: 44, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  badge: { position: "absolute", top: -2, right: -2, minWidth: 18, height: 18, borderRadius: radius.pill, backgroundColor: colors.brand, alignItems: "center", justifyContent: "center", paddingHorizontal: 4 },
  badgeText: { color: colors.onBrand, fontFamily: fonts.text, fontSize: 10, fontWeight: "800" },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", alignItems: "flex-end", paddingTop: 72, paddingHorizontal: spacing.lg },
  panel: { width: "100%", maxWidth: 420, maxHeight: "76%", backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.lg },
  panelHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  panelTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  panelSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 3 },
  close: { width: 40, height: 40, borderRadius: radius.pill, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  list: { flexGrow: 0 },
  emptyList: { minHeight: 180, alignItems: "center", justifyContent: "center" },
  emptyTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700", marginTop: spacing.md, textAlign: "center" },
  emptyText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, textAlign: "center", marginTop: spacing.xs, maxWidth: 260 },
  item: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, marginBottom: spacing.sm },
  itemUnread: { backgroundColor: colors.brandTertiary },
  itemIcon: { width: 36, height: 36, borderRadius: radius.pill, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  itemTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  itemBody: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginTop: 3 },
  dot: { width: 8, height: 8, borderRadius: radius.pill, backgroundColor: colors.brand },
});
