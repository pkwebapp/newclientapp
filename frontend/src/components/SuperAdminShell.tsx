import React, { useState } from "react";
import { Modal, Platform, Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { usePathname, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "@/src/context/AuthContext";
import { colors, fonts, radius, spacing } from "@/src/theme";

export const SUPERADMIN_NAV = [
  { key: "dashboard", label: "Dashboard", icon: "grid-outline", href: "/superadmin" },
  { key: "photographers", label: "Photographers", icon: "people-outline", href: "/superadmin/photographers" },
  { key: "memberships", label: "Memberships", icon: "card-outline", href: "/superadmin/memberships" },
  { key: "galleries", label: "Galleries", icon: "images-outline", href: "/superadmin/galleries" },
  { key: "storage", label: "Storage", icon: "cloud-outline", href: "/superadmin/storage" },
  { key: "activity", label: "Activity Logs", icon: "pulse-outline", href: "/superadmin/activity" },
  { key: "settings", label: "Settings", icon: "settings-outline", href: "/superadmin/settings" },
] as const;

function activeKey(pathname: string) {
  if (pathname === "/superadmin") return "dashboard";
  return SUPERADMIN_NAV.find((item) => item.key !== "dashboard" && pathname.startsWith(item.href))?.key || "dashboard";
}

export function SuperAdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const { user, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const desktop = Platform.OS === "web" && width >= 900;
  const active = activeKey(pathname);

  const navigate = (href: string) => {
    setMenuOpen(false);
    router.replace(href as any);
  };

  const nav = (
    <View style={styles.navList}>
      {SUPERADMIN_NAV.map((item) => (
        <Pressable
          key={item.key}
          testID={`superadmin-nav-${item.key}`}
          onPress={() => navigate(item.href)}
          style={[styles.navItem, active === item.key && styles.navItemActive]}
        >
          <Ionicons name={item.icon as any} size={19} color={active === item.key ? colors.onBrand : colors.onSurfaceTertiary} />
          <Text style={[styles.navLabel, active === item.key && styles.navLabelActive]}>{item.label}</Text>
        </Pressable>
      ))}
    </View>
  );

  const sidebar = (
    <View style={styles.sidebar}>
      <View style={styles.brandRow}>
        <View style={styles.brandIcon}><Ionicons name="aperture" size={22} color={colors.brand} /></View>
        <View><Text style={styles.brand}>PIK CONNECT</Text><Text style={styles.superTag}>SUPER ADMIN</Text></View>
      </View>
      <View style={styles.divider} />
      {nav}
      <View style={styles.sidebarBottom}>
        <Text style={styles.accountLabel}>PLATFORM OWNER</Text>
        <Text style={styles.accountEmail} numberOfLines={1}>{user?.email}</Text>
        <Pressable testID="superadmin-logout" onPress={signOut} style={styles.logout}>
          <Ionicons name="log-out-outline" size={18} color={colors.onError} />
          <Text style={styles.logoutText}>Logout</Text>
        </Pressable>
      </View>
    </View>
  );

  if (desktop) return <View style={styles.root}>{sidebar}<View style={styles.content}>{children}</View></View>;

  return (
    <View style={styles.mobileRoot}>
      <View style={styles.mobileBar}>
        <Pressable testID="superadmin-menu-btn" onPress={() => setMenuOpen(true)} style={styles.menuButton}>
          <Ionicons name="menu" size={24} color={colors.onSurface} />
        </Pressable>
        <View style={{ flex: 1 }}><Text style={styles.mobileTitle}>PIK CONNECT</Text><Text style={styles.mobileSubtitle}>SUPER ADMIN</Text></View>
        <Ionicons name="shield-checkmark-outline" size={22} color={colors.brand} />
      </View>
      {children}
      <Modal visible={menuOpen} transparent animationType="fade" onRequestClose={() => setMenuOpen(false)}>
        <View style={styles.modalLayer}>
          <Pressable style={styles.modalBackdrop} onPress={() => setMenuOpen(false)} />
          <View style={styles.mobileDrawer}>
            <View style={styles.brandRow}><View style={styles.brandIcon}><Ionicons name="aperture" size={22} color={colors.brand} /></View><View><Text style={styles.brand}>PIK CONNECT</Text><Text style={styles.superTag}>SUPER ADMIN</Text></View></View>
            <View style={styles.divider} />
            {nav}
            <View style={styles.sidebarBottom}><Text style={styles.accountEmail}>{user?.email}</Text><Pressable onPress={signOut} style={styles.logout}><Ionicons name="log-out-outline" size={18} color={colors.onError} /><Text style={styles.logoutText}>Logout</Text></Pressable></View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

export function SuperAdminHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return <View style={styles.pageHeader}><Text style={styles.pageTitle}>{title}</Text>{subtitle ? <Text style={styles.pageSubtitle}>{subtitle}</Text> : null}</View>;
}

export function StatCard({ label, value, icon, accent = false }: { label: string; value: string; icon: keyof typeof Ionicons.glyphMap; accent?: boolean }) {
  return <View style={styles.statCard}><View style={[styles.statIcon, accent && styles.statIconAccent]}><Ionicons name={icon} size={19} color={accent ? colors.onBrand : colors.brand} /></View><Text style={styles.statLabel}>{label}</Text><Text style={styles.statValue}>{value}</Text></View>;
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase().replace("_", " ");
  const tone = normalized === "active" || normalized === "success" ? "success" : normalized === "trial" ? "warning" : normalized.includes("disabled") || normalized === "suspended" ? "danger" : "neutral";
  return <View style={[styles.badge, tone === "success" ? styles.badgeSuccess : tone === "warning" ? styles.badgeWarning : tone === "danger" ? styles.badgeDanger : styles.badgeNeutral]}><Text style={styles.badgeText}>{status}</Text></View>;
}

export function ProgressBar({ value }: { value: number }) {
  const percent = Math.min(100, Math.max(0, value));
  return <View style={styles.progressTrack}><View style={[styles.progressFill, { width: `${percent}%` }]} /></View>;
}

export function formatBytes(bytes: number) {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

const styles = StyleSheet.create({
  root: { flex: 1, flexDirection: "row", backgroundColor: "#F7F8FA" },
  content: { flex: 1, backgroundColor: "#F7F8FA" },
  mobileRoot: { flex: 1, backgroundColor: "#F7F8FA" },
  sidebar: { width: 248, backgroundColor: "#FFFFFF", borderRightWidth: 1, borderRightColor: "#E7E9ED", padding: spacing.lg },
  brandRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  brandIcon: { width: 38, height: 38, borderRadius: radius.md, backgroundColor: "#FFF1EC", alignItems: "center", justifyContent: "center" },
  brand: { color: "#1D2025", fontFamily: fonts.text, fontSize: 13, fontWeight: "800", letterSpacing: 2 },
  superTag: { color: colors.brand, fontFamily: fonts.text, fontSize: 9, fontWeight: "700", letterSpacing: 1.2, marginTop: 3 },
  divider: { height: 1, backgroundColor: "#E7E9ED", marginVertical: spacing.lg },
  navList: { gap: 4 },
  navItem: { minHeight: 46, flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.md, borderRadius: radius.md },
  navItemActive: { backgroundColor: colors.brand },
  navLabel: { color: "#667085", fontFamily: fonts.text, fontSize: 14, fontWeight: "500" },
  navLabelActive: { color: colors.onBrand, fontWeight: "700" },
  sidebarBottom: { marginTop: "auto", borderTopWidth: 1, borderTopColor: "#E7E9ED", paddingTop: spacing.lg },
  accountLabel: { color: "#98A2B3", fontFamily: fonts.text, fontSize: 10, letterSpacing: 1, marginBottom: spacing.xs },
  accountEmail: { color: "#475467", fontFamily: fonts.text, fontSize: 12, marginBottom: spacing.md },
  logout: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.sm },
  logoutText: { color: "#B42318", fontFamily: fonts.text, fontSize: 14, fontWeight: "600" },
  mobileBar: { minHeight: 68, paddingHorizontal: spacing.lg, flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: "#FFFFFF", borderBottomWidth: 1, borderBottomColor: "#E7E9ED" },
  menuButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  mobileTitle: { color: "#1D2025", fontFamily: fonts.text, fontSize: 13, fontWeight: "800", letterSpacing: 2 },
  mobileSubtitle: { color: colors.brand, fontFamily: fonts.text, fontSize: 9, fontWeight: "700", letterSpacing: 1 },
  modalLayer: { flex: 1, flexDirection: "row" },
  modalBackdrop: { flex: 1, backgroundColor: "rgba(16,24,40,0.36)" },
  mobileDrawer: { width: 300, backgroundColor: "#FFFFFF", padding: spacing.lg },
  pageHeader: { paddingHorizontal: spacing["2xl"], paddingTop: spacing["2xl"], paddingBottom: spacing.lg },
  pageTitle: { color: "#101828", fontFamily: fonts.display, fontSize: 30, fontWeight: "700" },
  pageSubtitle: { color: "#667085", fontFamily: fonts.text, fontSize: 14, marginTop: spacing.xs },
  statCard: { flex: 1, minWidth: 150, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.lg, padding: spacing.lg, minHeight: 132 },
  statIcon: { width: 38, height: 38, borderRadius: radius.md, backgroundColor: "#FFF1EC", alignItems: "center", justifyContent: "center", marginBottom: spacing.md },
  statIconAccent: { backgroundColor: colors.brand },
  statLabel: { color: "#667085", fontFamily: fonts.text, fontSize: 12 },
  statValue: { color: "#101828", fontFamily: fonts.display, fontSize: 25, fontWeight: "700", marginTop: 4 },
  badge: { alignSelf: "flex-start", paddingHorizontal: 9, paddingVertical: 5, borderRadius: radius.pill },
  badgeSuccess: { backgroundColor: "#ECFDF3" },
  badgeWarning: { backgroundColor: "#FFFAEB" },
  badgeDanger: { backgroundColor: "#FEF3F2" },
  badgeNeutral: { backgroundColor: "#F2F4F7" },
  badgeText: { color: "#344054", fontFamily: fonts.text, fontSize: 11, fontWeight: "600", textTransform: "capitalize" },
  progressTrack: { height: 8, borderRadius: radius.pill, backgroundColor: "#EAECF0", overflow: "hidden" },
  progressFill: { height: 8, borderRadius: radius.pill, backgroundColor: colors.brand },
});
