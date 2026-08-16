import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { BlurView } from "expo-blur";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, downloadPhoto } from "@/src/api/client";
import { PhotoGrid } from "@/src/components/PhotoGrid";
import { EmptyState, GlassHeader, useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

export default function AdminClientGallery() {
  const { eventId, clientId, name } = useLocalSearchParams<{ eventId: string; clientId: string; name?: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [tab, setTab] = useState<"matched" | "liked">("matched");
  const [matched, setMatched] = useState<any[]>([]);
  const [liked, setLiked] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/events/${eventId}/clients/${clientId}/photos`);
      setMatched(res.matched || []);
      setLiked(res.liked || []);
    } catch (e: any) {
      toast.show(e?.message || "Could not load client gallery", "error");
    } finally {
      setLoading(false);
    }
  }, [eventId, clientId, toast]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const photos = tab === "matched" ? matched : liked;

  const download = async (photo: any) => {
    try {
      await downloadPhoto(photo);
    } catch {
      toast.show("Could not download", "error");
    }
  };

  const header = (
    <View style={{ paddingTop: spacing.lg }}>
      <BlurView intensity={30} tint="dark" style={styles.segment}>
        <Segment label={`My Photos${matched.length ? ` (${matched.length})` : ""}`} active={tab === "matched"} onPress={() => setTab("matched")} testID="admin-client-tab-matched" />
        <Segment label={`Liked${liked.length ? ` (${liked.length})` : ""}`} active={tab === "liked"} onPress={() => setTab("liked")} testID="admin-client-tab-liked" />
      </BlurView>
    </View>
  );

  return (
    <View style={styles.container} testID="admin-client-gallery-screen">
      <GlassHeader
        title={name || "Client gallery"}
        subtitle={tab === "matched" ? "Matched photos" : "Liked photos"}
        onBack={() => router.back()}
        topInset={insets.top}
      />
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : photos.length === 0 ? (
        <View style={{ flex: 1 }}>
          {header}
          <EmptyState
            icon={tab === "matched" ? "images-outline" : "heart-outline"}
            title={tab === "matched" ? "No matched photos" : "No liked photos"}
            subtitle={tab === "matched" ? "This client hasn't been matched to any photos yet." : "This client hasn't liked any photos yet."}
          />
        </View>
      ) : (
        <PhotoGrid photos={photos} showScore={tab === "matched"} onDownload={download} ListHeaderComponent={header} />
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
});
