import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Dimensions,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { imgUrl } from "@/src/api/client";
import { Pill } from "@/src/components/ui";

export type Photo = {
  photo_id: string;
  thumb_path?: string | null;
  storage_path?: string | null;
  url?: string | null;
  thumb_url?: string | null;
  filename?: string | null;
  width?: number;
  height?: number;
  similarity?: number | null;
  liked?: boolean;
};

const GAP = spacing.sm;

function BrandedImage({
  photoId,
  uri,
  style,
  contentFit,
  cachePolicy = "memory",
  transition = 200,
}: {
  photoId?: string;
  uri?: string;
  style?: any;
  contentFit: "cover" | "contain";
  cachePolicy?: "memory" | "disk" | "memory-disk" | "none";
  transition?: number;
}) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">(uri ? "loading" : "error");
  const [retryKey, setRetryKey] = useState(0);
  const [lastUri, setLastUri] = useState(uri);

  // Reset synchronously during render (not in an effect) so a recycled cell
  // never shows the previous photo's state for even a single frame.
  if (lastUri !== uri) {
    setLastUri(uri);
    setStatus(uri ? "loading" : "error");
    setRetryKey(0);
  }

  const retry = (event?: { stopPropagation?: () => void }) => {
    event?.stopPropagation?.();
    if (!uri) return;
    setStatus("loading");
    setRetryKey((key) => key + 1);
  };

  return (
    <View style={style}>
      {uri ? (
        <Image
          key={`${photoId || "photo"}-${uri}-${retryKey}`}
          recyclingKey={photoId || uri}
          source={{ uri }}
          style={StyleSheet.absoluteFill}
          contentFit={contentFit}
          transition={transition}
          cachePolicy={cachePolicy}
          onLoadStart={() => setStatus("loading")}
          onLoad={() => setStatus("ready")}
          onError={() => setStatus("error")}
        />
      ) : null}
      {status !== "ready" && (
        <View style={styles.imageStateOverlay} pointerEvents={status === "error" ? "auto" : "none"}>
          <View style={styles.imageStateMark}>
            <Ionicons name="aperture-outline" size={22} color={colors.brand} />
          </View>
          {status === "loading" ? (
            <>
              <ActivityIndicator color={colors.brand} size="small" />
              <Text style={styles.imageStateBrand}>PIK CONNECT</Text>
              <Text style={styles.imageStateLabel}>Loading photo</Text>
            </>
          ) : (
            <>
              <Text style={styles.imageStateBrand}>PIK CONNECT</Text>
              <Text style={styles.imageStateLabel}>Photo unavailable</Text>
              <Pressable testID="photo-retry" onPress={retry} style={styles.imageRetry}>
                <Ionicons name="refresh-outline" size={15} color={colors.onBrand} />
                <Text style={styles.imageRetryText}>Tap to retry</Text>
              </Pressable>
            </>
          )}
        </View>
      )}
    </View>
  );
}

/** Virtualized masonry grid (2 → 3 → 4 columns) with captions + like/download
 *  and built-in infinite scroll. Powered by @shopify/flash-list. */
