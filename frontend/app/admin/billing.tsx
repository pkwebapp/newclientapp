import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
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

type MockOrder = {
  order_id: string;
  amount: number;
  currency: string;
  plan: "standard" | "pro";
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
  const [pendingOrder, setPendingOrder] = useState<MockOrder | null>(null);
  const [checkoutBusy, setCheckoutBusy] = useState(false);

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
        // MOCKED Razorpay checkout: create the order first, then wait for the
        // photographer to confirm payment in the test checkout below.
        setPendingOrder(order);
      } else {
        // Live flow: open Razorpay Checkout, then call /payments/verify.
        // (Wired once real keys are added.)
        toast.show("Live payments not enabled yet", "info");
      }
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Payment could not be started", "error");
    } finally {
      setBusyPlan(null);
    }
  };

  const completeMockPayment = async () => {
    if (!pendingOrder) return;
    setCheckoutBusy(true);
    try {
      await api.post("/payments/mock-complete", { order_id: pendingOrder.order_id });
      const planName = pendingOrder.plan === "pro" ? "Pro" : "Standard";
      setPendingOrder(null);
      await refresh();
      await load();
      toast.show(`You're now on the ${planName} plan`, "success");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Payment could not be completed", "error");
    } finally {
      setCheckoutBusy(false);
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

      <Modal
        visible={!!pendingOrder}
        transparent
        animationType="slide"
        onRequestClose={() => !checkoutBusy && setPendingOrder(null)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.checkoutCard} testID="mock-razorpay-modal">
            <View style={styles.checkoutHeader}>
              <View style={styles.razorpayMark}>
                <Text style={styles.razorpayMarkText}>R</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.checkoutBrand}>RAZORPAY</Text>
                <Text style={styles.checkoutMerchant}>PIK Connect</Text>
              </View>
              <View style={styles.testBadge}>
                <Text style={styles.testBadgeText}>MOCK TEST</Text>
              </View>
            </View>

            <Text style={styles.checkoutTitle}>Complete your subscription</Text>
            <Text style={styles.checkoutSub}>Secure test checkout for your {pendingOrder?.plan === "pro" ? "Pro" : "Standard"} plan.</Text>

            <View style={styles.orderSummary}>
              <View>
                <Text style={styles.orderLabel}>Amount to pay</Text>
                <Text style={styles.orderPlan}>{pendingOrder?.plan === "pro" ? "Pro" : "Standard"} monthly plan</Text>
              </View>
              <Text style={styles.orderAmount}>₹{pendingOrder ? Math.round(pendingOrder.amount / 100).toLocaleString("en-IN") : "0"}</Text>
            </View>

            <Text style={styles.simulatedLabel}>Card details · simulated</Text>
            <View style={styles.mockField}>
              <Text style={styles.mockFieldLabel}>Card number</Text>
              <Text style={styles.mockFieldValue}>4242 4242 4242 4242</Text>
            </View>
            <View style={styles.mockFieldRow}>
              <View style={[styles.mockField, { flex: 1 }]}>
                <Text style={styles.mockFieldLabel}>Expiry</Text>
                <Text style={styles.mockFieldValue}>12 / 30</Text>
              </View>
              <View style={[styles.mockField, { flex: 1 }]}>
                <Text style={styles.mockFieldLabel}>CVV</Text>
                <Text style={styles.mockFieldValue}>123</Text>
              </View>
            </View>

            <Text style={styles.mockDisclaimer}>MOCKED: No real card is charged. Your plan activates only after you confirm this test payment.</Text>
            <Button
              testID="mock-razorpay-pay-btn"
              title={checkoutBusy ? "Processing…" : `Pay ₹${pendingOrder ? Math.round(pendingOrder.amount / 100).toLocaleString("en-IN") : "0"}`}
              icon="lock-closed-outline"
              loading={checkoutBusy}
              onPress={completeMockPayment}
            />
            <Pressable
              testID="mock-razorpay-cancel-btn"
              disabled={checkoutBusy}
              onPress={() => setPendingOrder(null)}
              style={styles.cancelCheckout}
            >
              <Text style={styles.cancelCheckoutText}>Cancel</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
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
  modalOverlay: { flex: 1, backgroundColor: "rgba(8, 10, 14, 0.78)", justifyContent: "flex-end" },
  checkoutCard: { width: "100%", maxWidth: 520, alignSelf: "center", backgroundColor: colors.surface, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: spacing.xl, paddingBottom: spacing["2xl"] },
  checkoutHeader: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginBottom: spacing.xl },
  razorpayMark: { width: 38, height: 38, borderRadius: radius.sm, backgroundColor: "#2B6EF3", alignItems: "center", justifyContent: "center" },
  razorpayMarkText: { color: "#FFFFFF", fontSize: 22, fontWeight: "800" },
  checkoutBrand: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "800", letterSpacing: 1.5 },
  checkoutMerchant: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  testBadge: { backgroundColor: colors.brandTertiary, borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: 5 },
  testBadgeText: { color: colors.onBrandTertiary, fontFamily: fonts.text, fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
  checkoutTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  checkoutSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: spacing.xs, marginBottom: spacing.xl },
  orderSummary: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.xl },
  orderLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  orderPlan: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600", marginTop: 4 },
  orderAmount: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], fontWeight: "700" },
  simulatedLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700", marginBottom: spacing.sm },
  mockFieldRow: { flexDirection: "row", gap: spacing.md, marginTop: spacing.md },
  mockField: { backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md },
  mockFieldLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 },
  mockFieldValue: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: 4 },
  mockDisclaimer: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginVertical: spacing.lg },
  cancelCheckout: { minHeight: 44, alignItems: "center", justifyContent: "center", marginTop: spacing.sm },
  cancelCheckoutText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
});
