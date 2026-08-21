import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

export default function ReviewScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [googleUrl, setGoogleUrl] = useState("");

  useFocusEffect(
    useCallback(() => {
      api.get("/me/dashboard").then((d) => setGoogleUrl(d?.studio?.google_review_url || "")).catch(() => {});
    }, [])
  );

  const submit = async () => {
    if (rating === 0) {
      toast.show("Tap a star to rate your experience", "error");
      return;
    }
    setLoading(true);
    try {
      await api.post("/me/reviews", { rating, text: text.trim() || undefined });
      setDone(true);
      toast.show("Thank you for your review!", "success");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not submit review", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container} testID="review-screen">
      <GlassHeader title="Review Your Experience" onBack={() => router.back()} topInset={insets.top} />
      <KeyboardAwareScrollView contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing["2xl"] }]} bottomOffset={24} keyboardShouldPersistTaps="handled">
        {done ? (
          <View style={styles.doneWrap}>
            <View style={styles.doneIcon}>
              <Ionicons name="heart" size={40} color={colors.brand} />
            </View>
            <Text style={styles.doneTitle}>You’re wonderful — thank you!</Text>
            <Text style={styles.doneSub}>Your feedback means the world to your studio.</Text>
            {googleUrl ? (
              <View style={{ width: "100%", marginTop: spacing.xl }}>
                <Button title="Also leave a Google review" icon="logo-google" onPress={() => Linking.openURL(googleUrl).catch(() => {})} />
              </View>
            ) : null}
            <View style={{ width: "100%", marginTop: spacing.md }}>
              <Button title="Back to memories" variant="ghost" onPress={() => router.replace("/client")} />
            </View>
          </View>
        ) : (
          <>
            <Text style={styles.prompt}>How was your experience with us?</Text>
            <View style={styles.stars}>
              {[1, 2, 3, 4, 5].map((n) => (
                <Pressable key={n} testID={`star-${n}`} onPress={() => setRating(n)} hitSlop={6} style={{ padding: 4 }}>
                  <Ionicons name={n <= rating ? "star" : "star-outline"} size={40} color={n <= rating ? colors.brand : colors.muted} />
                </Pressable>
              ))}
            </View>
            <View style={{ marginTop: spacing.xl }}>
              <TextField testID="review-text" label="Write a review (optional)" value={text} onChangeText={setText} placeholder="Share a few words…" multiline />
              <Button testID="review-submit" title="Submit review" loading={loading} onPress={submit} icon="checkmark" />
            </View>
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl },
  prompt: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, textAlign: "center", marginTop: spacing.lg, marginBottom: spacing.lg },
  stars: { flexDirection: "row", justifyContent: "center", gap: spacing.xs },
  doneWrap: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.lg, marginTop: spacing["2xl"] },
  doneIcon: { width: 84, height: 84, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", marginBottom: spacing.lg },
  doneTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], textAlign: "center" },
  doneSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, textAlign: "center", marginTop: spacing.sm, lineHeight: 20, maxWidth: 300 },
});
