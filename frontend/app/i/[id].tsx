import { useEffect, useState } from "react";
import { useLocalSearchParams } from "expo-router";
import Head from "expo-router/head";
import {
  ActivityIndicator,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { api } from "@/src/api/client";
import { formatINR } from "@/src/utils/format";

const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

// Standalone light theme for the public-facing invoice (no app chrome).
const c = {
  bg: "#F3EFE8",
  card: "#FFFFFF",
  ink: "#1A1A1A",
  sub: "#6B6459",
  brand: "#E2623C",
  brandSoft: "#F6E5DC",
  line: "#E6E0D6",
};

export default function PublicInvoice() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [inv, setInv] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/public/invoices/${id}`);
        setInv(res);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  if (loading) {
    return (
      <View style={[styles.screen, styles.center]}>
        <ActivityIndicator color={c.brand} />
      </View>
    );
  }

  if (error || !inv) {
    return (
      <View style={[styles.screen, styles.center]}>
        <Ionicons name="document-outline" size={48} color={c.sub} />
        <Text style={styles.notFound}>Invoice not available</Text>
        <Text style={styles.notFoundSub}>This link may have been disabled by the studio.</Text>
      </View>
    );
  }

  const gm = inv.gst_mode;
  const studio = inv.studio || {};
  const client = inv.client || {};

  return (
    <View style={styles.screen}>
      <Head><title>{`Invoice ${inv.invoice_number}`}</title></Head>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.card}>
          <View style={styles.head}>
            <View style={{ flex: 1 }}>
              <Text style={styles.studio}>{studio.name || "Studio"}</Text>
              {!!studio.address && <Text style={styles.small}>{studio.address}</Text>}
              {!!studio.gstin && <Text style={styles.small}>GSTIN: {studio.gstin}</Text>}
              {!!studio.phone && <Text style={styles.small}>{studio.phone}</Text>}
            </View>
            <View style={{ alignItems: "flex-end" }}>
              <Text style={styles.taxInvoice}>TAX INVOICE</Text>
              <Text style={styles.invNo}>{inv.invoice_number}</Text>
              <Text style={styles.small}>{inv.issue_date}</Text>
              <View style={styles.badge}><Text style={styles.badgeText}>{String(inv.status || "").toUpperCase()}</Text></View>
            </View>
          </View>

          <View style={styles.billTo}>
            <Text style={styles.label}>BILL TO</Text>
            <Text style={styles.clientName}>{client.name || "-"}</Text>
            {!!client.address && <Text style={styles.small}>{client.address}</Text>}
            {!!client.state && <Text style={styles.small}>State: {client.state}</Text>}
            {!!client.gstin && <Text style={styles.small}>GSTIN: {client.gstin}</Text>}
          </View>

          {/* items */}
          <View style={styles.itemsHead}>
            <Text style={[styles.ih, { flex: 3 }]}>Item</Text>
            <Text style={[styles.ih, styles.right, { flex: 1 }]}>Qty</Text>
            <Text style={[styles.ih, styles.right, { flex: 1.4 }]}>Amount</Text>
          </View>
          {(inv.line_items || []).map((li: any, i: number) => (
            <View key={i} style={styles.itemRow}>
              <View style={{ flex: 3 }}>
                <Text style={styles.itemDesc}>{li.description}</Text>
                <Text style={styles.itemMeta}>{li.hsn_sac ? `HSN ${li.hsn_sac}` : ""}{gm !== "none" ? `  ·  GST ${li.gst_rate}%` : ""}</Text>
              </View>
              <Text style={[styles.itemCell, styles.right, { flex: 1 }]}>{li.qty}</Text>
              <Text style={[styles.itemCell, styles.right, { flex: 1.4 }]}>{formatINR((li.amount || 0) + (li.tax || 0))}</Text>
            </View>
          ))}

          <View style={styles.totals}>
            <SumRow label="Taxable value" value={formatINR(inv.taxable_total)} />
            {gm === "cgst_sgst" && (<><SumRow label="CGST" value={formatINR(inv.cgst_total)} /><SumRow label="SGST" value={formatINR(inv.sgst_total)} /></>)}
            {gm === "igst" && <SumRow label="IGST" value={formatINR(inv.igst_total)} />}
            {!!inv.round_off && <SumRow label="Round off" value={formatINR(inv.round_off)} />}
            <View style={styles.grandRow}>
              <Text style={styles.grandLabel}>Total</Text>
              <Text style={styles.grandValue}>{formatINR(inv.total)}</Text>
            </View>
            {inv.amount_received > 0 && (
              <>
                <SumRow label="Received" value={formatINR(inv.amount_received)} />
                <SumRow label="Balance due" value={formatINR(inv.balance_due)} strong />
              </>
            )}
          </View>

          {!!inv.amount_in_words && <Text style={styles.words}>{inv.amount_in_words}</Text>}
          {!!inv.notes && <Text style={styles.note}>{inv.notes}</Text>}
          {!!inv.terms && <Text style={styles.terms}>{inv.terms}</Text>}

          <Pressable style={styles.dlBtn} onPress={() => Linking.openURL(`${BASE}/public/invoices/${id}/pdf`)}>
            <Ionicons name="download-outline" size={18} color="#fff" />
            <Text style={styles.dlText}>Download PDF</Text>
          </Pressable>
          <Text style={styles.powered}>Powered by PIK Connect</Text>
        </View>
      </ScrollView>
    </View>
  );
}

function SumRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <View style={styles.sumRow}>
      <Text style={[styles.sumLabel, strong && { color: c.ink, fontWeight: "700" }]}>{label}</Text>
      <Text style={[styles.sumValue, strong && { color: c.ink, fontWeight: "700" }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: c.bg },
  center: { alignItems: "center", justifyContent: "center", padding: 24 },
  notFound: { color: c.ink, fontSize: 20, fontWeight: "700", marginTop: 12 },
  notFoundSub: { color: c.sub, fontSize: 14, marginTop: 6, textAlign: "center" },
  scroll: { padding: 16, alignItems: "center" },
  card: { width: "100%", maxWidth: 640, backgroundColor: c.card, borderRadius: 16, padding: 24, borderWidth: 1, borderColor: c.line },
  head: { flexDirection: "row", gap: 16, marginBottom: 20 },
  studio: { color: c.ink, fontSize: 22, fontWeight: "800" },
  small: { color: c.sub, fontSize: 13, marginTop: 2 },
  taxInvoice: { color: c.brand, fontSize: 16, fontWeight: "800", letterSpacing: 1 },
  invNo: { color: c.ink, fontSize: 15, fontWeight: "700", marginTop: 4 },
  badge: { backgroundColor: c.brandSoft, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3, marginTop: 6 },
  badgeText: { color: c.brand, fontSize: 11, fontWeight: "800" },
  billTo: { borderTopWidth: 1, borderTopColor: c.line, paddingTop: 16, marginBottom: 16 },
  label: { color: c.sub, fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  clientName: { color: c.ink, fontSize: 18, fontWeight: "700", marginTop: 4 },
  itemsHead: { flexDirection: "row", backgroundColor: c.brand, borderRadius: 8, paddingVertical: 8, paddingHorizontal: 10 },
  ih: { color: "#fff", fontSize: 12, fontWeight: "700" },
  right: { textAlign: "right" },
  itemRow: { flexDirection: "row", alignItems: "flex-start", paddingVertical: 10, paddingHorizontal: 10, borderBottomWidth: 1, borderBottomColor: c.line },
  itemDesc: { color: c.ink, fontSize: 14, fontWeight: "600" },
  itemMeta: { color: c.sub, fontSize: 12, marginTop: 2 },
  itemCell: { color: c.ink, fontSize: 14 },
  totals: { marginTop: 16 },
  sumRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  sumLabel: { color: c.sub, fontSize: 14 },
  sumValue: { color: c.ink, fontSize: 14 },
  grandRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 8, paddingTop: 8, borderTopWidth: 2, borderTopColor: c.brand },
  grandLabel: { color: c.ink, fontSize: 18, fontWeight: "800" },
  grandValue: { color: c.brand, fontSize: 22, fontWeight: "800" },
  words: { color: c.sub, fontSize: 13, fontStyle: "italic", marginTop: 12 },
  note: { color: c.ink, fontSize: 13, marginTop: 12 },
  terms: { color: c.sub, fontSize: 13, marginTop: 8 },
  dlBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, backgroundColor: c.brand, borderRadius: 12, paddingVertical: 14, marginTop: 24 },
  dlText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  powered: { color: c.sub, fontSize: 12, textAlign: "center", marginTop: 16 },
});
