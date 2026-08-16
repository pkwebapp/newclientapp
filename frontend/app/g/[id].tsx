import { useCallback, useEffect, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, publicApi, setAuthToken, ApiError } from "@/src/api/client";
import { storage } from "@/src/utils/storage";
import { Button, TextField, EmptyState, useToast } from "@/src/components/ui";
import { PhotoGrid, Photo } from "@/src/components/PhotoGrid";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

type Phase = "loading" | "gate" | "gallery" | "notfound" | "disabled";
type Tab = "all" | "liked" | "mine";

const tokenKey = (id: string) => `pik_visitor_token_${id}`;

export default function PublicGallery() {
  const { id, tab: tabParam } = useLocalSearchParams<{ id: string; tab?: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [phase, setPhase] = useState<Phase>("loading");
  const [event, setEvent] = useState<any>(null);
  const [visitorName, setVisitorName] = useState<string>("");

  // gate form
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // gallery
  const [tab, setTab] = useState<Tab>((tabParam as Tab) || "all");
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [loadingPhotos, setLoadingPhotos] = useState(false);
  const [searched, setSearched] = useState(false);

  // --- Data loading helpers ---
  const loadTab = useCallback(
    async (which: Tab) => {
      setLoadingPhotos(true);
      try {
        if (which === "all") {
          const ps = await api.get(`/client/events/${id}/photos`);
          setPhotos(ps);
        } else if (which === "liked") {
          const r = await api.get(`/client/events/${id}/liked`);
          setPhotos(r.photos || []);
        } else {
          const r = await api.get(`/client/events/${id}/my-photos`);
          setPhotos(r.photos || []);
          setSearched(!!r.searched);
        }
      } catch (e: any) {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
          // token invalid / blocked → back to gate
          await storage.secureRemove(tokenKey(String(id)));
          setAuthToken(null);
          setPhase("gate");
          if (e.status === 403) toast.show(e.message, "error");
        } else {
          toast.show("Could not load photos", "error");
        }
      } finally {
        setLoadingPhotos(false);
      }
    },
    [id, toast]
  );

  const enterGallery = useCallback(
    async (token: string, eventData?: any, nm?: string) => {
      setAuthToken(token);
      await storage.secureSet(tokenKey(String(id)), token);
      if (eventData) setEvent(eventData);
      if (nm) setVisitorName(nm);
      setPhase("gallery");
    },
    [id]
  );

  // --- Bootstrap ---
  const bootstrap = useCallback(async () => {
    try {
      const info = await publicApi.get(`/public/events/${id}`);
      setEvent(info);
      const stored = await storage.secureGet<string>(tokenKey(String(id)), "");
      if (stored) {
        setAuthToken(stored);
        try {
          const me = await api.get(`/auth/me`);
          setVisitorName(me?.user?.name || "");
          setPhase("gallery");
          return;
        } catch {
          await storage.secureRemove(tokenKey(String(id)));
          setAuthToken(null);
        }
      }
      setPhase("gate");
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 403) setPhase("disabled");
      else setPhase("notfound");
    }
  }, [id]);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  // Reload the active tab whenever gallery is shown / refocused (e.g. after selfie).
  useFocusEffect(
    useCallback(() => {
      (async () => {
        if (phase === "gallery") {
          // Re-apply token in case it was cleared by another screen.
          const stored = await storage.secureGet<string>(tokenKey(String(id)), "");
          if (stored) setAuthToken(stored);
          loadTab(tab);
        }
      })();
    }, [phase, tab, id, loadTab])
  );

  const submitAccess = async () => {
    if (!name.trim()) return toast.show("Please enter your name", "error");
    if (phone.trim().length < 6) return toast.show("Enter a valid mobile number", "error");
    Keyboard.dismiss();
    setSubmitting(true);
    try {
      const res = await publicApi.post(`/public/events/${id}/access`, {
        name: name.trim(),
        phone: phone.trim(),
      });
      await enterGallery(res.session_token, res.event, res.user?.name);
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not open gallery", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleLike = async (photo: Photo) => {
    try {
      const r = await api.post(`/client/events/${id}/photos/${photo.photo_id}/like`);
      setPhotos((prev) =>
        tab === "liked" && !r.liked
          ? prev.filter((p) => p.photo_id !== photo.photo_id)
          : prev.map((p) => (p.photo_id === photo.photo_id ? { ...p, liked: r.liked } : p))
      );
    } catch {
      toast.show("Could not update like", "error");
    }
  };

  const switchVisitor = async () => {
    await storage.secureRemove(tokenKey(String(id)));
    setAuthToken(null);
    setName("");
    setPhone("");
    setPhotos([]);
    setPhase("gate");
  };

  // ---------------- RENDER ----------------
  if (phase === "loading") {
    return (
      <View style={styles.center} testID="public-loading">
        <Text style={styles.brand}>PIK CONNECT</Text>
        <ActivityIndicator color={colors.brand} style={{ marginTop: spacing.lg }} />
      </View>
    );
  }

  if (phase === "notfound" || phase === "disabled") {
    return (
      <View style={styles.center} testID="public-unavailable">
        <View style={styles.unavailIcon}>
          <Ionicons name={phase === "disabled" ? "lock-closed-outline" : "image-outline"} size={30} color={colors.brand} />
        </View>
        <Text style={styles.unavailTitle}>
          {phase === "disabled" ? "Gallery not available" : "Gallery not found"}
        </Text>
        <Text style={styles.unavailSub}>
          {phase === "disabled"
            ? "The photographer has turned off sharing for this gallery."
            : "This link may be incorrect or has expired."}
        </Text>
      </View>
    );
  }

  if (phase === "gate") {
    return (
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        testID="public-gate-screen"
      >
        <LinearGradient colors={["#141207", colors.surface]} style={StyleSheet.absoluteFill} />
        <ScrollView
          contentContainerStyle={[styles.gateBody, { paddingTop: insets.top + spacing["3xl"], paddingBottom: insets.bottom + spacing.xl }]}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.logoRow}>
            <Ionicons name="aperture-outline" size={24} color={colors.brand} />
            <Text style={styles.logo}>PIK CONNECT</Text>
          </View>

          <View style={styles.gateCard}>
            <View style={styles.gateIcon}>
              <Ionicons name={(categoryMeta[event?.category]?.icon as any) || "images"} size={26} color={colors.brand} />
            </View>
            <Text style={styles.gateEyebrow}>You're invited to</Text>
            <Text style={styles.gateTitle}>{event?.name}</Text>
            <Text style={styles.gateMeta}>
              {[categoryMeta[event?.category]?.label, event?.photographer, event?.photo_count ? `${event.photo_count} photos` : null]
                .filter(Boolean)
                .join("  ·  ")}
            </Text>

            <View style={{ height: spacing.xl }} />
            <Text style={styles.formHint}>Enter your details to view the gallery</Text>
            <TextField
              testID="visitor-name-input"
              label="Your name"
              value={name}
              onChangeText={setName}
              placeholder="e.g. Riya Sharma"
              autoCapitalize="words"
              returnKeyType="next"
            />
            <TextField
              testID="visitor-phone-input"
              label="Mobile number"
              value={phone}
              onChangeText={setPhone}
              placeholder="e.g. +91 98765 43210"
              keyboardType="phone-pad"
              returnKeyType="done"
              onSubmitEditing={submitAccess}
            />
            <Button testID="visitor-enter-btn" title="View gallery" icon="arrow-forward" loading={submitting} onPress={submitAccess} />
            <Text style={styles.privacy}>
              By continuing you agree the studio may contact you about these photos.
            </Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    );
  }

  // ---------------- GALLERY ----------------
  const emptyForTab =
    tab === "liked"
      ? { icon: "heart-outline", title: "No liked photos yet", subtitle: "Tap the heart on any photo to save it here." }
      : tab === "mine"
      ? {
          icon: "person-outline",
          title: searched ? "No matches found" : "Find your photos",
          subtitle: searched
            ? "We couldn't find you this time. Try a clearer selfie in good light."
            : "Take a quick selfie and we'll surface every photo you're in.",
        }
      : { icon: "images-outline", title: "No photos yet", subtitle: "The photographer hasn't added photos to this gallery." };

  const header = (
    <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.md }}>
      <Text style={styles.galleryTitle} numberOfLines={1}>{event?.name}</Text>
      <Text style={styles.gallerySub}>
        {visitorName ? `Viewing as ${visitorName}` : "Public gallery"}
      </Text>

      <View style={styles.tabs}>
        {(["all", "liked", "mine"] as Tab[]).map((t) => (
          <Pressable key={t} testID={`public-tab-${t}`} onPress={() => setTab(t)} style={[styles.tab, tab === t && styles.tabActive]}>
            <Ionicons
              name={t === "all" ? "grid-outline" : t === "liked" ? "heart-outline" : "person-outline"}
              size={15}
              color={tab === t ? colors.onBrand : colors.onSurfaceTertiary}
            />
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t === "all" ? "All photos" : t === "liked" ? "Liked" : "My photos"}
            </Text>
          </Pressable>
        ))}
      </View>

      {tab === "mine" && (
        <Button
          testID="find-my-photos-btn"
          title={searched ? "Re-scan my selfie" : "Find my photos"}
          icon="sparkles"
          onPress={() => router.push(`/g/selfie/${id}`)}
          style={{ marginBottom: spacing.md }}
        />
      )}
    </View>
  );

  return (
    <View style={styles.container} testID="public-gallery-screen">
      <View style={[styles.galleryTop, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.logoRow}>
          <Ionicons name="aperture-outline" size={20} color={colors.brand} />
          <Text style={styles.logoSm}>PIK CONNECT</Text>
        </View>
        <Pressable testID="switch-visitor-btn" onPress={switchVisitor} style={styles.exitBtn} hitSlop={8}>
          <Ionicons name="log-out-outline" size={16} color={colors.onSurfaceTertiary} />
          <Text style={styles.exitText}>Exit</Text>
        </Pressable>
      </View>

      {loadingPhotos && photos.length === 0 ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : photos.length === 0 ? (
        <ScrollView contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xl }}>
          {header}
          <EmptyState icon={emptyForTab.icon as any} title={emptyForTab.title} subtitle={emptyForTab.subtitle} />
        </ScrollView>
      ) : (
        <PhotoGrid
          photos={photos}
          showScore={tab === "mine"}
          onToggleLike={toggleLike}
          ListHeaderComponent={header}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  brand: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize["2xl"], letterSpacing: 2 },
  logoRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  logo: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, letterSpacing: 4, fontWeight: "600" },
  logoSm: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm, letterSpacing: 3, fontWeight: "600" },

  // gate
  gateBody: { paddingHorizontal: spacing.xl, flexGrow: 1, width: "100%", maxWidth: 560, alignSelf: "center" },
  gateCard: {
    marginTop: spacing["2xl"],
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.xl,
  },
  gateIcon: {
    width: 60, height: 60, borderRadius: radius.pill, backgroundColor: colors.brandTertiary,
    alignItems: "center", justifyContent: "center", marginBottom: spacing.lg,
  },
  gateEyebrow: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, letterSpacing: 1, textTransform: "uppercase" },
  gateTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["3xl"], marginTop: 4 },
  gateMeta: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: spacing.sm },
  formHint: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, marginBottom: spacing.lg },
  privacy: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.lg, lineHeight: 18, textAlign: "center" },

  // unavailable
  unavailIcon: {
    width: 72, height: 72, borderRadius: radius.pill, backgroundColor: colors.brandTertiary,
    alignItems: "center", justifyContent: "center", marginBottom: spacing.lg,
  },
  unavailTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], textAlign: "center" },
  unavailSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, textAlign: "center", marginTop: spacing.sm, maxWidth: 300, lineHeight: 20 },

  // gallery
  galleryTop: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: spacing.lg, paddingBottom: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border,
  },
  exitBtn: { flexDirection: "row", alignItems: "center", gap: 4 },
  exitText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm },
  galleryTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  gallerySub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2, marginBottom: spacing.md },
  tabs: { flexDirection: "row", backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.xs, marginBottom: spacing.md },
  tab: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: spacing.md, borderRadius: radius.sm },
  tabActive: { backgroundColor: colors.brand },
  tabText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.sm },
  tabTextActive: { color: colors.onBrand, fontWeight: "600" },
});
