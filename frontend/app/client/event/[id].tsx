import { useCallback, useEffect, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ActivityIndicator, Platform, Pressable, Share, StyleSheet, Text, View } from "react-native";
import { BlurView } from "expo-blur";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";

import { api, downloadPhoto, ApiError } from "@/src/api/client";
import { EmptyState, GlassHeader, Button, useToast } from "@/src/components/ui";
import { PhotoGrid } from "@/src/components/PhotoGrid";
import { sharePhotoFile } from "@/src/utils/share-photo";

import { goBackOr } from "@/src/navigation/back";

import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

export default function ClientEventDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [detail, setDetail] = useState<any>(null);
  const [tab, setTab] = useState<"mine" | "liked" | "all">("mine");
  const [myPhotos, setMyPhotos] = useState<any[]>([]);
  const [likedPhotos, setLikedPhotos] = useState<any[]>([]);
  const [allPhotos, setAllPhotos] = useState<any[]>([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(true);
  const [allOffset, setAllOffset] = useState(0);
  const [allHasMore, setAllHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const PAGE = 60;
  const [sharing, setSharing] = useState(false);


  const loadDetail = useCallback(async () => {
    try {
      const d = await api.get(`/client/events/${id}`);
      setDetail(d);
      const mp = await api.get(`/client/events/${id}/my-photos`);
      setMyPhotos(mp.photos);
      setSearched(mp.searched);
      const lk = await api.get(`/client/events/${id}/liked`);
      setLikedPhotos(lk.photos);
      if (d.full_gallery_access) {
        const ap = await api.get(`/client/events/${id}/photos?limit=${PAGE}&offset=0`);
        setAllPhotos(ap.items || []);
        setAllOffset((ap.items || []).length);
        setAllHasMore(!!ap.has_more);
      }
    } catch (e: any) {
      toast.show(e?.message || "Could not load gallery", "error");
    } finally {
      setLoading(false);
    }
  }, [id, toast]);

  const loadMoreAll = useCallback(async () => {
    if (tab !== "all" || !allHasMore || loadingMore) return;
    setLoadingMore(true);
    try {
      const ap = await api.get(`/client/events/${id}/photos?limit=${PAGE}&offset=${allOffset}`);
      setAllPhotos((prev) => [...prev, ...(ap.items || [])]);
      setAllOffset((o) => o + (ap.items || []).length);
      setAllHasMore(!!ap.has_more);
    } catch {
    } finally {
      setLoadingMore(false);
    }
  }, [tab, allHasMore, loadingMore, allOffset, id]);

  useFocusEffect(
    useCallback(() => {
      loadDetail();
    }, [loadDetail])
  );

  useEffect(() => {
    if (detail && !detail.full_gallery_access && tab === "all") setTab("mine");
  }, [detail, tab]);

  const showAll = detail?.full_gallery_access;
  const photos = tab === "mine" ? myPhotos : tab === "liked" ? likedPhotos : allPhotos;

  const goScan = () => router.push(`/client/selfie/${id}`);

  const setLikedFlag = (photoId: string, liked: boolean) => {
    const upd = (arr: any[]) => arr.map((p) => (p.photo_id === photoId ? { ...p, liked } : p));
    setMyPhotos(upd);
    setAllPhotos(upd);
  };

  const toggleLike = async (photo: any) => {
    const next = !photo.liked;
    // optimistic
    setLikedFlag(photo.photo_id, next);
    setLikedPhotos((prev) =>
      next
        ? prev.some((p) => p.photo_id === photo.photo_id)
          ? prev.map((p) => (p.photo_id === photo.photo_id ? { ...p, liked: true } : p))
          : [{ ...photo, liked: true }, ...prev]
        : prev.filter((p) => p.photo_id !== photo.photo_id)
    );
    try {
      await api.post(`/client/events/${id}/photos/${photo.photo_id}/like`);
    } catch (e: any) {
      // revert
      setLikedFlag(photo.photo_id, !next);
      loadDetail();
      toast.show(e?.message || "Could not update like", "error");
    }
  };

  const download = async (photo: any) => {
    try {
      await downloadPhoto(photo);
    } catch {
      toast.show("Could not download", "error");
    }
  };

  const sharePhoto = async (photo: any) => {
    try {
      const result = await sharePhotoFile(photo);
      toast.show(
        result === "downloaded" ? "Photo downloaded — share it from your device" : "Share sheet opened",
        "success",
      );
    } catch (e: any) {
      toast.show(e?.message || "Could not share this photo", "error");
    }
  };

  const shareCurrentTab = async () => {
    const scopeMap = { all: "all", liked: "liked", mine: "matched" } as const;
    const labelMap = { all: "all photos", liked: "liked photos", mine: "my photos" } as const;
    setSharing(true);
    try {
      const r = await api.post(`/client/events/${id}/share`, { scope: scopeMap[tab] });
      const url = r.share_url as string;
      if (Platform.OS === "web") {
        await Clipboard.setStringAsync(url);
        toast.show("Share link copied to clipboard", "success");
      } else {
        await Share.share({ message: `View ${labelMap[tab]} from ${detail?.name || "our gallery"}: ${url}`, url });
      }
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not create share link", "error");
    } finally {
      setSharing(false);
    }
  };

  const TABS: { key: "mine" | "liked" | "all"; label: string }[] = [
    { key: "mine", label: `My Photos${myPhotos.length ? ` (${myPhotos.length})` : ""}` },
    { key: "liked", label: `Liked${likedPhotos.length ? ` (${likedPhotos.length})` : ""}` },
    ...(showAll ? [{ key: "all" as const, label: "All Photos" }] : []),
  ];

  const header = (
    <View style={{ paddingTop: spacing.lg }}>
      <BlurView intensity={30} tint="dark" style={styles.segment}>
        {TABS.map((t) => (
          <Segment key={t.key} label={t.label} active={tab === t.key} onPress={() => setTab(t.key)} testID={`tab-${t.key}`} />
        ))}
      </BlurView>
      <Button
        testID="share-gallery-btn"
        title={`Share ${tab === "all" ? "All Photos" : tab === "liked" ? "Liked" : "My Photos"}`}
        variant="secondary"
        icon="share-social-outline"
        loading={sharing}
        onPress={shareCurrentTab}
        style={{ marginTop: spacing.md }}
      />
    </View>
  );

  return (
    <View style={styles.container} testID="client-event-screen">
      <GlassHeader
        title={detail?.name || "Gallery"}
        subtitle={detail ? categoryMeta[detail.category]?.label : undefined}
        onBack={() => goBackOr(router, "/client")}
        topInset={insets.top}
      />
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : tab === "mine" && !searched ? (
        <View style={{ flex: 1 }}>
          {header}
          <EmptyState
            icon="scan-outline"
            title="Find yourself in this gallery"
            subtitle="Take a quick selfie and we'll instantly gather every photo you appear in."
            action={<Button testID="scan-cta-empty" title="Scan my face" icon="camera" onPress={goScan} />}
          />
        </View>
      ) : photos.length === 0 ? (
        <View style={{ flex: 1 }}>
          {header}
          <EmptyState
            icon={tab === "liked" ? "heart-outline" : "images-outline"}
            title={tab === "mine" ? "No matches found" : tab === "liked" ? "No liked photos yet" : "No photos yet"}
            subtitle={
              tab === "mine"
                ? "We couldn't find you in this gallery. Try scanning again with better lighting."
                : tab === "liked"
                ? "Tap the heart on any photo to save it to your Liked gallery."
                : "The studio hasn't added photos yet."
            }
            action={tab === "mine" ? <Button testID="scan-cta-retry" title="Scan again" icon="camera" onPress={goScan} /> : undefined}
          />
        </View>
      ) : (
        <PhotoGrid
          photos={photos}
          showScore={tab !== "all"}
          onToggleLike={toggleLike}
          onDownload={download}
          onShare={sharePhoto}
          onEndReached={loadMoreAll}
          loadingMore={loadingMore && tab === "all"}
          ListHeaderComponent={header}
        />
      )}

      {/* Floating scan CTA */}
      {!loading && (searched || photos.length > 0) && (
        <View style={[styles.fabWrap, { bottom: insets.bottom + spacing.lg }]} pointerEvents="box-none">
          <Pressable testID="scan-fab" onPress={goScan} style={styles.fab}>
            <Ionicons name="camera" size={20} color={colors.onBrand} />
            <Text style={styles.fabText}>{searched ? "Re-scan" : "Scan my face"}</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

function Segment({ label, active, onPress, testID }: { label: string; active: boolean; onPress: () => void; testID: string }) {
  return (
    <Pressable testID={testID} onPress={onPress} style={[styles.segBtn, active && styles.segActive]}>
      <Text style={[styles.segText, active && styles.segTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  segment: {
    flexDirection: "row",
    marginHorizontal: spacing.lg,
    padding: spacing.xs,
    borderRadius: radius.md,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
  },
  segBtn: { flex: 1, paddingVertical: spacing.md, alignItems: "center", borderRadius: radius.sm },
  segActive: { backgroundColor: colors.brand },
  segText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  segTextActive: { color: colors.onBrand, fontWeight: "600" },
  fabWrap: { position: "absolute", left: 0, right: 0, alignItems: "center" },
  fab: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.brand,
    paddingHorizontal: spacing.xl,
    height: 52,
    borderRadius: radius.pill,
    shadowColor: "#000",
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  fabText: { color: colors.onBrand, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "600" },
});
