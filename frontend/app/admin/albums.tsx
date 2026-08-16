import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as DocumentPicker from "expo-document-picker";
import * as Clipboard from "expo-clipboard";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, GlassHeader, EmptyState, Pill, useToast } from "@/src/components/ui";
import { useResponsive } from "@/src/hooks/use-responsive";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

type Album = {
  album_id: string;
  title: string;
  client_name?: string | null;
  event_name?: string | null;
  status: string;
  total_spreads: number;
  page_count: number;
  has_pdf: boolean;
  cover_url?: string | null;
  warnings: string[];
  share_token: string;
  share_url: string;
  preview_url: string;
};

function previewK(previewUrl: string): string {
  const m = previewUrl.match(/[?&]k=([^&]+)/);
  return m ? m[1] : "";
}

export default function AlbumsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { isDesktop } = useResponsive();

  const [albums, setAlbums] = useState<Album[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [client, setClient] = useState("");
  const [event, setEvent] = useState("");

  const load = useCallback(async () => {
    try {
      setAlbums(await api.get("/albums"));
    } catch {
      toast.show("Could not load albums", "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [toast]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const create = async () => {
    if (!title.trim()) { toast.show("Give the album a title", "error"); return; }
    setCreating(true);
    try {
      await api.post("/albums", {
        title: title.trim(),
        client_name: client.trim() || undefined,
        event_name: event.trim() || undefined,
      });
      toast.show("Album created — upload a PDF next", "success");
      setShowCreate(false); setTitle(""); setClient(""); setEvent("");
      load();
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not create album", "error");
    } finally {
      setCreating(false);
    }
  };

  const uploadPdf = async (a: Album) => {
    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: "application/pdf",
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (res.canceled || !res.assets?.length) return;
      const asset = res.assets[0];
      setBusyId(a.album_id);
      toast.show("Processing PDF… this can take a moment", "info");
      const updated: Album = await api.upload(
        `/albums/${a.album_id}/pdf`,
        asset.uri,
        asset.name || "album.pdf",
        "application/pdf",
      );
      if (updated.warnings?.length) {
        toast.show(updated.warnings[0], "info");
      } else {
        toast.show(`Rendered ${updated.total_spreads} spreads`, "success");
      }
      load();
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Unable to process this PDF", "error");
    } finally {
      setBusyId(null);
    }
  };

  const togglePublish = async (a: Album) => {
    setBusyId(a.album_id);
    try {
      await api.post(`/albums/${a.album_id}/${a.status === "published" ? "unpublish" : "publish"}`);
      toast.show(a.status === "published" ? "Unpublished" : "Published", "success");
      load();
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Action failed", "error");
    } finally {
      setBusyId(null);
    }
  };

  const copyLink = async (a: Album) => {
    await Clipboard.setStringAsync(a.share_url);
    toast.show(a.status === "published" ? "Share link copied" : "Link copied (publish to make it live)", "success");
  };

  const preview = (a: Album) => {
    router.push(`/a/${a.share_token}?k=${previewK(a.preview_url)}` as any);
  };

  const remove = async (a: Album) => {
    setBusyId(a.album_id);
    try {
      await api.del(`/albums/${a.album_id}`);
      toast.show("Album deleted", "success");
      load();
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Delete failed", "error");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <View style={styles.container} testID="admin-albums-screen">
      <GlassHeader title="Albums" subtitle="Premium PDF flipbooks" onBack={() => router.back()} topInset={insets.top} />

      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 96 }}
          refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        >
          {albums.length === 0 ? (
            <EmptyState icon="book-outline" title="No albums yet" subtitle="Create an album, upload a designed PDF, and share a realistic 3D flipbook with your clients." />
          ) : (
            <View style={isDesktop ? styles.grid : undefined}>
              {albums.map((a) => {
                const busy = busyId === a.album_id;
                return (
                  <View key={a.album_id} style={[styles.card, isDesktop && styles.cardDesktop]} testID={`album-${a.album_id}`}>
                    <View style={styles.cardHead}>
                      <View style={styles.thumb}>
                        <Ionicons name="book" size={22} color={colors.brand} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.title} numberOfLines={1}>{a.title}</Text>
                        <Text style={styles.sub} numberOfLines={1}>
                          {[a.client_name, a.event_name].filter(Boolean).join(" · ") || "No client set"}
                        </Text>
                        <Text style={styles.meta}>
                          {a.has_pdf ? `${a.total_spreads} spreads · ${a.page_count} pages` : "No PDF uploaded"}
                        </Text>
                      </View>
                      <Pill label={a.status === "published" ? "Published" : "Draft"} tone={a.status === "published" ? "success" : "neutral"} />
                    </View>

                    {a.warnings?.length ? (
                      <View style={styles.warnBox}>
                        <Ionicons name="alert-circle-outline" size={14} color={colors.warning} />
                        <Text style={styles.warnText} numberOfLines={2}>{a.warnings[0]}</Text>
                      </View>
                    ) : null}

                    <View style={styles.actions}>
                      <ActionBtn icon={a.has_pdf ? "refresh-outline" : "cloud-upload-outline"} label={a.has_pdf ? "Replace PDF" : "Upload PDF"} onPress={() => uploadPdf(a)} disabled={busy} />
                      <ActionBtn icon="eye-outline" label="Preview" onPress={() => preview(a)} disabled={busy || !a.has_pdf} />
                      <ActionBtn icon={a.status === "published" ? "cloud-offline-outline" : "cloud-done-outline"} label={a.status === "published" ? "Unpublish" : "Publish"} onPress={() => togglePublish(a)} disabled={busy || !a.has_pdf} />
                      <ActionBtn icon="link-outline" label="Copy link" onPress={() => copyLink(a)} disabled={busy} />
                      <ActionBtn icon="trash-outline" label="Delete" tone="danger" onPress={() => remove(a)} disabled={busy} />
                    </View>

                    {busy ? (
                      <View style={styles.busyOverlay}><ActivityIndicator color={colors.brand} /></View>
                    ) : null}
                  </View>
                );
              })}
            </View>
          )}
        </ScrollView>
      )}

      <Pressable testID="new-album-fab" onPress={() => setShowCreate(true)} style={[styles.fab, { bottom: insets.bottom + spacing.lg }]}>
        <Ionicons name="add" size={26} color={colors.onBrand} />
        <Text style={styles.fabText}>New Album</Text>
      </Pressable>

      <Modal visible={showCreate} transparent animationType="slide" onRequestClose={() => setShowCreate(false)}>
        <Pressable style={styles.backdrop} onPress={() => setShowCreate(false)} />
        <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]}>
          <View style={styles.sheetHandle} />
          <Text style={styles.sheetTitle}>New Album</Text>
          <KeyboardAwareScrollView keyboardShouldPersistTaps="handled" bottomOffset={24}>
            <TextField testID="album-title-input" label="Album title" value={title} onChangeText={setTitle} placeholder="The Wedding Album" />
            <TextField testID="album-client-input" label="Client name" value={client} onChangeText={setClient} placeholder="Aisha & Rohan" />
            <TextField testID="album-event-input" label="Event" value={event} onChangeText={setEvent} placeholder="Dec 2025" />
            <Button testID="create-album-btn" title="Create album" loading={creating} onPress={create} />
          </KeyboardAwareScrollView>
        </View>
      </Modal>
    </View>
  );
}

