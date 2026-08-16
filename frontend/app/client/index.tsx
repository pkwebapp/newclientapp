import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, imgUrl } from "@/src/api/client";
import { useAuth } from "@/src/context/AuthContext";
import { EmptyState, Pill, GlassHeader, useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

const FALLBACK =
  "https://images.unsplash.com/photo-1623672655496-1537b4d84eb4?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NzB8MHwxfHNlYXJjaHwxfHxlbGVnYW50JTIwd2VkZGluZyUyMGV2ZW50JTIwcGhvdG9ncmFwaHklMjBkYXJrfGVufDB8fHx8MTc4NjgyMzAxOXww&ixlib=rb-4.1.0&q=85";

export default function ClientEvents() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, signOut } = useAuth();
  const toast = useToast();
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get("/client/events");
      setEvents(res);
    } catch {
      toast.show("Could not load your galleries", "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [toast]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  return (
    <View style={styles.container} testID="client-events-screen">
      <GlassHeader
        title="Your Galleries"
        subtitle={user?.name ? `Hi, ${user.name}` : undefined}
        topInset={insets.top}
        right={
          <Pressable testID="signout-btn" onPress={signOut} hitSlop={10} style={{ padding: 6 }}>
            <Ionicons name="log-out-outline" size={22} color={colors.onSurfaceTertiary} />
          </Pressable>
        }
      />
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing["3xl"] }}
          refreshControl={
            <RefreshControl
              tintColor={colors.brand}
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                load();
              }}
            />
          }
        >
          {events.length === 0 ? (
            <EmptyState
              icon="mail-open-outline"
              title="No galleries yet"
              subtitle="When a studio shares an event with you, it will appear here. Pull down to refresh."
            />
          ) : (
            events.map((e) => (
              <Pressable
                key={e.event_id}
                testID={`event-card-${e.event_id}`}
                onPress={() => router.push(`/client/event/${e.event_id}`)}
                style={styles.card}
              >
                <Image
                  source={{ uri: imgUrl(e.cover_url, e.cover_path) || FALLBACK }}
                  style={StyleSheet.absoluteFill}
                  contentFit="cover"
                  transition={250}
                />
                <LinearGradient
                  colors={["transparent", "rgba(13,13,13,0.35)", "rgba(13,13,13,0.92)"]}
                  locations={[0, 0.45, 1]}
                  style={StyleSheet.absoluteFill}
                />
                <View style={styles.cardTop}>
                  <Pill
                    label={categoryMeta[e.category]?.label || e.category}
                    tone="gold"
                  />
                  {e.my_photos_count > 0 && (
                    <Pill label={`${e.my_photos_count} of you`} tone="success" icon="sparkles" />
                  )}
                </View>
                <View style={styles.cardBottom}>
                  <Text style={styles.cardTitle} numberOfLines={1}>
                    {e.name}
                  </Text>
                  <View style={styles.metaRow}>
                    {e.date ? (
                      <Text style={styles.meta}>
                        <Ionicons name="calendar-outline" size={12} /> {e.date}
                      </Text>
                    ) : null}
                    {e.photographer ? <Text style={styles.meta}>  •  {e.photographer}</Text> : null}
                  </View>
                </View>
              </Pressable>
            ))
          )}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: {
    width: "100%",
    height: 220,
    borderRadius: radius.lg,
    overflow: "hidden",
    marginBottom: spacing.lg,
    backgroundColor: colors.surfaceSecondary,
  },
  cardTop: {
    position: "absolute",
    top: spacing.md,
    left: spacing.md,
    right: spacing.md,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  cardBottom: { position: "absolute", left: spacing.lg, right: spacing.lg, bottom: spacing.lg },
  cardTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  metaRow: { flexDirection: "row", alignItems: "center", marginTop: spacing.xs },
  meta: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm },
});