export function PhotoGrid({
  photos,
  showScore,
  showCaption = false,
  contentPadding = spacing.lg,
  ListHeaderComponent,
  onToggleLike,
  onDownload,
  onShare,
  onEndReached,
  loadingMore,
}: {
  photos: Photo[];
  showScore?: boolean;
  showCaption?: boolean;
  contentPadding?: number;
  ListHeaderComponent?: React.ReactElement;
  onToggleLike?: (photo: Photo) => void;
  onDownload?: (photo: Photo) => void;
  onShare?: (photo: Photo) => void;
  onEndReached?: () => void;
  loadingMore?: boolean;
}) {
  const [viewerPhotoId, setViewerPhotoId] = useState<string | null>(null);
  const [containerW, setContainerW] = useState(Dimensions.get("window").width);
  const [captionsOn, setCaptionsOn] = useState(showCaption);

  const numCols = containerW >= 1000 ? 4 : containerW >= 640 ? 3 : 2;
  const colW = Math.max(80, (containerW - contentPadding * 2) / numCols - GAP);

  const caption = (p: Photo, index: number) =>
    (p.filename && p.filename.trim()) || `#${index + 1}`;

  const renderItem = ({ item, index }: { item: Photo; index: number }) => {
    const ratio = item.width && item.height ? item.height / item.width : 1.25;
    const h = Math.max(120, Math.min(colW * ratio, colW * 1.8));
    return (
      <View style={{ paddingHorizontal: GAP / 2, marginBottom: GAP }}>
        <Pressable
          testID={`photo-${item.photo_id}`}
          onPress={() => {
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
            setViewerPhotoId(item.photo_id);
          }}
          style={[styles.card, { height: h }]}
        >
          <BrandedImage
            photoId={item.photo_id}
            uri={imgUrl(item.thumb_url || item.url, item.thumb_path || item.storage_path)}
            style={StyleSheet.absoluteFill}
            contentFit="cover"
          />
          {showScore && item.similarity != null && (
            <View style={styles.scoreTag}>
              <Pill label={`${Math.round(item.similarity)}% match`} tone="gold" icon="sparkles" />
            </View>
          )}
          {onToggleLike && (
            <Pressable
              testID={`like-${item.photo_id}`}
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
                onToggleLike(item);
              }}
              hitSlop={8}
              style={styles.heartBtn}
            >
              <Ionicons
                name={item.liked ? "heart" : "heart-outline"}
                size={18}
                color={item.liked ? colors.brand : colors.onSurface}
              />
            </Pressable>
          )}
        </Pressable>
        {captionsOn && (
          <Text style={styles.caption} numberOfLines={1}>
            {caption(item, index)}
          </Text>
        )}
      </View>
    );
  };

  return (
    <View
      style={{ flex: 1 }}
      onLayout={(e) => {
        const w = e.nativeEvent.layout.width;
        if (w && Math.abs(w - containerW) > 1) setContainerW(w);
      }}
    >
      <FlashList
        data={photos}
        masonry
        optimizeItemArrangement
        numColumns={numCols}
        keyExtractor={(item) => item.photo_id}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <View>
            {ListHeaderComponent}
            {photos.length > 0 && (
              <View style={styles.toolbar}>
                <Pressable
                  testID="toggle-numbers"
                  onPress={() => {
                    Haptics.selectionAsync().catch(() => {});
                    setCaptionsOn((v) => !v);
                  }}
                  hitSlop={8}
                  style={[styles.numBtn, captionsOn && styles.numBtnActive]}
                >
                  <Ionicons
                    name={captionsOn ? "pricetags" : "pricetags-outline"}
                    size={14}
                    color={captionsOn ? colors.onBrand : colors.onSurfaceTertiary}
                  />
                  <Text style={[styles.numText, captionsOn && styles.numTextActive]}>
                    {captionsOn ? "Numbers on" : "Numbers off"}
                  </Text>
                </Pressable>
              </View>
            )}
          </View>
        }
        contentContainerStyle={{ paddingHorizontal: contentPadding - GAP / 2, paddingBottom: spacing["3xl"] }}
        renderItem={renderItem}
        onEndReached={onEndReached}
        onEndReachedThreshold={0.6}
        ListFooterComponent={
          loadingMore ? (
            <View style={styles.footer}>
              <ActivityIndicator color={colors.brand} />
            </View>
          ) : null
        }
      />
      <FullscreenViewer
        photos={photos}
        photoId={viewerPhotoId}
        onClose={() => setViewerPhotoId(null)}
        onToggleLike={onToggleLike}
        onDownload={onDownload}
        onShare={onShare}
      />
    </View>
  );
}

