import { useEffect, useState } from "react";
import { useRouter } from "expo-router";
import { Modal, Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { Button, TextField, GlassHeader, useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing, categoryMeta } from "@/src/theme";
import { goBackOr } from "@/src/navigation/back";


const CATEGORIES = ["portrait", "wedding", "event"];
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const WEEKDAY_NAMES = ["S", "M", "T", "W", "T", "F", "S"];

function toIsoDate(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDateLabel(isoDate: string) {
  const [year, month, day] = isoDate.split("-").map(Number);
  if (!year || !month || !day) return "Choose a date";
  return `${day} ${MONTH_NAMES[month - 1]} ${year}`;
}

function calendarWeeks(month: Date) {
  const year = month.getFullYear();
  const monthIndex = month.getMonth();
  const firstDay = new Date(year, monthIndex, 1).getDay();
  const totalDays = new Date(year, monthIndex + 1, 0).getDate();
  const cells: (number | null)[] = Array(firstDay).fill(null);
  for (let day = 1; day <= totalDays; day += 1) cells.push(day);
  while (cells.length % 7 !== 0) cells.push(null);
  return Array.from({ length: cells.length / 7 }, (_, index) => cells.slice(index * 7, index * 7 + 7));
}

export default function NewEvent() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();

  const today = new Date();
  const [name, setName] = useState("");
  const [date, setDate] = useState(toIsoDate(today));
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [photographer, setPhotographer] = useState("Ritik");
  const [category, setCategory] = useState("portrait");
  const [mode, setMode] = useState<"upload" | "gdrive">("upload");
  const [faceSearchEnabled, setFaceSearchEnabled] = useState(true);
  const [driveLink, setDriveLink] = useState("");
  const [value, setValue] = useState("");
  const [clients, setClients] = useState<any[]>([]);
  const [clientId, setClientId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get("/clients").then(setClients).catch(() => {});
  }, []);

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
          face_search_enabled: faceSearchEnabled,
          drive_link: driveLink.trim(),
          value: value.trim() ? Number(value.trim()) : undefined,
          client_id: clientId || undefined,
        });
        const n = res?.sync?.total ?? 0;
        toast.show(`Gallery created — ${n} photo${n === 1 ? "" : "s"} found`, "success");
      } else {
        res = await api.post("/events", {
          name: name.trim(),
          date: date.trim() || undefined,
          photographer: photographer.trim() || undefined,
          category,
          face_search_enabled: faceSearchEnabled,
          value: value.trim() ? Number(value.trim()) : undefined,
          client_id: clientId || undefined,
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
      <GlassHeader title="New Event" onBack={() => goBackOr(router, "/admin")} topInset={insets.top} />
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

        <View style={styles.faceSearchCard} testID="face-search-toggle-card">
          <View style={styles.faceSearchCopy}>
            <View style={styles.faceSearchTitleRow}>
              <Ionicons name="scan-outline" size={18} color={faceSearchEnabled ? colors.brand : colors.muted} />
              <Text style={styles.faceSearchTitle}>Face search</Text>
            </View>
            <Text style={styles.faceSearchHint}>
              {faceSearchEnabled
                ? "Index faces so clients can find themselves with a selfie."
                : "Off — photos will upload without face indexing or selfie search."}
            </Text>
          </View>
          <Switch
            testID="face-search-switch"
            value={faceSearchEnabled}
            onValueChange={setFaceSearchEnabled}
            trackColor={{ true: colors.brand, false: colors.surfaceTertiary }}
            thumbColor={colors.onSurface}
          />
        </View>

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
          <View style={styles.dateFieldWrap}>
            <Text style={styles.label}>Date</Text>
            <Pressable
              testID="event-date-input"
              accessibilityRole="button"
              accessibilityLabel={`Event date ${formatDateLabel(date)}`}
              onPress={() => {
                const [year, month] = date.split("-").map(Number);
                setCalendarMonth(new Date(year, month - 1, 1));
                setCalendarOpen(true);
              }}
              style={styles.dateField}
            >
              <View style={styles.dateIcon}>
                <Ionicons name="calendar-outline" size={20} color={colors.brand} />
              </View>
              <View style={styles.dateCopy}>
                <Text style={styles.dateValue}>{formatDateLabel(date)}</Text>
                <Text style={styles.dateHint}>Tap to choose a date</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </Pressable>
          </View>
          <TextField testID="event-photographer-input" label="Photographer" value={photographer} onChangeText={setPhotographer} placeholder="Ritik" />
          <TextField testID="event-value-input" label="Booking value (₹)" value={value} onChangeText={setValue} placeholder="120000" keyboardType="numeric" />

          <Text style={styles.label}>Attach to client (optional)</Text>
          {clients.length === 0 ? (
            <Text style={styles.hint}>No clients yet. Create one from the Clients tab to link events and track lifetime value.</Text>
          ) : (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipWrap}>
              <Pressable testID="client-none" onPress={() => setClientId(null)} style={[styles.chip, !clientId && styles.chipActive]}>
                <Text style={[styles.chipText, !clientId && styles.chipTextActive]}>None</Text>
              </Pressable>
              {clients.map((c) => (
                <Pressable key={c.client_id} testID={`client-pick-${c.client_id}`} onPress={() => setClientId(c.client_id)} style={[styles.chip, clientId === c.client_id && styles.chipActive]}>
                  <Ionicons name="people" size={13} color={clientId === c.client_id ? colors.onBrand : colors.onSurfaceTertiary} />
                  <Text style={[styles.chipText, clientId === c.client_id && styles.chipTextActive]}>{c.name}</Text>
                </Pressable>
              ))}
            </ScrollView>
          )}

          <View style={{ marginTop: spacing.xl }}>
            <Button testID="create-event-btn" title={mode === "gdrive" ? "Create Drive gallery" : "Create event"} loading={loading} onPress={create} />
          </View>
        </View>
      </KeyboardAwareScrollView>
      <Modal visible={calendarOpen} transparent animationType="fade" onRequestClose={() => setCalendarOpen(false)} statusBarTranslucent>
        <View style={styles.modalBackdrop}>
          <View style={styles.calendarCard}>
            <View style={styles.calendarTopRow}>
              <View>
                <Text style={styles.calendarEyebrow}>SELECT DATE</Text>
                <Text style={styles.calendarSelected}>{formatDateLabel(date)}</Text>
              </View>
              <Pressable testID="event-date-close" accessibilityLabel="Close calendar" onPress={() => setCalendarOpen(false)} style={styles.calendarClose}>
                <Ionicons name="close" size={22} color={colors.onSurfaceTertiary} />
              </Pressable>
            </View>
            <View style={styles.calendarMonthRow}>
              <Pressable
                testID="event-calendar-prev"
                accessibilityLabel="Previous month"
                onPress={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1))}
                style={styles.calendarArrow}
              >
                <Ionicons name="chevron-back" size={20} color={colors.onSurface} />
              </Pressable>
              <Text style={styles.calendarMonthTitle}>{MONTH_NAMES[calendarMonth.getMonth()]} {calendarMonth.getFullYear()}</Text>
              <Pressable
                testID="event-calendar-next"
                accessibilityLabel="Next month"
                onPress={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1))}
                style={styles.calendarArrow}
              >
                <Ionicons name="chevron-forward" size={20} color={colors.onSurface} />
              </Pressable>
            </View>
            <View style={styles.weekdayRow}>
              {WEEKDAY_NAMES.map((day, index) => <Text key={`${day}-${index}`} style={styles.weekday}>{day}</Text>)}
            </View>
            <View style={styles.calendarGrid}>
              {calendarWeeks(calendarMonth).map((week, weekIndex) => (
                <View key={`week-${weekIndex}`} style={styles.calendarWeek}>
                  {week.map((day, dayIndex) => {
                    const value = day ? toIsoDate(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), day)) : "";
                    const selected = value === date;
                    return (
                      <Pressable
                        key={`day-${weekIndex}-${dayIndex}`}
                        disabled={!day}
                        testID={day ? `event-calendar-day-${day}` : undefined}
                        accessibilityRole={day ? "button" : undefined}
                        accessibilityLabel={day ? formatDateLabel(value) : undefined}
                        onPress={() => {
                          if (!day) return;
                          setDate(value);
                          setCalendarOpen(false);
                        }}
                        style={[styles.calendarDay, selected && styles.calendarDaySelected]}
                      >
                        <Text style={[styles.calendarDayText, selected && styles.calendarDayTextSelected]}>{day || ""}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              ))}
            </View>
            <Pressable
              testID="event-calendar-today"
              onPress={() => {
                const current = new Date();
                setDate(toIsoDate(current));
                setCalendarMonth(new Date(current.getFullYear(), current.getMonth(), 1));
                setCalendarOpen(false);
              }}
              style={styles.todayButton}
            >
              <Ionicons name="today-outline" size={17} color={colors.brand} />
              <Text style={styles.todayButtonText}>Jump to today</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
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
  faceSearchCard: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginTop: spacing.xl, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, padding: spacing.lg },
  faceSearchCopy: { flex: 1 },
  faceSearchTitleRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  faceSearchTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  faceSearchHint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginTop: spacing.xs },
  hintRow: { flexDirection: "row", gap: 6, alignItems: "flex-start", marginTop: spacing.xs },
  hint: { flex: 1, color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18 },
  dateFieldWrap: { marginBottom: spacing.lg },
  dateField: { minHeight: 64, flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: spacing.lg },
  dateIcon: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", marginRight: spacing.md },
  dateCopy: { flex: 1 },
  dateValue: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "600" },
  dateHint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  modalBackdrop: { flex: 1, backgroundColor: "rgba(0, 0, 0, 0.72)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  calendarCard: { width: "100%", maxWidth: 420, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.borderStrong, padding: spacing.xl },
  calendarTopRow: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between" },
  calendarEyebrow: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700", letterSpacing: 1.2 },
  calendarSelected: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], fontWeight: "700", marginTop: spacing.xs },
  calendarClose: { width: 44, height: 44, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceTertiary },
  calendarMonthRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.xl, marginBottom: spacing.md },
  calendarArrow: { width: 44, height: 44, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceTertiary },
  calendarMonthTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "700" },
  weekdayRow: { flexDirection: "row", marginBottom: spacing.xs },
  weekday: { flex: 1, color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700", textAlign: "center", paddingVertical: spacing.sm },
  calendarGrid: { gap: spacing.xs },
  calendarWeek: { flexDirection: "row", gap: spacing.xs },
  calendarDay: { flex: 1, minHeight: 44, borderRadius: radius.sm, alignItems: "center", justifyContent: "center" },
  calendarDaySelected: { backgroundColor: colors.brand },
  calendarDayText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  calendarDayTextSelected: { color: colors.onBrand, fontWeight: "700" },
  todayButton: { minHeight: 48, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, marginTop: spacing.lg, paddingTop: spacing.lg },
  todayButtonText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
});
