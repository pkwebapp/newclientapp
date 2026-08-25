import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  AppState,
  Platform,
  Pressable,
  Share,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { BlurView } from "expo-blur";
import {
  cacheGallery,
  pendingLikeActions,
  queueLikeAction,
  removeLikeActions,
  restoreCachedGallery,
} from "@/src/utils/offline-gallery";

import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";

import { api, downloadPhoto, ApiError } from "@/src/api/client";
import { EmptyState, GlassHeader, Button, LuxeLoader, useToast } from "@/src/components/ui";
import { PhotoGrid } from "@/src/components/PhotoGrid";
import { sharePhotoFile } from "@/src/utils/share-photo";

import { goBackOr } from "@/src/navigation/back";

import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

export default function ClientEventDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
const PRELOAD_TIMEOUT_MS = 30_000;

  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [detail, setDetail] = useState<any>(null);
  const [tab, setTab] = useState<"mine" | "liked" | "all">("mine");
  const [myPhotos, setMyPhotos] = useState<any[]>([]);
  const loadingRef = useRef(false);

  const [likedPhotos, setLikedPhotos] = useState<any[]>([]);
  const [allPhotos, setAllPhotos] = useState<any[]>([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(true);
  const [allOffset, setAllOffset] = useState(0);
  const [allHasMore, setAllHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const PAGE = 60;
  const [sharing, setSharing] = useState(false);
  const [offlineMode, setOfflineMode] = useState(false);
  const [fetchingGallery, setFetchingGallery] = useState(false);
  const [preloadTimedOut, setPreloadTimedOut] = useState(false);

  const [fetchedPhotos, setFetchedPhotos] = useState(0);
  const [totalGalleryPhotos, setTotalGalleryPhotos] = useState(0);



  const applyCachedGallery = useCallback(async () => {
    const cached = await restoreCachedGallery(String(id));
    if (!cached) return false;
    const matchedSet = new Set(cached.matchedIds || []);
    const likedSet = new Set(cached.likedIds || []);
    const cachedPhotos = cached.photos || [];
    setDetail(cached.event);
    setMyPhotos(cachedPhotos.filter((photo) => matchedSet.has(photo.photo_id)));
    setLikedPhotos(cachedPhotos.filter((photo) => likedSet.has(photo.photo_id)).map((photo) => ({ ...photo, liked: true })));
    setAllPhotos(cachedPhotos);
    setAllOffset(cachedPhotos.length);
    setAllHasMore(false);
    setSearched(!!cached.searched);
    setOfflineMode(true);
    setFetchedPhotos(cachedPhotos.length);
    setTotalGalleryPhotos(cachedPhotos.length);
    setFetchingGallery(false);
    setLoading(false);
    return true;
  }, [id]);

  const syncPendingLikes = useCallback(async () => {
    const pending = await pendingLikeActions(String(id));
    if (!pending.length) return;
    try {
      const live = await api.get(`/client/events/${id}/liked`);
      const liveIds = new Set((live.photos || []).map((photo: any) => photo.photo_id));
      const synced: string[] = [];
      for (const action of pending) {
        if (liveIds.has(action.photoId) !== action.liked) {
          await api.post(`/client/events/${id}/photos/${action.photoId}/like`);
        }
        synced.push(action.photoId);
      }
      await removeLikeActions(String(id), synced);
    } catch {
      // Keep queued likes until the next successful online refresh.
    }
  }, [id]);

  const loadDetail = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setPreloadTimedOut(false);
    try {
      const d = await api.get(`/client/events/${id}`);
      setTotalGalleryPhotos(Number(d.photo_count || 0));
      setFetchedPhotos(0);
      setFetchingGallery(!!d.full_gallery_access && Number(d.photo_count || 0) > 0);
      const mp = await api.get(`/client/events/${id}/my-photos`);
      const lk = await api.get(`/client/events/${id}/liked`);
      let firstPage: any = { items: [], has_more: false };
      if (d.full_gallery_access) {
        firstPage = await api.get(`/client/events/${id}/photos?limit=${PAGE}&offset=0`);
      }
      setOfflineMode(false);
      setDetail(d);
      setMyPhotos(mp.photos || []);
      setSearched(!!mp.searched);
      setLikedPhotos(lk.photos || []);

      let all = firstPage.items || [];
      let offset = all.length;
      let hasMore = !!firstPage.has_more;
      let releasedEarly = false;
      const releaseTimer = d.full_gallery_access && hasMore
        ? setTimeout(() => {
            releasedEarly = true;
            setPreloadTimedOut(true);
            setAllPhotos(all);
            setAllOffset(all.length);
            setAllHasMore(hasMore);
            setLoading(false);
          }, PRELOAD_TIMEOUT_MS)
        : null;

      setFetchedPhotos(all.length);
      await cacheGallery(
        String(id),
        d,
        [...(mp.photos || []), ...(lk.photos || []), ...all],
        (lk.photos || []).map((photo: any) => photo.photo_id),
        (mp.photos || []).map((photo: any) => photo.photo_id),
        !!mp.searched,
      );

      while (d.full_gallery_access && hasMore) {
        try {
          const page = await api.get(`/client/events/${id}/photos?limit=${PAGE}&offset=${offset}`);
          all = [...all, ...(page.items || [])];
          offset = all.length;
          hasMore = !!page.has_more;
          setFetchedPhotos(all.length);
          if (releasedEarly) {
            setAllPhotos(all);
            setAllOffset(all.length);
            setAllHasMore(hasMore);
          }
          await cacheGallery(
            String(id),
            d,
            [...(mp.photos || []), ...(lk.photos || []), ...all],
            (lk.photos || []).map((photo: any) => photo.photo_id),
            (mp.photos || []).map((photo: any) => photo.photo_id),
            !!mp.searched,
          );
        } catch {
          break;
        }
      }

      if (releaseTimer) clearTimeout(releaseTimer);
      setAllPhotos(all);
      setAllOffset(all.length);
      setAllHasMore(hasMore);
      setFetchingGallery(false);
      void syncPendingLikes();
    } catch (e: any) {
      const restored = await applyCachedGallery();
      if (!restored) toast.show("This gallery is unavailable offline and has no saved previews", "error");
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [applyCachedGallery, id, syncPendingLikes, toast]);

  const loadMoreAll = useCallback(async () => {
    if (tab !== "all" || !allHasMore || loadingMore) return;
    setLoadingMore(true);
    try {
      const ap = await api.get(`/client/events/${id}/photos?limit=${PAGE}&offset=${allOffset}`);
      const nextPhotos = [...allPhotos, ...(ap.items || [])];
      setAllPhotos(nextPhotos);
      setAllOffset((o) => o + (ap.items || []).length);
      setAllHasMore(!!ap.has_more);
      setFetchedPhotos(nextPhotos.length);
      void cacheGallery(
        String(id),
        detail,
        [...myPhotos, ...likedPhotos, ...nextPhotos],
        likedPhotos.map((photo) => photo.photo_id),
        myPhotos.map((photo) => photo.photo_id),
        searched,
      );
    } catch {
    } finally {
      setLoadingMore(false);
    }
  }, [tab, allHasMore, loadingMore, allOffset, allPhotos, detail, id, likedPhotos, myPhotos, searched]);

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


  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") void loadDetail();
    });
    return () => subscription.remove();
  }, [loadDetail]);

  const goScan = () => {
    if (offlineMode) {
      toast.show("Face scan needs an internet connection", "info");
      return;
    }
    router.push(`/client/selfie/${id}`);
  };

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
      await queueLikeAction({ eventId: String(id), photoId: photo.photo_id, liked: next });
      toast.show("Like saved offline — it will sync when you’re back online", "info");
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

  const fetchProgress = totalGalleryPhotos > 0
    ? Math.min(100, Math.round((fetchedPhotos / totalGalleryPhotos) * 100))
    : 0;

  const header = (
    <View style={{ paddingTop: spacing.lg }}>
      <BlurView intensity={30} tint="dark" style={styles.segment}>
        {TABS.map((t) => (
          <Segment key={t.key} label={t.label} active={tab === t.key} onPress={() => setTab(t.key)} testID={`tab-${t.key}`} />
        ))}
      </BlurView>
      {fetchingGallery && (
        <View style={styles.fetchProgress} testID="gallery-fetch-progress">
          <View style={styles.fetchProgressHeader}>
            <Text style={styles.fetchProgressLabel}>{preloadTimedOut ? "Gallery open · loading remaining" : "Loading all photos"}</Text>
            <Text style={styles.fetchProgressCount}>{fetchedPhotos} of {totalGalleryPhotos}</Text>
          </View>
          <View style={styles.fetchTrack}>
            <View style={[styles.fetchFill, { width: `${fetchProgress}%` }]} />
          </View>
        </View>
      )}
      {offlineMode && (
        <View style={styles.offlineNotice} testID="offline-gallery-notice">
          <Ionicons name="cloud-offline-outline" size={15} color={colors.brand} />
          <Text style={styles.offlineText}>Offline · showing saved previews</Text>
        </View>
      )}
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
        <LuxeLoader
          title={detail?.name ? `Opening ${detail.name}` : "Opening your gallery"}
          subtitle={totalGalleryPhotos > 0 ? `Loading all photos · ${fetchedPhotos} of ${totalGalleryPhotos}` : "Preparing your photos…"}
          progress={totalGalleryPhotos > 0 ? fetchProgress : undefined}
        />
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
  fetchProgress: { marginTop: spacing.md, marginHorizontal: spacing.lg, padding: spacing.md, borderRadius: radius.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  fetchProgressHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.sm },
  fetchProgressLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm },
  fetchProgressCount: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
  fetchTrack: { height: 6, borderRadius: radius.pill, backgroundColor: colors.surfaceTertiary, overflow: "hidden" },
  fetchFill: { height: 6, borderRadius: radius.pill, backgroundColor: colors.brand },

  segBtn: { flex: 1, paddingVertical: spacing.md, alignItems: "center", borderRadius: radius.sm },
  segActive: { backgroundColor: colors.brand },
  segText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  offlineNotice: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.xs, marginTop: spacing.sm },
  offlineText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm },
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
