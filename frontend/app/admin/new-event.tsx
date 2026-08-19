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
  const [mode, setMode] = useState<"upload" | "gdrive">("upload");
  const [driveLink, setDriveLink] = useState("");
  const [loading, setLoading] = useState(false);

  const create = async () => {
    if (!name.trim()) {
      toast.show("Give your event a name", "error");
      return;
    }
    if (mode === "gdrive" && !driveLink.trim()) {
      toast.show("Paste a Google Drive folder link", "error");
      return;
    }
    setLoading(true);
    try {
      let res: any;
      if (mode === "gdrive") {
        res = await api.post("/events/gdrive", {
          name: name.trim(),
          date: date.trim() || undefined,
          photographer: photographer.trim() || undefined,
          category,
          drive_link: driveLink.trim(),
        });
        const n = res?.sync?.total ?? 0;
        toast.show(`Gallery created — ${n} photo${n === 1 ? "" : "s"} found`, "success");
      } else {
        res = await api.post("/events", {
          name: name.trim(),
          date: date.trim() || undefined,
          photographer: photographer.trim() || undefined,
          category,
        });
        toast.show("Event created", "success");
      }
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
        <Text style={styles.label}>Photo source</Text>
        <View style={styles.segment}>
          <Pressable testID="source-upload" onPress={() => setMode("upload")} style={[styles.segBtn, mode === "upload" && styles.segBtnActive]}>
            <Ionicons name="cloud-upload-outline" size={16} color={mode === "upload" ? colors.onBrand : colors.onSurfaceTertiary} />
            <Text style={[styles.segText, mode === "upload" && styles.segTextActive]}>Upload photos</Text>
          </Pressable>
          <Pressable testID="source-gdrive" onPress={() => setMode("gdrive")} style={[styles.segBtn, mode === "gdrive" && styles.segBtnActive]}>
            <Ionicons name="logo-google" size={16} color={mode === "gdrive" ? colors.onBrand : colors.onSurfaceTertiary} />
            <Text style={[styles.segText, mode === "gdrive" && styles.segTextActive]}>Google Drive</Text>
          </Pressable>
        </View>

        {mode === "gdrive" && (
          <View style={styles.driveBox}>
            <TextField
              testID="drive-link-input"
              label="Google Drive folder link"
              value={driveLink}
              onChangeText={setDriveLink}
              placeholder="https://drive.google.com/drive/folders/..."
              autoCapitalize="none"
            />
            <View style={styles.hintRow}>
              <Ionicons name="information-circle-outline" size={15} color={colors.muted} />
              <Text style={styles.hint}>
                Share the folder as “Anyone with the link → Viewer”. Originals stay on Drive — we build a fast preview gallery with face search.
              </Text>
            </View>
          </View>
        )}

        <Text style={[styles.label, { marginTop: spacing.xl }]}>Category</Text>
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
          <Button testID="create-event-btn" title={mode === "gdrive" ? "Create Drive gallery" : "Create event"} loading={loading} onPress={create} />
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
  segment: { flexDirection: "row", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.pill, padding: 4, borderWidth: 1, borderColor: colors.border },
  segBtn: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, height: 40, borderRadius: radius.pill },
  segBtnActive: { backgroundColor: colors.brand },
  segText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  segTextActive: { color: colors.onBrand, fontWeight: "600" },
  driveBox: { marginTop: spacing.lg, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.brandTertiary },
  hintRow: { flexDirection: "row", gap: 6, alignItems: "flex-start", marginTop: spacing.xs },
  hint: { flex: 1, color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18 },
});
