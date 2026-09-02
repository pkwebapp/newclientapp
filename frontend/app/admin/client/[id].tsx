import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
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
import { Image } from "expo-image";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, Pill, GlassHeader, useToast } from "@/src/components/ui";
import { PhoneField } from "@/src/components/PhoneField";
import DatePickerField, { todayIso } from "@/src/components/DatePickerField";
import { formatINR } from "@/src/utils/format";
import { emailError } from "@/src/utils/validators";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

const statusTone = (s: string) => (s === "active" ? "success" : s === "lead" ? "gold" : "neutral");
const TYPE_LABEL: Record<string, string> = { family: "Family", individual: "Individual", corporate: "Corporate" };

export async function generateStaticParams(): Promise<Record<string, string>[]> {
  return [];
}

export default function ClientProfile() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [client, setClient] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // modal state
  const [editClient, setEditClient] = useState(false);
  const [contactModal, setContactModal] = useState<any>(null); // {contact?} or null
  const [dateModal, setDateModal] = useState<any>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = useCallback(async () => {
    try {
      setClient(await api.get(`/clients/${id}`));
    } catch {
      toast.show("Could not load client", "error");
    } finally {
      setLoading(false);
    }
  }, [id, toast]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const deleteClient = async () => {
    setBusy(true);
    try {
      await api.del(`/clients/${id}`);
      toast.show("Client deleted", "success");
      router.replace("/admin/clients");
    } catch {
      toast.show("Could not delete client", "error");
    } finally {
      setBusy(false);
      setConfirmDelete(false);
    }
  };

  const removeContact = async (contactId: string) => {
    try {
      await api.del(`/clients/${id}/contacts/${contactId}`);
      toast.show("Contact removed", "success");
      load();
    } catch {
      toast.show("Could not remove contact", "error");
    }
  };
  const removeDate = async (dateId: string) => {
    try {
      await api.del(`/clients/${id}/important-dates/${dateId}`);
      toast.show("Date removed", "success");
      load();
    } catch {
      toast.show("Could not remove date", "error");
    }
  };

  if (loading) {
    return (
      <View style={styles.center} testID="client-profile-loading">
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }
  if (!client) return null;

  const s = client.stats || {};

  return (
    <View style={styles.container} testID="client-profile-screen">
      <GlassHeader
        title={client.name}
        subtitle={TYPE_LABEL[client.type]}
        onBack={() => router.push("/admin/clients")}
        topInset={insets.top}
        right={
          <View style={{ flexDirection: "row", gap: spacing.md }}>
            <Pressable testID="edit-client-btn" onPress={() => setEditClient(true)} hitSlop={8}>
              <Ionicons name="create-outline" size={22} color={colors.onSurfaceTertiary} />
            </Pressable>
            <Pressable testID="delete-client-btn" onPress={() => setConfirmDelete(true)} hitSlop={8}>
              <Ionicons name="trash-outline" size={22} color={colors.onError} />
            </Pressable>
          </View>
        }
      />

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing["2xl"] }}>
        {/* Status + tags */}
        <View style={styles.tagRow}>
          <Pill label={client.status} tone={statusTone(client.status) as any} />
          {(client.tags || []).map((t: string) => (
            <Pill key={t} label={t} tone="neutral" />
          ))}
        </View>

        {/* Stats */}
        <View style={styles.statsRow}>
          <Stat icon="albums-outline" label="Events" value={String(s.event_count || 0)} />
          <Stat icon="cash-outline" label="Lifetime" value={formatINR(s.lifetime_value)} />
        </View>
        <View style={styles.statsRow}>
          <Stat icon="people-outline" label="Contacts" value={String(s.contact_count || 0)} />
          <Stat icon="calendar-outline" label="Dates" value={String(s.date_count || 0)} />
        </View>

        {client.notes ? (
          <View style={styles.notesBox}>
            <Ionicons name="document-text-outline" size={16} color={colors.muted} />
            <Text style={styles.notesText}>{client.notes}</Text>
          </View>
        ) : null}

        {client.user_profile ? (
          <View style={styles.userProfileBox}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>Client profile</Text>
              <Pill label="Submitted by client" tone="success" />
            </View>
            {client.user_profile.profile_photo_base64 ? (
              <Image source={{ uri: client.user_profile.profile_photo_base64 }} style={styles.profilePhoto} contentFit="cover" />
            ) : null}
            <ProfileLine label="Full name" value={client.user_profile.full_name} />
            <ProfileLine label="Gender" value={client.user_profile.gender} />
            <ProfileLine label="Mobile" value={client.user_profile.phone} />
            <ProfileLine label="Email" value={client.user_profile.email} />
            <ProfileLine label="City" value={client.user_profile.city} />
            <ProfileLine label="Date of birth" value={client.user_profile.dob} />
            <ProfileLine label="Profession" value={client.user_profile.profession} />
            <ProfileLine label="Company" value={client.user_profile.company} />
            <ProfileLine label="About" value={client.user_profile.about} />
            <ProfileLine label="Instagram" value={client.user_profile.instagram} />
            <ProfileLine label="Website" value={client.user_profile.website} />
          </View>
        ) : null}

        {/* Contacts */}
        <Section
          title="Contacts"
          onAdd={() => setContactModal({})}
          empty={(client.contacts || []).length === 0}
          emptyText="Add the people in this family — bride, groom, parents, billing contact."
        >
          {(client.contacts || []).map((c: any) => (
            <View key={c.contact_id} style={styles.itemRow}>
              <View style={styles.itemIcon}>
                <Ionicons name="person" size={18} color={colors.brand} />
              </View>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  <Text style={styles.itemTitle} numberOfLines={1}>{c.name}</Text>
                  {c.is_primary ? <Ionicons name="star" size={13} color={colors.brand} /> : null}
                </View>
                <Text style={styles.itemSub} numberOfLines={1}>
                  {[c.role, c.phone, c.email].filter(Boolean).join(" · ") || "No details"}
                </Text>
              </View>
              <Pressable testID={`edit-contact-${c.contact_id}`} onPress={() => setContactModal(c)} hitSlop={8} style={styles.itemAction}>
                <Ionicons name="create-outline" size={18} color={colors.onSurfaceTertiary} />
              </Pressable>
              <Pressable testID={`del-contact-${c.contact_id}`} onPress={() => removeContact(c.contact_id)} hitSlop={8} style={styles.itemAction}>
                <Ionicons name="trash-outline" size={18} color={colors.onError} />
              </Pressable>
            </View>
          ))}
        </Section>

        {/* Important dates */}
        <Section
          title="Important Dates"
          onAdd={() => setDateModal({})}
          empty={(client.important_dates || []).length === 0}
          emptyText="Birthdays & anniversaries — the foundation for future reminders."
        >
          {(client.important_dates || []).map((d: any) => (
            <View key={d.date_id} style={styles.itemRow}>
              <View style={styles.itemIcon}>
                <Ionicons name={/anniv/i.test(d.occasion) ? "heart" : "gift"} size={18} color={colors.brand} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.itemTitle} numberOfLines={1}>{d.person_label} · {d.occasion}</Text>
                <Text style={styles.itemSub}>{d.date}</Text>
              </View>
              <Pressable testID={`edit-date-${d.date_id}`} onPress={() => setDateModal(d)} hitSlop={8} style={styles.itemAction}>
                <Ionicons name="create-outline" size={18} color={colors.onSurfaceTertiary} />
              </Pressable>
              <Pressable testID={`del-date-${d.date_id}`} onPress={() => removeDate(d.date_id)} hitSlop={8} style={styles.itemAction}>
                <Ionicons name="trash-outline" size={18} color={colors.onError} />
              </Pressable>
            </View>
          ))}
        </Section>

        {/* Events */}
        <View style={styles.sectionHead}>
          <Text style={styles.sectionTitle}>Events</Text>
        </View>
        {(client.events || []).length === 0 ? (
          <Text style={styles.emptyText}>No events linked yet. Create one from the dashboard and attach it to this client.</Text>
        ) : (
          (client.events || []).map((e: any) => (
            <Pressable
              key={e.event_id}
              testID={`client-event-${e.event_id}`}
              onPress={() => router.push(`/admin/event/${e.event_id}`)}
              style={styles.itemRow}
            >
              <View style={styles.itemIcon}>
                <Ionicons name={(categoryMeta[e.category]?.icon as any) || "star"} size={18} color={colors.brand} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.itemTitle} numberOfLines={1}>{e.name}</Text>
                <Text style={styles.itemSub}>
                  {[categoryMeta[e.category]?.label, e.date, `${e.photo_count || 0} photos`].filter(Boolean).join(" · ")}
                </Text>
              </View>
              {e.value ? <Text style={styles.eventValue}>{formatINR(e.value)}</Text> : null}
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </Pressable>
          ))
        )}
      </ScrollView>

      {/* ---------- Modals ---------- */}
      {editClient && (
        <ClientEditModal
          client={client}
          onClose={() => setEditClient(false)}
          onSaved={() => { setEditClient(false); load(); }}
        />
      )}
      {contactModal && (
        <ContactModal
          clientId={id as string}
          contact={contactModal.contact_id ? contactModal : null}
          onClose={() => setContactModal(null)}
          onSaved={() => { setContactModal(null); load(); }}
        />
      )}
      {dateModal && (
        <DateModal
          clientId={id as string}
          date={dateModal.date_id ? dateModal : null}
          onClose={() => setDateModal(null)}
          onSaved={() => { setDateModal(null); load(); }}
        />
      )}
      <ConfirmModal
        visible={confirmDelete}
        title="Delete this client?"
        message="Contacts and important dates will be removed. Linked events (galleries) stay intact but are unlinked."
        confirmLabel="Delete"
        busy={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={deleteClient}
      />
    </View>
  );
}

