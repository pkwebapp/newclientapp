import { useCallback, useRef, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";

import { api, ApiError } from "@/src/api/client";
import { Button, GlassHeader, useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

export default function SelfieScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const cameraRef = useRef<CameraView>(null);

  const [permission, requestPermission] = useCameraPermissions();
  const [consentGiven, setConsentGiven] = useState<boolean | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [processing, setProcessing] = useState(false);

  useFocusEffect(
    useCallback(() => {
      (async () => {
        try {
          const d = await api.get(`/client/events/${id}`);
          setConsentGiven(!!d.consent_given);
        } catch {
          setConsentGiven(false);
        }
      })();
    }, [id])
  );

  const acceptConsent = async () => {
    setAccepting(true);
    try {
      await api.post(`/client/events/${id}/consent`, { accepted: true });
      setConsentGiven(true);
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not save consent", "error");
    } finally {
      setAccepting(false);
    }
  };

  const runSearch = async (uri: string) => {
    setProcessing(true);
    try {
      const res = await api.upload(`/client/events/${id}/search`, uri, "selfie.jpg", "image/jpeg");
      if (res.status === "retake") {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
        toast.show(res.reason || "Please retake your selfie", "error");
        return;
      }
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      if (res.count > 0) {
        toast.show(`Found you in ${res.count} photo${res.count > 1 ? "s" : ""}!`, "success");
      } else {
        toast.show("No matches this time. Try better lighting.", "info");
      }
      router.replace(`/client/event/${id}`);
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Search failed", "error");
    } finally {
      setProcessing(false);
    }
  };

  const capture = async () => {
    if (!cameraRef.current || processing) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.6 });
      if (photo?.uri) await runSearch(photo.uri);
    } catch {
      toast.show("Couldn't capture. Try uploading instead.", "error");
    }
  };

  const pickFromLibrary = async () => {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      toast.show("Photo access is needed to upload a selfie", "error");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.6,
      allowsEditing: true,
    });
    if (!result.canceled && result.assets?.[0]?.uri) {
      await runSearch(result.assets[0].uri);
    }
  };

  // ---------- Consent step ----------
  if (consentGiven === null) {
    return (
      <View style={styles.center} testID="selfie-loading">
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }

  if (!consentGiven) {
    return (
      <View style={styles.container} testID="consent-screen">
        <GlassHeader title="Before we begin" onBack={() => router.back()} topInset={insets.top} />
        <ScrollView contentContainerStyle={[styles.consentBody, { paddingBottom: insets.bottom + spacing.xl }]}>
          <View style={styles.consentIcon}>
            <Ionicons name="shield-checkmark-outline" size={30} color={colors.brand} />
          </View>
          <Text style={styles.consentTitle}>Biometric consent</Text>
          <Text style={styles.consentText}>
            To find your photos, we analyse your selfie to create a temporary face signature and match it
            against this event's gallery.
          </Text>
          {[
            ["camera-outline", "Your selfie is used only for matching and is never stored."],
            ["finger-print-outline", "Only a match reference is kept — you can ask the studio to delete it anytime."],
            ["lock-closed-outline", "Your results stay private to you within this gallery."],
          ].map(([icon, text]) => (
            <View key={text} style={styles.bullet}>
              <Ionicons name={icon as any} size={18} color={colors.brand} />
              <Text style={styles.bulletText}>{text}</Text>
            </View>
          ))}
          <View style={{ marginTop: spacing["2xl"] }}>
            <Button testID="accept-consent-btn" title="I agree — continue" loading={accepting} onPress={acceptConsent} />
            <Pressable testID="decline-consent-btn" onPress={() => router.back()} style={{ marginTop: spacing.lg, alignItems: "center" }}>
              <Text style={styles.decline}>Not now</Text>
            </Pressable>
          </View>
        </ScrollView>
      </View>
    );
  }

  // ---------- Camera permission step ----------
  if (!permission?.granted) {
    return (
      <View style={styles.container} testID="camera-permission-screen">
        <GlassHeader title="Camera access" onBack={() => router.back()} topInset={insets.top} />
        <View style={styles.permBody}>
          <View style={styles.consentIcon}>
            <Ionicons name="camera-outline" size={30} color={colors.brand} />
          </View>
          <Text style={styles.consentTitle}>Enable your camera</Text>
          <Text style={styles.consentText}>We need the camera to take a selfie so we can find your photos.</Text>
          <View style={{ marginTop: spacing.xl, width: "100%" }}>
            {permission?.canAskAgain !== false ? (
              <Button testID="grant-camera-btn" title="Allow camera" icon="camera" onPress={requestPermission} />
            ) : (
              <Button testID="open-settings-btn" title="Open Settings" icon="settings-outline" onPress={() => Linking.openSettings()} />
            )}
            <Button testID="upload-instead-btn" title="Upload a selfie instead" variant="ghost" icon="image-outline" onPress={pickFromLibrary} style={{ marginTop: spacing.md }} />
          </View>
        </View>
      </View>
    );
  }

  // ---------- Camera capture step ----------
  return (
    <View style={styles.cameraContainer} testID="selfie-camera-screen">
      <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing="front" />

      {/* Silhouette mask overlay (>50% opacity outside the oval) */}
      <View style={styles.overlay} pointerEvents="none">
        <View style={styles.maskTop} />
        <View style={styles.maskMiddle}>
          <View style={styles.maskSide} />
          <View style={styles.ovalWrap}>
            <View style={styles.oval} />
          </View>
          <View style={styles.maskSide} />
        </View>
        <View style={styles.maskBottom} />
      </View>

      <View style={[styles.camHeader, { paddingTop: insets.top + spacing.sm }]}>
        <Pressable testID="camera-back" onPress={() => router.back()} style={styles.roundBtn} hitSlop={10}>
          <Ionicons name="chevron-back" size={24} color={colors.onSurface} />
        </Pressable>
        <View style={styles.tip}>
          <Ionicons name="bulb-outline" size={14} color={colors.brand} />
          <Text style={styles.tipText}>Face the light, look straight ahead</Text>
        </View>
        <View style={{ width: 44 }} />
      </View>

      <LinearGradient colors={["transparent", "rgba(13,13,13,0.9)"]} style={[styles.camFooter, { paddingBottom: insets.bottom + spacing.xl }]}>
        {processing ? (
          <View style={styles.analyzing}>
            <ActivityIndicator color={colors.brand} />
            <Text style={styles.analyzingText}>Analysing your photo…</Text>
          </View>
        ) : (
          <View style={styles.shutterRow}>
            <Pressable testID="upload-instead-btn" onPress={pickFromLibrary} style={styles.roundBtn}>
              <Ionicons name="images-outline" size={22} color={colors.onSurface} />
            </Pressable>
            <Pressable testID="capture-btn" onPress={capture} style={styles.shutterOuter}>
              <View style={styles.shutterInner} />
            </Pressable>
            <View style={{ width: 44 }} />
          </View>
        )}
      </LinearGradient>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  consentBody: { padding: spacing.xl, paddingTop: spacing["2xl"] },
  permBody: { flex: 1, padding: spacing.xl, alignItems: "center", justifyContent: "center" },
  consentIcon: {
    width: 64,
    height: 64,
    borderRadius: radius.pill,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  consentTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], textAlign: "center" },
  consentText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 22, marginTop: spacing.sm, marginBottom: spacing.lg, textAlign: "center" },
  bullet: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md, marginBottom: spacing.md, backgroundColor: colors.surfaceSecondary, padding: spacing.md, borderRadius: radius.md },
  bulletText: { flex: 1, color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 20 },
  decline: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base },
  cameraContainer: { flex: 1, backgroundColor: "#000" },
  overlay: { ...StyleSheet.absoluteFillObject, flexDirection: "column" },
  maskTop: { flex: 1, backgroundColor: "rgba(13,13,13,0.72)" },
  maskMiddle: { height: 340, flexDirection: "row" },
  maskSide: { flex: 1, backgroundColor: "rgba(13,13,13,0.72)" },
  ovalWrap: { width: 260, alignItems: "center", justifyContent: "center" },
  oval: { width: 250, height: 330, borderRadius: 160, borderWidth: 2, borderColor: colors.brand },
  maskBottom: { flex: 1, backgroundColor: "rgba(13,13,13,0.72)" },
  camHeader: { position: "absolute", top: 0, left: 0, right: 0, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md },
  roundBtn: { width: 44, height: 44, borderRadius: radius.pill, backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center" },
  tip: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: "rgba(0,0,0,0.5)", paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderRadius: radius.pill },
  tipText: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm },
  camFooter: { position: "absolute", bottom: 0, left: 0, right: 0, paddingTop: spacing["2xl"] },
  shutterRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing["2xl"] },
  shutterOuter: { width: 78, height: 78, borderRadius: 40, borderWidth: 4, borderColor: colors.onSurface, alignItems: "center", justifyContent: "center" },
  shutterInner: { width: 60, height: 60, borderRadius: 32, backgroundColor: colors.brand },
  analyzing: { alignItems: "center", gap: spacing.sm, paddingVertical: spacing.lg },
  analyzingText: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
});
