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
  width?: number;
  height?: number;
  similarity?: number | null;
};

const GAP = spacing.sm;

/** Two-column masonry grid that respects each photo's aspect ratio. */
export function PhotoGrid({
  photos,
  showScore,
  contentPadding = spacing.lg,
  ListHeaderComponent,
}: {
  photos: Photo[];
  showScore?: boolean;
  contentPadding?: number;
  ListHeaderComponent?: React.ReactElement;
}) {
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);
  const screenW = Dimensions.get("window").width;
  const colW = (screenW - contentPadding * 2 - GAP) / 2;

  const columns = useMemo(() => {
    const left: { photo: Photo; h: number; index: number }[] = [];
    const right: typeof left = [];
    let lh = 0;
    let rh = 0;
    photos.forEach((p, index) => {
      const ratio = p.width && p.height ? p.height / p.width : 1.25;
      const h = Math.max(120, Math.min(colW * ratio, colW * 1.8));
      if (lh <= rh) {
        left.push({ photo: p, h, index });
        lh += h + GAP;
      } else {
        right.push({ photo: p, h, index });
        rh += h + GAP;
      }
    });
    return { left, right };
  }, [photos, colW]);

  const renderCol = (items: { photo: Photo; h: number; index: number }[]) => (
    <View style={{ width: colW }}>
      {items.map(({ photo, h, index }) => (
        <Pressable
          key={photo.photo_id}
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
        </Pressable>
      ))}
    </View>
  );

  return (
    <>
      <FlatList
        data={[0]}
        keyExtractor={() => "grid"}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={ListHeaderComponent}
        renderItem={() => (
          <View style={[styles.masonry, { paddingHorizontal: contentPadding }]}>
            {renderCol(columns.left)}
            <View style={{ width: GAP }} />
            {renderCol(columns.right)}
          </View>
        )}
      />
      <FullscreenViewer
        photos={photos}
        index={viewerIndex}
        onClose={() => setViewerIndex(null)}
      />
    </>
  );
}

function FullscreenViewer({
  photos,
  index,
  onClose,
}: {
  photos: Photo[];
  index: number | null;
  onClose: () => void;
}) {
  const screenW = Dimensions.get("window").width;
  const screenH = Dimensions.get("window").height;
  if (index == null) return null;
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.viewer}>
        <FlatList
          data={photos}
          horizontal
          pagingEnabled
          initialScrollIndex={index}
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
    marginBottom: GAP,
    backgroundColor: colors.surfaceSecondary,
  },
  scoreTag: { position: "absolute", top: spacing.sm, left: spacing.sm },
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
  viewerScore: {
    position: "absolute",
    bottom: 60,
    alignSelf: "center",
    backgroundColor: "rgba(0,0,0,0.6)",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
  },
  viewerScoreText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base },
});
