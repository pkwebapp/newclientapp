import { useEffect, useMemo, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api } from "@/src/api/client";
import { Button, GlassHeader, TextField, useToast } from "@/src/components/ui";
import { computeQuoteTotals, QuoteMode, QuoteTemplate } from "@/src/api/quotations";
import RichHtml from "@/src/components/RichHtml";
import QuoteBodyEditorModal, { StudioLetterhead } from "@/src/components/QuoteBodyEditorModal";
import { paper, paperPalette } from "@/src/components/paper-theme";
import { isHtml, plainToHtml } from "@/src/utils/richtext";
import { formatINR } from "@/src/utils/format";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { gstinError, phoneError } from "@/src/utils/validators";
import DatePickerField from "@/src/components/DatePickerField";

type Row = { description: string; qty: string; rate: string; gst_rate: string };

const todayIso = () => new Date().toISOString().slice(0, 10);

const GST_MODES: { key: QuoteMode; label: string }[] = [
  { key: "none", label: "No GST" },
  { key: "cgst_sgst", label: "CGST+SGST" },
  { key: "igst", label: "IGST" },
];

export default function QuotationFormScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const isEdit = !!id;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [clients, setClients] = useState<any[]>([]);
  const [clientPicker, setClientPicker] = useState(false);
  const [templates, setTemplates] = useState<QuoteTemplate[]>([]);
  const [templatePicker, setTemplatePicker] = useState(false);
  const [revisionNote, setRevisionNote] = useState("");
  const [revisionNumber, setRevisionNumber] = useState(1);

  const [clientId, setClientId] = useState<string | null>(null);
  const [clientName, setClientName] = useState("");
  const [clientState, setClientState] = useState("");
  const [clientGstin, setClientGstin] = useState("");
  const [clientPhone, setClientPhone] = useState("");
  const [clientEmail, setClientEmail] = useState("");
  const [clientAddress, setClientAddress] = useState("");
  const clientGstinErr = gstinError(clientGstin);
  const clientPhoneErr = phoneError(clientPhone);

  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [bodyEditor, setBodyEditor] = useState(false);
  const [studio, setStudio] = useState<StudioLetterhead>({});
  const [quotationNumber, setQuotationNumber] = useState("");
  const [showPricing, setShowPricing] = useState(false);
  const [gstMode, setGstMode] = useState<QuoteMode>("none");
  const [defaultGst, setDefaultGst] = useState("18");
  const [discount, setDiscount] = useState("");
  const [rows, setRows] = useState<Row[]>([{ description: "", qty: "1", rate: "", gst_rate: "18" }]);
  const [issueDate, setIssueDate] = useState(todayIso());
  const [validUntil, setValidUntil] = useState("");
  const [terms, setTerms] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [settings, cl, tpl] = await Promise.all([
          api.get("/invoice-settings"),
          api.get("/clients").catch(() => []),
          api.get("/quotation-templates").catch(() => ({ items: [] })),
        ]);
        setClients(Array.isArray(cl) ? cl : []);
        setTemplates(Array.isArray(tpl?.items) ? tpl.items : []);
        setDefaultGst(String(settings.default_gst_rate ?? "18"));
        setStudio({
          name: settings.legal_name,
          address: settings.address,
          phone: settings.phone,
          email: settings.email,
          website: settings.website,
          gstin: settings.gstin,
          logo_base64: settings.logo_base64,
        });
        if (!isEdit) {
          setTerms(settings.default_terms || "");
          setRows([{ description: "", qty: "1", rate: "", gst_rate: String(settings.default_gst_rate ?? "18") }]);
        }
        if (isEdit && id) {
          const q = await api.get(`/quotations/${id}`);
          setClientId(q.client_id || null);
          setClientName(q.client?.name || "");
          setClientState(q.client?.state || "");
          setClientGstin(q.client?.gstin || "");
          setClientPhone(q.client?.phone || "");
          setClientEmail(q.client?.email || "");
          setClientAddress(q.client?.address || "");
          setSubject(q.subject || "");
          setBody(q.body || "");
          setShowPricing(!!q.show_pricing);
          setGstMode(q.gst_mode || "none");
          setDiscount(q.discount_amount ? String(q.discount_amount) : "");
          setIssueDate(q.issue_date || todayIso());
          setValidUntil(q.valid_until || "");
          setTerms(q.terms || "");
          setNotes(q.notes || "");
          setRevisionNote(q.revision_note || "");
          setRevisionNumber(Number(q.revision_number) || 1);
          setQuotationNumber(q.quotation_number || "");
          if ((q.line_items || []).length) {
            setRows((q.line_items || []).map((li: any) => ({
              description: li.description || "",
              qty: String(li.qty ?? 1),
              rate: String(li.rate ?? 0),
              gst_rate: String(li.gst_rate ?? 18),
            })));
          }
        }
      } catch {
        toast.show("Could not load quotation", "error");
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isEdit, toast]);

  const totals = useMemo(
    () => computeQuoteTotals(
      rows.map((r) => ({ description: r.description, qty: Number(r.qty) || 0, rate: Number(r.rate) || 0, gst_rate: Number(r.gst_rate) || 0 })),
      gstMode,
      Number(discount) || 0
    ),
    [rows, gstMode, discount]
  );

  const updateRow = (idx: number, key: keyof Row, val: string) =>
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [key]: val } : r)));
  const addRow = () => setRows((prev) => [...prev, { description: "", qty: "1", rate: "", gst_rate: defaultGst }]);
  const removeRow = (idx: number) => setRows((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== idx) : prev));

  const pickClient = (c: any) => {
    setClientId(c.client_id);
    setClientName(c.name || "");
    if (c.state) setClientState(c.state);
    if (c.gstin) setClientGstin(c.gstin);
    if (c.address) setClientAddress(c.address);
    setClientPicker(false);
  };

  const applyTemplate = (t: QuoteTemplate) => {
    setSubject(t.subject || "");
    setBody(t.body || "");
    setShowPricing(!!t.show_pricing);
    setGstMode(t.gst_mode || "none");
    setDiscount(t.discount_amount ? String(t.discount_amount) : "");
    setTerms(t.terms || "");
    setNotes(t.notes || "");
    if ((t.line_items || []).length) {
      setRows(t.line_items.map((li) => ({
        description: li.description || "",
        qty: String(li.qty ?? 1),
        rate: String(li.rate ?? 0),
        gst_rate: String(li.gst_rate ?? defaultGst),
      })));
    }
    setTemplatePicker(false);
    toast.show(`Template “${t.name}” applied`, "success");
  };

  const deleteTemplate = async (t: QuoteTemplate) => {
    try {
      await api.del(`/quotation-templates/${t.template_id}`);
      setTemplates((prev) => prev.filter((x) => x.template_id !== t.template_id));
      toast.show("Template deleted", "success");
    } catch {
      toast.show("Could not delete template", "error");
    }
  };

  const save = async () => {
    if (!clientName.trim()) return toast.show("Add a client name", "error");
    if (clientGstinErr) return toast.show(clientGstinErr, "error");
    if (clientPhoneErr) return toast.show(clientPhoneErr, "error");
    if (!subject.trim() && !body.trim() && !showPricing) return toast.show("Add a subject or some content", "error");

    const validRows = rows.filter((r) => r.description.trim() && (Number(r.rate) || 0) > 0 && (Number(r.qty) || 0) > 0);
    if (showPricing && validRows.length === 0) return toast.show("Add at least one priced item, or turn off pricing", "error");

    const payload: any = {
      client_id: clientId || undefined,
      client: { name: clientName, state: clientState, gstin: clientGstin, phone: clientPhone, email: clientEmail, address: clientAddress },
      subject: subject || undefined,
      body: body || undefined,
      show_pricing: showPricing,
      gst_mode: gstMode,
      discount_amount: Number(discount) || 0,
      line_items: showPricing
        ? validRows.map((r) => ({
            description: r.description.trim(),
            qty: Number(r.qty) || 0,
            rate: Number(r.rate) || 0,
            gst_rate: gstMode === "none" ? 0 : Number(r.gst_rate) || 0,
          }))
        : [],
      issue_date: issueDate || undefined,
      valid_until: validUntil || undefined,
      terms: terms || undefined,
      notes: notes || undefined,
      status: "sent",
    };

    setSaving(true);
    try {
      const res = isEdit ? await api.patch(`/quotations/${id}`, payload) : await api.post("/quotations", payload);
      toast.show(isEdit ? "Saved" : "Quotation created", "success");
      router.replace(`/admin/quotation/${res.quotation_id}`);
    } catch {
      toast.show("Could not save quotation", "error");
    } finally {
      setSaving(false);
    }
  };

  const headerTitle = isEdit ? "Edit Quotation" : "New Quotation";

  if (loading) {
    return (
      <View style={styles.container}>
        <GlassHeader title={headerTitle} topInset={insets.top} onBack={() => router.back()} />
        <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID="admin-quotation-form-screen">
      <GlassHeader title={headerTitle} topInset={insets.top} onBack={() => router.back()} />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 160 }} keyboardShouldPersistTaps="handled">
          <Text style={styles.helper}>Your studio letterhead (logo, name, address, GSTIN, website) is added automatically. Set it in Invoice Settings.</Text>

          {!isEdit && (
            <Pressable testID="start-from-template" onPress={() => setTemplatePicker(true)} style={styles.templateBtn}>
              <Ionicons name="documents-outline" size={18} color={colors.brand} />
              <Text style={styles.templateBtnText}>Start from a template</Text>
              <Ionicons name="chevron-forward" size={16} color={colors.muted} />
            </Pressable>
          )}

          {isEdit && revisionNumber > 1 && (
            <View style={styles.revisionBanner} testID="revision-banner">
              <View style={styles.rowStart}>
                <Ionicons name="git-branch-outline" size={16} color={colors.brand} />
                <Text style={styles.revisionBannerTitle}>Revision {revisionNumber} draft</Text>
              </View>
              {!!revisionNote ? (
                <Text style={styles.revisionBannerNote}>Client asked: “{revisionNote}”</Text>
              ) : (
                <Text style={styles.revisionBannerNote}>Edit and send this updated quotation.</Text>
              )}
            </View>
          )}

          {/* Client */}
          <Text style={styles.section}>Prepared for</Text>
          <Pressable testID="pick-client" onPress={() => setClientPicker(true)} style={styles.pickerBtn}>
            <Ionicons name="person-outline" size={18} color={colors.brand} />
            <Text style={styles.pickerText}>{clientId ? clientName : "Choose an existing client"}</Text>
            <Ionicons name="chevron-down" size={16} color={colors.muted} />
          </Pressable>
          <TextField label="Client name" value={clientName} onChangeText={setClientName} placeholder="e.g. Sharma Wedding" testID="quote-client-name" />
          <View style={styles.two}>
            <View style={{ flex: 1 }}><TextField label="Phone" value={clientPhone} onChangeText={setClientPhone} keyboardType="phone-pad" placeholder="optional" error={clientPhoneErr || undefined} /></View>
            <View style={{ flex: 1 }}><TextField label="Email" value={clientEmail} onChangeText={setClientEmail} keyboardType="email-address" autoCapitalize="none" placeholder="optional" /></View>
          </View>
          <View style={styles.two}>
            <View style={{ flex: 1 }}><TextField label="GSTIN" value={clientGstin} onChangeText={(v) => setClientGstin(v.toUpperCase())} autoCapitalize="characters" placeholder="optional" error={clientGstinErr || undefined} /></View>
            <View style={{ flex: 1 }}><TextField label="Address" value={clientAddress} onChangeText={setClientAddress} placeholder="optional" /></View>
          </View>

          {/* Content */}
          <Text style={styles.section}>Content</Text>
          <TextField label="Subject / title" value={subject} onChangeText={setSubject} placeholder="Wedding Photography Package — Dec 2026" testID="quote-subject" />
          <Text style={styles.fieldLabel}>Body</Text>
          <Pressable testID="open-body-editor" onPress={() => setBodyEditor(true)} style={styles.bodyCard}>
            {body.trim() ? (
              <View style={styles.bodyPreview}>
                <RichHtml html={isHtml(body) ? body : plainToHtml(body)} palette={paperPalette} fontSize={13} lineHeight={20} testID="body-preview" />
              </View>
            ) : (
              <View style={styles.bodyEmpty}>
                <Ionicons name="document-text-outline" size={26} color={paperPalette.sub} />
                <Text style={styles.bodyEmptyTitle}>Write the quotation body</Text>
                <Text style={styles.bodyEmptySub}>Full-page editor with headings, bold, lists and tables. Paste from Word or Google Docs — formatting is kept.</Text>
              </View>
            )}
            <View style={styles.bodyFoot}>
              <Ionicons name="create-outline" size={16} color={colors.brand} />
              <Text style={styles.bodyFootText}>{body.trim() ? "Open full-page editor" : "Open editor"}</Text>
            </View>
          </Pressable>

          {/* Pricing (optional) */}
          <View style={styles.toggleRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.section}>Pricing table</Text>
              <Text style={styles.helper}>Optional. Add itemised pricing with a grand total.</Text>
            </View>
            <Pressable testID="toggle-pricing" onPress={() => setShowPricing((v) => !v)} style={[styles.switch, showPricing && styles.switchOn]}>
              <View style={[styles.knob, showPricing && styles.knobOn]} />
            </Pressable>
          </View>

          {showPricing && (
            <>
              <Text style={styles.fieldLabel}>GST type</Text>
              <View style={styles.modeRow}>
                {GST_MODES.map((m) => (
                  <Pressable key={m.key} testID={`quote-gst-${m.key}`} onPress={() => setGstMode(m.key)} style={[styles.modeBtn, gstMode === m.key && styles.modeBtnActive]}>
                    <Text style={[styles.modeLabel, gstMode === m.key && styles.modeLabelActive]}>{m.label}</Text>
                  </Pressable>
                ))}
              </View>
              {rows.map((r, idx) => (
                <View key={idx} style={styles.itemCard}>
                  <View style={styles.itemHead}>
                    <Text style={styles.itemNum}>Item {idx + 1}</Text>
                    {rows.length > 1 && (
                      <Pressable testID={`remove-item-${idx}`} hitSlop={8} onPress={() => removeRow(idx)}>
                        <Ionicons name="trash-outline" size={18} color={colors.onError} />
                      </Pressable>
                    )}
                  </View>
                  <TextField label="Description" value={r.description} onChangeText={(t) => updateRow(idx, "description", t)} placeholder="Candid Photography (2 days)" testID={`item-desc-${idx}`} />
                  <View style={styles.two}>
                    <View style={{ flex: 1 }}><TextField label="Qty" value={r.qty} onChangeText={(t) => updateRow(idx, "qty", t)} keyboardType="numeric" /></View>
                    <View style={{ flex: 1 }}><TextField label="Rate (₹)" value={r.rate} onChangeText={(t) => updateRow(idx, "rate", t)} keyboardType="numeric" placeholder="50000" testID={`item-rate-${idx}`} /></View>
                    {gstMode !== "none" && (
                      <View style={{ flex: 1 }}><TextField label="GST %" value={r.gst_rate} onChangeText={(t) => updateRow(idx, "gst_rate", t)} keyboardType="numeric" placeholder="18" /></View>
                    )}
                  </View>
                </View>
              ))}
              <Pressable testID="add-item" onPress={addRow} style={styles.addRow}>
                <Ionicons name="add-circle-outline" size={20} color={colors.brand} />
                <Text style={styles.addText}>Add item</Text>
              </Pressable>
              <TextField label="Discount (₹)" value={discount} onChangeText={setDiscount} keyboardType="numeric" placeholder="0" />
              <View style={styles.totalsCard}>
                <TotalRow label="Sub total" value={totals.taxable_total} />
                {gstMode === "cgst_sgst" && (<><TotalRow label="CGST" value={totals.cgst_total} /><TotalRow label="SGST" value={totals.sgst_total} /></>)}
                {gstMode === "igst" && <TotalRow label="IGST" value={totals.igst_total} />}
                <View style={styles.grandRow}>
                  <Text style={styles.grandLabel}>Estimated total</Text>
                  <Text style={styles.grandValue}>{formatINR(totals.total)}</Text>
                </View>
              </View>
            </>
          )}

          {/* Meta */}
          <Text style={styles.section}>Validity & terms</Text>
          <View style={styles.two}>
            <View style={{ flex: 1 }}><DatePickerField label="Quotation date" value={issueDate} onChange={setIssueDate} testID="issue-date-picker" /></View>
            <View style={{ flex: 1 }}><DatePickerField label="Valid until" value={validUntil} onChange={setValidUntil} testID="valid-until-picker" emptyLabel="No expiry" /></View>
          </View>
          <TextField label="Terms & conditions" value={terms} onChangeText={setTerms} multiline placeholder="50% advance to confirm the date…" />
          <TextField label="Notes" value={notes} onChangeText={setNotes} multiline placeholder="optional" />

          <Button testID="save-quotation" title={isEdit ? "Update quotation" : "Create quotation"} icon="checkmark-circle-outline" loading={saving} onPress={save} style={{ marginTop: spacing.md }} />
        </ScrollView>
      </KeyboardAvoidingView>

      <QuoteBodyEditorModal
        visible={bodyEditor}
        onClose={() => setBodyEditor(false)}
        value={body}
        onChange={setBody}
        studio={studio}
        clientName={clientName}
        subject={subject}
        numberLabel={quotationNumber ? (revisionNumber > 1 ? `${quotationNumber} · Rev ${revisionNumber}` : quotationNumber) : "Number assigned on save"}
        issueDate={issueDate}
      />

      <Modal visible={clientPicker} transparent animationType="slide" onRequestClose={() => setClientPicker(false)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setClientPicker(false)}>
          <Pressable style={styles.modalCard} onPress={() => {}}>
            <View style={styles.modalHead}>
              <Text style={styles.modalTitle}>Select client</Text>
              <Pressable hitSlop={8} onPress={() => setClientPicker(false)}><Ionicons name="close" size={22} color={colors.muted} /></Pressable>
            </View>
            <ScrollView style={{ maxHeight: 420 }}>
              {clients.length === 0 ? (
                <Text style={styles.modalEmpty}>No clients yet. Type the name above instead.</Text>
              ) : (
                clients.map((item) => (
                  <Pressable key={item.client_id} style={styles.modalRow} onPress={() => pickClient(item)}>
                    <Text style={styles.modalRowText} numberOfLines={1}>{item.name}</Text>
                    <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                  </Pressable>
                ))
              )}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal visible={templatePicker} transparent animationType="slide" onRequestClose={() => setTemplatePicker(false)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setTemplatePicker(false)}>
          <Pressable style={styles.modalCard} onPress={() => {}}>
            <View style={styles.modalHead}>
              <Text style={styles.modalTitle}>Start from a template</Text>
              <Pressable hitSlop={8} onPress={() => setTemplatePicker(false)}><Ionicons name="close" size={22} color={colors.muted} /></Pressable>
            </View>
            <ScrollView style={{ maxHeight: 420 }}>
              {templates.length === 0 ? (
                <Text style={styles.modalEmpty}>No templates yet. Open any quotation and tap “Save as template” to reuse it later.</Text>
              ) : (
                templates.map((t) => (
                  <View key={t.template_id} style={styles.templateRow}>
                    <Pressable style={{ flex: 1 }} testID={`apply-template-${t.template_id}`} onPress={() => applyTemplate(t)}>
                      <Text style={styles.modalRowText} numberOfLines={1}>{t.name}</Text>
                      <Text style={styles.templateMeta} numberOfLines={1}>
                        {t.subject || "No subject"}{t.show_pricing ? ` · ${(t.line_items || []).length} item(s)` : " · free-form"}
                      </Text>
                    </Pressable>
                    <Pressable hitSlop={8} testID={`delete-template-${t.template_id}`} onPress={() => deleteTemplate(t)} style={styles.templateDelete}>
                      <Ionicons name="trash-outline" size={18} color={colors.onError} />
                    </Pressable>
                  </View>
                ))
              )}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

