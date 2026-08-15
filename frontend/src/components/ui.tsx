import React, { createContext, useCallback, useContext, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
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
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

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

// ---------------- TextField ----------------
export function TextField({
  label,
  error,
  testID,
  ...props
}: TextInputProps & { label?: string; error?: string; testID?: string }) {
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
}: {
  icon?: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <View style={styles.empty}>
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

  return (
    <ToastCtx.Provider value={{ show }}>
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
  right,
  subtitle,
  topInset = 0,
}: {
  title: string;
  onBack?: () => void;
  right?: React.ReactNode;
  subtitle?: string;
  topInset?: number;
}) {
  return (
    <BlurView intensity={40} tint="dark" style={[styles.header, { paddingTop: topInset + spacing.sm }]}>
      <View style={styles.headerRow}>
        {onBack ? (
          <Pressable testID="header-back" onPress={onBack} style={styles.iconBtn} hitSlop={10}>
            <Ionicons name="chevron-back" size={24} color={colors.onSurface} />
          </Pressable>
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

const styles = StyleSheet.create({
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
});
