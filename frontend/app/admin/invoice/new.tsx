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
import { computeTotals, GstMode } from "@/src/api/invoices";
import { formatINR } from "@/src/utils/format";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { gstinError, phoneError } from "@/src/utils/validators";
import DatePickerField from "@/src/components/DatePickerField";

type Row = { description: string; hsn_sac: string; qty: string; rate: string; gst_rate: string };

const todayIso = () => new Date().toISOString().slice(0, 10);

const GST_MODES: { key: GstMode; label: string }[] = [
  { key: "cgst_sgst", label: "CGST+SGST" },
  { key: "igst", label: "IGST" },
  { key: "none", label: "No GST" },
];

export default function InvoiceFormScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const isEdit = !!id;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [clients, setClients] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [clientPicker, setClientPicker] = useState(false);
  const [eventPicker, setEventPicker] = useState(false);

  const [clientId, setClientId] = useState<string | null>(null);
  const [clientName, setClientName] = useState("");
  const [clientState, setClientState] = useState("");
  const [clientGstin, setClientGstin] = useState("");
  const [clientPhone, setClientPhone] = useState("");
  const clientGstinErr = gstinError(clientGstin);
  const clientPhoneErr = phoneError(clientPhone);
  const [clientAddress, setClientAddress] = useState("");

  const [eventId, setEventId] = useState<string | null>(null);
  const [eventName, setEventName] = useState("");

  const [issueDate, setIssueDate] = useState(todayIso());
  const [dueDate, setDueDate] = useState("");
  const [docType, setDocType] = useState<"invoice" | "proforma">("invoice");
  const [advance, setAdvance] = useState("");
  const [placeOfSupply, setPlaceOfSupply] = useState("");
  const [gstMode, setGstMode] = useState<GstMode>("cgst_sgst");
  const [defaultGst, setDefaultGst] = useState("18");
  const [discount, setDiscount] = useState("");
  const [notes, setNotes] = useState("");
  const [terms, setTerms] = useState("");
  const [rows, setRows] = useState<Row[]>([{ description: "", hsn_sac: "", qty: "1", rate: "", gst_rate: "18" }]);

  useEffect(() => {
    (async () => {
      try {
        const [settings, cl, ev] = await Promise.all([
          api.get("/invoice-settings"),
          api.get("/clients").catch(() => []),
          api.get("/events").catch(() => []),
        ]);
        setClients(Array.isArray(cl) ? cl : []);
        setEvents(Array.isArray(ev) ? ev : []);
        setDefaultGst(String(settings.default_gst_rate ?? "18"));
        setPlaceOfSupply(settings.place_of_supply_default || "");
        if (!isEdit) {
          setGstMode((settings.default_gst_mode as GstMode) || "cgst_sgst");
          setTerms(settings.default_terms || "");
          setRows([{ description: "", hsn_sac: "", qty: "1", rate: "", gst_rate: String(settings.default_gst_rate ?? "18") }]);
        }
        if (isEdit && id) {
          const inv = await api.get(`/invoices/${id}`);
          setClientId(inv.client_id || null);
          setClientName(inv.client?.name || "");
          setClientState(inv.client?.state || "");
          setClientGstin(inv.client?.gstin || "");
          setClientPhone(inv.client?.phone || "");
          setClientAddress(inv.client?.address || "");
          setEventId(inv.event_id || null);
          setEventName(inv.event_name || "");
          setIssueDate(inv.issue_date || todayIso());
          setDueDate(inv.due_date || "");
          setDocType(inv.doc_type === "proforma" ? "proforma" : "invoice");
          setAdvance(inv.advance_amount ? String(inv.advance_amount) : "");
          setPlaceOfSupply(inv.place_of_supply || "");
          setGstMode(inv.gst_mode || "cgst_sgst");
          setDiscount(inv.discount_amount ? String(inv.discount_amount) : "");
          setNotes(inv.notes || "");
          setTerms(inv.terms || "");
          setRows((inv.line_items || []).map((li: any) => ({
            description: li.description || "",
            hsn_sac: li.hsn_sac || "",
            qty: String(li.qty ?? 1),
            rate: String(li.rate ?? 0),
            gst_rate: String(li.gst_rate ?? 18),
          })));
        }
      } catch {
        toast.show("Could not load invoice", "error");
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isEdit, toast]);

  const totals = useMemo(
    () => computeTotals(
      rows.map((r) => ({ description: r.description, qty: Number(r.qty) || 0, rate: Number(r.rate) || 0, gst_rate: Number(r.gst_rate) || 0 })),
      gstMode,
      Number(discount) || 0
    ),
    [rows, gstMode, discount]
  );

  const discountTooHigh = totals.subtotal > 0 && (Number(discount) || 0) > totals.subtotal;
  const advanceExceedsTotal = totals.total > 0 && (Number(advance) || 0) > totals.total;

  const updateRow = (idx: number, key: keyof Row, val: string) =>
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [key]: val } : r)));
  const addRow = () => setRows((prev) => [...prev, { description: "", hsn_sac: "", qty: "1", rate: "", gst_rate: defaultGst }]);
  const removeRow = (idx: number) => setRows((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== idx) : prev));

  const pickClient = (c: any) => {
    setClientId(c.client_id);
    setClientName(c.name || "");
    if (c.state) setClientState(c.state);
    if (c.gstin) setClientGstin(c.gstin);
    if (c.address) setClientAddress(c.address);
    setClientPicker(false);
  };

  const pickEvent = (e: any) => {
    setEventId(e.event_id);
    setEventName(e.name || "");
    // Auto-fill a line item from the gallery's shoot value (auto-calculate).
    if (e.value && rows.length === 1 && !rows[0].description && !rows[0].rate) {
      setRows([{ description: e.name || "Photography", hsn_sac: "998383", qty: "1", rate: String(e.value), gst_rate: defaultGst }]);
    }
    setEventPicker(false);
  };

  const save = async () => {
    if (!clientName.trim()) return toast.show("Add a client name", "error");
    if (clientGstinErr) return toast.show(clientGstinErr, "error");
    if (clientPhoneErr) return toast.show(clientPhoneErr, "error");
    const validRows = rows.filter((r) => r.description.trim() && (Number(r.rate) || 0) > 0 && (Number(r.qty) || 0) > 0);
    if (validRows.length === 0) return toast.show("Add at least one item with a rate", "error");
    const badGst = validRows.find((r) => { const g = Number(r.gst_rate) || 0; return g < 0 || g > 100; });
    if (badGst) return toast.show("GST % must be between 0 and 100", "error");
    if (discountTooHigh) return toast.show("Discount can't exceed the subtotal", "error");

    const payload: any = {
      client_id: clientId || undefined,
      client: { name: clientName, state: clientState, gstin: clientGstin, phone: clientPhone, address: clientAddress },
      event_id: eventId || undefined,
      doc_type: docType,
      issue_date: issueDate || undefined,
      due_date: dueDate || undefined,
      place_of_supply: placeOfSupply || undefined,
      gst_mode: gstMode,
      discount_amount: Number(discount) || 0,
      advance_amount: Number(advance) || 0,
      line_items: validRows.map((r) => ({
        description: r.description.trim(),
        hsn_sac: r.hsn_sac.trim(),
        qty: Number(r.qty) || 0,
        rate: Number(r.rate) || 0,
        gst_rate: gstMode === "none" ? 0 : Number(r.gst_rate) || 0,
      })),
      notes: notes || undefined,
      terms: terms || undefined,
      status: "sent",
    };

    setSaving(true);
    try {
      const res = isEdit ? await api.patch(`/invoices/${id}`, payload) : await api.post("/invoices", payload);
      toast.show(isEdit ? "Saved" : (docType === "proforma" ? "Proforma created" : "Invoice created"), "success");
      router.replace(`/admin/invoice/${res.invoice_id}`);
    } catch {
      toast.show("Could not save invoice", "error");
    } finally {
      setSaving(false);
    }
  };

  const headerTitle = docType === "proforma"
    ? (isEdit ? "Edit Proforma" : "New Proforma")
    : (isEdit ? "Edit Invoice" : "New Invoice");

  if (loading) {
    return (
      <View style={styles.container}>
        <GlassHeader title={headerTitle} topInset={insets.top} onBack={() => router.back()} />
        <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>
      </View>
    );
  }

  return (
    <View style={styles.container} testID="admin-invoice-form-screen">
      <GlassHeader title={headerTitle} topInset={insets.top} onBack={() => router.back()} />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 160 }} keyboardShouldPersistTaps="handled">
          {/* Document type */}
          <Text style={styles.fieldLabel}>Document type</Text>
          <View style={styles.modeRow}>
            {([{ key: "invoice", label: "Tax Invoice" }, { key: "proforma", label: "Proforma" }] as const).map((d) => (
              <Pressable key={d.key} testID={`doctype-${d.key}`} onPress={() => setDocType(d.key)} style={[styles.modeBtn, docType === d.key && styles.modeBtnActive]}>
                <Text style={[styles.modeLabel, docType === d.key && styles.modeLabelActive]}>{d.label}</Text>
              </Pressable>
            ))}
          </View>
          {docType === "proforma" && (
            <Text style={styles.helper}>Proforma is an estimate — it uses a separate number series and is NOT counted in revenue.</Text>
          )}

          {/* Client */}
          <Text style={styles.section}>Bill to</Text>
          <Pressable testID="pick-client" onPress={() => setClientPicker(true)} style={styles.pickerBtn}>
            <Ionicons name="person-outline" size={18} color={colors.brand} />
            <Text style={styles.pickerText}>{clientId ? clientName : "Choose an existing client"}</Text>
            <Ionicons name="chevron-down" size={16} color={colors.muted} />
          </Pressable>
          <TextField label="Client name" value={clientName} onChangeText={setClientName} placeholder="e.g. Divik Sharma" />
          <View style={styles.two}>
            <View style={{ flex: 1 }}><TextField label="State" value={clientState} onChangeText={setClientState} placeholder="Karnataka" /></View>
            <View style={{ flex: 1 }}><TextField label="Client GSTIN" value={clientGstin} onChangeText={(v) => setClientGstin(v.toUpperCase())} autoCapitalize="characters" placeholder="optional" error={clientGstinErr || undefined} /></View>
          </View>
          <View style={styles.two}>
            <View style={{ flex: 1 }}><TextField label="Phone" value={clientPhone} onChangeText={setClientPhone} keyboardType="phone-pad" placeholder="optional" error={clientPhoneErr || undefined} /></View>
            <View style={{ flex: 1 }}><TextField label="Address" value={clientAddress} onChangeText={setClientAddress} placeholder="optional" /></View>
          </View>

          {/* Gallery link */}
          <Text style={styles.section}>Link a gallery (optional)</Text>
          <Text style={styles.helper}>Linking a gallery avoids double-counting revenue and can auto-fill the amount.</Text>
          <Pressable testID="pick-event" onPress={() => setEventPicker(true)} style={styles.pickerBtn}>
            <Ionicons name="images-outline" size={18} color={colors.brand} />
            <Text style={styles.pickerText}>{eventId ? eventName : "No gallery linked"}</Text>
            {eventId ? (
              <Pressable hitSlop={8} onPress={() => { setEventId(null); setEventName(""); }}><Ionicons name="close-circle" size={18} color={colors.muted} /></Pressable>
            ) : (
              <Ionicons name="chevron-down" size={16} color={colors.muted} />
            )}
          </Pressable>

          {/* Dates + GST */}
          <Text style={styles.section}>Invoice details</Text>
          <View style={styles.two}>
            <View style={{ flex: 1 }}><DatePickerField label="Issue date" value={issueDate} onChange={setIssueDate} testID="issue-date-picker" /></View>
            <View style={{ flex: 1 }}><DatePickerField label="Due date" value={dueDate} onChange={setDueDate} testID="due-date-picker" emptyLabel="No due date" /></View>
          </View>
          <Text style={styles.fieldLabel}>GST type</Text>
          <View style={styles.modeRow}>
            {GST_MODES.map((m) => (
              <Pressable key={m.key} testID={`gst-${m.key}`} onPress={() => setGstMode(m.key)} style={[styles.modeBtn, gstMode === m.key && styles.modeBtnActive]}>
                <Text style={[styles.modeLabel, gstMode === m.key && styles.modeLabelActive]}>{m.label}</Text>
              </Pressable>
            ))}
          </View>
          <TextField label="Place of supply" value={placeOfSupply} onChangeText={setPlaceOfSupply} placeholder="Karnataka (29)" />

          {/* Line items */}
          <Text style={styles.section}>Items</Text>
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
              <TextField label="Description" value={r.description} onChangeText={(t) => updateRow(idx, "description", t)} placeholder="Wedding Photography" testID={`item-desc-${idx}`} />
              <View style={styles.two}>
                <View style={{ flex: 1 }}><TextField label="HSN/SAC" value={r.hsn_sac} onChangeText={(t) => updateRow(idx, "hsn_sac", t)} placeholder="998383" keyboardType="numeric" /></View>
                <View style={{ flex: 1 }}><TextField label="Qty" value={r.qty} onChangeText={(t) => updateRow(idx, "qty", t)} keyboardType="numeric" /></View>
              </View>
              <View style={styles.two}>
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

          <TextField label="Discount (₹)" value={discount} onChangeText={setDiscount} keyboardType="numeric" placeholder="0" error={discountTooHigh ? `Can't exceed the subtotal (${formatINR(totals.subtotal)})` : undefined} />
          <TextField label="Advance received (₹)" value={advance} onChangeText={setAdvance} keyboardType="numeric" placeholder="0" testID="advance-input" />
          {advanceExceedsTotal ? <Text style={styles.helper}>This is more than the invoice total ({formatINR(totals.total)}).</Text> : null}
          {!!(Number(advance) || 0) && (
            <Text style={styles.helper}>Balance due after advance: {formatINR(Math.max(totals.total - (Number(advance) || 0), 0))}</Text>
          )}

          {/* Live totals */}
          <View style={styles.totalsCard}>
            <TotalRow label="Taxable value" value={totals.taxable_total} />
            {gstMode === "cgst_sgst" && (<><TotalRow label="CGST" value={totals.cgst_total} /><TotalRow label="SGST" value={totals.sgst_total} /></>)}
            {gstMode === "igst" && <TotalRow label="IGST" value={totals.igst_total} />}
            {!!totals.round_off && <TotalRow label="Round off" value={totals.round_off} />}
            <View style={styles.grandRow}>
              <Text style={styles.grandLabel}>Total</Text>
              <Text style={styles.grandValue}>{formatINR(totals.total)}</Text>
            </View>
          </View>

          <TextField label="Notes" value={notes} onChangeText={setNotes} multiline placeholder="optional" />
          <TextField label="Terms" value={terms} onChangeText={setTerms} multiline placeholder="Payment terms…" />

          <Button testID="save-invoice" title={isEdit ? "Update invoice" : "Create invoice"} icon="checkmark-circle-outline" loading={saving} onPress={save} style={{ marginTop: spacing.md }} />
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Client picker modal */}
      <PickerModal
        visible={clientPicker}
        title="Select client"
        onClose={() => setClientPicker(false)}
        data={clients}
        emptyText="No clients yet. Type the name below instead."
        keyExtractor={(c) => c.client_id}
        renderLabel={(c) => c.name}
        onPick={pickClient}
      />
      {/* Event picker modal */}
      <PickerModal
        visible={eventPicker}
        title="Link a gallery"
        onClose={() => setEventPicker(false)}
        data={events}
        emptyText="No galleries yet."
        keyExtractor={(e) => e.event_id}
        renderLabel={(e) => `${e.name}${e.value ? `  ·  ${formatINR(e.value)}` : ""}`}
        onPick={pickEvent}
      />
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

