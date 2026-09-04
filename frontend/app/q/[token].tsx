import { useEffect, useState } from "react";
import { useLocalSearchParams } from "expo-router";
import Head from "expo-router/head";
import {
  ActivityIndicator,
  Image,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { api } from "@/src/api/client";
import RichHtml from "@/src/components/RichHtml";
import { paperPalette } from "@/src/components/paper-theme";
import { plainToHtml } from "@/src/utils/richtext";
import { formatINR } from "@/src/utils/format";

const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

// Standalone light "letterhead" theme for the public-facing quotation (no app chrome).
const c = {
  bg: "#F3EFE8",
  card: "#FFFFFF",
  ink: "#1A1A1A",
  sub: "#6B6459",
  brand: "#E2623C",
  brandSoft: "#F6E5DC",
  line: "#E6E0D6",
  success: "#2E7D4F",
  successSoft: "#E3F3EA",
  warn: "#B7791F",
  warnSoft: "#FBF1DD",
};

export default function PublicQuotation() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const [q, setQ] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [note, setNote] = useState("");
  const [noteErr, setNoteErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/public/quotations/${token}`);
        setQ(res);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const respond = async (action: "accept" | "revision") => {
    if (action === "revision" && !note.trim()) {
      setNoteErr("Please tell the studio what you'd like changed.");
      return;
    }
    setBusy(true);
    try {
      const res = await api.post(`/public/quotations/${token}/respond`, { action, note: action === "revision" ? note.trim() : "" });
      setQ((prev: any) => ({ ...prev, status: res.status, client_response: res.client_response }));
      setRevisionOpen(false);
    } catch {
      setNoteErr("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <View style={[styles.screen, styles.center]}>
        <ActivityIndicator color={c.brand} />
      </View>
    );
  }

  if (error || !q) {
    return (
      <View style={[styles.screen, styles.center]}>
        <Ionicons name="document-outline" size={48} color={c.sub} />
        <Text style={styles.notFound}>Quotation not available</Text>
        <Text style={styles.notFoundSub}>This link may have been disabled by the studio.</Text>
      </View>
    );
  }

  const studio = q.studio || {};
  const client = q.client || {};
  const gm = q.gst_mode || "none";
  const showPricing = !!q.show_pricing && (q.line_items || []).length > 0;
  const resp = q.client_response;
  const canRespond = q.status === "sent" || q.status === "draft";
  const hasLogo = typeof studio.logo_base64 === "string" && studio.logo_base64.startsWith("data:image");
  const contactBits = [studio.address, studio.phone ? `Ph: ${studio.phone}` : "", studio.email, studio.website, studio.gstin ? `GSTIN: ${studio.gstin}` : ""].filter(Boolean);

  return (
    <View style={styles.screen}>
      <Head><title>{`Quotation ${q.quotation_number}`}</title></Head>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.card} testID="public-quotation-card">
          {/* Letterhead */}
          <View style={styles.letterhead}>
            {hasLogo && <Image source={{ uri: studio.logo_base64 }} style={styles.logo} resizeMode="contain" />}
            <View style={{ flex: 1 }}>
              <Text style={styles.studio}>{studio.name || "Studio"}</Text>
              {contactBits.length > 0 && <Text style={styles.contact}>{contactBits.join("  ·  ")}</Text>}
            </View>
          </View>
          <View style={styles.rule} />

          {/* Title row */}
          <View style={styles.head}>
            <View>
              <Text style={styles.qTitle}>QUOTATION</Text>
              <View style={[styles.badge, q.status === "accepted" && { backgroundColor: c.successSoft }, q.status === "revision_requested" && { backgroundColor: c.warnSoft }]}>
                <Text style={[styles.badgeText, q.status === "accepted" && { color: c.success }, q.status === "revision_requested" && { color: c.warn }]}>
                  {String(q.status || "").replace("_", " ").toUpperCase()}
                </Text>
              </View>
            </View>
            <View style={{ alignItems: "flex-end" }}>
              <Text style={styles.qNo}>{q.quotation_number}</Text>
              <Text style={styles.small}>Date: {q.issue_date}</Text>
              {!!q.valid_until && <Text style={styles.small}>Valid until: {q.valid_until}</Text>}
            </View>
          </View>

          {/* Prepared for */}
          <View style={styles.party}>
            <Text style={styles.label}>PREPARED FOR</Text>
            <Text style={styles.clientName}>{client.name || "-"}</Text>
            {!!client.address && <Text style={styles.small}>{client.address}</Text>}
            {!!client.gstin && <Text style={styles.small}>GSTIN: {client.gstin}</Text>}
            {!!client.phone && <Text style={styles.small}>Ph: {client.phone}</Text>}
            {!!client.email && <Text style={styles.small}>{client.email}</Text>}
          </View>

          {/* Content */}
          {!!q.subject && <Text style={styles.subject}>{q.subject}</Text>}
          {!!q.body && (
            <View style={{ marginTop: 10 }}>
              <RichHtml html={q.body_html || plainToHtml(q.body)} palette={paperPalette} fontSize={14} lineHeight={22} testID="public-quotation-body" />
            </View>
          )}

          {/* Pricing */}
          {showPricing && (
            <View style={{ marginTop: 16 }}>
              <View style={styles.itemsHead}>
                <Text style={[styles.ih, { flex: 3 }]}>Description</Text>
                <Text style={[styles.ih, styles.right, { flex: 1 }]}>Qty</Text>
                <Text style={[styles.ih, styles.right, { flex: 1.4 }]}>Amount</Text>
              </View>
              {q.line_items.map((li: any, i: number) => (
                <View key={i} style={styles.itemRow}>
                  <View style={{ flex: 3 }}>
                    <Text style={styles.itemDesc}>{li.description}</Text>
                    <Text style={styles.itemMeta}>{formatINR(li.rate)} each{gm !== "none" ? `  ·  GST ${li.gst_rate}%` : ""}</Text>
                  </View>
                  <Text style={[styles.itemCell, styles.right, { flex: 1 }]}>{li.qty}</Text>
                  <Text style={[styles.itemCell, styles.right, { flex: 1.4 }]}>{formatINR(li.amount || 0)}</Text>
                </View>
              ))}
              <View style={styles.totals}>
                {!!q.discount_amount && <SumRow label="Discount" value={`- ${formatINR(q.discount_amount)}`} />}
                <SumRow label="Sub total" value={formatINR(q.taxable_total || 0)} />
                {gm === "cgst_sgst" && (<><SumRow label="CGST" value={formatINR(q.cgst_total || 0)} /><SumRow label="SGST" value={formatINR(q.sgst_total || 0)} /></>)}
                {gm === "igst" && <SumRow label="IGST" value={formatINR(q.igst_total || 0)} />}
                <View style={styles.grandRow}>
                  <Text style={styles.grandLabel}>Estimated Total</Text>
                  <Text style={styles.grandValue}>{formatINR(q.total || 0)}</Text>
                </View>
                {!!q.amount_in_words && <Text style={styles.words}>{q.amount_in_words}</Text>}
              </View>
            </View>
          )}

          {!!q.terms && (<><Text style={[styles.label, { marginTop: 20 }]}>TERMS &amp; CONDITIONS</Text><Text style={styles.terms}>{q.terms}</Text></>)}
          {!!q.notes && (<><Text style={[styles.label, { marginTop: 14 }]}>NOTES</Text><Text style={styles.terms}>{q.notes}</Text></>)}

          {/* Response state */}
          {!!resp && (
            <View style={[styles.respBox, resp.action === "accept" ? { backgroundColor: c.successSoft } : { backgroundColor: c.warnSoft }]} testID="public-response-box">
              <Ionicons name={resp.action === "accept" ? "checkmark-circle" : "chatbubble-ellipses"} size={20} color={resp.action === "accept" ? c.success : c.warn} />
              <View style={{ flex: 1 }}>
                <Text style={[styles.respTitle, { color: resp.action === "accept" ? c.success : c.warn }]}>
                  {resp.action === "accept" ? "You accepted this quotation" : "Revision requested"}
                </Text>
                <Text style={styles.respSub}>
                  {resp.action === "accept" ? "The studio has been notified and will be in touch shortly." : "The studio has been notified and will send an updated quotation."}
                </Text>
                {!!resp.note && <Text style={styles.respNote}>“{resp.note}”</Text>}
              </View>
            </View>
          )}

          {/* Actions */}
          {canRespond && !revisionOpen && (
            <View style={styles.actionRow}>
              <Pressable testID="accept-quotation" disabled={busy} style={[styles.btn, styles.btnAccept]} onPress={() => respond("accept")}>
                {busy ? <ActivityIndicator color="#fff" /> : <Ionicons name="checkmark-circle-outline" size={18} color="#fff" />}
                <Text style={styles.btnText}>Accept quotation</Text>
              </Pressable>
              <Pressable testID="request-revision" disabled={busy} style={[styles.btn, styles.btnOutline]} onPress={() => { setNoteErr(""); setRevisionOpen(true); }}>
                <Ionicons name="create-outline" size={18} color={c.brand} />
                <Text style={[styles.btnText, { color: c.brand }]}>Request changes</Text>
              </Pressable>
            </View>
          )}

          {canRespond && revisionOpen && (
            <View style={styles.revisionBox} testID="revision-box">
              <Text style={styles.revisionTitle}>What would you like changed?</Text>
              <TextInput
                testID="revision-note"
                value={note}
                onChangeText={(t) => { setNote(t); if (noteErr) setNoteErr(""); }}
                placeholder="e.g. Please include a pre-wedding shoot and adjust the total…"
                placeholderTextColor="#9A938A"
                multiline
                style={styles.noteInput}
              />
              {!!noteErr && <Text style={styles.noteErr}>{noteErr}</Text>}
              <View style={styles.actionRow}>
                <Pressable testID="send-revision" disabled={busy} style={[styles.btn, styles.btnAccept]} onPress={() => respond("revision")}>
                  {busy ? <ActivityIndicator color="#fff" /> : <Ionicons name="send-outline" size={18} color="#fff" />}
                  <Text style={styles.btnText}>Send request</Text>
                </Pressable>
                <Pressable disabled={busy} style={[styles.btn, styles.btnOutline]} onPress={() => setRevisionOpen(false)}>
                  <Text style={[styles.btnText, { color: c.sub }]}>Cancel</Text>
                </Pressable>
              </View>
            </View>
          )}

          <Pressable testID="download-quotation-pdf" style={styles.dlBtn} onPress={() => Linking.openURL(`${BASE}/public/quotations/${token}/pdf`)}>
            <Ionicons name="download-outline" size={18} color={c.ink} />
            <Text style={styles.dlText}>Download PDF</Text>
          </Pressable>
          <Pressable onPress={() => Linking.openURL("https://www.pikconnect.com")}>
            <Text style={styles.powered}>Powered by www.pikconnect.com</Text>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}

function SumRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.sumRow}>
      <Text style={styles.sumLabel}>{label}</Text>
      <Text style={styles.sumValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: c.bg },
  center: { alignItems: "center", justifyContent: "center", padding: 24 },
  notFound: { color: c.ink, fontSize: 20, fontWeight: "700", marginTop: 12 },
  notFoundSub: { color: c.sub, fontSize: 14, marginTop: 6, textAlign: "center" },
  scroll: { padding: 16, alignItems: "center" },
  card: { width: "100%", maxWidth: 680, backgroundColor: c.card, borderRadius: 16, padding: 24, borderWidth: 1, borderColor: c.line },
  letterhead: { flexDirection: "row", alignItems: "center", gap: 16 },
  logo: { width: 64, height: 64, borderRadius: 8 },
  studio: { color: c.ink, fontSize: 22, fontWeight: "800", letterSpacing: 0.3 },
  contact: { color: c.sub, fontSize: 12, marginTop: 4, lineHeight: 18 },
  rule: { height: 3, backgroundColor: c.brand, marginTop: 14, marginBottom: 14, borderRadius: 2 },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 16 },
  qTitle: { color: c.brand, fontSize: 20, fontWeight: "800", letterSpacing: 3 },
  qNo: { color: c.ink, fontSize: 15, fontWeight: "700" },
  small: { color: c.sub, fontSize: 13, marginTop: 2 },
  badge: { alignSelf: "flex-start", backgroundColor: c.brandSoft, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3, marginTop: 6 },
  badgeText: { color: c.brand, fontSize: 11, fontWeight: "800" },
  party: { borderTopWidth: 1, borderTopColor: c.line, paddingTop: 16, marginTop: 16 },
  label: { color: c.sub, fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  clientName: { color: c.ink, fontSize: 18, fontWeight: "700", marginTop: 4 },
  subject: { color: c.ink, fontSize: 18, fontWeight: "800", marginTop: 20 },
  itemsHead: { flexDirection: "row", backgroundColor: c.brand, borderRadius: 8, paddingVertical: 8, paddingHorizontal: 10 },
  ih: { color: "#fff", fontSize: 12, fontWeight: "700" },
  right: { textAlign: "right" },
  itemRow: { flexDirection: "row", alignItems: "flex-start", paddingVertical: 10, paddingHorizontal: 10, borderBottomWidth: 1, borderBottomColor: c.line },
  itemDesc: { color: c.ink, fontSize: 14, fontWeight: "600" },
  itemMeta: { color: c.sub, fontSize: 12, marginTop: 2 },
  itemCell: { color: c.ink, fontSize: 14 },
  totals: { marginTop: 12 },
  sumRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 3 },
  sumLabel: { color: c.sub, fontSize: 14 },
  sumValue: { color: c.ink, fontSize: 14 },
  grandRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 8, paddingTop: 8, borderTopWidth: 2, borderTopColor: c.brand },
  grandLabel: { color: c.ink, fontSize: 18, fontWeight: "800" },
  grandValue: { color: c.brand, fontSize: 22, fontWeight: "800" },
  words: { color: c.sub, fontSize: 13, fontStyle: "italic", marginTop: 8 },
  terms: { color: c.sub, fontSize: 13, lineHeight: 20, marginTop: 4 },
  respBox: { flexDirection: "row", gap: 12, alignItems: "flex-start", borderRadius: 12, padding: 14, marginTop: 20 },
  respTitle: { fontSize: 15, fontWeight: "800" },
  respSub: { color: c.sub, fontSize: 13, marginTop: 2 },
  respNote: { color: c.ink, fontSize: 13, fontStyle: "italic", marginTop: 6 },
  actionRow: { flexDirection: "row", gap: 10, marginTop: 20, flexWrap: "wrap" },
  btn: { flex: 1, minWidth: 160, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, borderRadius: 12, paddingVertical: 14, paddingHorizontal: 12, minHeight: 48 },
  btnAccept: { backgroundColor: c.brand },
  btnOutline: { backgroundColor: c.card, borderWidth: 1.5, borderColor: c.brand },
  btnText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  revisionBox: { marginTop: 20, backgroundColor: c.bg, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: c.line },
  revisionTitle: { color: c.ink, fontSize: 15, fontWeight: "700", marginBottom: 8 },
  noteInput: { minHeight: 100, backgroundColor: c.card, borderRadius: 10, borderWidth: 1, borderColor: c.line, padding: 12, color: c.ink, fontSize: 14, textAlignVertical: "top" },
  noteErr: { color: "#B42318", fontSize: 13, marginTop: 6 },
  dlBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, backgroundColor: c.bg, borderRadius: 12, paddingVertical: 14, marginTop: 14, borderWidth: 1, borderColor: c.line, minHeight: 48 },
  dlText: { color: c.ink, fontSize: 15, fontWeight: "700" },
  powered: { color: c.sub, fontSize: 12, textAlign: "center", marginTop: 16, letterSpacing: 0.4 },
});