function ActionBtn({ icon, label, onPress, disabled, tone }: { icon: any; label: string; onPress: () => void; disabled?: boolean; tone?: "danger" }) {
  return (
    <Pressable onPress={onPress} disabled={disabled} style={[styles.action, disabled && { opacity: 0.4 }]} testID={`action-${label}`}>
      <Ionicons name={icon} size={16} color={tone === "danger" ? colors.error : colors.onSurfaceSecondary} />
      <Text style={[styles.actionText, tone === "danger" && { color: colors.error }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  grid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between" },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.md, overflow: "hidden" },
  cardDesktop: { width: "48.5%" },
  cardHead: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  thumb: { width: 46, height: 46, borderRadius: radius.sm, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  sub: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  meta: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  warnBox: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.md, backgroundColor: colors.surface, borderRadius: radius.sm, padding: spacing.sm },
  warnText: { flex: 1, color: colors.warning, fontFamily: fonts.text, fontSize: fontSize.sm },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.md },
  action: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: spacing.md, height: 38, borderRadius: radius.pill, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  actionText: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm },
  busyOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.35)", alignItems: "center", justifyContent: "center" },
  fab: { position: "absolute", right: spacing.lg, flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: colors.brand, paddingHorizontal: spacing.xl, height: 52, borderRadius: radius.pill, elevation: 6, shadowColor: "#000", shadowOpacity: 0.4, shadowRadius: 12, shadowOffset: { width: 0, height: 4 } },
  fabText: { color: colors.onBrand, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "600" },
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.6)" },
  sheet: { position: "absolute", left: 0, right: 0, bottom: 0, backgroundColor: colors.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: spacing.xl, maxHeight: "80%" },
  sheetHandle: { alignSelf: "center", width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, marginBottom: spacing.lg },
  sheetTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], marginBottom: spacing.lg },
});
