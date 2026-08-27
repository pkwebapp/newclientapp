import { useCallback, useMemo, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Image } from "expo-image";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, GlassHeader, EmptyState, Pill, useToast } from "@/src/components/ui";
import DatePickerField from "@/src/components/DatePickerField";
import { HeaderMenuButton } from "@/src/components/MobileShell";
import { useResponsive } from "@/src/hooks/use-responsive";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

type Album = {
  album_id: string;
  title: string;
  client_name?: string | null;
  event_name?: string | null;
  event_date?: string | null;
  status: string;
  archived?: boolean;
  total_spreads: number;
  page_count: number;
  has_pdf: boolean;
  cover_url?: string | null;
  warnings: string[];
  share_token: string;
  share_url: string;
  preview_url: string;
  music?: { filename?: string; url?: string | null } | null;
};

export default function AlbumsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { isDesktop } = useResponsive();

  const [albums, setAlbums] = useState<Album[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [client, setClient] = useState("");
  const [eventDate, setEventDate] = useState("");

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

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return albums;
    return albums.filter((a) =>
      [a.title, a.client_name, a.event_name]
        .filter(Boolean)
        .some((v) => (v as string).toLowerCase().includes(needle))
    );
  }, [albums, q]);

  const create = async () => {
    if (!title.trim()) { toast.show("Give the album a title", "error"); return; }
    setCreating(true);
    try {
      const a: Album = await api.post("/albums", {
        title: title.trim(),
        client_name: client.trim() || undefined,
        event_date: eventDate || undefined,
      });
      toast.show("Album created — upload a PDF next", "success");
      setShowCreate(false); setTitle(""); setClient(""); setEventDate("");
      router.push(`/admin/album/${a.album_id}` as any);
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not create album", "error");
    } finally {
      setCreating(false);
    }
  };

  return (
    <View style={styles.container} testID="admin-albums-screen">
      <GlassHeader title="Albums" subtitle="Premium PDF flipbooks" left={<HeaderMenuButton />} topInset={insets.top} />

      <View style={styles.controls}>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput
            testID="album-search-input"
            value={q}
            onChangeText={setQ}
            placeholder="Search albums by title, client…"
            placeholderTextColor={colors.muted}
            style={styles.searchInput}
            autoCapitalize="none"
          />
          {q ? (
            <Pressable onPress={() => setQ("")} hitSlop={8}>
              <Ionicons name="close-circle" size={18} color={colors.muted} />
            </Pressable>
          ) : null}
        </View>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.brand} /></View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing["3xl"] + 72 }}
          refreshControl={<RefreshControl tintColor={colors.brand} refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        >
          {filtered.length === 0 ? (
            <EmptyState
              icon={q ? "search-outline" : "book-outline"}
              title={q ? "No matching albums" : "No albums yet"}
              subtitle={q ? "Try a different search." : "Create an album, upload a designed PDF, and share a realistic 3D flipbook with your clients."}
            />
          ) : (
            <View style={isDesktop ? styles.grid : undefined}>
              {filtered.map((a) => (
                <Pressable
                  key={a.album_id}
                  style={[styles.card, isDesktop && styles.cardDesktop]}
                  testID={`album-${a.album_id}`}
                  onPress={() => router.push(`/admin/album/${a.album_id}` as any)}
                >
                  <View style={styles.cardHead}>
                    <View style={styles.thumb}>
                      {a.cover_url ? (
                        <Image source={{ uri: a.cover_url }} style={StyleSheet.absoluteFill} contentFit="cover" />
                      ) : (
                        <Ionicons name="book" size={22} color={colors.brand} />
                      )}
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.title} numberOfLines={1}>{a.title}</Text>
                      <Text style={styles.sub} numberOfLines={1}>
                        {[a.client_name, a.event_name, a.event_date].filter(Boolean).join(" · ") || "No client set"}
                      </Text>
                      <Text style={styles.meta}>
                        {a.has_pdf ? `${a.total_spreads} spreads · ${a.page_count} pages` : "No PDF uploaded"}
                      </Text>
                    </View>
                    <View style={{ alignItems: "flex-end", gap: 6 }}>
                      <Pill label={a.archived ? "Archived" : a.status === "published" ? "Published" : "Draft"} tone={a.archived ? "warning" : a.status === "published" ? "success" : "neutral"} />
                      <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                    </View>
                  </View>

                  {a.warnings?.length ? (
                    <View style={styles.warnBox}>
                      <Ionicons name="alert-circle-outline" size={14} color={colors.warning} />
                      <Text style={styles.warnText} numberOfLines={2}>{a.warnings[0]}</Text>
                    </View>
                  ) : null}
                </Pressable>
              ))}
            </View>
          )}
        </ScrollView>
      )}

      <Pressable testID="new-album-fab" onPress={() => setShowCreate(true)} style={[styles.fab, { bottom: spacing.lg }]}>
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
            <DatePickerField testID="album-event-date-input" label="Album date" value={eventDate} onChange={setEventDate} emptyLabel="Choose album date" hint="Optional · select from calendar" />
            <Button testID="create-album-btn" title="Create album" loading={creating} onPress={create} />
          </KeyboardAwareScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  controls: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
  searchBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    height: 46,
  },
  searchInput: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  grid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between" },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.md, overflow: "hidden" },
  cardDesktop: { width: "48.5%" },
  cardHead: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  thumb: { width: 46, height: 60, borderRadius: radius.sm, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", overflow: "hidden" },
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  sub: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  meta: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  warnBox: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.md, backgroundColor: colors.surface, borderRadius: radius.sm, padding: spacing.sm },
  warnText: { flex: 1, color: colors.warning, fontFamily: fonts.text, fontSize: fontSize.sm },
  fab: { position: "absolute", right: spacing.lg, flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: colors.brand, paddingHorizontal: spacing.xl, height: 52, borderRadius: radius.pill, elevation: 6, shadowColor: "#000", shadowOpacity: 0.4, shadowRadius: 12, shadowOffset: { width: 0, height: 4 } },
  fabText: { color: colors.onBrand, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "600" },
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.6)" },
  sheet: { position: "absolute", left: 0, right: 0, bottom: 0, backgroundColor: colors.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: spacing.xl, maxHeight: "80%" },
  sheetHandle: { alignSelf: "center", width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, marginBottom: spacing.lg },
  sheetTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], marginBottom: spacing.lg },
});
