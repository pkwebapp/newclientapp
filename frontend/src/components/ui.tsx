import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  Easing,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  View,
  ViewStyle,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { BlurView } from "expo-blur";
import { Palette, fonts, fontSize, radius, spacing } from "@/src/theme";
import { usePalette, useThemedStyles } from "@/src/theme-context";
import { useResponsive } from "@/src/hooks/use-responsive";

// ---------------- Button ----------------
export function Button({
  title,
  onPress,
  variant = "primary",
  loading,
  disabled,
  icon,
  testID,
  style,
}: {
  title: string;
  onPress?: () => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
  disabled?: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
  testID?: string;
  style?: ViewStyle;
}) {
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const isPrimary = variant === "primary";
  const isDanger = variant === "danger";
  const bg =
    variant === "primary"
      ? colors.brand
      : variant === "danger"
      ? colors.error
      : variant === "secondary"
      ? colors.surfaceTertiary
      : "transparent";
  const fg = isPrimary ? colors.onBrand : isDanger ? colors.onError : colors.onSurface;
  return (
    <Pressable
      testID={testID}
      disabled={disabled || loading}
      onPress={() => {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
        onPress?.();
      }}
      style={({ pressed }) => [
        styles.btn,
        { backgroundColor: bg, opacity: disabled ? 0.45 : pressed ? 0.85 : 1 },
        variant === "ghost" && { borderWidth: 1, borderColor: colors.borderStrong },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <View style={styles.btnRow}>
          {icon && <Ionicons name={icon} size={18} color={fg} style={{ marginRight: spacing.sm }} />}
          <Text style={[styles.btnText, { color: fg }]}>{title}</Text>
        </View>
      )}
    </Pressable>
  );
}

// ---------------- Luxe loading screen ----------------
export function LuxeLoader({
  title = "Loading PIK Connect",
  subtitle = "Preparing your experience…",
  progress,
}: {
  title?: string;
  subtitle?: string;
  progress?: number;
}) {
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const spin = useRef(new Animated.Value(0)).current;
  const pulse = useRef(new Animated.Value(0.85)).current;

  React.useEffect(() => {
    const rotation = Animated.loop(
      Animated.timing(spin, { toValue: 1, duration: 2400, easing: Easing.linear, useNativeDriver: true })
    );
    const breathing = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.85, duration: 900, useNativeDriver: true }),
      ])
    );
    rotation.start();
    breathing.start();
    return () => {
      rotation.stop();
      breathing.stop();
    };
  }, [pulse, spin]);

  const rotate = spin.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] });
  const safeProgress = typeof progress === "number" ? Math.min(100, Math.max(0, progress)) : null;

  return (
    <View style={styles.loaderScreen} testID="luxe-loader">
      <View style={styles.loaderVisual}>
        <Animated.View style={[styles.loaderRingOuter, { transform: [{ rotate }] }]} />
        <Animated.View style={[styles.loaderRingInner, { opacity: pulse, transform: [{ rotate: "-45deg" }] }]} />
        <Animated.View style={[styles.loaderLogo, { transform: [{ scale: pulse }] }]}>
          <Ionicons name="aperture" size={38} color={colors.brand} />
        </Animated.View>
      </View>
      <Text style={styles.loaderTitle}>{title}</Text>
      <Text style={styles.loaderSubtitle}>{subtitle}</Text>
      {safeProgress !== null ? (
        <View style={styles.loaderProgressTrack}>
          <View style={[styles.loaderProgressFill, { width: `${safeProgress}%` }]} />
        </View>
      ) : null}
      <Text style={styles.loaderBrand}>POWERED BY PIK CONNECT</Text>
    </View>
  );
}


// ---------------- TextField ----------------
export function TextField({
  label,
  error,
  testID,
  ...props
}: TextInputProps & { label?: string; error?: string; testID?: string }) {
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const [focused, setFocused] = useState(false);
  return (
    <View style={{ marginBottom: spacing.lg }}>
      {label && <Text style={styles.fieldLabel}>{label}</Text>}
      <TextInput
        testID={testID}
        placeholderTextColor={colors.muted}
        {...props}
        onFocus={(e) => {
          setFocused(true);
          props.onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          props.onBlur?.(e);
        }}
        style={[
          styles.input,
          { borderColor: error ? colors.onError : focused ? colors.brand : colors.border },
        ]}
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}
    </View>
  );
}

