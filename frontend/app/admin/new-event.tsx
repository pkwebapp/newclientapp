import { useState } from "react";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";

const CATEGORIES = ["wedding", "corporate", "school", "studio", "nightlife", "event"];

export default function NewEvent() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const [name, setName] = useState("");
  const [date, setDate] = useState("");
  const [photographer, setPhotographer] = useState("");
  const [category, setCategory] = useState("wedding");
  const [loading, setLoading] = useState(false);

  const create = async () => {
    if (!name.trim()) {
      toast.show("Give your event a name", "error");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("/events", { name: name.trim(), date: date.trim() || undefined, photographer: photographer.trim() || undefined, category });
      toast.show("Event created", "success");
      router.replace(`/admin/event/${res.event_id}`);
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not create event", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container} testID="new-event-screen">
      <GlassHeader title="New Event" onBack={() => router.back()} topInset={insets.top} />
      <KeyboardAwareScrollView contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing["2xl"] }]} bottomOffset={24} keyboardShouldPersistTaps="handled">
        <Text style={styles.label}>Category</Text>
        <View style={styles.chipWrap}>
          {CATEGORIES.map((c) => (
            <Pressable key={c} testID={`category-${c}`} onPress={() => setCategory(c)} style={[styles.chip, category === c && styles.chipActive]}>
              <Ionicons name={(categoryMeta[c]?.icon as any) || "star"} size={14} color={category === c ? colors.onBrand : colors.onSurfaceTertiary} />
              <Text style={[styles.chipText, category === c && styles.chipTextActive]}>{categoryMeta[c]?.label}</Text>
            </Pressable>
          ))}
        </View>

        <View style={{ marginTop: spacing.xl }}>
          <TextField testID="event-name-input" label="Event name" value={name} onChangeText={setName} placeholder="Sharma Wedding" />
          <TextField testID="event-date-input" label="Date" value={date} onChangeText={setDate} placeholder="2026-05-01" autoCapitalize="none" />
          <TextField testID="event-photographer-input" label="Photographer" value={photographer} onChangeText={setPhotographer} placeholder="Ravi Kapoor" />
          <Button testID="create-event-btn" title="Create event" loading={loading} onPress={create} />
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl },
  label: { color: colors.onSurfaceSecondary, fontSize: fontSize.sm, marginBottom: spacing.md, fontFamily: fonts.text, letterSpacing: 0.5, textTransform: "uppercase" },
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: spacing.lg, height: 40, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  chipTextActive: { color: colors.onBrand, fontWeight: "600" },
});
