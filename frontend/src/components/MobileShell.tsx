import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  Easing,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { useRouter, usePathname } from "expo-router";
import { BlurView } from "expo-blur";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";

import { useAuth } from "@/src/context/AuthContext";
import {
  ADMIN_TABS,
  ADMIN_TAB_ROOTS,
  ADMIN_DRAWER_ITEMS,
  ADMIN_DRAWER_FOOTER,
  CLIENT_DRAWER_ITEMS,
  TabItem,
  DrawerItem,
} from "@/src/navigation/nav-config";
import { Palette, fonts, fontSize, radius, spacing } from "@/src/theme";
import { usePalette, useThemedStyles } from "@/src/theme-context";

const USE_NATIVE = Platform.OS !== "web";

// ---------------- Nav context (drawer control) ----------------
const NavContext = createContext<{ openDrawer: () => void }>({ openDrawer: () => {} });
export const useNav = () => useContext(NavContext);

/** Hamburger button for screen headers. Safe no-op outside a MobileShell. */
export function HeaderMenuButton() {
  const { openDrawer } = useNav();
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  return (
    <Pressable testID="header-menu-btn" onPress={openDrawer} hitSlop={10} style={styles.menuBtn}>
      <Ionicons name="menu" size={24} color={colors.onSurface} />
    </Pressable>
  );
}

// ---------------- Mobile shell ----------------
export function MobileShell({
  role,
  children,
}: {
  role: "admin" | "client";
  children: React.ReactNode;
}) {
  const styles = useThemedStyles(makeStyles);
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);
  // Stable across renders (see the ToastProvider fix in ui.tsx for why this matters): a fresh
  // { openDrawer } object on every render would give any effect keying off useNav() a reason to
  // re-fire on every MobileShell re-render, not just when the drawer control actually changes.
  const openDrawer = useCallback(() => setDrawerOpen(true), []);
  const navValue = useMemo(() => ({ openDrawer }), [openDrawer]);

  const tabs = role === "admin" ? ADMIN_TABS : [];
  const tabRoots = role === "admin" ? ADMIN_TAB_ROOTS : [];
  const showTabBar = tabs.length > 1 && tabRoots.includes(pathname);

  return (
    <NavContext.Provider value={navValue}>
      <View style={styles.root}>
        <View style={{ flex: 1 }}>{children}</View>
        {showTabBar ? <TabBar tabs={tabs} pathname={pathname} /> : null}
      </View>
      <Drawer role={role} open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </NavContext.Provider>
  );
}

// ---------------- Bottom tab bar ----------------
function TabBar({ tabs, pathname }: { tabs: TabItem[]; pathname: string }) {
  const { colors, scheme } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const go = (href: string, active: boolean) => {
    if (active) return;
    Haptics.selectionAsync().catch(() => {});
    // replace keeps the stack shallow while switching between tab roots
    router.replace(href as any);
  };

  return (
    <BlurView intensity={40} tint={scheme === "light" ? "light" : "dark"} style={[styles.tabBar, { paddingBottom: insets.bottom || spacing.sm }]}>
      {tabs.map((t) => {
        const active = t.isActive(pathname);
        return (
          <Pressable
            key={t.key}
            testID={`tab-${t.key}`}
            onPress={() => go(t.href, active)}
            style={styles.tabItem}
            hitSlop={6}
          >
            <Ionicons name={active ? t.activeIcon : t.icon} size={24} color={active ? colors.brand : colors.muted} />
            <Text style={[styles.tabLabel, active && styles.tabLabelActive]} numberOfLines={1}>
              {t.label}
            </Text>
          </Pressable>
        );
      })}
    </BlurView>
  );
}