// ---------------- Pill / Badge ----------------
export function Pill({
  label,
  tone = "neutral",
  icon,
}: {
  label: string;
  tone?: "neutral" | "gold" | "success" | "warning";
  icon?: keyof typeof Ionicons.glyphMap;
}) {
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const map = {
    neutral: { bg: colors.surfaceTertiary, fg: colors.onSurfaceTertiary },
    gold: { bg: colors.brandTertiary, fg: colors.onBrandTertiary },
    success: { bg: colors.success, fg: colors.onSuccess },
    warning: { bg: colors.warning, fg: colors.onWarning },
  }[tone];
  return (
    <View style={[styles.pill, { backgroundColor: map.bg }]}>
      {icon && <Ionicons name={icon} size={12} color={map.fg} style={{ marginRight: 4 }} />}
      <Text style={[styles.pillText, { color: map.fg }]}>{label}</Text>
    </View>
  );
}

// ---------------- EmptyState ----------------
export function EmptyState({
  icon = "images-outline",
  title,
  subtitle,
  action,
  style,
}: {
  icon?: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  style?: any;
}) {
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  return (
    <View style={[styles.empty, style]}>
      <View style={styles.emptyIcon}>
        <Ionicons name={icon} size={34} color={colors.brand} />
      </View>
      <Text style={styles.emptyTitle}>{title}</Text>
      {subtitle ? <Text style={styles.emptySub}>{subtitle}</Text> : null}
      {action ? <View style={{ marginTop: spacing.lg }}>{action}</View> : null}
    </View>
  );
}

// ---------------- Toast ----------------
type ToastType = "info" | "success" | "error";
const ToastCtx = createContext<{ show: (m: string, t?: ToastType) => void }>({ show: () => {} });
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const [msg, setMsg] = useState<string | null>(null);
  const [type, setType] = useState<ToastType>("info");
  const anim = useRef(new Animated.Value(0)).current;
  const timer = useRef<any>(null);

  const show = useCallback(
    (m: string, t: ToastType = "info") => {
      setMsg(m);
      setType(t);
      if (t === "error") Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
      if (t === "success") Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      Animated.spring(anim, { toValue: 1, useNativeDriver: true }).start();
      clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        Animated.timing(anim, { toValue: 0, duration: 250, useNativeDriver: true }).start(() =>
          setMsg(null)
        );
      }, 3200);
    },
    [anim]
  );

  const bg = type === "error" ? colors.error : type === "success" ? colors.success : colors.surfaceTertiary;
  const fg = type === "error" ? colors.onError : type === "success" ? colors.onSuccess : colors.onSurface;

  // Memoized so the context value keeps its identity across renders unless show changes
  // (it never does -- see the useCallback above). Without this, every render of ToastProvider
  // (which happens on every toast.show(), since it flips local msg/type state) would hand
  // consumers a brand-new { show } object, and any effect that lists toast as a dependency --
  // several screens do, to reload data on mount -- would re-fire and clobber in-progress form state.
  const value = useMemo(() => ({ show }), [show]);

  return (
    <ToastCtx.Provider value={value}>
      {children}
      {msg && (
        <Animated.View
          pointerEvents="none"
          style={[
            styles.toast,
            {
              backgroundColor: bg,
              opacity: anim,
              transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [-20, 0] }) }],
            },
          ]}
        >
          <Ionicons
            name={type === "error" ? "alert-circle" : type === "success" ? "checkmark-circle" : "information-circle"}
            size={18}
            color={fg}
          />
          <Text style={[styles.toastText, { color: fg }]}>{msg}</Text>
        </Animated.View>
      )}
    </ToastCtx.Provider>
  );
}

// ---------------- GlassHeader ----------------
export function GlassHeader({
  title,
  onBack,
  left,
  right,
  subtitle,
  topInset = 0,
}: {
  title: string;
  onBack?: () => void;
  left?: React.ReactNode;
  right?: React.ReactNode;
  subtitle?: string;
  topInset?: number;
}) {
  const { colors, scheme } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const { isDesktop } = useResponsive();

  // Desktop: slim, left-aligned title bar (no blur / no full-bleed). The
  // persistent sidebar provides primary navigation, so we only surface a back
  // affordance when one is given plus any screen-specific right actions.
  if (isDesktop) {
    return (
      <View style={styles.headerDesktop}>
        {onBack ? (
          <Pressable testID="header-back" onPress={onBack} style={styles.backDesktop} hitSlop={10}>
            <Ionicons name="chevron-back" size={20} color={colors.onSurfaceTertiary} />
            <Text style={styles.backDesktopText}>Back</Text>
          </Pressable>
        ) : null}
        <View style={{ flex: 1 }}>
          <Text numberOfLines={1} style={styles.headerTitleDesktop}>
            {title}
          </Text>
          {subtitle ? (
            <Text numberOfLines={1} style={styles.headerSub}>
              {subtitle}
            </Text>
          ) : null}
        </View>
        {right ? <View style={{ marginLeft: spacing.md }}>{right}</View> : null}
      </View>
    );
  }

  return (
    <BlurView intensity={40} tint={scheme === "light" ? "light" : "dark"} style={[styles.header, { paddingTop: topInset + spacing.sm }]}>
      <View style={styles.headerRow}>
        {onBack ? (
          <Pressable testID="header-back" onPress={onBack} style={styles.iconBtn} hitSlop={10}>
            <Ionicons name="chevron-back" size={24} color={colors.onSurface} />
          </Pressable>
        ) : left ? (
          <View style={{ minWidth: 40 }}>{left}</View>
        ) : (
          <View style={{ width: 40 }} />
        )}
        <View style={{ flex: 1, alignItems: "center" }}>
          <Text numberOfLines={1} style={styles.headerTitle}>
            {title}
          </Text>
          {subtitle ? (
            <Text numberOfLines={1} style={styles.headerSub}>
              {subtitle}
            </Text>
          ) : null}
        </View>
        <View style={{ minWidth: 40, alignItems: "flex-end" }}>{right}</View>
      </View>
    </BlurView>
  );
}

