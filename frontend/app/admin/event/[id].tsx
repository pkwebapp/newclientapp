import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError, fileUrl, getAuthToken } from "@/src/api/client";
import { Button, TextField, Pill, GlassHeader, EmptyState, useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

type Tab = "photos" | "access" | "settings";

export default function AdminEvent() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [tab, setTab] = useState<Tab>("photos");
  const [event, setEvent] = useState<any>(null);
  const [photos, setPhotos] = useState<any[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [grants, setGrants] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  // access form
  const [channel, setChannel] = useState<"email" | "phone">("email");
  const [grantValue, setGrantValue] = useState("");
  const [fullAccess, setFullAccess] = useState(false);
  const [threshold, setThreshold] = useState("85");
  const [savingThreshold, setSavingThreshold] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<any>(null);

  const load = useCallback(async () => {
    try {
      const e = await api.get(`/events/${id}`);
      setEvent(e);
      setThreshold(String(Math.round(e.similarity_threshold)));
      const [ps, st, gr, cl] = await Promise.all([
        api.get(`/events/${id}/photos`),
        api.get(`/events/${id}/indexing-status`),
        api.get(`/events/${id}/access`),
        api.get(`/events/${id}/clients`),
      ]);
      setPhotos(ps);
      setStatus(st);
      setGrants(gr);
      setClients(cl);
    } catch (e: any) {
      toast.show(e?.message || "Could not load event", "error");
    } finally {
      setLoading(false);
    }
  }, [id, toast]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const uploadPhotos = async () => {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      toast.show("Photo access is needed to upload", "error");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsMultipleSelection: true,
      quality: 0.8,
    });
    if (result.canceled || !result.assets?.length) return;
    setUploading(true);
    let ok = 0;
    for (const asset of result.assets) {
      try {
        await api.upload(`/events/${id}/photos`, asset.uri, asset.fileName || "photo.jpg", asset.mimeType || "image/jpeg");
        ok++;
      } catch {}
    }
    setUploading(false);
    toast.show(`Uploaded & indexed ${ok} photo${ok !== 1 ? "s" : ""}`, ok ? "success" : "error");
    load();
  };

  const addGrant = async () => {
    if (!grantValue.trim()) {
      toast.show(channel === "email" ? "Enter client email" : "Enter client phone", "error");
      return;
    }
    try {
      const body: any = { channel, full_gallery_access: fullAccess };
      if (channel === "email") body.email = grantValue.trim();
      else body.phone = grantValue.trim();
      await api.post(`/events/${id}/access`, body);
      setGrantValue("");
      setFullAccess(false);
      toast.show("Access granted", "success");
      load();
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not grant access", "error");
    }
  };

  const toggleGrantAccess = async (g: any) => {
    try {
      const form = new FormData();
      form.append("full_gallery_access", String(!g.full_gallery_access));
      await fetch(`${process.env.EXPO_PUBLIC_BACKEND_URL}/api/events/${id}/access/${g.grant_id}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${getAuthToken()}` },
        body: form,
      });
      load();
    } catch {
      toast.show("Could not update access", "error");
    }
  };

  const revokeGrant = async (g: any) => {
    try {
      await api.del(`/events/${id}/access/${g.grant_id}`);
      toast.show("Access revoked", "info");
      load();
    } catch {
      toast.show("Could not revoke", "error");
    }
  };

  const saveThreshold = async () => {
    const t = parseInt(threshold, 10);
    if (isNaN(t) || t < 50 || t > 100) {
      toast.show("Threshold must be 50–100", "error");
      return;
    }
    setSavingThreshold(true);
    try {
      await api.patch(`/events/${id}`, { similarity_threshold: t });
      toast.show("Threshold saved", "success");
      load();
    } catch (e: any) {
      toast.show(e?.message || "Could not save", "error");
    } finally {
      setSavingThreshold(false);
    }
  };

  const deleteFaceData = async (c: any) => {
    setConfirmDelete(null);
    try {
      await api.del(`/events/${id}/clients/${c.client_user_id}/face-data`);
      toast.show("Face data & album deleted", "info");
      load();
    } catch {
      toast.show("Could not delete", "error");
    }
  };

  if (loading) {
    return (
      <View style={styles.center} testID="admin-event-loading">
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }

  return (
    <View style={styles.container} testID="admin-event-screen">
      <GlassHeader title={event?.name} subtitle={categoryMeta[event?.category]?.label} onBack={() => router.back()} topInset={insets.top} />

      <View style={styles.tabs}>
        {(["photos", "access", "settings"] as Tab[]).map((t) => (
          <Pressable key={t} testID={`admin-tab-${t}`} onPress={() => setTab(t)} style={[styles.tab, tab === t && styles.tabActive]}>
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t === "photos" ? "Photos" : t === "access" ? "Access" : "Settings"}
            </Text>
          </Pressable>
        ))}
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing["3xl"] }}>
        {/* ---------------- PHOTOS ---------------- */}
        {tab === "photos" && (
          <>
            <View style={styles.statusCard}>
              <View>
                <Text style={styles.statusTitle}>Indexing status</Text>
                <Text style={styles.statusSub}>
                  {status?.indexed_photos}/{status?.total_photos} indexed · {status?.total_faces} faces detected
                </Text>
              </View>
              <Pill label={event?.indexing_status} tone={event?.indexing_status === "ready" ? "success" : "neutral"} />
            </View>

            <Button testID="upload-photos-btn" title={uploading ? "Uploading…" : "Upload photos"} icon="cloud-upload-outline" loading={uploading} onPress={uploadPhotos} />

            {photos.length === 0 ? (
              <EmptyState icon="images-outline" title="No photos yet" subtitle="Upload event photos — faces are detected and indexed automatically." />
            ) : (
              <View style={styles.thumbGrid}>
                {photos.map((p) => (
                  <View key={p.photo_id} style={styles.thumb} testID={`admin-photo-${p.photo_id}`}>
                    <Image source={{ uri: fileUrl(p.thumb_path) }} style={StyleSheet.absoluteFill} contentFit="cover" transition={150} cachePolicy="memory-disk" />
                    {p.face_count > 0 && (
                      <View style={styles.faceBadge}>
                        <Ionicons name="person" size={10} color={colors.onBrand} />
                        <Text style={styles.faceBadgeText}>{p.face_count}</Text>
                      </View>
                    )}
                  </View>
                ))}
              </View>
            )}
          </>
        )}

        {/* ---------------- ACCESS ---------------- */}
        {tab === "access" && (
          <>
            <Text style={styles.sectionTitle}>Grant access</Text>
            <View style={styles.channelRow}>
              {(["email", "phone"] as const).map((c) => (
                <Pressable key={c} testID={`grant-channel-${c}`} onPress={() => setChannel(c)} style={[styles.channelBtn, channel === c && styles.channelActive]}>
                  <Text style={[styles.channelText, channel === c && styles.channelTextActive]}>{c === "email" ? "Email" : "Phone"}</Text>
                </Pressable>
              ))}
            </View>
            <TextField
              testID="grant-value-input"
              value={grantValue}
              onChangeText={setGrantValue}
              placeholder={channel === "email" ? "client@example.com" : "+1 555 000 1234"}
              autoCapitalize="none"
              keyboardType={channel === "email" ? "email-address" : "phone-pad"}
            />
            <View style={styles.switchRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.switchLabel}>Full gallery access</Text>
                <Text style={styles.switchHint}>Off = client sees only their matched photos</Text>
              </View>
              <Switch testID="grant-full-access-switch" value={fullAccess} onValueChange={setFullAccess} trackColor={{ true: colors.brand, false: colors.surfaceTertiary }} thumbColor={colors.onSurface} />
            </View>
            <Button testID="add-grant-btn" title="Invite client" icon="person-add-outline" onPress={addGrant} />

            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Invited clients ({grants.filter((g) => g.status === "active").length})</Text>
            {grants.length === 0 ? (
              <Text style={styles.muted}>No clients invited yet.</Text>
            ) : (
              grants.map((g) => (
                <View key={g.grant_id} style={styles.grantRow} testID={`grant-${g.grant_id}`}>
                  <Ionicons name={g.channel === "email" ? "mail-outline" : "call-outline"} size={18} color={colors.brand} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.grantValue} numberOfLines={1}>{g.client_email || g.client_phone}</Text>
                    <View style={{ flexDirection: "row", gap: 6, marginTop: 4 }}>
                      <Pill label={g.status === "active" ? "Active" : "Revoked"} tone={g.status === "active" ? "success" : "neutral"} />
                      {g.full_gallery_access && <Pill label="Full gallery" tone="gold" />}
                    </View>
                  </View>
                  {g.status === "active" && (
                    <View style={{ alignItems: "flex-end", gap: 6 }}>
                      <Switch
                        testID={`grant-toggle-${g.grant_id}`}
                        value={g.full_gallery_access}
                        onValueChange={() => toggleGrantAccess(g)}
                        trackColor={{ true: colors.brand, false: colors.surfaceTertiary }}
                        thumbColor={colors.onSurface}
                      />
                      <Pressable testID={`revoke-${g.grant_id}`} onPress={() => revokeGrant(g)} hitSlop={8}>
                        <Text style={styles.revoke}>Revoke</Text>
                      </Pressable>
                    </View>
                  )}
                </View>
              ))
            )}

            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Face data ({clients.length})</Text>
            <Text style={styles.muted}>Clients who have searched. Delete removes their face signature & album.</Text>
            {clients.map((c) => (
              <View key={c.client_user_id} style={styles.grantRow} testID={`client-${c.client_user_id}`}>
                <Ionicons name="person-circle-outline" size={22} color={colors.brand} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.grantValue}>{c.name || c.email || c.phone}</Text>
                  <Text style={styles.muted}>{c.matched_count} matched photos</Text>
                </View>
                <Pressable testID={`delete-face-${c.client_user_id}`} onPress={() => setConfirmDelete(c)} hitSlop={8}>
                  <Ionicons name="trash-outline" size={20} color={colors.onError} />
                </Pressable>
              </View>
            ))}
          </>
        )}

        {/* ---------------- SETTINGS ---------------- */}
        {tab === "settings" && (
          <>
            <Text style={styles.sectionTitle}>Match similarity threshold</Text>
            <Text style={styles.muted}>Higher = stricter matching, fewer false positives.</Text>
            <View style={styles.presetRow}>
              {["80", "85", "90", "95"].map((p) => (
                <Pressable key={p} testID={`preset-${p}`} onPress={() => setThreshold(p)} style={[styles.preset, threshold === p && styles.presetActive]}>
                  <Text style={[styles.presetText, threshold === p && styles.presetTextActive]}>{p}%</Text>
                </Pressable>
              ))}
            </View>
            <TextField testID="threshold-input" label="Custom (50–100)" value={threshold} onChangeText={setThreshold} keyboardType="number-pad" maxLength={3} />
            <Button testID="save-threshold-btn" title="Save threshold" loading={savingThreshold} onPress={saveThreshold} />

            <View style={styles.infoCard}>
              <InfoRow label="Category" value={categoryMeta[event?.category]?.label} />
              <InfoRow label="Date" value={event?.date || "—"} />
              <InfoRow label="Photographer" value={event?.photographer || "—"} />
              <InfoRow label="Photos" value={String(event?.photo_count)} />
            </View>
          </>
        )}
      </ScrollView>

      {/* delete confirm */}
      <Modal visible={!!confirmDelete} transparent animationType="fade" onRequestClose={() => setConfirmDelete(null)}>
        <Pressable style={styles.modalBg} onPress={() => setConfirmDelete(null)}>
          <View style={styles.modalCard} testID="delete-confirm-modal">
            <Ionicons name="trash-outline" size={28} color={colors.onError} />
            <Text style={styles.modalTitle}>Delete face data?</Text>
            <Text style={styles.modalText}>
              This removes {confirmDelete?.name || "this client"}'s face signature and matched album for this event. They can re-scan later.
            </Text>
            <Button testID="confirm-delete-btn" title="Delete" variant="danger" onPress={() => deleteFaceData(confirmDelete)} />
            <Pressable onPress={() => setConfirmDelete(null)} style={{ marginTop: spacing.md, alignItems: "center" }}>
              <Text style={styles.muted}>Cancel</Text>
            </Pressable>
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

