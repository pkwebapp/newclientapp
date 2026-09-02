import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "expo-router";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { goBackOr } from "@/src/navigation/back";
import { urlError } from "@/src/utils/validators";

type Audience = "gallery" | "all_clients" | "specific";

type ClientRow = {
  client_id?: string;
  user_id?: string;
  name?: string;
  full_name?: string;
  email?: string;
  phone?: string;
};

const TITLE_MAX = 120;
const BODY_MAX = 500;

export default function NotifyBroadcast() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [audience, setAudience] = useState<Audience>("gallery");
  const [events, setEvents] = useState<any[]>([]);
  const [eventId, setEventId] = useState<string | null>(null);
  const [showEventPicker, setShowEventPicker] = useState(false);

  const [clients, setClients] = useState<ClientRow[]>([]);
  const [selectedClientIds, setSelectedClientIds] = useState<string[]>([]);
  const [clientSearch, setClientSearch] = useState("");
  const [showClientPicker, setShowClientPicker] = useState(false);

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [actionUrl, setActionUrl] = useState("");
  const urlErr = urlError(actionUrl);

  const [galleryCount, setGalleryCount] = useState<number | null>(null);
  const [allClientsCount, setAllClientsCount] = useState<number | null>(null);
  const [sending, setSending] = useState(false);
  const [loadingLists, setLoadingLists] = useState(true);

  const loadLists = useCallback(async () => {
    setLoadingLists(true);
    try {
      const [evs, cls] = await Promise.all([
        api.get("/events").catch(() => []),
        api.get("/clients").catch(() => []),
      ]);
      setEvents(Array.isArray(evs) ? evs : []);
      setClients(Array.isArray(cls) ? cls : []);
      const sum = await api.get("/notifications/audiences/summary").catch(() => ({}));
      setAllClientsCount(typeof sum?.all_clients === "number" ? sum.all_clients : 0);
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not load data", "error");
    } finally {
      setLoadingLists(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadLists();
  }, [loadLists]);

  // Refresh gallery count whenever the picked event changes.
  useEffect(() => {
    let alive = true;
    if (!eventId) {
      setGalleryCount(null);
      return;
    }
    (async () => {
      try {
        const sum = await api.get(`/notifications/audiences/summary?event_id=${eventId}`);
        if (alive) setGalleryCount(typeof sum?.gallery === "number" ? sum.gallery : 0);
      } catch {
        if (alive) setGalleryCount(0);
      }
    })();
    return () => {
      alive = false;
    };
  }, [eventId]);

  const selectedEvent = useMemo(
    () => events.find((e) => e.event_id === eventId) || null,
    [events, eventId]
  );

  const filteredClients = useMemo(() => {
    const q = clientSearch.trim().toLowerCase();
    if (!q) return clients;
    return clients.filter((c) => {
      const bag = `${c.name || c.full_name || ""} ${c.email || ""} ${c.phone || ""}`.toLowerCase();
      return bag.includes(q);
    });
  }, [clients, clientSearch]);

  const recipientCount = useMemo(() => {
    if (audience === "gallery") return galleryCount ?? 0;
    if (audience === "all_clients") return allClientsCount ?? 0;
    return selectedClientIds.length;
  }, [audience, galleryCount, allClientsCount, selectedClientIds]);

  const canSend =
    title.trim().length > 0 &&
    body.trim().length > 0 &&
    !urlErr &&
    !sending &&
    ((audience === "gallery" && !!eventId) ||
      audience === "all_clients" ||
      (audience === "specific" && selectedClientIds.length > 0));

  const send = async () => {
    setSending(true);
    try {
      const payload: any = {
        audience,
        title: title.trim(),
        body: body.trim(),
      };
      if (actionUrl.trim()) payload.action_url = actionUrl.trim();
      if (audience === "gallery") payload.event_id = eventId;
      if (audience === "specific") payload.client_user_ids = selectedClientIds;
      const res: any = await api.post("/notifications/broadcast", payload);
      if (res?.status === "no_recipients") {
        toast.show("No recipients matched — no notifications sent.", "error");
      } else {
        toast.show(
          `Sent to ${res?.sent ?? 0}${res?.skipped_prefs ? ` (${res.skipped_prefs} opted out)` : ""}`,
          "success"
        );
        setTitle("");
        setBody("");
        setActionUrl("");
        setSelectedClientIds([]);
      }
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Send failed", "error");
    } finally {
      setSending(false);
    }
  };

  const AudienceRadio = ({
    value,
    icon,
    label,
    hint,
  }: {
    value: Audience;
    icon: string;
    label: string;
    hint: string;
  }) => {
    const selected = audience === value;
    return (
      <Pressable
        testID={`audience-${value}`}
        onPress={() => setAudience(value)}
        style={[styles.radio, selected && styles.radioSelected]}
      >
        <View style={[styles.radioIcon, selected && styles.radioIconSelected]}>
          <Ionicons name={icon as any} size={18} color={selected ? colors.onBrand : colors.brand} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.radioLabel}>{label}</Text>
          <Text style={styles.radioHint}>{hint}</Text>
        </View>
        <Ionicons
          name={selected ? "radio-button-on" : "radio-button-off"}
          size={20}
          color={selected ? colors.brand : colors.muted}
        />
      </Pressable>
    );
  };

  return (
    <View style={styles.container} testID="notify-screen">
      <GlassHeader
        title="Send announcement"
        onBack={() => goBackOr(router, "/admin")}
        topInset={insets.top}
      />
      {loadingLists ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : (
        <KeyboardAwareScrollView
          contentContainerStyle={[
            styles.body,
            { paddingBottom: insets.bottom + spacing["2xl"] },
          ]}
          bottomOffset={40}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.info}>
            <Ionicons name="megaphone-outline" size={16} color={colors.brand} />
            <Text style={styles.infoText}>
              Send in-app notifications (and push where available) to your clients.
              They can opt out per-type in their own settings.
            </Text>
          </View>

          <Text style={styles.section}>Who should get this?</Text>
          <View style={{ gap: spacing.sm }}>
            <AudienceRadio
              value="gallery"
              icon="images-outline"
              label="One gallery's guests"
              hint={
                selectedEvent
                  ? `${selectedEvent.title || "Selected gallery"} · ${galleryCount ?? "…"} recipients`
                  : "Pick a gallery below"
              }
            />
            <AudienceRadio
              value="all_clients"
              icon="people-outline"
              label="All my clients"
              hint={`${allClientsCount ?? 0} recipients across every gallery`}
            />
            <AudienceRadio
              value="specific"
              icon="person-outline"
              label="Specific clients"
              hint={
                selectedClientIds.length
                  ? `${selectedClientIds.length} selected`
                  : "Pick one or more clients"
              }
            />
          </View>

          {audience === "gallery" ? (
            <Pressable
              testID="pick-gallery"
              onPress={() => setShowEventPicker(true)}
              style={styles.picker}
            >
              <Ionicons name="images-outline" size={18} color={colors.brand} />
              <Text style={styles.pickerText}>
                {selectedEvent ? selectedEvent.title || "Selected gallery" : "Choose a gallery…"}
              </Text>
              <Ionicons name="chevron-down" size={16} color={colors.muted} />
            </Pressable>
          ) : null}

          {audience === "specific" ? (
            <Pressable
              testID="pick-clients"
              onPress={() => setShowClientPicker(true)}
              style={styles.picker}
            >
              <Ionicons name="person-outline" size={18} color={colors.brand} />
              <Text style={styles.pickerText}>
                {selectedClientIds.length
                  ? `${selectedClientIds.length} client${selectedClientIds.length === 1 ? "" : "s"} selected`
                  : "Choose clients…"}
              </Text>
              <Ionicons name="chevron-down" size={16} color={colors.muted} />
            </Pressable>
          ) : null}

          <Text style={styles.section}>Your message</Text>

          <TextField
            testID="notify-title"
            label={`Title (${title.length}/${TITLE_MAX})`}
            value={title}
            onChangeText={(v) => setTitle(v.slice(0, TITLE_MAX))}
            placeholder="A short, clear headline"
          />
          <TextField
            testID="notify-body"
            label={`Message (${body.length}/${BODY_MAX})`}
            value={body}
            onChangeText={(v) => setBody(v.slice(0, BODY_MAX))}
            placeholder="Type the message your clients will see"
            multiline
            numberOfLines={4}
          />
          <TextField
            testID="notify-url"
            label="Link (optional)"
            value={actionUrl}
            onChangeText={setActionUrl}
            placeholder="/client/event/… or https://…"
            autoCapitalize="none"
          error={urlErr || undefined}
          />

          {/* Preview card */}
          <View style={styles.previewWrap}>
            <Text style={styles.previewLabel}>Preview</Text>
            <View style={styles.preview}>
              <View style={styles.previewIcon}>
                <Ionicons name="notifications" size={16} color={colors.brand} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.previewTitle}>{title || "Your headline"}</Text>
                <Text style={styles.previewBody}>
                  {body || "Your message will appear here."}
                </Text>
                {actionUrl.trim() ? (
                  <Text style={styles.previewLink}>Open →</Text>
                ) : null}
              </View>
            </View>
          </View>

          <View style={styles.sendRow}>
            <Text style={styles.recipients}>
              Sending to <Text style={styles.recipientsCount}>{recipientCount}</Text>{" "}
              recipient{recipientCount === 1 ? "" : "s"}
            </Text>
            <Button
              testID="notify-send-btn"
              title={sending ? "Sending…" : "Send now"}
              icon="paper-plane"
              loading={sending}
              onPress={send}
              disabled={!canSend}
            />
          </View>
        </KeyboardAwareScrollView>
      )}

      {/* Gallery picker modal */}
      <Modal visible={showEventPicker} transparent animationType="fade" onRequestClose={() => setShowEventPicker(false)}>
        <Pressable style={styles.backdrop} onPress={() => setShowEventPicker(false)}>
          <Pressable style={styles.pickerPanel} onPress={() => {}}>
            <View style={styles.pickerHead}>
              <Text style={styles.pickerHeadTitle}>Choose a gallery</Text>
              <Pressable onPress={() => setShowEventPicker(false)} style={styles.close}>
                <Ionicons name="close" size={18} color={colors.muted} />
              </Pressable>
            </View>
            <ScrollView>
              {events.length === 0 ? (
                <Text style={styles.emptyPicker}>You don&apos;t have any galleries yet.</Text>
              ) : (
                events.map((e) => (
                  <Pressable
                    key={e.event_id}
                    onPress={() => {
                      setEventId(e.event_id);
                      setShowEventPicker(false);
                    }}
                    style={[styles.pickerRow, eventId === e.event_id && styles.pickerRowSel]}
                  >
                    <Ionicons
                      name={eventId === e.event_id ? "checkmark-circle" : "images-outline"}
                      size={18}
                      color={eventId === e.event_id ? colors.brand : colors.muted}
                    />
                    <Text style={styles.pickerRowText} numberOfLines={1}>
                      {e.title || "Untitled gallery"}
                    </Text>
                  </Pressable>
                ))
              )}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>

      {/* Client picker modal */}
      <Modal visible={showClientPicker} transparent animationType="fade" onRequestClose={() => setShowClientPicker(false)}>
        <Pressable style={styles.backdrop} onPress={() => setShowClientPicker(false)}>
          <Pressable style={styles.pickerPanel} onPress={() => {}}>
            <View style={styles.pickerHead}>
              <Text style={styles.pickerHeadTitle}>Choose clients</Text>
              <Pressable onPress={() => setShowClientPicker(false)} style={styles.close}>
                <Ionicons name="close" size={18} color={colors.muted} />
              </Pressable>
            </View>
            <TextField
              testID="client-search"
              label="Search"
              value={clientSearch}
              onChangeText={setClientSearch}
              placeholder="Name, email or phone"
              autoCapitalize="none"
            />
            <ScrollView>
              {filteredClients.length === 0 ? (
                <Text style={styles.emptyPicker}>No matching clients.</Text>
              ) : (
                filteredClients.map((c) => {
                  const uid = c.user_id || c.client_id;
                  if (!uid) return null;
                  const on = selectedClientIds.includes(uid);
                  return (
                    <Pressable
                      key={uid}
                      onPress={() =>
                        setSelectedClientIds((cur) =>
                          on ? cur.filter((x) => x !== uid) : [...cur, uid]
                        )
                      }
                      style={[styles.pickerRow, on && styles.pickerRowSel]}
                    >
                      <Ionicons
                        name={on ? "checkbox" : "square-outline"}
                        size={18}
                        color={on ? colors.brand : colors.muted}
                      />
                      <View style={{ flex: 1 }}>
                        <Text style={styles.pickerRowText}>
                          {c.name || c.full_name || "Unnamed"}
                        </Text>
                        <Text style={styles.pickerRowSub}>
                          {c.email || c.phone || ""}
                        </Text>
                      </View>
                    </Pressable>
                  );
                })
              )}
            </ScrollView>
            <Button
              testID="client-picker-done"
              title={`Done · ${selectedClientIds.length} selected`}
              onPress={() => setShowClientPicker(false)}
              icon="checkmark"
            />
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  body: { padding: spacing.xl, gap: spacing.md },

  info: {
    flexDirection: "row",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.brandTertiary,
  },
  infoText: { flex: 1, color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18 },

  section: {
    color: colors.onSurface,
    fontFamily: fonts.text,
    fontSize: fontSize.sm,
    fontWeight: "700",
    letterSpacing: 1,
    marginTop: spacing.md,
    textTransform: "uppercase",
  },

  radio: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
    minHeight: 60,
  },
  radioSelected: { borderColor: colors.brand, backgroundColor: colors.brandTertiary },
  radioIcon: { width: 36, height: 36, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
  radioIconSelected: { backgroundColor: colors.brand },
  radioLabel: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  radioHint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },

  picker: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    minHeight: 48,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.surfaceSecondary,
  },
  pickerText: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },

  previewWrap: { marginTop: spacing.lg },
  previewLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginBottom: spacing.xs, textTransform: "uppercase", letterSpacing: 1 },
  preview: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.brandTertiary },
  previewIcon: { width: 32, height: 32, borderRadius: radius.pill, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  previewTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  previewBody: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginTop: 3 },
  previewLink: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 6, fontWeight: "700" },

  sendRow: { marginTop: spacing.lg, gap: spacing.md },
  recipients: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  recipientsCount: { color: colors.onSurface, fontWeight: "800" },

  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "center", padding: spacing.lg },
  pickerPanel: { maxWidth: 460, width: "100%", alignSelf: "center", maxHeight: "80%", backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.lg, gap: spacing.md },
  pickerHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  pickerHeadTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  close: { width: 36, height: 36, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceTertiary },
  pickerRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, minHeight: 48, paddingHorizontal: spacing.md, borderRadius: radius.md, marginBottom: 4 },
  pickerRowSel: { backgroundColor: colors.brandTertiary },
  pickerRowText: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  pickerRowSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  emptyPicker: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, textAlign: "center", padding: spacing.lg },
});