const makeStyles = (colors: Palette) => StyleSheet.create({
  loaderScreen: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl, backgroundColor: colors.surface },
  loaderVisual: { width: 138, height: 138, alignItems: "center", justifyContent: "center", marginBottom: spacing.xl },
  loaderRingOuter: { position: "absolute", width: 132, height: 132, borderRadius: 66, borderWidth: 4, borderColor: colors.brand, borderLeftColor: "transparent", borderBottomColor: "transparent" },
  loaderRingInner: { position: "absolute", width: 104, height: 104, borderRadius: 52, borderWidth: 2, borderColor: colors.onSurfaceTertiary, borderRightColor: "transparent", borderTopColor: "transparent" },
  loaderLogo: { width: 72, height: 72, borderRadius: 36, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  loaderTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, textAlign: "center" },
  loaderSubtitle: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, textAlign: "center", marginTop: spacing.sm },
  loaderProgressTrack: { width: "100%", maxWidth: 280, height: 6, borderRadius: radius.pill, backgroundColor: colors.surfaceTertiary, overflow: "hidden", marginTop: spacing.lg },
  loaderProgressFill: { height: 6, borderRadius: radius.pill, backgroundColor: colors.brand },
  loaderBrand: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, letterSpacing: 2, marginTop: spacing["2xl"] },

  btn: {
    height: 52,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
  },
  btnRow: { flexDirection: "row", alignItems: "center" },
  btnText: { fontSize: fontSize.lg, fontFamily: fonts.text, fontWeight: "600" },
  fieldLabel: {
    color: colors.onSurfaceSecondary,
    fontSize: fontSize.sm,
    marginBottom: spacing.sm,
    fontFamily: fonts.text,
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  input: {
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderRadius: radius.md,
    color: colors.onSurface,
    paddingHorizontal: spacing.lg,
    height: 52,
    fontSize: fontSize.lg,
    fontFamily: fonts.text,
  },
  fieldError: { color: colors.onError, fontSize: fontSize.sm, marginTop: spacing.xs },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: 5,
    borderRadius: radius.pill,
    alignSelf: "flex-start",
  },
  pillText: { fontSize: fontSize.sm, fontFamily: fonts.text, fontWeight: "500" },
  empty: { alignItems: "center", justifyContent: "center", padding: spacing["2xl"], marginTop: spacing["3xl"] },
  emptyIcon: {
    width: 76,
    height: 76,
    borderRadius: radius.pill,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  emptyTitle: { color: colors.onSurface, fontSize: fontSize.xl, fontFamily: fonts.display, textAlign: "center" },
  emptySub: {
    color: colors.muted,
    fontSize: fontSize.base,
    fontFamily: fonts.text,
    textAlign: "center",
    marginTop: spacing.sm,
    lineHeight: 20,
    maxWidth: 280,
  },
  toast: {
    position: "absolute",
    top: 56,
    left: spacing.lg,
    right: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.md,
    borderRadius: radius.md,
    zIndex: 9999,
  },
  toastText: { color: colors.onSurface, marginLeft: spacing.sm, fontFamily: fonts.text, flex: 1 },
  header: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    overflow: "hidden",
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    minHeight: 48,
  },
  iconBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  headerTitle: { color: colors.onSurface, fontSize: fontSize.lg, fontFamily: fonts.display },
  headerSub: { color: colors.muted, fontSize: fontSize.sm, fontFamily: fonts.text, marginTop: 2 },
  headerDesktop: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.xl,
    paddingBottom: spacing.lg,
    gap: spacing.lg,
  },
  headerTitleDesktop: { color: colors.onSurface, fontSize: fontSize["3xl"], fontFamily: fonts.display },
  backDesktop: { flexDirection: "row", alignItems: "center", gap: 2 },
  backDesktopText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
});
