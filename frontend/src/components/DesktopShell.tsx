import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter, usePathname } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "@/src/context/AuthContext";
import { SIDEBAR_WIDTH, CONTENT_MAX_WIDTH } from "@/src/hooks/use-responsive";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

type NavItem = { label: string; icon: keyof typeof Ionicons.glyphMap; href: string };

const ADMIN_NAV: NavItem[] = [
  { label: "Home", icon: "home-outline", href: "/admin" },
  { label: "Client Galleries", icon: "images-outline", href: "/admin/galleries" },
  { label: "Clients", icon: "people-outline", href: "/admin/clients" },
  { label: "Albums", icon: "book-outline", href: "/admin/albums" },
];

const CLIENT_NAV: NavItem[] = [
  { label: "Your Memories", icon: "images-outline", href: "/client" },
];

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
  const router = useRouter();
  const pathname = usePathname();
  const { user, signOut } = useAuth();

  const nav = role === "admin" ? ADMIN_NAV : CLIENT_NAV;

  const isActive = (href: string) => {
    if (href === "/admin") return pathname === "/admin";
    if (href === "/admin/galleries") return pathname.startsWith("/admin/galleries") || pathname.startsWith("/admin/event");
    if (href === "/admin/clients") return pathname === "/admin/clients" || pathname.startsWith("/admin/client");
    if (href === "/admin/albums") return pathname.startsWith("/admin/album");
    if (href === "/client") return pathname === "/client" || pathname.startsWith("/client/");
    return pathname === href;
  };

  return (
    <View style={styles.root}>
      {/* ---------------- Sidebar ---------------- */}
      <View style={styles.sidebar}>
        <View style={styles.brandRow}>
          <Ionicons name="aperture-outline" size={24} color={colors.brand} />
          <Text style={styles.brand}>PK PHOTOGRAPHY</Text>
        </View>
        <Text style={styles.roleTag}>{role === "admin" ? "Studio Console" : "Client Gallery"}</Text>

        <View style={styles.nav}>
          {nav.map((item) => {
            const active = isActive(item.href);
            return (
              <Pressable
                key={item.href}
                testID={`nav-${item.href}`}
                onPress={() => router.push(item.href as any)}
                style={[styles.navItem, active && styles.navItemActive]}
              >
                <Ionicons name={item.icon} size={20} color={active ? colors.onBrand : colors.onSurfaceTertiary} />
                <Text style={[styles.navText, active && styles.navTextActive]}>{item.label}</Text>
              </Pressable>
            );
          })}
        </View>

        <View style={styles.sidebarFooter}>
          {role === "admin" ? (
            <Pressable testID="nav-settings" onPress={() => router.push("/admin/settings" as any)} style={[styles.navItem, isActive("/admin/settings") && styles.navItemActive]}>
              <Ionicons name="settings-outline" size={20} color={isActive("/admin/settings") ? colors.onBrand : colors.onSurfaceTertiary} />
              <Text style={[styles.navText, isActive("/admin/settings") && styles.navTextActive]}>Settings</Text>
            </Pressable>
          ) : null}
          <Pressable testID="nav-home" onPress={() => router.push("/login")} style={styles.navItem}>
            <Ionicons name="home-outline" size={20} color={colors.onSurfaceTertiary} />
            <Text style={styles.navText}>Home</Text>
          </Pressable>
          <Pressable testID="nav-signout" onPress={signOut} style={styles.navItem}>
            <Ionicons name="log-out-outline" size={20} color={colors.onSurfaceTertiary} />
            <Text style={styles.navText}>Sign out</Text>
          </Pressable>
          {user?.email ? (
            <Text style={styles.userLine} numberOfLines={1}>{user.email}</Text>
          ) : user?.name ? (
            <Text style={styles.userLine} numberOfLines={1}>{user.name}</Text>
          ) : null}
        </View>
      </View>

      {/* ---------------- Content ---------------- */}
      <View style={styles.contentArea}>
        <View style={styles.contentColumn}>{children}</View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
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
  sidebarFooter: { marginTop: "auto", borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: spacing.md, gap: spacing.xs },
  userLine: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, paddingHorizontal: spacing.md, marginTop: spacing.sm },
  contentArea: { flex: 1, flexDirection: "row", justifyContent: "center", backgroundColor: colors.surface },
  contentColumn: { flex: 1, maxWidth: CONTENT_MAX_WIDTH, width: "100%" },
});