function ZoomablePhoto({
  photo,
  screenW,
  screenH,
  onTap,
}: {
  photo: Photo;
  screenW: number;
  screenH: number;
  onTap: () => void;
}) {
  const scale = useSharedValue(1);
  const savedScale = useSharedValue(1);

  useEffect(() => {
    scale.value = 1;
    savedScale.value = 1;
  }, [photo.photo_id, savedScale, scale]);
  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  const pinch = Gesture.Pinch()
    .onStart(() => {
      savedScale.value = scale.value;
    })
    .onUpdate((event) => {
      scale.value = Math.min(4, Math.max(1, savedScale.value * event.scale));
    })
    .onEnd(() => {
      if (scale.value < 1.05) {
        scale.value = withTiming(1);
        savedScale.value = 1;
      } else {
        savedScale.value = scale.value;
      }
    });

  const doubleTap = Gesture.Tap()
    .numberOfTaps(2)
    .maxDuration(250)
    .onEnd(() => {
      const next = scale.value > 1.05 ? 1 : 2.5;
      scale.value = withTiming(next);
      savedScale.value = next;
    });

  const singleTap = Gesture.Tap()
    .maxDuration(220)
    .onEnd(() => runOnJS(onTap)());

  const gesture = Gesture.Simultaneous(pinch, Gesture.Exclusive(doubleTap, singleTap));

  return (
    <GestureDetector gesture={gesture}>
      <View style={[styles.zoomStage, { width: screenW, height: screenH }]}>
        <Animated.View style={[styles.zoomImage, { width: screenW, height: screenH }, animatedStyle]}>
          <BrandedImage
            photoId={photo.photo_id}
            uri={imgUrl(photo.url || photo.thumb_url, photo.storage_path || photo.thumb_path)}
            style={StyleSheet.absoluteFill}
            contentFit="contain"
            cachePolicy="none"
            transition={150}
          />
        </Animated.View>
      </View>
    </GestureDetector>
  );
}
function FullscreenViewer({
  photos,
  photoId,
  onClose,
  onToggleLike,
  onDownload,
  onShare,
}: {
  photos: Photo[];
  photoId: string | null;
  onClose: () => void;
  onToggleLike?: (photo: Photo) => void;
  onDownload?: (photo: Photo) => void;
  onShare?: (photo: Photo) => void;
}) {
  const [current, setCurrent] = useState(0);
  const listRef = useRef<FlatList<Photo>>(null);
  const screenW = Dimensions.get("window").width;
  const screenH = Dimensions.get("window").height;
  const selectedIndex = photoId ? photos.findIndex((photo) => photo.photo_id === photoId) : -1;
  const selectedPhoto = selectedIndex >= 0 ? photos[selectedIndex] : null;
  const selectedPhotoId = selectedPhoto?.photo_id;
  // Put the tapped photo first. React Native Web can ignore/restore FlatList's
  // initialScrollIndex inside a Modal, so making the selected item index 0
  // guarantees the first rendered image matches the card that was tapped.
  const viewerPhotos = selectedPhoto
    ? [selectedPhoto, ...photos.filter((photo) => photo.photo_id !== selectedPhoto.photo_id)]
    : [];

  useEffect(() => {
    if (!photoId || !selectedPhotoId) return;
    setCurrent(0);
    requestAnimationFrame(() => {
      listRef.current?.scrollToOffset({ offset: 0, animated: false });
    });
  }, [photoId, selectedPhotoId]);

  if (!photoId || !selectedPhoto) return null;
  const active = viewerPhotos[current] || selectedPhoto;

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.viewer}>
        <FlatList
          data={viewerPhotos}
          key={`viewer-${photoId}`}
          ref={listRef}
          horizontal
          pagingEnabled
          initialScrollIndex={0}
          onMomentumScrollEnd={(e) => setCurrent(Math.round(e.nativeEvent.contentOffset.x / screenW))}
          getItemLayout={(_, i) => ({ length: screenW, offset: screenW * i, index: i })}
          keyExtractor={(p) => p.photo_id}
          extraData={`${photoId}-${current}`}
          initialNumToRender={1}
          maxToRenderPerBatch={2}
          windowSize={3}
          removeClippedSubviews={false}
          showsHorizontalScrollIndicator={false}
          renderItem={({ item }) => (
            <View key={item.photo_id} style={{ width: screenW, height: screenH }}>
              <ZoomablePhoto
                photo={item}
                screenW={screenW}
                screenH={screenH}
                onTap={onClose}
              />
              {item.similarity != null && (
                <View style={styles.viewerScore} pointerEvents="none">
                  <Text style={styles.viewerScoreText}>{Math.round(item.similarity)}% match</Text>
                </View>
              )}
            </View>
          )}
        />

        {/* Filename */}
        {active?.filename ? (
          <View style={styles.viewerName} pointerEvents="none">
            <Text style={styles.viewerNameText} numberOfLines={1}>{active.filename}</Text>
          </View>
        ) : null}

        {/* Action bar (like + download) */}
        {(onToggleLike || onDownload || onShare) && active && (
          <View style={styles.viewerActions}>
            {onToggleLike && (
              <Pressable testID="viewer-like" onPress={() => onToggleLike(active)} style={styles.actionBtn} hitSlop={10}>
                <Ionicons name={active.liked ? "heart" : "heart-outline"} size={24} color={active.liked ? colors.brand : colors.onSurface} />
                <Text style={styles.actionText}>{active.liked ? "Liked" : "Like"}</Text>
              </Pressable>
            )}
            {onDownload && (
              <Pressable testID="viewer-download" onPress={() => onDownload(active)} style={styles.actionBtn} hitSlop={10}>
                <Ionicons name="download-outline" size={24} color={colors.onSurface} />
                <Text style={styles.actionText}>Download</Text>
              </Pressable>
            )}
            {onShare && (
              <Pressable testID="viewer-share" onPress={() => onShare(active)} style={styles.actionBtn} hitSlop={10}>
                <Ionicons name="share-social-outline" size={24} color={colors.onSurface} />
                <Text style={styles.actionText}>Share</Text>
              </Pressable>
            )}
          </View>
        )}

        <Pressable testID="viewer-close" onPress={onClose} style={styles.closeBtn} hitSlop={12}>
          <Ionicons name="close" size={26} color={colors.onSurface} />
        </Pressable>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  masonry: { flexDirection: "row", paddingTop: spacing.md, paddingBottom: spacing["3xl"] },
  footer: { paddingVertical: spacing.xl, alignItems: "center" },
  card: {
    width: "100%",
    borderRadius: radius.md,
    overflow: "hidden",
    backgroundColor: colors.surfaceSecondary,
  },
  caption: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 4, paddingHorizontal: 2 },
  toolbar: { flexDirection: "row", justifyContent: "flex-end", paddingHorizontal: GAP / 2, marginBottom: spacing.sm },
  numBtn: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: spacing.md, height: 32, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  numBtnActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  numText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm },
  numTextActive: { color: colors.onBrand, fontWeight: "600" },
  scoreTag: { position: "absolute", top: spacing.sm, left: spacing.sm },
  heartBtn: {
    position: "absolute",
    top: spacing.sm,
    right: spacing.sm,
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    backgroundColor: "rgba(0,0,0,0.45)",
    alignItems: "center",
    justifyContent: "center",
  },
  viewer: { flex: 1, backgroundColor: "#000", justifyContent: "center" },
  zoomStage: { alignItems: "center", justifyContent: "center", overflow: "hidden" },
  zoomImage: { alignItems: "center", justifyContent: "center" },
  closeBtn: {
    position: "absolute",
    top: 50,
    right: spacing.lg,
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    backgroundColor: "rgba(0,0,0,0.5)",
    alignItems: "center",
    justifyContent: "center",
  },
  viewerName: { position: "absolute", top: 56, left: spacing.lg, right: 80, backgroundColor: "rgba(0,0,0,0.45)", paddingHorizontal: spacing.md, paddingVertical: spacing.xs, borderRadius: radius.pill },
  viewerNameText: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm },
  viewerActions: {
    position: "absolute",
    bottom: 40,
    alignSelf: "center",
    flexDirection: "row",
    gap: spacing.md,
    backgroundColor: "rgba(0,0,0,0.6)",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: radius.pill,
  },
  actionBtn: { flexDirection: "row", alignItems: "center", gap: spacing.xs, paddingHorizontal: spacing.md },
  actionText: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  viewerScore: {
    position: "absolute",
    bottom: 110,
    alignSelf: "center",
    backgroundColor: "rgba(0,0,0,0.6)",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
  },
  viewerScoreText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base },
  imageStateOverlay: { ...StyleSheet.absoluteFillObject, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceTertiary, padding: spacing.sm },
  imageStateMark: { width: 42, height: 42, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.brandTertiary, marginBottom: spacing.sm },
  imageStateBrand: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: 10, fontWeight: "800", letterSpacing: 1.4, marginTop: spacing.sm, textAlign: "center" },
  imageStateLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.xs, textAlign: "center" },
  imageRetry: { minHeight: 44, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.xs, backgroundColor: colors.brand, borderRadius: radius.pill, paddingHorizontal: spacing.md, marginTop: spacing.md },
  imageRetryText: { color: colors.onBrand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
});
