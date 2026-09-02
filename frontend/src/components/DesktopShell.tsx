import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter, usePathname } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "@/src/context/AuthContext";
import { SIDEBAR_WIDTH, CONTENT_MAX_WIDTH } from "@/src/hooks/use-responsive";
import { Palette, fonts, fontSize, radius, spacing } from "@/src/theme";
import { usePalette, useThemedStyles } from "@/src/theme-context";
import {
  ADMIN_TABS,
  ADMIN_DRAWER_ITEMS,
  ADMIN_DRAWER_FOOTER,
  CLIENT_DRAWER_ITEMS,
  type TabItem,
  type DrawerItem,
} from "@/src/navigation/nav-config";

// The client side has no bottom tab bar (its mobile nav is drawer-only), so its
// single "home" tab is defined here rather than in nav-config. Everything else --
// the admin tabs, both drawers, and the footer actions -- comes from that shared
// config, so mobile and desktop navigation can no longer drift apart the way the
// old hardcoded copy here once did.
const CLIENT_HOME: TabItem = {
  key: "home",
  label: "Your Memories",
  icon: "images-outline",
  activeIcon: "images",
  href: "/client",
  isActive: (p) => p === "/client",
};

/**
 * Desktop application shell: a persistent left sidebar with brand + navigation,
 * and a centered, width-capped content column that hosts the routed screen.
 * Rendered only on wide viewports (see the group _layout files).
 */
export function DesktopShell({
  role,
  children,
}: {
  role: "admin" | "client";
  children: React.ReactNode;
}) {
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const router = useRouter();
  const pathname = usePathname();
  const { user, signOut } = useAuth();

  const primaryNav: TabItem[] = role === "admin" ? ADMIN_TABS : [CLIENT_HOME];
  const secondaryNav: DrawerItem[] = role === "admin" ? ADMIN_DRAWER_ITEMS : CLIENT_DRAWER_ITEMS;
  const isDrawerActive = (href?: string) => !!href && (pathname === href || pathname.startsWith(`${href}/`));

  return (
    <View style={styles.root}>
      {/* ------------------------- Sidebar ------------------------- */}
      <View style={styles.sidebar}>
        <View style={styles.brandRow}>
          <Ionicons name="aperture-outline" size={24} color={colors.brand} />
          <Text style={styles.brand}>PIK CONNECT</Text>
        </View>
        <Text style={styles.roleTag}>{role === "admin" ? "Studio Console" : "Client Gallery"}</Text>

        <View style={styles.nav}>
          {primaryNav.map((item) => {
            const active = item.isActive(pathname);
            return (
              <Pressable
                key={item.href}
                testID={`nav-${item.href}`}
                onPress={() => router.push(item.href as any)}
                style={[styles.navItem, active && styles.navItemActive]}
              >
                <Ionicons name={active ? item.activeIcon : item.icon} size={20} color={active ? colors.onBrand : colors.onSurfaceTertiary} />
                <Text style={[styles.navText, active && styles.navTextActive]}>{item.label}</Text>
              </Pressable>
            );
          })}
        </View>

        {secondaryNav.length > 0 ? (
          <>
            <Text style={styles.navSectionLabel}>Manage</Text>
            <View style={styles.nav}>
              {secondaryNav.map((item) => {
                const active = isDrawerActive(item.href);
                return (
                  <Pressable
                    key={item.key}
                    testID={`nav-${item.href}`}
                    onPress={() => item.href && router.push(item.href as any)}
                    style={[styles.navItem, active && styles.navItemActive]}
                  >
                    <Ionicons name={item.icon} size={20} color={active ? colors.onBrand : colors.onSurfaceTertiary} />
                    <Text style={[styles.navText, active && styles.navTextActive]}>{item.label}</Text>
                  </Pressable>
                );
              })}
            </View>
          </>
        ) : null}

        <View style={styles.sidebarFooter}>
          {ADMIN_DRAWER_FOOTER.map((item) => (
            <Pressable
              key={item.key}
              testID={`nav-${item.key}`}
              onPress={() => (item.action === "signout" ? signOut() : router.push("/"))}
              style={styles.navItem}
            >
              <Ionicons name={item.icon} size={20} color={item.tone === "danger" ? colors.error : colors.onSurfaceTertiary} />
              <Text style={[styles.navText, item.tone === "danger" && { color: colors.error }]}>{item.label}</Text>
            </Pressable>
          ))}
          {user?.email ? (
            <Text style={styles.userLine} numberOfLines={1}>{user.email}</Text>
          ) : user?.name ? (
            <Text style={styles.userLine} numberOfLines={1}>{user.name}</Text>
          ) : null}
        </View>
      </View>

      {/* --------------------------- Content --------------------------- */}
      <View style={styles.contentArea}>
        <View style={styles.contentColumn}>{children}</View>
      </View>
    </View>
  );
}

const makeStyles = (colors: Palette) => StyleSheet.create({
  root: { flex: 1, flexDirection: "row", backgroundColor: colors.surface },
  sidebar: {
    width: SIDEBAR_WIDTH,
    backgroundColor: colors.surfaceSecondary,
    borderRightWidth: StyleSheet.hairlineWidth,
    borderRightColor: colors.borderStrong,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xl,
  },
  brandRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  brand: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, letterSpacing: 3, fontWeight: "700" },
  roleTag: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize.sm, marginTop: spacing.xs, marginLeft: 34, letterSpacing: 0.5 },
  nav: { marginTop: spacing["2xl"], gap: spacing.xs },
  navSectionLabel: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm, letterSpacing: 1, textTransform: "uppercase", marginTop: spacing.xl, marginBottom: spacing.xs, marginLeft: spacing.md },
  navItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
  },
  navItemActive: { backgroundColor: colors.brand },
  navText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.lg },
  navTextActive: { color: colors.onBrand, fontWeight: "600" },
  sidebarFooter: { marginTop: "auto", borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.borderStrong, paddingTop: spacing.md, gap: spacing.xs },
  userLine: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, paddingHorizontal: spacing.md, marginTop: spacing.sm },
  contentArea: { flex: 1, flexDirection: "row", justifyContent: "center", backgroundColor: colors.surface },
  contentColumn: { flex: 1, maxWidth: CONTENT_MAX_WIDTH, width: "100%" },
});
