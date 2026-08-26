import { useState } from "react";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import DatePickerField, { todayIso } from "@/src/components/DatePickerField";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { goBackOr } from "@/src/navigation/back";


const TYPES = [
  { key: "family", label: "Family", icon: "people" },
  { key: "individual", label: "Individual", icon: "person" },
  { key: "corporate", label: "Corporate", icon: "business" },
];
const STATUSES = [
  { key: "active", label: "Active" },
  { key: "lead", label: "Lead" },
  { key: "past", label: "Past" },
];

type Contact = { name: string; role: string; phone: string; email: string; is_primary: boolean };
type ImpDate = { person_label: string; occasion: string; date: string };

export default function NewClient() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [name, setName] = useState("");
  const [type, setType] = useState("family");
  const [status, setStatus] = useState("active");
  const [tags, setTags] = useState("");
  const [notes, setNotes] = useState("");
  const [contacts, setContacts] = useState<Contact[]>([
    { name: "", role: "", phone: "", email: "", is_primary: true },
  ]);
  const [dates, setDates] = useState<ImpDate[]>([]);
  const [loading, setLoading] = useState(false);

  const updateContact = (i: number, patch: Partial<Contact>) =>
    setContacts((prev) => prev.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  const setPrimary = (i: number) =>
    setContacts((prev) => prev.map((c, idx) => ({ ...c, is_primary: idx === i })));
  const addContact = () =>
    setContacts((prev) => [...prev, { name: "", role: "", phone: "", email: "", is_primary: prev.length === 0 }]);
  const removeContact = (i: number) => setContacts((prev) => prev.filter((_, idx) => idx !== i));

  const updateDate = (i: number, patch: Partial<ImpDate>) =>
    setDates((prev) => prev.map((d, idx) => (idx === i ? { ...d, ...patch } : d)));
  const addDate = () => setDates((prev) => [...prev, { person_label: "", occasion: "Birthday", date: todayIso() }]);
  const removeDate = (i: number) => setDates((prev) => prev.filter((_, idx) => idx !== i));

  const save = async () => {
    if (!name.trim()) {
      toast.show("Give this client a name (e.g. Sharma Family)", "error");
      return;
    }
    const cleanContacts = contacts
      .filter((c) => c.name.trim())
      .map((c) => ({
        name: c.name.trim(),
        role: c.role.trim() || undefined,
        phone: c.phone.trim() || undefined,
        email: c.email.trim() || undefined,
        is_primary: c.is_primary,
      }));
    const cleanDates = dates
      .filter((d) => d.person_label.trim() && d.date.trim())
      .map((d) => ({ person_label: d.person_label.trim(), occasion: d.occasion.trim() || "Birthday", date: d.date.trim() }));

    setLoading(true);
    try {
      const res = await api.post("/clients", {
        name: name.trim(),
        type,
        status,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        notes: notes.trim() || undefined,
        contacts: cleanContacts,
        important_dates: cleanDates,
      });
      toast.show("Client created", "success");
      router.replace(`/admin/client/${res.client_id}`);
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not create client", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container} testID="new-client-screen">
      <GlassHeader title="New Client" onBack={() => goBackOr(router, "/admin/clients")} topInset={insets.top} />
      <KeyboardAwareScrollView
        contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing["2xl"] }]}
        bottomOffset={24}
        keyboardShouldPersistTaps="handled"
      >
        <TextField testID="client-name-input" label="Client / Family name" value={name} onChangeText={setName} placeholder="Sharma Family" />

        <Text style={styles.label}>Type</Text>
        <View style={styles.chipWrap}>
          {TYPES.map((t) => (
            <Pressable key={t.key} testID={`type-${t.key}`} onPress={() => setType(t.key)} style={[styles.chip, type === t.key && styles.chipActive]}>
              <Ionicons name={t.icon as any} size={14} color={type === t.key ? colors.onBrand : colors.onSurfaceTertiary} />
              <Text style={[styles.chipText, type === t.key && styles.chipTextActive]}>{t.label}</Text>
            </Pressable>
          ))}
        </View>

        <Text style={[styles.label, { marginTop: spacing.xl }]}>Status</Text>
        <View style={styles.chipWrap}>
          {STATUSES.map((s) => (
            <Pressable key={s.key} testID={`status-${s.key}`} onPress={() => setStatus(s.key)} style={[styles.chip, status === s.key && styles.chipActive]}>
              <Text style={[styles.chipText, status === s.key && styles.chipTextActive]}>{s.label}</Text>
            </Pressable>
          ))}
        </View>

        <View style={{ marginTop: spacing.xl }}>
          <TextField testID="client-tags-input" label="Tags (comma separated)" value={tags} onChangeText={setTags} placeholder="wedding, high-value" autoCapitalize="none" />
        </View>

        {/* Contacts */}
        <View style={styles.sectionHead}>
          <Text style={styles.sectionTitle}>Contacts</Text>
          <Pressable testID="add-contact-btn" onPress={addContact} style={styles.addBtn} hitSlop={8}>
            <Ionicons name="add" size={16} color={colors.brand} />
            <Text style={styles.addBtnText}>Add</Text>
          </Pressable>
        </View>
        {contacts.map((c, i) => (
          <View key={i} style={styles.card}>
            <View style={styles.cardHead}>
              <Pressable testID={`contact-primary-${i}`} onPress={() => setPrimary(i)} style={styles.primaryToggle} hitSlop={6}>
                <Ionicons name={c.is_primary ? "star" : "star-outline"} size={16} color={c.is_primary ? colors.brand : colors.muted} />
                <Text style={[styles.primaryText, c.is_primary && { color: colors.brand }]}>Primary</Text>
              </Pressable>
              {contacts.length > 1 ? (
                <Pressable onPress={() => removeContact(i)} hitSlop={6}>
                  <Ionicons name="trash-outline" size={18} color={colors.onError} />
                </Pressable>
              ) : null}
            </View>
            <TextField testID={`contact-name-${i}`} label="Name" value={c.name} onChangeText={(v) => updateContact(i, { name: v })} placeholder="Priya Sharma" />
            <TextField testID={`contact-role-${i}`} label="Role" value={c.role} onChangeText={(v) => updateContact(i, { role: v })} placeholder="Bride / Groom / Father…" />
            <TextField testID={`contact-phone-${i}`} label="Phone" value={c.phone} onChangeText={(v) => updateContact(i, { phone: v })} placeholder="+91…" keyboardType="phone-pad" />
            <TextField testID={`contact-email-${i}`} label="Email" value={c.email} onChangeText={(v) => updateContact(i, { email: v })} placeholder="name@email.com" autoCapitalize="none" keyboardType="email-address" />
          </View>
        ))}

        {/* Important dates */}
        <View style={styles.sectionHead}>
          <Text style={styles.sectionTitle}>Important Dates</Text>
          <Pressable testID="add-date-btn" onPress={addDate} style={styles.addBtn} hitSlop={8}>
            <Ionicons name="add" size={16} color={colors.brand} />
            <Text style={styles.addBtnText}>Add</Text>
          </Pressable>
        </View>
        {dates.length === 0 ? (
          <Text style={styles.hint}>Birthdays, anniversaries & milestones — power future reminders.</Text>
        ) : null}
        {dates.map((d, i) => (
          <View key={i} style={styles.card}>
            <View style={styles.cardHead}>
              <Text style={styles.cardHint}>Occasion</Text>
              <Pressable onPress={() => removeDate(i)} hitSlop={6}>
                <Ionicons name="trash-outline" size={18} color={colors.onError} />
              </Pressable>
            </View>
            <TextField testID={`date-person-${i}`} label="Person" value={d.person_label} onChangeText={(v) => updateDate(i, { person_label: v })} placeholder="Priya" />
            <TextField testID={`date-occasion-${i}`} label="Occasion" value={d.occasion} onChangeText={(v) => updateDate(i, { occasion: v })} placeholder="Birthday / Anniversary" />
            <DatePickerField
              testID={`date-date-${i}`}
              label="Date"
              value={d.date}
              onChange={(v) => updateDate(i, { date: v })}
            />
          </View>
        ))}

        <View style={{ marginTop: spacing.xl }}>
          <TextField testID="client-notes-input" label="Notes" value={notes} onChangeText={setNotes} placeholder="Anything worth remembering…" multiline />
          <Button testID="save-client-btn" title="Create client" loading={loading} onPress={save} icon="checkmark" />
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl },
  label: { color: colors.onSurfaceSecondary, fontSize: fontSize.sm, marginBottom: spacing.md, fontFamily: fonts.text, letterSpacing: 0.5, textTransform: "uppercase" },
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: spacing.lg, height: 40, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  chipTextActive: { color: colors.onBrand, fontWeight: "600" },
  sectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing["2xl"], marginBottom: spacing.md },
  sectionTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  addBtn: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: spacing.md, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: colors.brandTertiary },
  addBtnText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.md, borderWidth: 1, borderColor: colors.border },
  cardHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  cardHint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, textTransform: "uppercase", letterSpacing: 0.5 },
  primaryToggle: { flexDirection: "row", alignItems: "center", gap: 6 },
  primaryText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base },
  hint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginBottom: spacing.md, lineHeight: 18 },
});