function PickerModal({ visible, title, onClose, data, emptyText, keyExtractor, renderLabel, onPick }: {
  visible: boolean; title: string; onClose: () => void; data: any[]; emptyText: string;
  keyExtractor: (x: any) => string; renderLabel: (x: any) => string; onPick: (x: any) => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.modalBackdrop} onPress={onClose}>
        <Pressable style={styles.modalCard} onPress={() => {}}>
          <View style={styles.modalHead}>
            <Text style={styles.modalTitle}>{title}</Text>
            <Pressable hitSlop={8} onPress={onClose}><Ionicons name="close" size={22} color={colors.muted} /></Pressable>
          </View>
          <ScrollView style={{ maxHeight: 420 }}>
            {data.length === 0 ? (
              <Text style={styles.modalEmpty}>{emptyText}</Text>
            ) : (
              data.map((item) => (
                <Pressable key={keyExtractor(item)} style={styles.modalRow} onPress={() => onPick(item)}>
                  <Text style={styles.modalRowText} numberOfLines={1}>{renderLabel(item)}</Text>
                  <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                </Pressable>
              ))
            )}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  section: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing.lg, marginBottom: spacing.md },
  helper: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginBottom: spacing.md, lineHeight: 18 },
  fieldLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600", marginBottom: spacing.sm },
  two: { flexDirection: "row", gap: spacing.sm },
  pickerBtn: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.lg },
  pickerText: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
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
