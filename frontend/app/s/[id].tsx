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

import { api, publicApi, setAuthToken, downloadPhoto, ApiError } from "@/src/api/client";
import { storage } from "@/src/utils/storage";
import { Button, TextField, EmptyState, useToast } from "@/src/components/ui";
import { PhoneField, isPhoneNumberValid } from "@/src/components/PhoneField";
import { PhotoGrid, Photo } from "@/src/components/PhotoGrid";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

type Phase = "loading" | "gate" | "gallery" | "notfound" | "disabled";

const tokenKey = (id: string) => `pik_share_token_${id}`;

function scopeLabel(scope?: string, sharer?: string | null): string {
  if (scope === "matched") return sharer ? `Photos of ${sharer}` : "Tagged photos";
  if (scope === "liked") return sharer ? `${sharer}'s favourites` : "Liked photos";
  return "All photos";
}

export async function generateStaticParams(): Promise<Record<string, string>[]> {
  return [];
}

export default function SharedGallery() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [phase, setPhase] = useState<Phase>("loading");
  const [disabledMsg, setDisabledMsg] = useState<string>("");
  const [meta, setMeta] = useState<any>(null);
  const [scope, setScope] = useState<string>("all");
  const [sharerName, setSharerName] = useState<string>("");
  const [viewerName, setViewerName] = useState<string>("");

  // gate form
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // gallery
  const [photos, setPhotos] = useState<Photo[]>([]);

  const bootstrap = useCallback(async () => {
    try {
      const info = await publicApi.get(`/public/shares/${id}`);
      setMeta(info.event);
      setScope(info.scope);
      setSharerName(info.sharer_name || "");
      const stored = await storage.secureGet<string>(tokenKey(String(id)), "");
      if (stored) {
        setAuthToken(stored);
        try {
          const r = await api.get(`/public/shares/${id}/photos`);
          setPhotos(r.photos || []);
          setPhase("gallery");
          return;
        } catch {
          await storage.secureRemove(tokenKey(String(id)));
          setAuthToken(null);
        }
      }
      setPhase("gate");
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 403) {
        setDisabledMsg(e.message || "");
        setPhase("disabled");
      } else setPhase("notfound");
    }
  }, [id]);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useFocusEffect(
    useCallback(() => {
      (async () => {
        if (phase === "gallery") {
          const stored = await storage.secureGet<string>(tokenKey(String(id)), "");
          if (stored) setAuthToken(stored);
        }
      })();
    }, [phase, id])
  );

  const submitAccess = async () => {
    if (!name.trim()) return toast.show("Please enter your name", "error");
    if (!isPhoneNumberValid(phone)) return toast.show("Enter a valid mobile number for the selected country", "error");
    Keyboard.dismiss();
    setSubmitting(true);
    try {
      const res = await publicApi.post(`/public/shares/${id}/access`, {
        name: name.trim(),
        phone: phone.trim(),
      });
      setAuthToken(res.session_token);
      await storage.secureSet(tokenKey(String(id)), res.session_token);
      setPhotos(res.photos || []);
      setScope(res.scope);
      setSharerName(res.sharer_name || "");
      setViewerName(res.viewer?.name || "");
      setPhase("gallery");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not open gallery", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const exit = async () => {
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
      <View style={styles.center} testID="share-loading">
        <Text style={styles.brand}>PIK CONNECT</Text>
        <ActivityIndicator color={colors.brand} style={{ marginTop: spacing.lg }} />
      </View>
    );
  }

  if (phase === "notfound" || phase === "disabled") {
    return (
      <View style={styles.center} testID="share-unavailable">
        <View style={styles.unavailIcon}>
          <Ionicons name={phase === "disabled" ? "lock-closed-outline" : "image-outline"} size={30} color={colors.brand} />
        </View>
        <Text style={styles.unavailTitle}>
          {phase === "disabled" ? "Gallery not available" : "Share link not found"}
        </Text>
        <Text style={styles.unavailSub}>
          {phase === "disabled"
            ? disabledMsg || "The photographer has turned off sharing for this gallery."
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
        testID="share-gate-screen"
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
              <Ionicons name={(categoryMeta[meta?.category]?.icon as any) || "images"} size={26} color={colors.brand} />
            </View>
            <Text style={styles.gateEyebrow}>
              {sharerName ? `${sharerName} shared` : "Shared with you"}
            </Text>
            <Text style={styles.gateTitle}>{scopeLabel(scope, sharerName)}</Text>
            <Text style={styles.gateMeta}>
              {[meta?.name, categoryMeta[meta?.category]?.label].filter(Boolean).join("  ·  ")}
            </Text>

            <View style={{ height: spacing.xl }} />
            <Text style={styles.formHint}>Enter your details to view these photos</Text>
            <TextField
              testID="share-name-input"
              label="Your name"
              value={name}
              onChangeText={setName}
              placeholder="e.g. Riya Sharma"
              autoCapitalize="words"
              returnKeyType="next"
            />
            <PhoneField
              testID="share-phone-input"
              value={phone}
              onChangeText={setPhone}
              placeholder="Enter mobile number"
            />
            <Button testID="share-enter-btn" title="View photos" icon="arrow-forward" loading={submitting} onPress={submitAccess} />
            <Text style={styles.privacy}>
              By continuing you agree the studio may contact you about these photos.
            </Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    );
  }

  // ---------------- GALLERY ----------------
  const header = (
    <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.md }}>
      <Text style={styles.galleryTitle} numberOfLines={1}>{scopeLabel(scope, sharerName)}</Text>
      <Text style={styles.gallerySub} numberOfLines={1}>
        {[meta?.name, viewerName ? `Viewing as ${viewerName}` : null].filter(Boolean).join("  ·  ")}
      </Text>
      {meta?.face_search_enabled !== false && (
        <Pressable
          testID="share-find-own-btn"
          onPress={() => meta?.event_id && router.push(`/g/${meta.event_id}`)}
          style={styles.findOwn}
        >
          <Ionicons name="sparkles" size={15} color={colors.brand} />
          <Text style={styles.findOwnText}>Find your own photos in this gallery</Text>
          <Ionicons name="chevron-forward" size={15} color={colors.brand} />
        </Pressable>
      )}
    </View>
  );

  return (
    <View style={styles.container} testID="share-gallery-screen">
      <View style={[styles.galleryTop, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.logoRow}>
          <Ionicons name="aperture-outline" size={20} color={colors.brand} />
          <Text style={styles.logoSm}>PIK CONNECT</Text>
        </View>
        <Pressable testID="share-exit-btn" onPress={exit} style={styles.exitBtn} hitSlop={8}>
          <Ionicons name="log-out-outline" size={16} color={colors.onSurfaceTertiary} />
          <Text style={styles.exitText}>Exit</Text>
        </Pressable>
      </View>

      {photos.length === 0 ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : photos.length === 0 ? (
        <ScrollView contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xl }}>
          {header}
          <EmptyState icon="images-outline" title="No photos here" subtitle="This shared gallery doesn't have any photos yet." />
        </ScrollView>
      ) : (
        <PhotoGrid
          photos={photos}
          showScore={false}
          onDownload={(p) => downloadPhoto(p as any)}
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
  findOwn: {
    flexDirection: "row", alignItems: "center", gap: spacing.sm,
    backgroundColor: colors.brandTertiary, borderRadius: radius.md,
    paddingVertical: spacing.md, paddingHorizontal: spacing.lg, marginBottom: spacing.md,
  },
  findOwnText: { flex: 1, color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
});