function InfoRow({ label, value }: { label: string; value?: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.muted}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  tabs: { flexDirection: "row", backgroundColor: colors.surfaceSecondary, marginHorizontal: spacing.lg, marginTop: spacing.md, borderRadius: radius.md, padding: spacing.xs },
  tab: { flex: 1, paddingVertical: spacing.md, alignItems: "center", borderRadius: radius.sm },
  tabActive: { backgroundColor: colors.brand },
  tabText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  tabTextActive: { color: colors.onBrand, fontWeight: "600" },
  statusCard: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.lg },
  statusTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.lg },
  statusSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  thumbGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.lg },
  thumb: { width: "31.8%", aspectRatio: 1, borderRadius: radius.sm, overflow: "hidden", backgroundColor: colors.surfaceSecondary },
  faceBadge: { position: "absolute", bottom: 4, right: 4, flexDirection: "row", alignItems: "center", gap: 2, backgroundColor: colors.brand, paddingHorizontal: 6, paddingVertical: 2, borderRadius: radius.pill },
  faceBadgeText: { color: colors.onBrand, fontSize: 10, fontWeight: "700" },
  sectionTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginBottom: spacing.sm },
  channelRow: { flexDirection: "row", backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.xs, marginBottom: spacing.md },
  channelBtn: { flex: 1, paddingVertical: spacing.sm, alignItems: "center", borderRadius: radius.sm },
  channelActive: { backgroundColor: colors.brand },
  channelText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text },
  channelTextActive: { color: colors.onBrand, fontWeight: "600" },
  switchRow: { flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.lg },
  switchLabel: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg },
  switchHint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  grantRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginTop: spacing.md },
  grantValue: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  revoke: { color: colors.onError, fontFamily: fonts.text, fontSize: fontSize.sm },
  muted: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginBottom: spacing.sm },
  presetRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md, marginBottom: spacing.md },
  preset: { flex: 1, paddingVertical: spacing.md, alignItems: "center", borderRadius: radius.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  presetActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  presetText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  presetTextActive: { color: colors.onBrand, fontWeight: "600" },
  infoCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginTop: spacing.xl },
  infoRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.sm },
  infoValue: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  modalBg: { flex: 1, backgroundColor: "rgba(0,0,0,0.7)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  modalCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, padding: spacing.xl, width: "100%", alignItems: "center" },
  modalTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing.md, marginBottom: spacing.sm },
  modalText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base, textAlign: "center", marginBottom: spacing.xl, lineHeight: 20 },
});
