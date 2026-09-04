import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";

import { api } from "@/src/api/client";
import { Button, GlassHeader, Pill, useToast } from "@/src/components/ui";
import { QUOTE_STATUS_META, Quotation, openQuotationPdf } from "@/src/api/quotations";
import RichHtml from "@/src/components/RichHtml";
import { plainToHtml } from "@/src/utils/richtext";
import { formatINR } from "@/src/utils/format";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

export default function QuotationDetailScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [q, setQ] = useState<Quotation | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [convertModal, setConvertModal] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);
  const [templateModal, setTemplateModal] = useState(false);
  const [templateName, setTemplateName] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/quotations/${id}`);
      setQ(res);
    } catch {
      toast.show("Could not load quotation", "error");
    } finally {
      setLoading(false);
    }
  }, [id, toast]);

  useFocusEffect(useCallback(() => { setLoading(true); load(); }, [load]));

  const downloadPdf = async () => {
    try {
      await openQuotationPdf(id, q?.quotation_number);
    } catch {
      toast.show("Could not open PDF", "error");
    }
  };

  const share = async () => {
    setBusy(true);
    try {
      const res = await api.post(`/quotations/${id}/share`, { enabled: true });
      if (res.share_url) {
        await Clipboard.setStringAsync(res.share_url);
        toast.show("Share link copied to clipboard", "success");
      }
      setQ(res);
    } catch {
      toast.show("Could not create share link", "error");
    } finally {
      setBusy(false);
    }
  };

  const convert = async (target: "invoice" | "proforma") => {
    setBusy(true);
    try {
      const res = await api.post(`/quotations/${id}/convert`, { target });
      setConvertModal(false);
      toast.show(target === "proforma" ? "Proforma invoice created" : "Tax invoice created", "success");
      router.push(`/admin/invoice/${res.invoice.invoice_id}`);
    } catch {
      toast.show("Could not convert quotation", "error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await api.del(`/quotations/${id}`);
      toast.show("Quotation deleted", "success");
      router.replace("/admin/quotations");
    } catch {
      toast.show("Could not delete quotation", "error");
    } finally {
      setBusy(false);
      setDeleteModal(false);
    }
  };

  const createRevision = async () => {
    setBusy(true);
    try {
      const res = await api.post(`/quotations/${id}/revise`, {});
      toast.show(`Revision ${res.revision_number} draft created`, "success");
      router.push(`/admin/quotation/new?id=${res.quotation_id}`);
    } catch {
      toast.show("Could not create revision", "error");
    } finally {
      setBusy(false);
    }
  };

  const saveAsTemplate = async () => {
    const name = templateName.trim();
    if (!name) {
      toast.show("Give the template a name", "error");
      return;
    }
    setBusy(true);
    try {
      await api.post(`/quotations/${id}/save-as-template`, { name });
      toast.show(`Saved as template “${name}”`, "success");
      setTemplateModal(false);
      setTemplateName("");
    } catch {
      toast.show("Could not save template", "error");
    } finally {
      setBusy(false);
    }
  };

  if (loading || !q) {
    return (
      <View style={styles.container}>
        <GlassHeader title="Quotation" topInset={insets.top} onBack={() => router.back()} />
        <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>
      </View>
    );
  }

  const meta = QUOTE_STATUS_META[q.status] || QUOTE_STATUS_META.sent;
  const gm = q.gst_mode;
  const resp = q.client_response;
  const revN = q.revision_number || 1;
  const numberLabel = revN > 1 ? `${q.quotation_number} · Rev ${revN}` : q.quotation_number;
  const revisions = q.revisions || [];

  return (
    <View style={styles.container} testID="admin-quotation-detail-screen">
      <GlassHeader
        title={numberLabel}
        topInset={insets.top}
        onBack={() => router.back()}
        right={
          <Pressable testID="edit-quotation" onPress={() => router.push(`/admin/quotation/new?id=${id}`)} hitSlop={10}>
            <Ionicons name="create-outline" size={22} color={colors.brand} />
          </Pressable>
        }
      />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 40 }}>
        {/* status */}
        <View style={styles.topCard}>
          <View style={styles.rowBetween}>
            <Pill label={meta.label} tone={meta.tone} />
            <Text style={styles.issueDate}>{q.issue_date}{q.valid_until ? `  ·  valid till ${q.valid_until}` : ""}</Text>
          </View>
          {!!q.subject && <Text style={styles.subject}>{q.subject}</Text>}
          {q.show_pricing ? (
            <Text style={styles.grandValue}>{formatINR(q.total || 0)}</Text>
          ) : (
            <Text style={styles.noPricing}>Free-form quotation · no pricing table</Text>
          )}
        </View>

        {/* revision context (this is a revision draft) */}
        {!!q.revision_note && (
          <View style={[styles.card, styles.revisionNoteCard]} testID="revision-context">
            <View style={styles.rowStart}>
              <Ionicons name="git-branch-outline" size={16} color={colors.brand} />
              <Text style={styles.respTitle}>Revision {revN} · client's change request</Text>
            </View>
            <Text style={styles.respNote}>“{q.revision_note}”</Text>
          </View>
        )}

        {/* client response */}
        {!!resp && (
          <View style={[styles.card, resp.action === "accept" ? styles.respAccepted : styles.respRevision]} testID="client-response-card">
            <View style={styles.rowStart}>
              <Ionicons name={resp.action === "accept" ? "checkmark-circle" : "chatbubble-ellipses"} size={18} color={resp.action === "accept" ? colors.onSuccess : colors.onWarning} />
              <Text style={styles.respTitle}>
                {resp.action === "accept" ? "Client accepted this quotation" : "Client requested a revision"}
              </Text>
            </View>
            {!!resp.note && <Text style={styles.respNote}>“{resp.note}”</Text>}
            {!!resp.at && <Text style={styles.respAt}>{new Date(resp.at).toLocaleString()}</Text>}
          </View>
        )}

        {/* revision auto-draft CTA */}
        {q.status === "revision_requested" && !q.converted_invoice_id && (
          <Button testID="create-revision" title="Create revision draft" icon="git-branch-outline" loading={busy} onPress={createRevision} style={{ marginBottom: spacing.lg }} />
        )}

        {/* revision history thread */}
        {revisions.length > 1 && (
          <View style={styles.card} testID="revision-history">
            <Text style={styles.cardLabel}>REVISION HISTORY</Text>
            {revisions.map((r) => {
              const active = r.quotation_id === id;
              const rMeta = QUOTE_STATUS_META[r.status] || QUOTE_STATUS_META.sent;
              return (
                <Pressable
                  key={r.quotation_id}
                  testID={`revision-row-${r.revision_number || 1}`}
                  disabled={active}
                  onPress={() => router.push(`/admin/quotation/${r.quotation_id}`)}
                  style={[styles.revRow, active && styles.revRowActive]}
                >
                  <Ionicons name={active ? "ellipse" : "ellipse-outline"} size={12} color={colors.brand} />
                  <Text style={styles.revRowText}>Rev {r.revision_number || 1}{active ? " · viewing" : ""}</Text>
                  <Pill label={rMeta.label} tone={rMeta.tone} />
                  {!active && <Ionicons name="chevron-forward" size={14} color={colors.muted} />}
                </Pressable>
              );
            })}
          </View>
        )}

        {/* converted */}
        {!!q.converted_invoice_id && (
          <Pressable testID="view-converted-invoice" onPress={() => router.push(`/admin/invoice/${q.converted_invoice_id}`)} style={styles.convertedBox}>
            <Ionicons name="receipt-outline" size={16} color={colors.brand} />
            <Text style={styles.convertedText}>Converted to {q.converted_target === "proforma" ? "Proforma Invoice" : "Tax Invoice"} · tap to view</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.muted} />
          </Pressable>
        )}

        {/* client */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>PREPARED FOR</Text>
          <Text style={styles.partyName}>{q.client?.name || "Client"}</Text>
          {!!q.client?.address && <Text style={styles.partyLine}>{q.client.address}</Text>}
          {!!q.client?.gstin && <Text style={styles.partyLine}>GSTIN: {q.client.gstin}</Text>}
          {!!q.client?.phone && <Text style={styles.partyLine}>{q.client.phone}</Text>}
          {!!q.client?.email && <Text style={styles.partyLine}>{q.client.email}</Text>}
        </View>

        {/* body */}
        {!!q.body && (
          <View style={styles.card}>
            <Text style={styles.cardLabel}>CONTENT</Text>
            <View style={{ marginTop: spacing.sm }}>
              <RichHtml
                html={q.body_html || plainToHtml(q.body)}
                palette={{ text: colors.onSurfaceSecondary, ink: colors.onSurface, accent: colors.brand, accentSoft: colors.brandTertiary, line: colors.borderStrong, sub: colors.muted }}
                fontSize={fontSize.base}
                lineHeight={22}
                testID="quotation-body"
              />
            </View>
          </View>
        )}

        {/* pricing */}
        {q.show_pricing && (q.line_items || []).length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardLabel}>PRICING</Text>
            {q.line_items.map((li, i) => (
              <View key={i} style={styles.itemRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.itemDesc}>{li.description}</Text>
                  <Text style={styles.itemMeta}>{li.qty} × {formatINR(li.rate)}{gm !== "none" ? ` · GST ${li.gst_rate}%` : ""}</Text>
                </View>
                <Text style={styles.itemAmount}>{formatINR(li.amount || 0)}</Text>
              </View>
            ))}
            <View style={styles.divider} />
            {!!q.discount_amount && <Row label="Discount" value={`- ${formatINR(q.discount_amount)}`} />}
            <Row label="Sub total" value={formatINR(q.taxable_total || 0)} />
            {gm === "cgst_sgst" && (<><Row label="CGST" value={formatINR(q.cgst_total || 0)} /><Row label="SGST" value={formatINR(q.sgst_total || 0)} /></>)}
            {gm === "igst" && <Row label="IGST" value={formatINR(q.igst_total || 0)} />}
            <View style={styles.grandRow}>
              <Text style={styles.grandLabel}>Estimated total</Text>
              <Text style={styles.grandTotal}>{formatINR(q.total || 0)}</Text>
            </View>
            {!!q.amount_in_words && <Text style={styles.words}>{q.amount_in_words}</Text>}
          </View>
        )}

        {(!!q.terms || !!q.notes) && (
          <View style={styles.card}>
            {!!q.terms && (<><Text style={styles.cardLabel}>TERMS &amp; CONDITIONS</Text><Text style={[styles.bodyText, { marginBottom: q.notes ? spacing.md : 0 }]}>{q.terms}</Text></>)}
            {!!q.notes && (<><Text style={styles.cardLabel}>NOTES</Text><Text style={styles.bodyText}>{q.notes}</Text></>)}
          </View>
        )}

        {/* actions */}
        <View style={styles.actions}>
          <Button testID="download-quotation-pdf" title="Download PDF" icon="download-outline" variant="secondary" onPress={downloadPdf} />
          <Button testID="share-quotation" title={q.share_enabled ? "Copy share link" : "Create share link"} icon="link-outline" variant="secondary" loading={busy} onPress={share} />
          <Button testID="save-as-template" title="Save as template" icon="documents-outline" variant="secondary" onPress={() => { setTemplateName(q.subject || ""); setTemplateModal(true); }} />
          {!q.converted_invoice_id && (
            <Button testID="convert-quotation" title="Convert to invoice" icon="receipt-outline" onPress={() => setConvertModal(true)} />
          )}
          <Button testID="delete-quotation" title="Delete quotation" icon="trash-outline" variant="danger" onPress={() => setDeleteModal(true)} />
        </View>
        {!!q.share_url && (
          <Pressable testID="share-url-box" onPress={() => Clipboard.setStringAsync(q.share_url!).then(() => toast.show("Copied", "success"))} style={styles.linkBox}>
            <Ionicons name="globe-outline" size={14} color={colors.brand} />
            <Text style={styles.linkText} numberOfLines={1}>{q.share_url}</Text>
            <Ionicons name="copy-outline" size={14} color={colors.muted} />
          </Pressable>
        )}
      </ScrollView>

      {/* convert modal */}
      <Modal visible={convertModal} transparent animationType="fade" onRequestClose={() => setConvertModal(false)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setConvertModal(false)}>
          <Pressable style={styles.modalCard} onPress={() => {}} testID="convert-modal">
            <Text style={styles.modalTitle}>Convert to invoice</Text>
            <Text style={styles.modalSub}>A draft invoice will be created from this quotation. Choose the document type:</Text>
            <Pressable testID="convert-invoice" disabled={busy} onPress={() => convert("invoice")} style={styles.choice}>
              <View style={styles.choiceIcon}><Ionicons name="receipt-outline" size={20} color={colors.brand} /></View>
              <View style={{ flex: 1 }}>
                <Text style={styles.choiceTitle}>Tax Invoice</Text>
                <Text style={styles.choiceSub}>Final GST invoice · counted in revenue</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </Pressable>
            <Pressable testID="convert-proforma" disabled={busy} onPress={() => convert("proforma")} style={styles.choice}>
              <View style={styles.choiceIcon}><Ionicons name="document-text-outline" size={20} color={colors.brand} /></View>
              <View style={{ flex: 1 }}>
                <Text style={styles.choiceTitle}>Proforma Invoice</Text>
                <Text style={styles.choiceSub}>Advance / estimate · not counted in revenue</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </Pressable>
            {busy && <ActivityIndicator color={colors.brand} style={{ marginTop: spacing.md }} />}
          </Pressable>
        </Pressable>
      </Modal>

      {/* delete modal */}
      <Modal visible={deleteModal} transparent animationType="fade" onRequestClose={() => setDeleteModal(false)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setDeleteModal(false)}>
          <Pressable style={styles.modalCard} onPress={() => {}} testID="delete-modal">
            <Text style={styles.modalTitle}>Delete quotation?</Text>
            <Text style={styles.modalSub}>{q.quotation_number} will be permanently removed and its share link will stop working.</Text>
            <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm }}>
              <Button title="Keep" variant="secondary" onPress={() => setDeleteModal(false)} style={{ flex: 1 }} />
              <Button testID="confirm-delete-quotation" title="Delete" variant="danger" loading={busy} onPress={remove} style={{ flex: 1 }} />
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      {/* save as template modal */}
      <Modal visible={templateModal} transparent animationType="fade" onRequestClose={() => setTemplateModal(false)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setTemplateModal(false)}>
          <Pressable style={styles.modalCard} onPress={() => {}} testID="template-modal">
            <Text style={styles.modalTitle}>Save as template</Text>
            <Text style={styles.modalSub}>Reuse this content (subject, body, pricing, terms & notes) for future quotes. Client and dates are not saved.</Text>
            <TextInput
              testID="template-name-input"
              value={templateName}
              onChangeText={setTemplateName}
              placeholder="e.g. Wedding — Premium package"
              placeholderTextColor={colors.muted}
              style={styles.templateInput}
            />
            <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.md }}>
              <Button title="Cancel" variant="secondary" onPress={() => setTemplateModal(false)} style={{ flex: 1 }} />
              <Button testID="confirm-save-template" title="Save template" loading={busy} onPress={saveAsTemplate} style={{ flex: 1 }} />
            </View>
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
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  rowStart: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  topCard: { backgroundColor: colors.brandTertiary, borderRadius: radius.lg, padding: spacing.xl, borderWidth: 1, borderColor: colors.brand, marginBottom: spacing.lg },
  issueDate: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm },
  subject: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing.md },
  grandValue: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.hero, marginTop: spacing.sm },
  noPricing: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.sm },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.lg },
  respAccepted: { borderColor: colors.onSuccess },
  respRevision: { borderColor: colors.onWarning },
  respTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700", flex: 1 },
  respNote: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: spacing.sm, fontStyle: "italic", lineHeight: 20 },
  respAt: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.xs },
  revisionNoteCard: { borderColor: colors.brand, backgroundColor: colors.brandTertiary },
  revRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  revRowActive: { opacity: 0.9 },
  revRowText: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  templateInput: { backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, padding: spacing.md, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, minHeight: 48 },
  convertedBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.brand, marginBottom: spacing.lg },
  convertedText: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
  cardLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  partyName: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing.xs },
  partyLine: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: 2 },
  bodyText: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 22, marginTop: spacing.xs },
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
  actions: { gap: spacing.sm },
  linkBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border, marginTop: spacing.md },
  linkText: { flex: 1, color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm },
  modalBackdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.72)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  modalCard: { width: "100%", maxWidth: 460, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, padding: spacing.xl, borderWidth: 1, borderColor: colors.borderStrong },
  modalTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginBottom: spacing.sm },
  modalSub: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 20, marginBottom: spacing.lg },
  choice: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.sm },
  choiceIcon: { width: 40, height: 40, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  choiceTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  choiceSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
});