function Stat({ icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Ionicons name={icon} size={18} color={colors.brand} />
      <Text style={styles.statValue} numberOfLines={1} adjustsFontSizeToFit>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function ProfileLine({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <View style={styles.profileLine}>
      <Text style={styles.profileLabel}>{label}</Text>
      <Text style={styles.profileValue}>{value}</Text>
    </View>
  );
}

function Section({
  title, onAdd, empty, emptyText, children,
}: { title: string; onAdd: () => void; empty: boolean; emptyText: string; children: React.ReactNode }) {
  return (
    <View>
      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitle}>{title}</Text>
        <Pressable testID={`add-${title.replace(/\s/g, "-").toLowerCase()}`} onPress={onAdd} style={styles.addBtn} hitSlop={8}>
          <Ionicons name="add" size={16} color={colors.brand} />
          <Text style={styles.addBtnText}>Add</Text>
        </Pressable>
      </View>
      {empty ? <Text style={styles.emptyText}>{emptyText}</Text> : children}
    </View>
  );
}

// ---------------- Modals ----------------
function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <Modal transparent animationType="fade" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.modalWrap}>
        <View style={styles.modalCard}>
          <View style={styles.modalHead}>
            <Text style={styles.modalTitle}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={8}>
              <Ionicons name="close" size={22} color={colors.onSurfaceTertiary} />
            </Pressable>
          </View>
          <ScrollView keyboardShouldPersistTaps="handled">{children}</ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function ClientEditModal({ client, onClose, onSaved }: any) {
  const toast = useToast();
  const [name, setName] = useState(client.name || "");
  const [status, setStatus] = useState(client.status || "active");
  const [type, setType] = useState(client.type || "family");
  const [tags, setTags] = useState((client.tags || []).join(", "));
  const [notes, setNotes] = useState(client.notes || "");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!name.trim()) { toast.show("Name is required", "error"); return; }
    setBusy(true);
    try {
      await api.patch(`/clients/${client.client_id}`, {
        name: name.trim(), status, type,
        tags: tags.split(",").map((t: string) => t.trim()).filter(Boolean),
        notes: notes.trim(),
      });
      toast.show("Client updated", "success");
      onSaved();
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not update", "error");
    } finally { setBusy(false); }
  };

  return (
    <ModalShell title="Edit client" onClose={onClose}>
      <TextField label="Name" value={name} onChangeText={setName} testID="edit-name-input" />
      <Text style={styles.modalLabel}>Status</Text>
      <View style={styles.chipWrap}>
        {["active", "lead", "past"].map((k) => (
          <Pressable key={k} onPress={() => setStatus(k)} style={[styles.chip, status === k && styles.chipActive]}>
            <Text style={[styles.chipText, status === k && styles.chipTextActive]}>{k}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={[styles.modalLabel, { marginTop: spacing.lg }]}>Type</Text>
      <View style={styles.chipWrap}>
        {["family", "individual", "corporate"].map((k) => (
          <Pressable key={k} onPress={() => setType(k)} style={[styles.chip, type === k && styles.chipActive]}>
            <Text style={[styles.chipText, type === k && styles.chipTextActive]}>{k}</Text>
          </Pressable>
        ))}
      </View>
      <View style={{ marginTop: spacing.lg }}>
        <TextField label="Tags (comma separated)" value={tags} onChangeText={setTags} autoCapitalize="none" />
        <TextField label="Notes" value={notes} onChangeText={setNotes} multiline />
        <Button title="Save changes" loading={busy} onPress={save} testID="save-client-edit-btn" icon="checkmark" />
      </View>
    </ModalShell>
  );
}

function ContactModal({ clientId, contact, onClose, onSaved }: any) {
  const toast = useToast();
  const editing = !!contact;
  const [name, setName] = useState(contact?.name || "");
  const [role, setRole] = useState(contact?.role || "");
  const [phone, setPhone] = useState(contact?.phone || "");
  const [email, setEmail] = useState(contact?.email || "");
  const [isPrimary, setIsPrimary] = useState(!!contact?.is_primary);
  const [busy, setBusy] = useState(false);
  const emailErr = emailError(email);

  const save = async () => {
    if (!name.trim()) { toast.show("Contact name is required", "error"); return; }
    if (emailErr) { toast.show(emailErr, "error"); return; }
    setBusy(true);
    const body = { name: name.trim(), role: role.trim(), phone: phone.trim(), email: email.trim(), is_primary: isPrimary };
    try {
      if (editing) await api.patch(`/clients/${clientId}/contacts/${contact.contact_id}`, body);
      else await api.post(`/clients/${clientId}/contacts`, body);
      toast.show(editing ? "Contact updated" : "Contact added", "success");
      onSaved();
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not save contact", "error");
    } finally { setBusy(false); }
  };

  return (
    <ModalShell title={editing ? "Edit contact" : "Add contact"} onClose={onClose}>
      <TextField label="Name" value={name} onChangeText={setName} testID="contact-modal-name" placeholder="Priya Sharma" />
      <TextField label="Role" value={role} onChangeText={setRole} placeholder="Bride / Groom / Father…" />
      <PhoneField label="Phone" value={phone} onChangeText={setPhone} placeholder="Enter mobile number" required={false} />
      <TextField label="Email" value={email} onChangeText={setEmail} placeholder="name@email.com" autoCapitalize="none" keyboardType="email-address" error={emailErr || undefined} />
      <Pressable onPress={() => setIsPrimary((v) => !v)} style={styles.primaryToggle} testID="contact-modal-primary">
        <Ionicons name={isPrimary ? "checkbox" : "square-outline"} size={20} color={isPrimary ? colors.brand : colors.muted} />
        <Text style={styles.primaryText}>Primary contact</Text>
      </Pressable>
      <Button title={editing ? "Save" : "Add contact"} loading={busy} onPress={save} testID="contact-modal-save" icon="checkmark" />
    </ModalShell>
  );
}

function DateModal({ clientId, date, onClose, onSaved }: any) {
  const toast = useToast();
  const editing = !!date;
  const [person, setPerson] = useState(date?.person_label || "");
  const [occasion, setOccasion] = useState(date?.occasion || "Birthday");
  const [value, setValue] = useState(date?.date || todayIso());
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!person.trim() || !value.trim()) { toast.show("Person and date are required", "error"); return; }
    setBusy(true);
    const body = { person_label: person.trim(), occasion: occasion.trim() || "Birthday", date: value.trim() };
    try {
      if (editing) await api.patch(`/clients/${clientId}/important-dates/${date.date_id}`, body);
      else await api.post(`/clients/${clientId}/important-dates`, body);
      toast.show(editing ? "Date updated" : "Date added", "success");
      onSaved();
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not save date", "error");
    } finally { setBusy(false); }
  };

  return (
    <ModalShell title={editing ? "Edit date" : "Add important date"} onClose={onClose}>
      <TextField label="Person" value={person} onChangeText={setPerson} testID="date-modal-person" placeholder="Priya" />
      <TextField label="Occasion" value={occasion} onChangeText={setOccasion} placeholder="Birthday / Anniversary" />
      <DatePickerField testID="date-modal-date" label="Date" value={value} onChange={setValue} />
      <Button title={editing ? "Save" : "Add date"} loading={busy} onPress={save} testID="date-modal-save" icon="checkmark" />
    </ModalShell>
  );
}

