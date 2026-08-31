import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";

import { api } from "@/src/api/client";
import { Button, GlassHeader, Pill, TextField, useToast } from "@/src/components/ui";
import { STATUS_META, openInvoicePdf, Invoice } from "@/src/api/invoices";
import { formatINR } from "@/src/utils/format";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const METHODS = ["cash", "upi", "card", "bank"];

export default function InvoiceDetailScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [inv, setInv] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [payModal, setPayModal] = useState(false);
  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState("upi");

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/invoices/${id}`);
      setInv(res);
    } catch {
      toast.show("Could not load invoice", "error");
    } finally {
      setLoading(false);
    }
  }, [id, toast]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const downloadPdf = async () => {
    try {
      await openInvoicePdf(id, inv?.invoice_number);
    } catch {
      toast.show("Could not open PDF", "error");
    }
  };

  const share = async () => {
    setBusy(true);
    try {
      const res = await api.post(`/invoices/${id}/share`, { enabled: true });
      const url = res.share_url;
      if (url) {
        await Clipboard.setStringAsync(url);
        toast.show("Share link copied to clipboard", "success");
      }
      setInv(res);
    } catch {
      toast.show("Could not create share link", "error");
    } finally {
      setBusy(false);
    }
  };

  const recordPayment = async () => {
    const amt = Number(payAmount) || 0;
    if (amt <= 0) return toast.show("Enter an amount", "error");
    setBusy(true);
    try {
      const res = await api.post(`/invoices/${id}/payments`, { amount: amt, method: payMethod });
      setInv(res);
      setPayModal(false);
      setPayAmount("");
      toast.show("Payment recorded", "success");
    } catch {
      toast.show("Could not record payment", "error");
    } finally {
      setBusy(false);
    }
  };

  const cancelInvoice = async () => {
    setBusy(true);
    try {
      const res = await api.patch(`/invoices/${id}`, { status: "cancelled" });
      setInv(res);
      toast.show("Invoice cancelled", "success");
    } catch {
      toast.show("Could not cancel", "error");
    } finally {
      setBusy(false);
    }
  };

  if (loading || !inv) {
    return (
      <View style={styles.container}>
        <GlassHeader title="Invoice" topInset={insets.top} onBack={() => router.back()} />
        <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>
      </View>
    );
  }

  const meta = STATUS_META[inv.status] || STATUS_META.sent;
  const gm = inv.gst_mode;

  return (
    <View style={styles.container} testID="admin-invoice-detail-screen">
      <GlassHeader
        title={inv.invoice_number}
        topInset={insets.top}
        onBack={() => router.back()}
        right={
          inv.status !== "cancelled" ? (
            <Pressable testID="edit-invoice" onPress={() => router.push(`/admin/invoice/new?id=${id}`)} hitSlop={10}>
              <Ionicons name="create-outline" size={22} color={colors.brand} />
            </Pressable>
          ) : undefined
        }
      />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 40 }}>
        {/* status + amount */}
        <View style={styles.topCard}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Pill label={meta.label} tone={meta.tone} />
            <Text style={styles.issueDate}>{inv.issue_date}{inv.due_date ? `  ·  due ${inv.due_date}` : ""}</Text>
          </View>
          <Text style={styles.grandValue}>{formatINR(inv.total)}</Text>
          <View style={styles.balRow}>
            <Text style={styles.balText}>Received {formatINR(inv.amount_received)}</Text>
            <Text style={[styles.balText, { color: inv.balance_due > 0 ? colors.onWarning : colors.onSuccess }]}>Balance {formatINR(inv.balance_due)}</Text>
          </View>
        </View>

        {/* parties */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>BILL TO</Text>
          <Text style={styles.partyName}>{inv.client?.name || "Client"}</Text>
          {!!inv.client?.address && <Text style={styles.partyLine}>{inv.client.address}</Text>}
          {!!inv.client?.state && <Text style={styles.partyLine}>State: {inv.client.state}</Text>}
          {!!inv.client?.gstin && <Text style={styles.partyLine}>GSTIN: {inv.client.gstin}</Text>}
          {!!inv.client?.phone && <Text style={styles.partyLine}>{inv.client.phone}</Text>}
          {!!inv.event_name && <Text style={styles.linkedGallery}><Ionicons name="images-outline" size={12} color={colors.brand} /> Linked: {inv.event_name}</Text>}
        </View>

        {/* items */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>ITEMS</Text>
          {inv.line_items.map((li, i) => (
            <View key={i} style={styles.itemRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.itemDesc}>{li.description}</Text>
                <Text style={styles.itemMeta}>
                  {li.hsn_sac ? `HSN ${li.hsn_sac} · ` : ""}{li.qty} × {formatINR(li.rate)}{gm !== "none" ? ` · GST ${li.gst_rate}%` : ""}
                </Text>
              </View>
              <Text style={styles.itemAmount}>{formatINR((li.amount || 0) + (li.tax || 0))}</Text>
            </View>
          ))}
          <View style={styles.divider} />
          <Row label="Taxable value" value={formatINR(inv.taxable_total)} />
          {!!inv.discount_amount && <Row label="Discount" value={`- ${formatINR(inv.discount_amount)}`} />}
          {gm === "cgst_sgst" && (<><Row label="CGST" value={formatINR(inv.cgst_total)} /><Row label="SGST" value={formatINR(inv.sgst_total)} /></>)}
          {gm === "igst" && <Row label="IGST" value={formatINR(inv.igst_total)} />}
          {!!inv.round_off && <Row label="Round off" value={formatINR(inv.round_off)} />}
          <View style={styles.grandRow}>
            <Text style={styles.grandLabel}>Total</Text>
            <Text style={styles.grandTotal}>{formatINR(inv.total)}</Text>
          </View>
          {!!inv.amount_in_words && <Text style={styles.words}>{inv.amount_in_words}</Text>}
        </View>

        {/* payments */}
        <View style={styles.card}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.sm }}>
            <Text style={styles.cardLabel}>PAYMENTS</Text>
            {inv.status !== "cancelled" && inv.balance_due > 0 && (
              <Pressable testID="record-payment-btn" onPress={() => { setPayAmount(String(inv.balance_due)); setPayModal(true); }} hitSlop={8} style={styles.addPay}>
                <Ionicons name="add" size={16} color={colors.brand} />
                <Text style={styles.addPayText}>Record</Text>
              </Pressable>
            )}
          </View>
          {(inv.payments || []).length === 0 ? (
            <Text style={styles.partyLine}>No payments recorded yet.</Text>
          ) : (
            (inv.payments || []).map((p: any) => (
              <View key={p.payment_id} style={styles.payRow}>
                <Ionicons name="cash-outline" size={16} color={colors.onSuccess} />
                <Text style={styles.payText}>{formatINR(p.amount)} · {p.method} · {p.date}</Text>
              </View>
            ))
          )}
        </View>

        {/* actions */}
        <View style={styles.actions}>
          <Button testID="download-pdf" title="Download PDF" icon="download-outline" variant="secondary" onPress={downloadPdf} />
          <Button testID="share-invoice" title={inv.share_enabled ? "Copy share link" : "Create share link"} icon="link-outline" variant="secondary" loading={busy} onPress={share} />
          {inv.status !== "cancelled" && (
            <Button testID="cancel-invoice" title="Cancel invoice" icon="close-circle-outline" variant="danger" onPress={cancelInvoice} />
          )}
        </View>
        {!!inv.share_url && (
          <Pressable onPress={() => Clipboard.setStringAsync(inv.share_url!).then(() => toast.show("Copied", "success"))} style={styles.linkBox}>
            <Ionicons name="globe-outline" size={14} color={colors.brand} />
            <Text style={styles.linkText} numberOfLines={1}>{inv.share_url}</Text>
            <Ionicons name="copy-outline" size={14} color={colors.muted} />
          </Pressable>
        )}
      </ScrollView>

      {/* payment modal */}
      <Modal visible={payModal} transparent animationType="fade" onRequestClose={() => setPayModal(false)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setPayModal(false)}>
          <Pressable style={styles.modalCard} onPress={() => {}}>
            <Text style={styles.modalTitle}>Record payment</Text>
            <TextField label="Amount (₹)" value={payAmount} onChangeText={setPayAmount} keyboardType="numeric" testID="pay-amount" />
            <Text style={styles.fieldLabel}>Method</Text>
            <View style={styles.methodRow}>
              {METHODS.map((m) => (
                <Pressable key={m} onPress={() => setPayMethod(m)} style={[styles.methodBtn, payMethod === m && styles.methodBtnActive]}>
                  <Text style={[styles.methodText, payMethod === m && { color: colors.onBrand }]}>{m.toUpperCase()}</Text>
                </Pressable>
              ))}
            </View>
            <Button testID="confirm-payment" title="Save payment" loading={busy} onPress={recordPayment} style={{ marginTop: spacing.sm }} />
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.sumRow}>
      <Text style={styles.sumLabel}>{label}</Text>
      <Text style={styles.sumValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  topCard: { backgroundColor: colors.brandTertiary, borderRadius: radius.lg, padding: spacing.xl, borderWidth: 1, borderColor: colors.brand, marginBottom: spacing.lg },
  issueDate: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm },
  grandValue: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.hero, marginTop: spacing.md },
  balRow: { flexDirection: "row", justifyContent: "space-between", marginTop: spacing.sm },
  balText: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.lg },
  cardLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  partyName: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing.xs },
  partyLine: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: 2 },
  linkedGallery: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.sm },
  itemRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md, paddingVertical: spacing.sm, marginTop: spacing.sm },
  itemDesc: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  itemMeta: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  itemAmount: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: spacing.md },
  sumRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  sumLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base },
  sumValue: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  grandRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: spacing.sm, paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.borderStrong },
  grandLabel: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  grandTotal: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  words: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.sm, fontStyle: "italic" },
  addPay: { flexDirection: "row", alignItems: "center", gap: 2 },
  addPayText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  payRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingVertical: spacing.sm },
  payText: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base },
  actions: { gap: spacing.sm },
  linkBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border, marginTop: spacing.md },
  linkText: { flex: 1, color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm },
  modalBackdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.72)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  modalCard: { width: "100%", maxWidth: 460, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, padding: spacing.xl, borderWidth: 1, borderColor: colors.borderStrong },
  modalTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginBottom: spacing.lg },
  fieldLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600", marginBottom: spacing.sm },
  methodRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.sm },
  methodBtn: { flex: 1, backgroundColor: colors.surface, borderRadius: radius.sm, paddingVertical: spacing.sm, alignItems: "center", borderWidth: 1, borderColor: colors.border },
  methodBtnActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  methodText: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: 11, fontWeight: "700" },
});
