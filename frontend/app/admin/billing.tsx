import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { useAuth } from "@/src/context/AuthContext";
import { Button, GlassHeader, useToast } from "@/src/components/ui";
import { goBackOr } from "@/src/navigation/back";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

type Status = {
  plan: string;
  plan_name: string;
  price: number;
  days_left: number | null;
  locked: boolean;
  expires_at: string | null;
  limits: Record<string, number | null>;
  usage: Record<string, number>;
};

const PLAN_CARDS = [
  {
    key: "standard",
    name: "Standard",
    price: "₹499",
    features: ["20 galleries", "30 Google Drive galleries", "10 albums", "5 GB storage", "500 clients"],
  },
  {
    key: "pro",
    name: "Pro",
    price: "₹999",
    features: ["50 galleries", "100 Google Drive galleries", "50 albums", "15 GB storage", "Unlimited clients"],
  },
];

function fmtBytes(n: number): string {
  if (!n) return "0 MB";
  const gb = n / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(gb >= 10 ? 0 : 1)} GB`;
  return `${Math.max(1, Math.round(n / 1024 ** 2))} MB`;
}

function fmtLimit(n: number | null, isBytes = false): string {
  if (n == null) return "Unlimited";
  return isBytes ? fmtBytes(n) : String(n);
}

function UsageBar({ label, used, limit, isBytes }: { label: string; used: number; limit: number | null; isBytes?: boolean }) {
  const pct = limit == null ? 0 : Math.min(100, Math.round((used / limit) * 100));
  const near = limit != null && pct >= 85;
  return (
    <View style={styles.usageRow}>
      <View style={styles.usageHead}>
        <Text style={styles.usageLabel}>{label}</Text>
        <Text style={styles.usageValue}>
          {isBytes ? fmtBytes(used) : used} / {fmtLimit(limit, isBytes)}
        </Text>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${limit == null ? 4 : pct}%`, backgroundColor: near ? colors.warning : colors.brand }]} />
      </View>
    </View>
  );
}