function TotalRow({ label, value }: { label: string; value: number }) {
  return (
    <View style={styles.totalRow}>
      <Text style={styles.totalLabel}>{label}</Text>
      <Text style={styles.totalValue}>{formatINR(value)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  rowStart: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  templateBtn: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.brandTertiary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.brand, marginBottom: spacing.md },
  templateBtnText: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  revisionBanner: { backgroundColor: colors.brandTertiary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.brand, marginBottom: spacing.md },
  revisionBannerTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "800" },
  revisionBannerNote: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.xs, fontStyle: "italic", lineHeight: 18 },
  templateRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  templateMeta: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  templateDelete: { padding: spacing.sm },
  section: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing.lg, marginBottom: spacing.md },
  helper: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginBottom: spacing.md, lineHeight: 18 },
  fieldLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600", marginBottom: spacing.sm },
  two: { flexDirection: "row", gap: spacing.sm },
  bodyCard: { backgroundColor: paper.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.lg, overflow: "hidden" },
  bodyPreview: { padding: spacing.lg, maxHeight: 260, overflow: "hidden" },
  bodyEmpty: { alignItems: "center", padding: spacing.xl, gap: spacing.xs },
  bodyEmptyTitle: { color: paperPalette.ink, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700", marginTop: spacing.xs },
  bodyEmptySub: { color: paperPalette.sub, fontFamily: fonts.text, fontSize: fontSize.sm, textAlign: "center", lineHeight: 18, maxWidth: 360 },
  bodyFoot: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, paddingVertical: spacing.md, borderTopWidth: 1, borderTopColor: paperPalette.line, backgroundColor: paperPalette.accentSoft },
  bodyFootText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "800" },
  pickerBtn: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.lg },
  pickerText: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  toggleRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  switch: { width: 52, height: 30, borderRadius: 15, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, padding: 3, justifyContent: "center" },
  switchOn: { backgroundColor: colors.brand, borderColor: colors.brand },
  knob: { width: 22, height: 22, borderRadius: 11, backgroundColor: colors.muted },
  knobOn: { backgroundColor: colors.onBrand, alignSelf: "flex-end" },
  modeRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.lg },
  modeBtn: { flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, paddingVertical: spacing.md, borderWidth: 1, borderColor: colors.border, alignItems: "center" },
  modeBtnActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  modeLabel: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  modeLabelActive: { color: colors.onBrand },
  itemCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.md },
  itemHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.sm },
  itemNum: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "800", letterSpacing: 0.5 },
  addRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingVertical: spacing.md, marginBottom: spacing.md },
  addText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  totalsCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border, marginVertical: spacing.md },
  totalRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 },
  totalLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base },
  totalValue: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  grandRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: spacing.sm, paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.borderStrong },
  grandLabel: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  grandValue: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  modalBackdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.7)", justifyContent: "flex-end" },
  modalCard: { backgroundColor: colors.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: spacing.xl, borderWidth: 1, borderColor: colors.borderStrong },
  modalHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.lg },
  modalTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  modalEmpty: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, paddingVertical: spacing.lg },
  modalRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: spacing.lg, borderBottomWidth: 1, borderBottomColor: colors.border },
  modalRowText: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
});
