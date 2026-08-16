import React, { useMemo, useState } from "react";
import {
  Dimensions,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";
import { fileUrl } from "@/src/api/client";
import { Pill } from "@/src/components/ui";

export type Photo = {
  photo_id: string;
  thumb_path?: string | null;
  storage_path?: string | null;
  filename?: string | null;
  width?: number;
  height?: number;
  similarity?: number | null;
  liked?: boolean;
};

const GAP = spacing.sm;
const CAPTION_H = 22;

/** Responsive masonry grid (2 → 3 → 4 columns) with captions + like/download. */
export function PhotoGrid({
  photos,
  showScore,
  showCaption = true,
  contentPadding = spacing.lg,
  ListHeaderComponent,
  onToggleLike,
  onDownload,
}: {
  photos: Photo[];
  showScore?: boolean;
  showCaption?: boolean;
  contentPadding?: number;
  ListHeaderComponent?: React.ReactElement;
  onToggleLike?: (photo: Photo) => void;
  onDownload?: (photo: Photo) => void;
}) {
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);
  const [containerW, setContainerW] = useState(Dimensions.get("window").width);

  const numCols = containerW >= 1000 ? 4 : containerW >= 640 ? 3 : 2;
  const colW = (containerW - contentPadding * 2 - GAP * (numCols - 1)) / numCols;
  const capH = showCaption ? CAPTION_H : 0;

  const columns = useMemo(() => {
    const cols: { photo: Photo; h: number; index: number }[][] = Array.from({ length: numCols }, () => []);
    const heights = new Array(numCols).fill(0);
    photos.forEach((p, index) => {
      const ratio = p.width && p.height ? p.height / p.width : 1.25;
      const h = Math.max(120, Math.min(colW * ratio, colW * 1.8));
      let target = 0;
      for (let i = 1; i < numCols; i++) if (heights[i] < heights[target]) target = i;
      cols[target].push({ photo: p, h, index });
      heights[target] += h + capH + GAP;
    });
    return cols;
  }, [photos, colW, numCols, capH]);

  const caption = (p: Photo, index: number) =>
    (p.filename && p.filename.trim()) || `#${index + 1}`;

  const renderCol = (items: { photo: Photo; h: number; index: number }[], key: number) => (
    <View key={key} style={{ width: colW }}>
      {items.map(({ photo, h, index }) => (
        <View key={photo.photo_id} style={{ marginBottom: GAP }}>
          <Pressable
            testID={`photo-${photo.photo_id}`}
            onPress={() => {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
              setViewerIndex(index);
            }}
            style={[styles.card, { height: h }]}
          >
            <Image
              source={{ uri: fileUrl(photo.thumb_path || photo.storage_path) }}
              style={StyleSheet.absoluteFill}
              contentFit="cover"
              transition={200}
              cachePolicy="memory-disk"
            />
            {showScore && photo.similarity != null && (
              <View style={styles.scoreTag}>
                <Pill label={`${Math.round(photo.similarity)}% match`} tone="gold" icon="sparkles" />
              </View>
            )}
            {onToggleLike && (
              <Pressable
                testID={`like-${photo.photo_id}`}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
                  onToggleLike(photo);
                }}
                hitSlop={8}
                style={styles.heartBtn}
              >
                <Ionicons
                  name={photo.liked ? "heart" : "heart-outline"}
                  size={18}
                  color={photo.liked ? colors.brand : colors.onSurface}
                />
              </Pressable>
            )}
          </Pressable>
          {showCaption && (
            <Text style={styles.caption} numberOfLines={1}>
              {caption(photo, index)}
            </Text>
          )}
        </View>
      ))}
    </View>
  );

  return (
    <>
      <FlatList
        data={[0]}
        keyExtractor={() => "grid"}
        style={{ flex: 1 }}
        onLayout={(e) => {
          const w = e.nativeEvent.layout.width;
          if (w && Math.abs(w - containerW) > 1) setContainerW(w);
        }}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={ListHeaderComponent}
        renderItem={() => (
          <View style={[styles.masonry, { paddingHorizontal: contentPadding }]}>
            {columns.map((col, i) => (
              <React.Fragment key={i}>
                {i > 0 && <View style={{ width: GAP }} />}
                {renderCol(col, i)}
              </React.Fragment>
            ))}
          </View>
        )}
      />
      <FullscreenViewer
        photos={photos}
        index={viewerIndex}
        onClose={() => setViewerIndex(null)}
        onToggleLike={onToggleLike}
        onDownload={onDownload}
      />
    </>
  );
}

function FullscreenViewer({
  photos,
  index,
  onClose,
  onToggleLike,
  onDownload,
}: {
  photos: Photo[];
  index: number | null;
  onClose: () => void;
  onToggleLike?: (photo: Photo) => void;
  onDownload?: (photo: Photo) => void;
}) {
  const [current, setCurrent] = useState(0);
  const screenW = Dimensions.get("window").width;
  const screenH = Dimensions.get("window").height;
  if (index == null) return null;
  const active = photos[current] || photos[index];

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.viewer}>
        <FlatList
          data={photos}
          horizontal
          pagingEnabled
          initialScrollIndex={index}
          onMomentumScrollEnd={(e) => setCurrent(Math.round(e.nativeEvent.contentOffset.x / screenW))}
          getItemLayout={(_, i) => ({ length: screenW, offset: screenW * i, index: i })}
          keyExtractor={(p) => p.photo_id}
          showsHorizontalScrollIndicator={false}
          renderItem={({ item }) => (
            <Pressable style={{ width: screenW, height: screenH }} onPress={onClose}>
              <Image
                source={{ uri: fileUrl(item.storage_path || item.thumb_path) }}
                style={{ width: screenW, height: screenH }}
                contentFit="contain"
                transition={150}
                cachePolicy="memory-disk"
              />
              {item.similarity != null && (
                <View style={styles.viewerScore}>
                  <Text style={styles.viewerScoreText}>{Math.round(item.similarity)}% match</Text>
                </View>
              )}
            </Pressable>
          )}
        />

        {/* Filename */}
        {active?.filename ? (
          <View style={styles.viewerName} pointerEvents="none">
            <Text style={styles.viewerNameText} numberOfLines={1}>{active.filename}</Text>
          </View>
        ) : null}

        {/* Action bar (like + download) */}
        {(onToggleLike || onDownload) && active && (
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
  card: {
    width: "100%",
    borderRadius: radius.md,
    overflow: "hidden",
    backgroundColor: colors.surfaceSecondary,
  },
  caption: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 4, paddingHorizontal: 2 },
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
});