// ---------------- Slide-in drawer ----------------
function Drawer({
  role,
  open,
  onClose,
}: {
  role: "admin" | "client";
  open: boolean;
  onClose: () => void;
}) {
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const { user, signOut } = useAuth();

  const panelW = Math.min(320, width * 0.84);
  const anim = useRef(new Animated.Value(0)).current;
  const [mounted, setMounted] = useState(open);

  useEffect(() => {
    if (open) {
      setMounted(true);
      Animated.timing(anim, {
        toValue: 1,
        duration: 240,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: USE_NATIVE,
      }).start();
    } else {
      Animated.timing(anim, {
        toValue: 0,
        duration: 180,
        easing: Easing.in(Easing.cubic),
        useNativeDriver: USE_NATIVE,
      }).start(({ finished }) => finished && setMounted(false));
    }
  }, [open, anim]);

  if (!mounted) return null;

  const items = role === "admin" ? ADMIN_DRAWER_ITEMS : CLIENT_DRAWER_ITEMS;
  const footer = ADMIN_DRAWER_FOOTER;

  const handle = (item: DrawerItem) => {
    onClose();
    setTimeout(() => {
      if (item.action === "signout") signOut();
      else if (item.action === "home") router.replace("/" as any);
      else if (item.href) router.push(item.href as any);
    }, 60);
  };

  const translateX = anim.interpolate({ inputRange: [0, 1], outputRange: [-panelW - 8, 0] });
  const backdrop = anim.interpolate({ inputRange: [0, 1], outputRange: [0, 0.6] });

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
      <Animated.View style={[StyleSheet.absoluteFill, styles.backdrop, { opacity: backdrop }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} testID="drawer-backdrop" />
      </Animated.View>

      <Animated.View
        style={[
          styles.panel,
          { width: panelW, paddingTop: insets.top + spacing.lg, transform: [{ translateX }] },
        ]}
      >
        {/* Brand / account */}
        <View style={styles.brandRow}>
          <View style={styles.brandBadge}>
            <Ionicons name="aperture" size={22} color={colors.brand} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.brand}>PIK CONNECT</Text>
            <Text style={styles.roleTag}>{role === "admin" ? "Studio Console" : "Client Gallery"}</Text>
          </View>
        </View>
        {user?.email ? (
          <Text style={styles.account} numberOfLines={1}>
            {user.email}
          </Text>
        ) : null}

        <View style={styles.divider} />

        {/* Less-used destinations */}
        <View style={{ gap: spacing.xs }}>
          {items.map((item) => (
            <Pressable
              key={item.key}
              testID={`drawer-${item.key}`}
              onPress={() => handle(item)}
              style={({ pressed }) => [styles.drawerItem, pressed && styles.drawerItemPressed]}
            >
              <View style={styles.drawerIcon}>
                <Ionicons name={item.icon} size={20} color={colors.brand} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.drawerLabel}>{item.label}</Text>
                {item.sublabel ? <Text style={styles.drawerSub}>{item.sublabel}</Text> : null}
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.muted} />
            </Pressable>
          ))}
        </View>

        {/* Footer actions */}
        <View style={styles.drawerFooter}>
          {footer.map((item) => (
            <Pressable
              key={item.key}
              testID={`drawer-${item.key}`}
              onPress={() => handle(item)}
              style={({ pressed }) => [styles.footerItem, pressed && styles.drawerItemPressed]}
            >
              <Ionicons
                name={item.icon}
                size={20}
                color={item.tone === "danger" ? colors.onError : colors.onSurfaceTertiary}
              />
              <Text style={[styles.footerLabel, item.tone === "danger" && { color: colors.onError }]}>
                {item.label}
              </Text>
            </Pressable>
          ))}
        </View>
      </Animated.View>
    </View>
  );
}

const makeStyles = (colors: Palette) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  menuBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center" },

  // Tab bar
  tabBar: {
    flexDirection: "row",
    alignItems: "center",
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderStrong,
    backgroundColor: colors.shellBlur,
    overflow: "hidden",
  },
  tabItem: { flex: 1, alignItems: "center", justifyContent: "center", gap: 3, minHeight: 48, paddingVertical: 4 },
  tabLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: 11, letterSpacing: 0.2 },
  tabLabelActive: { color: colors.brand, fontWeight: "600" },

  // Drawer
  backdrop: { backgroundColor: "#000" },
  panel: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    backgroundColor: colors.surfaceSecondary,
    borderRightWidth: StyleSheet.hairlineWidth,
    borderRightColor: colors.borderStrong,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
  },
  brandRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  brandBadge: {
    width: 42,
    height: 42,
    borderRadius: radius.pill,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  brand: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, letterSpacing: 3, fontWeight: "700" },
  roleTag: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize.sm, marginTop: 2 },
  account: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.md },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border, marginVertical: spacing.lg },
  drawerItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
  },
  drawerItemPressed: { backgroundColor: colors.surfaceTertiary },
  drawerIcon: {
    width: 38,
    height: 38,
    borderRadius: radius.pill,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  drawerLabel: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "600" },
  drawerSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  drawerFooter: { marginTop: "auto", borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: spacing.md, gap: spacing.xs },
  footerItem: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md },
  footerLabel: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.lg },
});