function ConfirmModal({ visible, title, message, confirmLabel, busy, onCancel, onConfirm }: any) {
  if (!visible) return null;
  return (
    <Modal transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.modalWrap}>
        <View style={styles.confirmCard}>
          <Text style={styles.modalTitle}>{title}</Text>
          <Text style={styles.confirmMsg}>{message}</Text>
          <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.lg }}>
            <View style={{ flex: 1 }}><Button title="Cancel" variant="ghost" onPress={onCancel} /></View>
            <View style={{ flex: 1 }}><Button title={confirmLabel} variant="danger" loading={busy} onPress={onConfirm} testID="confirm-delete-btn" /></View>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
  tagRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.lg },
  statsRow: { flexDirection: "row", gap: spacing.md, marginBottom: spacing.md },
  stat: { flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, alignItems: "flex-start" },
  statValue: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing.sm },
  statLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  notesBox: { flexDirection: "row", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginTop: spacing.sm, marginBottom: spacing.sm },
  notesText: { flex: 1, color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 20 },
  userProfileBox: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginTop: spacing.sm, borderWidth: 1, borderColor: colors.border },
  profilePhoto: { width: 72, height: 72, borderRadius: radius.pill, marginBottom: spacing.md },
  profileLine: { flexDirection: "row", gap: spacing.md, paddingVertical: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  profileLabel: { width: 112, color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  profileValue: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  sectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.xl, marginBottom: spacing.md },
  sectionTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  addBtn: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: spacing.md, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: colors.brandTertiary },
  addBtnText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  emptyText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginBottom: spacing.sm },
  itemRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm },
  itemIcon: { width: 38, height: 38, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  itemTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "600" },
  itemSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  itemAction: { padding: 6 },
  eventValue: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  // modal
  modalWrap: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "center", padding: spacing.lg },
  modalCard: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.lg, maxHeight: "86%", borderWidth: 1, borderColor: colors.borderStrong },
  modalHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.lg },
  modalTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  modalLabel: { color: colors.onSurfaceSecondary, fontSize: fontSize.sm, marginBottom: spacing.sm, fontFamily: fonts.text, letterSpacing: 0.5, textTransform: "uppercase" },
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: { paddingHorizontal: spacing.lg, height: 38, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base, textTransform: "capitalize" },
  chipTextActive: { color: colors.onBrand, fontWeight: "600" },
  primaryToggle: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.lg },
  primaryText: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base },
  confirmCard: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.xl, borderWidth: 1, borderColor: colors.borderStrong },
  confirmMsg: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 20, marginTop: spacing.md },
});