export default function Billing() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { refresh } = useAuth();

  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const s = await api.get("/billing/status");
      setStatus(s);
    } catch {
      toast.show("Could not load your plan", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const subscribe = async (plan: string) => {
    setBusyPlan(plan);
    try {
      const order = await api.post("/payments/create-order", { plan });
      if (order.mock) {
        // Mock flow (no live Razorpay keys yet): activate server-side.
        await api.post("/payments/mock-complete", { order_id: order.order_id });
      } else {
        // Live flow: open Razorpay Checkout, then call /payments/verify.
        // (Wired once real keys are added.)
        toast.show("Live payments not enabled yet", "info");
        setBusyPlan(null);
        return;
      }
      await refresh();
      await load();
      toast.show(`You're now on the ${plan === "pro" ? "Pro" : "Standard"} plan`, "success");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Payment could not be completed", "error");
    } finally {
      setBusyPlan(null);
    }
  };

  const isTrial = status?.plan === "trial";
  const planColor = status?.locked ? colors.error : isTrial ? colors.warning : colors.brand;

  return (
    <View style={styles.container} testID="billing-screen">
      <GlassHeader title="Plan & Billing" onBack={() => goBackOr(router, "/admin")} topInset={insets.top} />
      {loading || !status ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing["3xl"] }}>
          {/* Current plan */}
          <View style={[styles.planCard, { borderColor: planColor }]} testID="current-plan-card">
            <View style={styles.planTop}>
              <View>
                <Text style={styles.planEyebrow}>Current plan</Text>
                <Text style={styles.planName}>{status.plan_name}</Text>
              </View>
              <View style={[styles.planBadge, { backgroundColor: planColor }]}>
                <Text style={styles.planBadgeText}>{status.locked ? "Expired" : "Active"}</Text>
              </View>
            </View>
            {status.days_left != null && (
              <Text style={[styles.planMeta, status.locked && { color: colors.onError }]}>
                {status.locked
                  ? "Your access has ended. Subscribe below to restore your galleries."
                  : isTrial
                  ? `Trial ends in ${status.days_left} day${status.days_left === 1 ? "" : "s"}`
                  : `Renews in ${status.days_left} day${status.days_left === 1 ? "" : "s"}`}
              </Text>
            )}
          </View>

          {/* Usage */}
          <Text style={styles.sectionTitle}>Your usage</Text>
          <View style={styles.usageCard}>
            <UsageBar label="Upload galleries" used={status.usage.galleries_created} limit={status.limits.galleries} />
            <UsageBar label="Google Drive galleries" used={status.usage.gdrive_created} limit={status.limits.gdrive_galleries} />
            <UsageBar label="Albums" used={status.usage.albums_created} limit={status.limits.albums} />
            <UsageBar label="Images" used={status.usage.images_uploaded} limit={status.limits.images} />
            <UsageBar label="Storage" used={status.usage.storage_bytes} limit={status.limits.storage_bytes} isBytes />
            <UsageBar label="Clients" used={status.usage.clients} limit={status.limits.clients} />
          </View>

          {/* Upgrade options */}
          <Text style={styles.sectionTitle}>{isTrial || status.locked ? "Choose a plan" : "Change plan"}</Text>
          {PLAN_CARDS.map((p) => {
            const current = status.plan === p.key;
            return (
              <View key={p.key} style={[styles.upgradeCard, current && styles.upgradeCardCurrent]} testID={`plan-card-${p.key}`}>
                <View style={styles.upgradeHead}>
                  <Text style={styles.upgradeName}>{p.name}</Text>
                  <Text style={styles.upgradePrice}>
                    {p.price}
                    <Text style={styles.upgradePer}> /mo</Text>
                  </Text>
                </View>
                {p.features.map((f) => (
                  <View key={f} style={styles.featureRow}>
                    <Ionicons name="checkmark-circle" size={16} color={colors.brand} />
                    <Text style={styles.featureText}>{f}</Text>
                  </View>
                ))}
                <Button
                  testID={`subscribe-${p.key}`}
                  title={current ? "Current plan" : `Subscribe to ${p.name}`}
                  icon={current ? "checkmark" : "card-outline"}
                  variant={current ? "secondary" : "primary"}
                  disabled={current}
                  loading={busyPlan === p.key}
                  onPress={() => subscribe(p.key)}
                  style={{ marginTop: spacing.md }}
                />
              </View>
            );
          })}

          <Text style={styles.disclaimer}>
            Payments are in test mode. Real card payments activate once Razorpay keys are added.
          </Text>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  planCard: { borderWidth: 1.5, borderRadius: radius.lg, padding: spacing.lg, backgroundColor: colors.surfaceSecondary },
  planTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  planEyebrow: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, textTransform: "uppercase", letterSpacing: 1 },
  planName: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], marginTop: 2 },
  planBadge: { paddingHorizontal: spacing.md, paddingVertical: 4, borderRadius: radius.pill },
  planBadgeText: { color: colors.onBrand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  planMeta: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: spacing.md },
  sectionTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing["2xl"], marginBottom: spacing.md },
  usageCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.lg, gap: spacing.lg },
  usageRow: { gap: spacing.sm },
  usageHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  usageLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base },
  usageValue: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm },
  track: { height: 6, borderRadius: radius.pill, backgroundColor: colors.surfaceTertiary, overflow: "hidden" },
  fill: { height: 6, borderRadius: radius.pill },
  upgradeCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.lg, marginBottom: spacing.md },
  upgradeCardCurrent: { borderColor: colors.brand },
  upgradeHead: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", marginBottom: spacing.md },
  upgradeName: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  upgradePrice: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  upgradePer: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base },
  featureRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.xs },
  featureText: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base },
  disclaimer: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, textAlign: "center", marginTop: spacing.lg, lineHeight: 18 },
});
