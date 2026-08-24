import { useCallback, useEffect, useState } from "react";
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
import * as ImagePicker from "expo-image-picker";
import * as Clipboard from "expo-clipboard";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError, imgUrl, getAuthToken, UploadItem } from "@/src/api/client";
import { Button, TextField, Pill, GlassHeader, EmptyState, useToast } from "@/src/components/ui";
import { useResponsive } from "@/src/hooks/use-responsive";
import { goBackOr } from "@/src/navigation/back";

import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

type Tab = "photos" | "access" | "share" | "settings";

export async function generateStaticParams(): Promise<Record<string, string>[]> {
  return [];
}

export default function AdminEvent() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { isDesktop } = useResponsive();

  const [tab, setTab] = useState<Tab>("photos");
  const [event, setEvent] = useState<any>(null);
  const [photos, setPhotos] = useState<any[]>([]);
  const [photosTotal, setPhotosTotal] = useState(0);
  const [photosHasMore, setPhotosHasMore] = useState(false);
  const [loadingMorePhotos, setLoadingMorePhotos] = useState(false);
  const PHOTO_PAGE = 60;
  const [status, setStatus] = useState<any>(null);
  const [grants, setGrants] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [crmClients, setCrmClients] = useState<any[]>([]);
  const [clientAssignments, setClientAssignments] = useState<any[]>([]);
  const [clientSearch, setClientSearch] = useState("");
  const [searchingClients, setSearchingClients] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadDone, setUploadDone] = useState(0);
  const [uploadTotal, setUploadTotal] = useState(0);
  const [importingS3, setImportingS3] = useState(false);

  // access form
  const [channel, setChannel] = useState<"email" | "phone">("email");
  const [grantValue, setGrantValue] = useState("");
  const [fullAccess, setFullAccess] = useState(false);
  const [threshold, setThreshold] = useState("85");
  const [savingThreshold, setSavingThreshold] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [confirmDeleteEvent, setConfirmDeleteEvent] = useState(false);
  const [deleteText, setDeleteText] = useState("");
  const [deletingEvent, setDeletingEvent] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<any>(null);

  // share
  const [share, setShare] = useState<any>(null);
  const [visitors, setVisitors] = useState<any[]>([]);
  const [savingShare, setSavingShare] = useState(false);

  const load = useCallback(async () => {
    try {
      const e = await api.get(`/events/${id}`);
      setEvent(e);
      setThreshold(String(Math.round(e.similarity_threshold)));
      const [ps, st, gr, cl, sh, vs, assigned] = await Promise.all([
        api.get(`/events/${id}/photos?limit=${PHOTO_PAGE}&offset=0`),
        api.get(`/events/${id}/indexing-status`),
        api.get(`/events/${id}/access`),
        api.get(`/events/${id}/clients`),
        api.get(`/events/${id}/share`),
        api.get(`/events/${id}/visitors`),
        api.get(`/events/${id}/client-assignments`),
      ]);
      setPhotos(ps.items || []);
      setPhotosTotal(ps.total || 0);
      setPhotosHasMore(!!ps.has_more);
      setStatus(st);
      setGrants(gr);
      setClients(cl);
      setShare(sh);
      setVisitors(vs);
      setClientAssignments(assigned || []);
    } catch (e: any) {
      toast.show(e?.message || "Could not load event", "error");
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

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  // Poll indexing status while photos are still being indexed in the background.
  useEffect(() => {
    if (!status || status.complete || (status.total_photos ?? 0) === 0) return;
    const t = setInterval(async () => {
      try {
        const st = await api.get(`/events/${id}/indexing-status`);
        setStatus(st);
        if (st.complete) {
          setEvent((e: any) => (e ? { ...e, indexing_status: st.status } : e));
          const ps = await api.get(`/events/${id}/photos?limit=${PHOTO_PAGE}&offset=0`);
          setPhotos(ps.items || []);
          setPhotosTotal(ps.total || 0);
          setPhotosHasMore(!!ps.has_more);
        }
      } catch {}
    }, 2500);
    return () => clearInterval(t);
  }, [status, id]);

  const CHUNK = 8;

  const runBulkUpload = async (items: UploadItem[]) => {
    if (!items.length) return;
    setUploading(true);
    setUploadTotal(items.length);
    setUploadDone(0);
    let ok = 0;
    for (let i = 0; i < items.length; i += CHUNK) {
      const chunk = items.slice(i, i + CHUNK);
      try {
        const r = await api.uploadBulk(`/events/${id}/photos/bulk`, chunk);
        ok += r.uploaded || 0;
      } catch {
        // continue with remaining chunks
      }
      setUploadDone(Math.min(i + chunk.length, items.length));
    }
    setUploading(false);
    setUploadTotal(0);
    toast.show(`Uploaded ${ok} photo${ok !== 1 ? "s" : ""} · indexing in background`, ok ? "success" : "error");
    // Kick off status polling.
    try {
      const st = await api.get(`/events/${id}/indexing-status`);
      setStatus(st);
      setEvent((e: any) => (e ? { ...e, indexing_status: st.status } : e));
      const ps = await api.get(`/events/${id}/photos?limit=${PHOTO_PAGE}&offset=0`);
      setPhotos(ps.items || []);
      setPhotosTotal(ps.total || 0);
      setPhotosHasMore(!!ps.has_more);
    } catch {}
  };

  const loadMorePhotos = async () => {
    if (!photosHasMore || loadingMorePhotos) return;
    setLoadingMorePhotos(true);
    try {
      const ps = await api.get(`/events/${id}/photos?limit=${PHOTO_PAGE}&offset=${photos.length}`);
      setPhotos((prev) => [...prev, ...(ps.items || [])]);
      setPhotosTotal(ps.total || 0);
      setPhotosHasMore(!!ps.has_more);
    } catch {
    } finally {
      setLoadingMorePhotos(false);
    }
  };

  // Web: pick many files or an entire folder via a native file input.
  const pickWebFiles = (folder: boolean) => {
    const input = window.document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.multiple = true;
    if (folder) (input as any).webkitdirectory = true;
    input.onchange = async () => {
      const files = Array.from(input.files || []).filter((f) => f.type.startsWith("image/"));
      const items = files.map((f) => ({ name: f.name, type: f.type || "image/jpeg", file: f }));
      await runBulkUpload(items);
    };
    input.click();
  };

  const uploadPhotos = async () => {
    if (Platform.OS === "web") {
      pickWebFiles(false);
      return;
    }
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      toast.show("Photo access is needed to upload", "error");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsMultipleSelection: true,
      selectionLimit: 0,
      quality: 0.85,
    });
    if (result.canceled || !result.assets?.length) return;
    const items = result.assets.map((a, i) => ({
      uri: a.uri,
      name: a.fileName || `photo_${Date.now()}_${i}.jpg`,
      type: a.mimeType || "image/jpeg",
    }));
    await runBulkUpload(items);
  };

  const importS3 = async () => {
    setImportingS3(true);
    try {
      const r = await api.post(`/events/${id}/import-s3`, {});
      if (r.imported > 0) {
        toast.show(`Imported ${r.imported} photos · indexing in background`, "success");
      } else {
        toast.show("No images found in the S3 bucket yet", "info");
      }
      load();
    } catch (e: any) {
      toast.show(e?.message || "S3 import failed", "error");
    } finally {
      setImportingS3(false);
    }
  };

  const [syncing, setSyncing] = useState(false);
  const [showNumbers, setShowNumbers] = useState(false);
  const syncDrive = async () => {
    setSyncing(true);
    try {
      const r = await api.post(`/events/${id}/sync`, {});
      const s = r?.sync || {};
      toast.show(
        `Synced · ${s.added || 0} new, ${s.updated || 0} updated, ${s.removed || 0} removed`,
        "success"
      );
      load();
    } catch (e: any) {
      toast.show(e?.message || "Sync failed", "error");
    } finally {
      setSyncing(false);
    }
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



  const assignClientGroup = async (client: any) => {
    const existing = clientAssignments.find((a) => a.client_id === client.client_id);
    try {
      if (existing) {
        await api.del(`/events/${id}/client-assignments/${client.client_id}`);
        toast.show(`${client.name} unassigned`, "info");
      } else {
        await api.post(`/events/${id}/client-assignments`, {
          client_id: client.client_id,
          full_gallery_access: true,
        });
        toast.show(`${client.name} assigned · all contacts now have access`, "success");
      }
      load();
    } catch (e: any) {
      toast.show(e?.message || "Could not update client assignment", "error");
    }
  };

  const toggleClientGroupAccess = async (assignment: any) => {
    try {
      await api.post(`/events/${id}/client-assignments`, {
        client_id: assignment.client_id,
        full_gallery_access: !assignment.full_gallery_access,
      });
      load();
    } catch (e: any) {
      toast.show(e?.message || "Could not update client access", "error");
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

  const reindex = async () => {
    setReindexing(true);
    try {
      const r = await api.post(`/events/${id}/reindex`);
      toast.show(`Re-indexed ${r.photos} photos · ${r.faces_indexed} faces`, "success");
      load();
    } catch (e: any) {
      toast.show(e?.message || "Re-index failed", "error");
    } finally {
      setReindexing(false);
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

  // ---------- Gallery lifecycle (archive / delete) ----------
  const toggleArchive = async () => {
    const archived = event?.status === "archived";
    setArchiving(true);
    try {
      await api.post(`/events/${id}/${archived ? "unarchive" : "archive"}`);
      toast.show(
        archived ? "Gallery restored — back online" : "Gallery archived — now offline",
        archived ? "success" : "info"
      );
      load();
    } catch (e: any) {
      toast.show(e?.message || "Could not update gallery", "error");
    } finally {
      setArchiving(false);
    }
  };

  const deleteEvent = async () => {
    setDeletingEvent(true);
    try {
      const r = await api.del(`/events/${id}`);
      setConfirmDeleteEvent(false);
      toast.show(`Gallery deleted · ${r.photos_removed} photo${r.photos_removed !== 1 ? "s" : ""} removed`, "info");
      router.replace("/admin");
    } catch (e: any) {
      toast.show(e?.message || "Could not delete gallery", "error");
      setDeletingEvent(false);
    }
  };

  // ---------- Share handlers ----------
  const toggleShare = async (value: boolean) => {
    setSavingShare(true);
    setShare((s: any) => ({ ...s, share_enabled: value }));
    try {
      await api.patch(`/events/${id}`, { share_enabled: value });
      const sh = await api.get(`/events/${id}/share`);
      setShare(sh);
      setEvent((e: any) => ({ ...e, share_enabled: value }));
      toast.show(value ? "Sharing enabled" : "Sharing turned off", value ? "success" : "info");
    } catch {
      setShare((s: any) => ({ ...s, share_enabled: !value }));
      toast.show("Could not update sharing", "error");
    } finally {
      setSavingShare(false);
    }
  };

  const copyLink = async () => {
    if (!share?.share_url) return;
    await Clipboard.setStringAsync(share.share_url);
    toast.show("Share link copied", "success");
  };

  const shareLink = async () => {
    if (!share?.share_url) return;
    if (Platform.OS === "web") return copyLink();
    try {
      await Share.share({ message: `View the "${event?.name}" gallery: ${share.share_url}` });
    } catch {}
  };

  const downloadQR = async () => {
    if (!share?.qr_base64) return;
    const filename = `${(event?.name || "gallery").replace(/[^a-z0-9]+/gi, "-")}-QR.png`;
    if (Platform.OS === "web") {
      const a = window.document.createElement("a");
      a.href = share.qr_base64;
      a.download = filename;
      window.document.body.appendChild(a);
      a.click();
      a.remove();
      toast.show("HD QR downloaded", "success");
    } else {
      await copyLink();
      toast.show("Link copied — screenshot the QR to save it", "info");
    }
  };

  const toggleBlockVisitor = async (v: any) => {
    const next = v.status === "active" ? "blocked" : "active";
    try {
      await api.patch(`/events/${id}/visitors/${v.visitor_id}`, { status: next });
      setVisitors((prev) => prev.map((x) => (x.visitor_id === v.visitor_id ? { ...x, status: next } : x)));
      toast.show(next === "blocked" ? "Visitor blocked" : "Visitor unblocked", next === "blocked" ? "info" : "success");
    } catch {
      toast.show("Could not update visitor", "error");
    }
  };

  const exportCSV = async () => {
    try {
      const res = await fetch(`${process.env.EXPO_PUBLIC_BACKEND_URL}/api/events/${id}/visitors/export`, {
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      });
      const text = await res.text();
      if (Platform.OS === "web") {
        const blob = new Blob([text], { type: "text/csv" });
        const href = window.URL.createObjectURL(blob);
        const a = window.document.createElement("a");
        a.href = href;
        a.download = `visitors_${id}.csv`;
        window.document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => window.URL.revokeObjectURL(href), 1000);
        toast.show("CSV exported", "success");
      } else {
        await Share.share({ message: text });
      }
    } catch {
      toast.show("Could not export CSV", "error");
    }
  };

  const clientOptions = Array.from(
    new Map(
      [...clientAssignments.map((a) => ({
        client_id: a.client_id,
        name: a.client_name,
        stats: { contact_count: a.contact_count },
      })), ...crmClients].map((client) => [client.client_id, client])
    ).values()
  );

  if (loading) {
    return (
      <View style={styles.center} testID="admin-event-loading">
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }

  return (
    <View style={styles.container} testID="admin-event-screen">
      <GlassHeader title={event?.name} subtitle={categoryMeta[event?.category]?.label} onBack={() => goBackOr(router, "/admin")} topInset={insets.top} />

      <View style={styles.tabs}>
        {(["photos", "access", "share", "settings"] as Tab[]).map((t) => (
          <Pressable key={t} testID={`admin-tab-${t}`} onPress={() => setTab(t)} style={[styles.tab, tab === t && styles.tabActive]}>
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t === "photos" ? "Photos" : t === "access" ? "Access" : t === "share" ? "Share" : "Settings"}
            </Text>
          </Pressable>
        ))}
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing["3xl"] }}>
        {/* ---------------- PHOTOS ---------------- */}
        {tab === "photos" && (
          <>
            <View style={styles.statusCard}>
              <View style={{ flex: 1 }}>
                <Text style={styles.statusTitle}>Indexing status</Text>
                <Text style={styles.statusSub}>

                  {status?.indexed_photos ?? 0}/{status?.total_photos ?? 0} indexed · {status?.total_faces ?? 0} faces
                  {status?.failed_photos ? ` · ${status.failed_photos} failed` : ""}
                </Text>
              </View>
              <Pill
                label={status?.complete === false ? "Indexing…" : (event?.indexing_status || "empty")}
                tone={status?.complete === false ? "gold" : event?.indexing_status === "ready" ? "success" : "neutral"}
              />
            </View>

            {status && status.total_photos > 0 && status.complete === false && (
              <View style={styles.progressWrap} testID="indexing-progress">
                <View style={styles.progressTrack}>
                  <View style={[styles.progressFill, { width: `${status.percent ?? 0}%` }]} />
                </View>
                <Text style={styles.progressLabel}>Indexing faces… {status.percent ?? 0}%</Text>
              </View>
            )}

            {uploading && (
              <View style={styles.progressWrap} testID="upload-progress">
                <View style={styles.progressTrack}>
                  <View style={[styles.progressFill, { width: `${uploadTotal ? Math.round((uploadDone / uploadTotal) * 100) : 0}%` }]} />
                </View>
                <Text style={styles.progressLabel}>Uploading {uploadDone}/{uploadTotal}…</Text>
              </View>
            )}

            {event?.source === "gdrive" ? (
              <View style={styles.driveCard} testID="drive-panel">
                <View style={styles.driveHead}>
                  <Ionicons name="logo-google" size={18} color={colors.brand} />
                  <Text style={styles.driveTitle}>Google Drive gallery</Text>
                </View>
                <Text style={styles.driveMeta} numberOfLines={1}>
                  {event?.last_synced_at
                    ? `Last synced ${new Date(event.last_synced_at).toLocaleString()}`
                    : "Not synced yet"}
                </Text>
                <Button testID="sync-drive-btn" title={syncing ? "Syncing…" : "Sync now"} icon="sync-outline" loading={syncing} onPress={syncDrive} style={{ marginTop: spacing.md }} />
                <Text style={styles.driveNote}>
                  Originals stay on Google Drive. Add or remove photos in the folder, then tap Sync to refresh the gallery and index new faces.
                </Text>
              </View>
            ) : (
              <>
                <Button testID="upload-photos-btn" title={uploading ? "Uploading…" : "Upload photos"} icon="cloud-upload-outline" loading={uploading} onPress={uploadPhotos} />
                {Platform.OS === "web" && (
                  <Button testID="upload-folder-btn" title="Upload a folder" variant="secondary" icon="folder-open-outline" disabled={uploading} onPress={() => pickWebFiles(true)} style={{ marginTop: spacing.md }} />
                )}
                <Button testID="import-s3-btn" title="Import from S3 bucket" variant="ghost" icon="cloud-download-outline" loading={importingS3} onPress={importS3} style={{ marginTop: spacing.md }} />
              </>
            )}

            {photos.length === 0 ? (
              <EmptyState icon="images-outline" title="No photos yet" subtitle="Upload event photos — faces are detected and indexed automatically in the background." />
            ) : (
              <>
                <View style={styles.gridToolbar}>
                  <Pressable
                    testID="admin-toggle-numbers"
                    onPress={() => setShowNumbers((v) => !v)}
                    hitSlop={8}
                    style={[styles.numBtn, showNumbers && styles.numBtnActive]}
                  >
                    <Ionicons name={showNumbers ? "pricetags" : "pricetags-outline"} size={14} color={showNumbers ? colors.onBrand : colors.onSurfaceTertiary} />
                    <Text style={[styles.numText, showNumbers && styles.numTextActive]}>{showNumbers ? "Numbers on" : "Numbers off"}</Text>
                  </Pressable>
                </View>
                <View style={styles.thumbGrid}>
                  {photos.map((p, i) => (
                    <View key={p.photo_id} style={[styles.thumbCell, isDesktop && styles.thumbCellDesktop]}>
                      <View style={styles.thumbImg} testID={`admin-photo-${p.photo_id}`}>
                        <Image source={{ uri: imgUrl(p.thumb_url, p.thumb_path) }} style={StyleSheet.absoluteFill} contentFit="cover" transition={150} cachePolicy="memory-disk" />
                        {p.indexing_status && p.indexing_status !== "indexed" && (
                          <View style={[styles.faceBadge, styles.pendingBadge]}>
                            <Ionicons name={p.indexing_status === "failed" ? "alert" : "time-outline"} size={10} color={colors.onBrand} />
                          </View>
                        )}
                        {p.face_count > 0 && (
                          <View style={styles.faceBadge}>
                            <Ionicons name="person" size={10} color={colors.onBrand} />
                            <Text style={styles.faceBadgeText}>{p.face_count}</Text>
                          </View>
                        )}
                      </View>
                      {showNumbers && (
                        <Text style={styles.thumbCaption} numberOfLines={1}>{p.filename || `#${i + 1}`}</Text>
                      )}
                    </View>
                  ))}
                </View>
              </>
            )}
            {photosHasMore && (
              <Button
                testID="load-more-photos-btn"
                title={loadingMorePhotos ? "Loading…" : `Load more (${photos.length}/${photosTotal})`}
                variant="secondary"
                icon="chevron-down"
                loading={loadingMorePhotos}
                onPress={loadMorePhotos}
                style={{ marginTop: spacing.lg }}
              />
            )}
          </>
        )}

        {/* ---------------- ACCESS ---------------- */}
        {tab === "access" && (
          <>
            <Text style={styles.sectionTitle}>Client groups</Text>
            <Text style={styles.muted}>
              Assigning a client gives access to every contact in that client. New contacts inherit access automatically.
            </Text>
            <View style={styles.clientSearchRow}>
              <View style={{ flex: 1 }}>
                <TextField
                  testID="client-group-search-input"
                  value={clientSearch}
                  onChangeText={setClientSearch}
                  placeholder="Search client, contact, email or phone"
                  autoCapitalize="none"
                />
              </View>
              <Button
                testID="client-group-search-btn"
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
                const assignment = clientAssignments.find((a) => a.client_id === client.client_id);
                return (
                  <View key={client.client_id} style={styles.grantRow} testID={`client-assignment-${client.client_id}`}>
                    <Pressable
                      testID={`assign-client-${client.client_id}`}
                      onPress={() => assignClientGroup(client)}
                      style={{ flexDirection: "row", alignItems: "center", gap: spacing.md, flex: 1, minHeight: 44 }}
                    >
                      <Ionicons name={assignment ? "checkmark-circle" : "people-outline"} size={22} color={assignment ? colors.brand : colors.muted} />
                      <View style={{ flex: 1 }}>
                        <Text style={styles.grantValue} numberOfLines={1}>{client.name}</Text>
                        <Text style={styles.muted}>{client.stats?.contact_count || 0} contacts · {assignment ? "Assigned" : "Not assigned"}</Text>
                      </View>
                    </Pressable>
                    {assignment ? (
                      <View style={{ alignItems: "flex-end", gap: spacing.xs }}>
                        <Switch
                          testID={`client-assignment-full-${client.client_id}`}
                          value={!!assignment.full_gallery_access}
                          onValueChange={() => toggleClientGroupAccess(assignment)}
                          trackColor={{ true: colors.brand, false: colors.surfaceTertiary }}
                          thumbColor={colors.onSurface}
                        />
                        <Text style={styles.muted}>{assignment.full_gallery_access ? "Full gallery" : "Matched only"}</Text>
                      </View>
                    ) : (
                      <Text style={styles.assignText}>Assign</Text>
                    )}
                  </View>
                );
              })
            )}

            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Grant individual access</Text>
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

            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Individual access ({grants.filter((g) => g.status === "active").length})</Text>
            {grants.length === 0 ? (
              <Text style={styles.muted}>No clients invited yet.</Text>
            ) : (
              grants.map((g) => (
                <View key={g.grant_id} style={styles.grantRow} testID={`grant-${g.grant_id}`}>
                  <Ionicons name={g.channel === "email" ? "mail-outline" : "call-outline"} size={18} color={colors.brand} />
                  <View style={{ flex: 1 }}>
                    {g.client_name ? <Text style={styles.grantValue} numberOfLines={1}>{g.client_name}</Text> : null}
                    <Text style={g.client_name ? styles.muted : styles.grantValue} numberOfLines={1}>{g.client_name ? (g.contact_name || g.client_email || g.client_phone) : (g.client_email || g.client_phone)}</Text>
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
                <Pressable
                  testID={`view-client-${c.client_user_id}`}
                  onPress={() =>
                    router.push({
                      pathname: "/admin/client-gallery",
                      params: { eventId: String(id), clientId: c.client_user_id, name: c.name || c.email || c.phone || "" },
                    })
                  }
                  style={{ flexDirection: "row", alignItems: "center", gap: spacing.md, flex: 1 }}
                >
                  <Ionicons name="person-circle-outline" size={22} color={colors.brand} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.grantValue}>{c.name || c.email || c.phone}</Text>
                    <Text style={styles.muted}>{c.matched_count} matched · tap to view galleries</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                </Pressable>
                <Pressable testID={`delete-face-${c.client_user_id}`} onPress={() => setConfirmDelete(c)} hitSlop={8} style={{ paddingLeft: spacing.sm }}>
                  <Ionicons name="trash-outline" size={20} color={colors.onError} />
                </Pressable>
              </View>
            ))}
          </>
        )}

        {/* ---------------- SHARE ---------------- */}
        {tab === "share" && (
          <>
            <View style={styles.switchRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.switchLabel}>Public sharing</Text>
                <Text style={styles.switchHint}>Anyone with the link or QR can view this gallery</Text>
              </View>
              <Switch
                testID="share-toggle"
                value={!!share?.share_enabled}
                onValueChange={toggleShare}
                disabled={savingShare}
                trackColor={{ true: colors.brand, false: colors.surfaceTertiary }}
                thumbColor={colors.onSurface}
              />
            </View>

            {share?.share_enabled ? (
              <>
                <Text style={styles.sectionTitle}>Shareable link</Text>
                <View style={styles.linkBox} testID="share-link-box">
                  <Ionicons name="link-outline" size={16} color={colors.brand} />
                  <Text style={styles.linkText} numberOfLines={1}>{share?.share_url}</Text>
                </View>
                <View style={styles.linkActions}>
                  <Button testID="copy-link-btn" title="Copy link" variant="secondary" icon="copy-outline" onPress={copyLink} style={{ flex: 1 }} />
                  {Platform.OS !== "web" && (
                    <Button testID="share-link-btn" title="Share" variant="secondary" icon="share-social-outline" onPress={shareLink} style={{ flex: 1 }} />
                  )}
                </View>

                <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>QR code</Text>
                <Text style={styles.muted}>Print it on cards or posters — guests scan to open the gallery.</Text>
                <View style={styles.qrCard}>
                  {share?.qr_base64 ? (
                    <Image source={{ uri: share.qr_base64 }} style={styles.qrImg} contentFit="contain" testID="share-qr-image" />
                  ) : (
                    <ActivityIndicator color={colors.brand} />
                  )}
                </View>
                <Button testID="download-qr-btn" title="Download HD QR" icon="download-outline" onPress={downloadQR} />
              </>
            ) : (
              <EmptyState
                icon="lock-closed-outline"
                title="Sharing is off"
                subtitle="Turn on public sharing to generate a link and QR code for this gallery."
              />
            )}

            <View style={styles.visitorsHeader}>
              <Text style={styles.sectionTitle}>Visitors ({visitors.length})</Text>
              {visitors.length > 0 && (
                <Pressable testID="export-csv-btn" onPress={exportCSV} style={styles.exportBtn} hitSlop={8}>
                  <Ionicons name="download-outline" size={15} color={colors.brand} />
                  <Text style={styles.exportText}>Export CSV</Text>
                </Pressable>
              )}
            </View>
            <Text style={styles.muted}>People who opened this gallery via the link or QR.</Text>
            {visitors.length === 0 ? (
              <Text style={styles.muted}>No visitors yet.</Text>
            ) : (
              visitors.map((v) => (
                <View key={v.visitor_id} style={styles.grantRow} testID={`visitor-${v.visitor_id}`}>
                  <Ionicons name="person-circle-outline" size={22} color={v.status === "active" ? colors.brand : colors.muted} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.grantValue} numberOfLines={1}>{v.name || "Guest"}</Text>
                    <Text style={styles.muted}>{v.phone}</Text>
                    <View style={{ flexDirection: "row", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                      <Pill label={v.status === "active" ? "Active" : "Blocked"} tone={v.status === "active" ? "success" : "neutral"} />
                      {v.matched_count > 0 && <Pill label={`${v.matched_count} matched`} tone="gold" />}
                      {v.liked_count > 0 && <Pill label={`${v.liked_count} liked`} tone="neutral" />}
                    </View>
                  </View>
                  <Pressable
                    testID={`block-visitor-${v.visitor_id}`}
                    onPress={() => toggleBlockVisitor(v)}
                    style={[styles.blockBtn, v.status === "blocked" && styles.unblockBtn]}
                    hitSlop={6}
                  >
                    <Text style={[styles.blockText, v.status === "blocked" && styles.unblockText]}>
                      {v.status === "active" ? "Block" : "Unblock"}
                    </Text>
                  </Pressable>
                </View>
              ))
            )}
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

            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Face index</Text>
            <Text style={styles.muted}>
              Rebuild face data for this gallery — run this after enabling AWS face search or if
              matches look off.
            </Text>
            <Button testID="reindex-btn" title="Re-index faces" variant="secondary" icon="refresh" loading={reindexing} onPress={reindex} />

            <View style={styles.divider} />
            <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Gallery status</Text>
            <View style={styles.statusRow}>
              <Text style={styles.muted}>Current</Text>
              <Pill
                label={event?.status === "archived" ? "Archived · offline" : "Active · online"}
                tone={event?.status === "archived" ? "warning" : "success"}
              />
            </View>
            <Text style={styles.muted}>
              {event?.status === "archived"
                ? "This gallery is offline. Clients and share links see a message to contact you. Restore it to bring it back online."
                : "Archiving takes the gallery offline. Clients and share links will be asked to contact you for access. You can restore it anytime."}
            </Text>
            <Button
              testID="archive-btn"
              title={event?.status === "archived" ? "Restore gallery" : "Archive gallery"}
              variant="secondary"
              icon={event?.status === "archived" ? "cloud-upload-outline" : "archive-outline"}
              loading={archiving}
              onPress={toggleArchive}
            />

            <View style={styles.dangerZone}>
              <Text style={styles.dangerTitle}>Danger zone</Text>
              <Text style={styles.muted}>
                Permanently delete this gallery and all its photos. Images are removed from cloud
                storage and face data is erased. This cannot be undone.
              </Text>
              <Button
                testID="delete-event-btn"
                title="Delete gallery"
                variant="danger"
                icon="trash-outline"
                onPress={() => {
                  setDeleteText("");
                  setConfirmDeleteEvent(true);
                }}
              />
            </View>
          </>
        )}
      </ScrollView>

      {/* delete gallery confirm (type-to-confirm) */}
      <Modal visible={confirmDeleteEvent} transparent animationType="fade" onRequestClose={() => setConfirmDeleteEvent(false)}>
        <Pressable style={styles.modalBg} onPress={() => !deletingEvent && setConfirmDeleteEvent(false)}>
          <Pressable style={styles.modalCard} testID="delete-event-modal" onPress={() => {}}>
            <Ionicons name="warning-outline" size={28} color={colors.onError} />
            <Text style={styles.modalTitle}>Delete this gallery?</Text>
            <Text style={styles.modalText}>
              This permanently deletes {event?.photo_count ?? 0} photo{(event?.photo_count ?? 0) !== 1 ? "s" : ""} from cloud
              storage, erases all face data, and removes every client’s access. This cannot be undone.
            </Text>
            <Text style={[styles.muted, { alignSelf: "stretch", marginBottom: spacing.xs }]}>
              Type DELETE to confirm
            </Text>
            <TextField
              testID="delete-confirm-input"
              value={deleteText}
              onChangeText={setDeleteText}
              autoCapitalize="characters"
              placeholder="DELETE"
            />
            <Button
              testID="confirm-delete-event-btn"
              title="Delete permanently"
              variant="danger"
              disabled={deleteText.trim().toUpperCase() !== "DELETE"}
              loading={deletingEvent}
              onPress={deleteEvent}
            />
            <Pressable onPress={() => !deletingEvent && setConfirmDeleteEvent(false)} style={{ marginTop: spacing.md, alignItems: "center" }}>
              <Text style={styles.muted}>Cancel</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>

      {/* delete confirm */}
      <Modal visible={!!confirmDelete} transparent animationType="fade" onRequestClose={() => setConfirmDelete(null)}>
        <Pressable style={styles.modalBg} onPress={() => setConfirmDelete(null)}>
          <View style={styles.modalCard} testID="delete-confirm-modal">
            <Ionicons name="trash-outline" size={28} color={colors.onError} />
            <Text style={styles.modalTitle}>Delete face data?</Text>
            <Text style={styles.modalText}>
              This removes {confirmDelete?.name || "this client"}’s face signature and matched album for this event. They can re-scan later.
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
  driveCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.brandTertiary },
  driveHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  driveTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.lg },
  driveMeta: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 4 },
  driveNote: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.md, lineHeight: 18 },
  gridToolbar: { flexDirection: "row", justifyContent: "flex-end", marginBottom: spacing.sm },
  numBtn: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: spacing.md, height: 32, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  numBtnActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  numText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm },
  numTextActive: { color: colors.onBrand, fontWeight: "600" },
  thumbGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.lg },
  thumbCell: { width: "31.8%" },
  thumbCellDesktop: { width: "23%" },
  thumbImg: { width: "100%", aspectRatio: 1, borderRadius: radius.sm, overflow: "hidden", backgroundColor: colors.surfaceSecondary },
  thumbCaption: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 4 },
  faceBadge: { position: "absolute", bottom: 4, right: 4, flexDirection: "row", alignItems: "center", gap: 2, backgroundColor: colors.brand, paddingHorizontal: 6, paddingVertical: 2, borderRadius: radius.pill },
  faceBadgeText: { color: colors.onBrand, fontSize: 10, fontWeight: "700" },
  sectionTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginBottom: spacing.sm },
  clientSearchRow: { flexDirection: "row", alignItems: "flex-end", gap: spacing.sm, marginBottom: spacing.md },
  clientSearchButton: { minWidth: 112 },
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
  assignText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
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
  // share
  linkBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.lg, height: 50, marginBottom: spacing.md },
  linkText: { flex: 1, color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base },
  linkActions: { flexDirection: "row", gap: spacing.md },
  qrCard: { backgroundColor: "#FFFFFF", borderRadius: radius.lg, padding: spacing.lg, alignItems: "center", justifyContent: "center", alignSelf: "center", marginTop: spacing.md, marginBottom: spacing.lg },
  qrImg: { width: 240, height: 240 },
  progressWrap: { marginBottom: spacing.md },
  progressTrack: { height: 8, borderRadius: radius.pill, backgroundColor: colors.surfaceTertiary, overflow: "hidden" },
  progressFill: { height: 8, borderRadius: radius.pill, backgroundColor: colors.brand },
  progressLabel: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 6 },
  pendingBadge: { backgroundColor: "rgba(0,0,0,0.6)", left: 6, right: undefined },
  visitorsHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.xl },
  exportBtn: { flexDirection: "row", alignItems: "center", gap: 4 },
  exportText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
  blockBtn: { paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderRadius: radius.sm, backgroundColor: colors.error },
  blockText: { color: colors.onError, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
  unblockBtn: { backgroundColor: colors.surfaceTertiary },
  unblockText: { color: colors.onSurfaceTertiary },
  modalBg: { flex: 1, backgroundColor: "rgba(0,0,0,0.7)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  modalCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, padding: spacing.xl, width: "100%", alignItems: "center" },
  modalTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, marginTop: spacing.md, marginBottom: spacing.sm },
  modalText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base, textAlign: "center", marginBottom: spacing.xl, lineHeight: 20 },
  divider: { height: 1, backgroundColor: colors.surfaceTertiary, marginTop: spacing.xl },
  statusRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.sm },
  dangerZone: { marginTop: spacing["2xl"], borderWidth: 1, borderColor: colors.error, borderRadius: radius.md, padding: spacing.lg, gap: spacing.md },
  dangerTitle: { color: colors.onError, fontFamily: fonts.display, fontSize: fontSize.lg },
});
