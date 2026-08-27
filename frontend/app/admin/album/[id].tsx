import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { Image } from "expo-image";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as DocumentPicker from "expo-document-picker";
import * as Clipboard from "expo-clipboard";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, GlassHeader, Pill, useToast } from "@/src/components/ui";
import { PhoneField } from "@/src/components/PhoneField";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { goBackOr } from "@/src/navigation/back";


type Tab = "pages" | "share" | "access" | "settings";

const SPEED_PRESETS = [
  { label: "Slow", value: 5.5 },
  { label: "Normal", value: 3.5 },
  { label: "Fast", value: 2.0 },
];

function previewK(previewUrl: string): string {
  const m = (previewUrl || "").match(/[?&]k=([^&]+)/);
  return m ? m[1] : "";
}

export async function generateStaticParams(): Promise<Record<string, string>[]> {
  return [];
}

export default function AlbumDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [tab, setTab] = useState<Tab>("pages");
  const [album, setAlbum] = useState<any>(null);
  const [share, setShare] = useState<any>(null);
  const [grants, setGrants] = useState<any[]>([]);
  const [crmClients, setCrmClients] = useState<any[]>([]);
  const [clientAssignments, setClientAssignments] = useState<any[]>([]);
  const [clientSearch, setClientSearch] = useState("");
  const [searchingClients, setSearchingClients] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // details form
  const [title, setTitle] = useState("");
  const [client, setClient] = useState("");
  const [event, setEvent] = useState("");
  const [savingDetails, setSavingDetails] = useState(false);

  // access form
  const [channel, setChannel] = useState<"email" | "phone">("email");
  const [grantValue, setGrantValue] = useState("");

  // delete confirm
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteText, setDeleteText] = useState("");
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, sh, ac, assigned] = await Promise.all([
        api.get(`/albums/${id}`),
        api.get(`/albums/${id}/share`),
        api.get(`/albums/${id}/access`),
        api.get(`/albums/${id}/client-assignments`),
      ]);
      setAlbum(a);
      setShare(sh);
      setGrants(ac);
      setClientAssignments(assigned || []);
      setTitle(a.title || "");
      setClient(a.client_name || "");
      setEvent(a.event_name || "");
    } catch {
      toast.show("Could not load album", "error");
    } finally {
      setLoading(false);
    }
  }, [id, toast]);

  const searchClients = async () => {
    const query = clientSearch.trim();
    if (query.length < 2) {
      toast.show("Enter at least 2 characters to search clients", "error");
      return;
    }
    setSearchingClients(true);
    try {
      setCrmClients(await api.get(`/clients?q=${encodeURIComponent(query)}`));
    } catch (e: any) {
      toast.show(e?.message || "Could not search clients", "error");
    } finally {
      setSearchingClients(false);
    }
  };


  useFocusEffect(useCallback(() => { load(); }, [load]));

  const patch = async (updates: any, okMsg?: string) => {
    // optimistic
    setAlbum((a: any) => ({ ...a, ...updates }));
    try {
      const a = await api.patch(`/albums/${id}`, updates);
      setAlbum(a);
      if (okMsg) toast.show(okMsg, "success");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not save", "error");
      load();
    }
  };

  // ---------- Pages ----------
  const uploadPdf = async () => {
    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: "application/pdf",
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (res.canceled || !res.assets?.length) return;
      const asset = res.assets[0];
      setBusy(true);
      toast.show("Processing PDF… this can take a moment", "info");
      const updated = await api.upload(`/albums/${id}/pdf`, asset.uri, asset.name || "album.pdf", "application/pdf");
      setAlbum(updated);
      if (updated.warnings?.length) toast.show(updated.warnings[0], "info");
      else toast.show(`Rendered ${updated.total_spreads} spreads`, "success");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Unable to process this PDF", "error");
    } finally {
      setBusy(false);
    }
  };

  const togglePublish = async () => {
    setBusy(true);
    try {
      const a = await api.post(`/albums/${id}/${album.status === "published" ? "unpublish" : "publish"}`);
      setAlbum(a);
      toast.show(a.status === "published" ? "Published — link is live" : "Unpublished", "success");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Action failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const preview = () => {
    router.push(`/a/${album.share_token}?k=${previewK(album.preview_url)}` as any);
  };

  // ---------- Share ----------
  const copyLink = async () => {
    await Clipboard.setStringAsync(album.share_url);
    toast.show(album.status === "published" ? "Share link copied" : "Link copied (publish to make it live)", "success");
  };

  const shareLink = async () => {
    try {
      await Share.share({ message: `View the "${album?.title}" album: ${album.share_url}` });
    } catch {}
  };

  const downloadQR = async () => {
    if (!share?.qr_base64) return;
    const filename = `${(album?.title || "album").replace(/[^a-z0-9]+/gi, "-")}-QR.png`;
    if (Platform.OS === "web") {
      const a = window.document.createElement("a");
      a.href = share.qr_base64;
      a.download = filename;
      window.document.body.appendChild(a);
      a.click();
      a.remove();
      toast.show("HD QR downloaded", "success");
    } else {
      await Clipboard.setStringAsync(album.share_url);
      toast.show("Link copied — screenshot the QR to save it", "info");
    }
  };

  // ---------- Access ----------
  const addGrant = async () => {
    const value = grantValue.trim();
    if (!value) {
      toast.show(channel === "email" ? "Enter an email" : "Enter a phone number", "error");
      return;
    }
    try {
      const body: any = { channel };
      if (channel === "email") body.email = value;
      else body.phone = value;
      await api.post(`/albums/${id}/access`, body);
      setGrantValue("");
      toast.show("Access granted — they'll see this album after login", "success");
      setGrants(await api.get(`/albums/${id}/access`));
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not grant access", "error");
    }
  };



  const assignClientGroup = async (client: any) => {
    const existing = clientAssignments.some((a) => a.client_id === client.client_id);
    try {
      if (existing) {
        await api.del(`/albums/${id}/client-assignments/${client.client_id}`);
        toast.show(`${client.name} unassigned`, "info");
      } else {
        await api.post(`/albums/${id}/client-assignments`, { client_id: client.client_id });
        toast.show(`${client.name} assigned · all contacts now have access`, "success");
      }
      load();
    } catch (e: any) {
      toast.show(e?.message || "Could not update client assignment", "error");
    }
  };

  const revokeGrant = async (g: any) => {
    try {
      await api.del(`/albums/${id}/access/${g.grant_id}`);
      toast.show("Access revoked", "info");
      setGrants(await api.get(`/albums/${id}/access`));
    } catch {
      toast.show("Could not revoke access", "error");
    }
  };

  // ---------- Settings ----------
  const saveDetails = async () => {
    if (!title.trim()) {
      toast.show("Title cannot be empty", "error");
      return;
    }
    setSavingDetails(true);
    await patch({ title: title.trim(), client_name: client.trim(), event_name: event.trim() }, "Details saved");
    setSavingDetails(false);
  };

  const uploadMusic = async () => {
    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: ["audio/*"],
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (res.canceled || !res.assets?.length) return;
      const asset = res.assets[0];
      setBusy(true);
      toast.show("Uploading music…", "info");
      const updated = await api.upload(
        `/albums/${id}/music`,
        asset.uri,
        asset.name || "music.mp3",
        asset.mimeType || "audio/mpeg",
      );
      setAlbum(updated);
      toast.show("Music added — it plays when the album opens", "success");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not upload music", "error");
    } finally {
      setBusy(false);
    }
  };

  const removeMusic = async () => {
    setBusy(true);
    try {
      const a = await api.del(`/albums/${id}/music`);
      setAlbum(a);
      toast.show("Music removed", "info");
    } catch {
      toast.show("Could not remove music", "error");
    } finally {
      setBusy(false);
    }
  };

  const toggleArchive = async () => {
    setBusy(true);
    try {
      const a = await api.post(`/albums/${id}/${album.archived ? "unarchive" : "archive"}`);
      setAlbum(a);
      toast.show(a.archived ? "Album archived — link is offline" : "Album restored", "success");
    } catch {
      toast.show("Action failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const deleteAlbum = async () => {
    setDeleting(true);
    try {
      await api.del(`/albums/${id}`);
      toast.show("Album deleted", "success");
      goBackOr(router, "/admin/albums");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Delete failed", "error");
      setDeleting(false);
    }
  };

  if (loading || !album) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }

  const activeGrants = grants.filter((g) => g.status === "active");
  const clientOptions = Array.from(
    new Map(
      [...clientAssignments.map((a) => ({
        client_id: a.client_id,
        name: a.client_name,
        stats: { contact_count: a.contact_count },
      })), ...crmClients].map((client) => [client.client_id, client])
    ).values()
  );


  const currentSpeed =
    SPEED_PRESETS.find((s) => Math.abs(s.value - (album.autoplay_interval ?? 3.5)) < 0.8)?.label ?? "Normal";

  return (
    <View style={styles.container} testID="admin-album-detail">
      <GlassHeader title={album.title} subtitle={[album.client_name, album.event_name].filter(Boolean).join(" · ") || "Album flipbook"} onBack={() => goBackOr(router, "/admin/albums")} topInset={insets.top} />

      <View style={styles.tabs}>
        {(["pages", "share", "access", "settings"] as Tab[]).map((t) => (
          <Pressable key={t} testID={`album-tab-${t}`} onPress={() => setTab(t)} style={[styles.tab, tab === t && styles.tabActive]}>
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t === "pages" ? "Pages" : t === "share" ? "Share" : t === "access" ? "Access" : "Settings"}
            </Text>
          </Pressable>
        ))}
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing["3xl"] }} keyboardShouldPersistTaps="handled">
        {/* ---------------- PAGES ---------------- */}
        {tab === "pages" && (
          <>
            <View style={styles.statusCard}>
              <View style={styles.coverThumb}>
                {album.cover_url ? (
                  <Image source={{ uri: album.cover_url }} style={StyleSheet.absoluteFill} contentFit="cover" />
                ) : (
                  <Ionicons name="book" size={26} color={colors.brand} />
                )}
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.statusTitle}>{album.has_pdf ? `${album.total_spreads} spreads · ${album.page_count} pages` : "No PDF uploaded yet"}</Text>
                <View style={{ flexDirection: "row", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                  <Pill label={album.status === "published" ? "Published" : "Draft"} tone={album.status === "published" ? "success" : "neutral"} />
                  {album.archived && <Pill label="Archived" tone="warning" />}
                  {album.music && <Pill label="Music" tone="gold" icon="musical-notes" />}
                </View>
              </View>
            </View>

            {album.warnings?.length ? (
              <View style={styles.warnBox}>
                <Ionicons name="alert-circle-outline" size={14} color={colors.warning} />
                <Text style={styles.warnText}>{album.warnings[0]}</Text>
              </View>
            ) : null}

            <Button
              testID="upload-pdf-btn"
              title={album.has_pdf ? "Replace PDF" : "Upload album PDF"}
              icon={album.has_pdf ? "refresh-outline" : "cloud-upload-outline"}
              loading={busy}
              onPress={uploadPdf}
            />
            <Button
              testID="preview-album-btn"
              title="Preview flipbook"
              variant="secondary"
              icon="eye-outline"
              disabled={!album.has_pdf || busy}
              onPress={preview}
              style={{ marginTop: spacing.md }}
            />
            <Button
              testID="publish-album-btn"
              title={album.status === "published" ? "Unpublish" : "Publish album"}
              variant="secondary"
              icon={album.status === "published" ? "cloud-offline-outline" : "cloud-done-outline"}
              disabled={!album.has_pdf || busy}
              onPress={togglePublish}
              style={{ marginTop: spacing.md }}
            />
            <Text style={[styles.muted, { marginTop: spacing.md }]}>
              Upload the designed album PDF (12×18 cover, 12×36 spreads). Publishing makes the share link and QR live for clients.
            </Text>
          </>
        )}

        {/* ---------------- SHARE ---------------- */}
        {tab === "share" && (
          <>
            {album.status !== "published" && (
              <View style={styles.warnBox}>
                <Ionicons name="lock-closed-outline" size={14} color={colors.warning} />
                <Text style={styles.warnText}>This album is a draft — publish it (Pages tab) to make the link and QR live.</Text>
              </View>
            )}

            <Text style={styles.sectionTitle}>Shareable link</Text>
            <View style={styles.linkBox} testID="album-share-link-box">
              <Ionicons name="link-outline" size={16} color={colors.brand} />
              <Text style={styles.linkText} numberOfLines={1}>{album.share_url}</Text>
            </View>
            <View style={styles.linkActions}>
              <Button testID="album-copy-link-btn" title="Copy link" variant="secondary" icon="copy-outline" onPress={copyLink} style={{ flex: 1 }} />
              {Platform.OS !== "web" && (
                <Button testID="album-share-link-btn" title="Share" variant="secondary" icon="share-social-outline" onPress={shareLink} style={{ flex: 1 }} />
              )}
            </View>

            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>QR code</Text>
            <Text style={styles.muted}>Print it on cards or frames — clients scan to open the album flipbook.</Text>
            <View style={styles.qrCard}>
              {share?.qr_base64 ? (
                <Image source={{ uri: share.qr_base64 }} style={styles.qrImg} contentFit="contain" testID="album-qr-image" />
              ) : (
                <ActivityIndicator color={colors.brand} />
              )}
            </View>
            <Button testID="album-download-qr-btn" title="Download HD QR" icon="download-outline" onPress={downloadQR} />
          </>
        )}

        {/* ---------------- ACCESS ---------------- */}
        {tab === "access" && (
          <>
            <Text style={styles.sectionTitle}>Client groups</Text>
            <Text style={styles.muted}>
              Assigning a client gives access to every contact in that client. New contacts inherit access automatically after this album is published.
            </Text>
            <View style={styles.clientSearchRow}>
              <View style={{ flex: 1 }}>
                <TextField
                  testID="album-client-group-search-input"
                  value={clientSearch}
                  onChangeText={setClientSearch}
                  placeholder="Search client, contact, email or phone"
                  autoCapitalize="none"
                />
              </View>
              <Button
                testID="album-client-group-search-btn"
                title="Search"
                icon="search-outline"
                loading={searchingClients}
                onPress={searchClients}
                style={styles.clientSearchButton}
              />
            </View>
            {clientOptions.length === 0 ? (
              <Text style={styles.muted}>{clientSearch.trim() ? "No matching clients found." : "Search to find a client group."}</Text>
            ) : (
              clientOptions.map((client) => {
                const assigned = clientAssignments.some((a) => a.client_id === client.client_id);
                return (
                  <Pressable
                    key={client.client_id}
                    testID={`album-client-assignment-${client.client_id}`}
                    onPress={() => assignClientGroup(client)}
                    style={styles.grantRow}
                  >
                    <Ionicons name={assigned ? "checkmark-circle" : "people-outline"} size={22} color={assigned ? colors.brand : colors.muted} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.grantValue} numberOfLines={1}>{client.name}</Text>
                      <Text style={styles.muted}>{client.stats?.contact_count || 0} contacts · {assigned ? "Assigned" : "Not assigned"}</Text>
                    </View>
                    <Text style={styles.assignText}>{assigned ? "Remove" : "Assign"}</Text>
                  </Pressable>
                );
              })
            )}

            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Grant individual access</Text>
            <Text style={styles.muted}>People you add directly can open this album after logging in with the same email or number.</Text>
            <View style={styles.channelRow}>
              {(["email", "phone"] as const).map((c) => (
                <Pressable key={c} testID={`album-grant-channel-${c}`} onPress={() => setChannel(c)} style={[styles.channelBtn, channel === c && styles.channelActive]}>
                  <Text style={[styles.channelText, channel === c && styles.channelTextActive]}>{c === "email" ? "Email" : "Phone"}</Text>
                </Pressable>
              ))}
            </View>
            {channel === "phone" ? (
              <PhoneField
                testID="album-grant-value-input"
                value={grantValue}
                onChangeText={setGrantValue}
                placeholder="Enter mobile number"
              />
            ) : (
              <TextField
                testID="album-grant-value-input"
                value={grantValue}
                onChangeText={setGrantValue}
                placeholder="client@example.com"
                autoCapitalize="none"
                keyboardType="email-address"
              />
            )}
            <Button testID="album-add-grant-btn" title="Grant access" icon="person-add-outline" onPress={addGrant} />

            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Individual access ({activeGrants.length})</Text>
            {grants.length === 0 ? (
              <Text style={styles.muted}>No one has been given access yet.</Text>
            ) : (
              grants.map((g) => (
                <View key={g.grant_id} style={styles.grantRow} testID={`album-grant-${g.grant_id}`}>
                  <Ionicons name={g.channel === "email" ? "mail-outline" : "call-outline"} size={18} color={colors.brand} />
                  <View style={{ flex: 1 }}>
                    {g.client_name ? <Text style={styles.grantValue} numberOfLines={1}>{g.client_name}</Text> : null}
                    <Text style={g.client_name ? styles.muted : styles.grantValue} numberOfLines={1}>{g.client_name ? (g.contact_name || g.client_email || g.client_phone) : (g.client_email || g.client_phone)}</Text>
                    <View style={{ flexDirection: "row", gap: 6, marginTop: 4 }}>
                      <Pill label={g.status === "active" ? "Active" : "Revoked"} tone={g.status === "active" ? "success" : "neutral"} />
                    </View>
                  </View>
                  {g.status === "active" && (
                    <Pressable testID={`album-revoke-${g.grant_id}`} onPress={() => revokeGrant(g)} hitSlop={8}>
                      <Text style={styles.revoke}>Revoke</Text>
                    </Pressable>
                  )}
                </View>
              ))
            )}
          </>
        )}

        {/* ---------------- SETTINGS ---------------- */}
        {tab === "settings" && (
          <>
            <Text style={styles.sectionTitle}>Album details</Text>
            <TextField testID="album-edit-title" label="Title" value={title} onChangeText={setTitle} placeholder="The Wedding Album" />
            <TextField testID="album-edit-client" label="Client name" value={client} onChangeText={setClient} placeholder="Aisha & Rohan" />
            <TextField testID="album-edit-event" label="Event" value={event} onChangeText={setEvent} placeholder="Dec 2025" />
            <Button testID="save-album-details-btn" title="Save details" loading={savingDetails} onPress={saveDetails} />

            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Background music</Text>
            {album.music ? (
              <View style={styles.grantRow}>
                <Ionicons name="musical-notes" size={18} color={colors.brand} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.grantValue} numberOfLines={1}>{album.music.filename}</Text>
                  <Text style={styles.muted}>Auto-plays when the album opens (with a mute button)</Text>
                </View>
                <Pressable testID="remove-music-btn" onPress={removeMusic} hitSlop={8}>
                  <Text style={styles.revoke}>Remove</Text>
                </Pressable>
              </View>
            ) : (
              <Text style={styles.muted}>Add a soundtrack — it plays softly while clients flip through the album.</Text>
            )}
            <Button
              testID="upload-music-btn"
              title={album.music ? "Replace music" : "Upload music"}
              variant="secondary"
              icon="musical-notes-outline"
              loading={busy}
              onPress={uploadMusic}
              style={{ marginTop: spacing.md }}
            />

            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Playback</Text>
            <View style={styles.switchRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.switchLabel}>Auto page-turn</Text>
                <Text style={styles.switchHint}>Album opens and turns pages by itself; pauses on touch</Text>
              </View>
              <Switch
                testID="autoplay-switch"
                value={!!album.autoplay}
                onValueChange={(v) => patch({ autoplay: v })}
                trackColor={{ true: colors.brand, false: colors.surfaceTertiary }}
                thumbColor={colors.onSurface}
              />
            </View>
            {!!album.autoplay && (
              <View style={styles.presetRow}>
                {SPEED_PRESETS.map((s) => (
                  <Pressable
                    key={s.label}
                    testID={`speed-${s.label}`}
                    onPress={() => patch({ autoplay_interval: s.value })}
                    style={[styles.preset, currentSpeed === s.label && styles.presetActive]}
                  >
                    <Text style={[styles.presetText, currentSpeed === s.label && styles.presetTextActive]}>{s.label}</Text>
                  </Pressable>
                ))}
              </View>
            )}
            <View style={styles.switchRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.switchLabel}>Open cover automatically</Text>
                <Text style={styles.switchHint}>The cover opens on its own shortly after loading</Text>
              </View>
              <Switch
                testID="auto-open-switch"
                value={!!album.auto_open}
                onValueChange={(v) => patch({ auto_open: v })}
                trackColor={{ true: colors.brand, false: colors.surfaceTertiary }}
                thumbColor={colors.onSurface}
              />
            </View>
            <View style={styles.switchRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.switchLabel}>Page-turn sound</Text>
                <Text style={styles.switchHint}>A soft paper rustle on every turn</Text>
              </View>
              <Switch
                testID="page-sound-switch"
                value={!!album.page_turn_sound}
                onValueChange={(v) => patch({ page_turn_sound: v })}
                trackColor={{ true: colors.brand, false: colors.surfaceTertiary }}
                thumbColor={colors.onSurface}
              />
            </View>

            <View style={styles.divider} />
            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Album status</Text>
            <View style={styles.statusRow}>
              <Text style={styles.muted}>Current</Text>
              <Pill label={album.archived ? "Archived · offline" : "Active · online"} tone={album.archived ? "warning" : "success"} />
            </View>
            <Text style={styles.muted}>
              {album.archived
                ? "The share link and client access are offline. Restore anytime to bring the album back."
                : "Archiving takes the album offline — the link, QR and client access stop working until you restore it."}
            </Text>
            <Button
              testID="archive-album-btn"
              title={album.archived ? "Restore album" : "Archive album"}
              variant="secondary"
              icon={album.archived ? "cloud-upload-outline" : "archive-outline"}
              loading={busy}
              onPress={toggleArchive}
            />

            <View style={styles.dangerZone}>
              <Text style={styles.dangerTitle}>Danger zone</Text>
              <Text style={styles.muted}>
                Permanently delete this album: all rendered pages and music are removed from cloud storage and every access grant is erased. This cannot be undone.
              </Text>
              <Button
                testID="delete-album-btn"
                title="Delete album"
                variant="danger"
                icon="trash-outline"
                onPress={() => {
                  setDeleteText("");
                  setConfirmDelete(true);
                }}
              />
            </View>
          </>
        )}
      </ScrollView>

      {/* delete confirm (type-to-confirm) */}
      <Modal visible={confirmDelete} transparent animationType="fade" onRequestClose={() => setConfirmDelete(false)}>
        <Pressable style={styles.modalBg} onPress={() => !deleting && setConfirmDelete(false)}>
          <Pressable style={styles.modalCard} testID="delete-album-modal" onPress={() => {}}>
            <Ionicons name="warning-outline" size={28} color={colors.onError} />
            <Text style={styles.modalTitle}>Delete this album?</Text>
            <Text style={styles.modalText}>
              This permanently deletes all {album.page_count || 0} rendered pages, the music track, and every client’s access. This cannot be undone.
            </Text>
            <Text style={[styles.muted, { alignSelf: "stretch", marginBottom: spacing.xs }]}>Type DELETE to confirm</Text>
            <TextField testID="delete-album-confirm-input" value={deleteText} onChangeText={setDeleteText} autoCapitalize="characters" placeholder="DELETE" />
            <Button
              testID="confirm-delete-album-btn"
              title="Delete permanently"
              variant="danger"
              disabled={deleteText.trim().toUpperCase() !== "DELETE"}
              loading={deleting}
              onPress={deleteAlbum}
            />
            <Pressable onPress={() => !deleting && setConfirmDelete(false)} style={{ marginTop: spacing.md, alignItems: "center" }}>
              <Text style={styles.muted}>Cancel</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
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
  statusCard: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.lg },
  coverThumb: { width: 56, height: 72, borderRadius: radius.sm, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", overflow: "hidden" },
  statusTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.lg },
  sectionTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginBottom: spacing.sm },
  muted: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginBottom: spacing.sm },
  warnBox: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.sm, padding: spacing.md },
  warnText: { flex: 1, color: colors.warning, fontFamily: fonts.text, fontSize: fontSize.sm },
  linkBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.lg, height: 50, marginBottom: spacing.md },
  linkText: { flex: 1, color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base },
  linkActions: { flexDirection: "row", gap: spacing.md },
  qrCard: { backgroundColor: "#FFFFFF", borderRadius: radius.lg, padding: spacing.lg, alignItems: "center", justifyContent: "center", alignSelf: "center", marginTop: spacing.md, marginBottom: spacing.lg },
  qrImg: { width: 240, height: 240 },
  clientSearchRow: { flexDirection: "row", alignItems: "flex-end", gap: spacing.sm, marginBottom: spacing.md },
  clientSearchButton: { minWidth: 112 },
  channelRow: { flexDirection: "row", backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.xs, marginBottom: spacing.md },
  channelBtn: { flex: 1, paddingVertical: spacing.sm, alignItems: "center", borderRadius: radius.sm },
  channelActive: { backgroundColor: colors.brand },
  channelText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text },
  channelTextActive: { color: colors.onBrand, fontWeight: "600" },
  grantRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginTop: spacing.md },
  grantValue: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  assignText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
  revoke: { color: colors.onError, fontFamily: fonts.text, fontSize: fontSize.sm },
  switchRow: { flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.md },
  switchLabel: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg },
  switchHint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  presetRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md },
  preset: { flex: 1, paddingVertical: spacing.md, alignItems: "center", borderRadius: radius.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  presetActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  presetText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  presetTextActive: { color: colors.onBrand, fontWeight: "600" },
  divider: { height: 1, backgroundColor: colors.surfaceTertiary, marginTop: spacing.xl },
  statusRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.sm },
  dangerZone: { marginTop: spacing["2xl"], borderWidth: 1, borderColor: colors.error, borderRadius: radius.md, padding: spacing.lg, gap: spacing.md },
  dangerTitle: { color: colors.onError, fontFamily: fonts.display, fontSize: fontSize.lg },
  modalBg: { flex: 1, backgroundColor: "rgba(0,0,0,0.7)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  modalCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, padding: spacing.xl, width: "100%", maxWidth: 480, alignItems: "center" },
  modalTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing.md, marginBottom: spacing.sm },
  modalText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base, textAlign: "center", marginBottom: spacing.xl, lineHeight: 20 },
});
