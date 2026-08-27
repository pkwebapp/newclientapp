import { useMemo, useState } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const WEEKDAY_NAMES = ["S", "M", "T", "W", "T", "F", "S"];

export function toIsoDate(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function todayIso() {
  return toIsoDate(new Date());
}

export function isValidIsoDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
}

export function formatDateLabel(isoDate: string, empty = "Choose a date") {
  if (!isValidIsoDate(isoDate)) return empty;
  const [year, month, day] = isoDate.split("-").map(Number);
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

type Props = {
  value: string;                        // ISO YYYY-MM-DD (or "")
  onChange: (iso: string) => void;
  label?: string;
  hint?: string;                        // small helper line under value
  emptyLabel?: string;                  // shown when value is ""
  testID?: string;
};

export default function DatePickerField({
  value,
  onChange,
  label = "Date",
  hint = "Tap to choose a date",
  emptyLabel = "Choose a date",
  testID = "date-picker",
}: Props) {
  const [open, setOpen] = useState(false);
  const initialMonth = useMemo(() => {
    if (isValidIsoDate(value)) {
      const [y, m] = value.split("-").map(Number);
      return new Date(y, m - 1, 1);
    }
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  }, [value]);
  const [calendarMonth, setCalendarMonth] = useState<Date>(initialMonth);

  const openPicker = () => {
    if (isValidIsoDate(value)) {
      const [y, m] = value.split("-").map(Number);
      setCalendarMonth(new Date(y, m - 1, 1));
    } else {
      const now = new Date();
      setCalendarMonth(new Date(now.getFullYear(), now.getMonth(), 1));
    }
    setOpen(true);
  };

  const displayLabel = value ? formatDateLabel(value, emptyLabel) : emptyLabel;

  return (
    <View style={styles.wrap}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <Pressable
        testID={testID}
        accessibilityRole="button"
        accessibilityLabel={`${label} ${displayLabel}`}
        onPress={openPicker}
        style={styles.field}
      >
        <View style={styles.iconWrap}>
          <Ionicons name="calendar-outline" size={20} color={colors.brand} />
        </View>
        <View style={styles.copy}>
          <Text style={[styles.value, !value && styles.valueEmpty]}>{displayLabel}</Text>
          <Text style={styles.hint}>{hint}</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.muted} />
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)} statusBarTranslucent>
        <View style={styles.modalBackdrop}>
          <View style={styles.calendarCard}>
            <View style={styles.calendarTopRow}>
              <View>
                <Text style={styles.calendarEyebrow}>SELECT DATE</Text>
                <Text style={styles.calendarSelected}>{value ? formatDateLabel(value) : "Choose a date"}</Text>
              </View>
              <Pressable
                testID={`${testID}-close`}
                accessibilityLabel="Close calendar"
                onPress={() => setOpen(false)}
                style={styles.calendarClose}
              >
                <Ionicons name="close" size={22} color={colors.onSurfaceTertiary} />
              </Pressable>
            </View>
            <View style={styles.calendarMonthRow}>
              <Pressable
                testID={`${testID}-prev`}
                accessibilityLabel="Previous month"
                onPress={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1))}
                style={styles.calendarArrow}
              >
                <Ionicons name="chevron-back" size={20} color={colors.onSurface} />
              </Pressable>
              <Text style={styles.calendarMonthTitle}>
                {MONTH_NAMES[calendarMonth.getMonth()]} {calendarMonth.getFullYear()}
              </Text>
              <Pressable
                testID={`${testID}-next`}
                accessibilityLabel="Next month"
                onPress={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1))}
                style={styles.calendarArrow}
              >
                <Ionicons name="chevron-forward" size={20} color={colors.onSurface} />
              </Pressable>
            </View>
            <View style={styles.weekdayRow}>
              {WEEKDAY_NAMES.map((day, index) => (
                <Text key={`${day}-${index}`} style={styles.weekday}>{day}</Text>
              ))}
            </View>
            <View style={styles.calendarGrid}>
              {calendarWeeks(calendarMonth).map((week, weekIndex) => (
                <View key={`week-${weekIndex}`} style={styles.calendarWeek}>
                  {week.map((day, dayIndex) => {
                    const iso = day
                      ? toIsoDate(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), day))
                      : "";
                    const selected = !!day && iso === value;
                    return (
                      <Pressable
                        key={`day-${weekIndex}-${dayIndex}`}
                        disabled={!day}
                        testID={day ? `${testID}-day-${day}` : undefined}
                        accessibilityRole={day ? "button" : undefined}
                        accessibilityLabel={day ? formatDateLabel(iso) : undefined}
                        onPress={() => {
                          if (!day) return;
                          onChange(iso);
                          setOpen(false);
                        }}
                        style={[styles.calendarDay, selected && styles.calendarDaySelected]}
                      >
                        <Text style={[styles.calendarDayText, selected && styles.calendarDayTextSelected]}>
                          {day || ""}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>
              ))}
            </View>
            <Pressable
              testID={`${testID}-today`}
              onPress={() => {
                const current = new Date();
                onChange(toIsoDate(current));
                setCalendarMonth(new Date(current.getFullYear(), current.getMonth(), 1));
                setOpen(false);
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
  wrap: { marginBottom: spacing.lg },
  label: {
    color: colors.onSurfaceSecondary,
    fontSize: fontSize.sm,
    marginBottom: spacing.md,
    fontFamily: fonts.text,
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  field: {
    minHeight: 64,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  copy: { flex: 1 },
  value: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "600" },
  valueEmpty: { color: colors.muted, fontWeight: "500" },
  hint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.72)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
  },
  calendarCard: {
    width: "100%",
    maxWidth: 420,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    padding: spacing.xl,
  },
  calendarTopRow: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between" },
  calendarEyebrow: {
    color: colors.brand,
    fontFamily: fonts.text,
    fontSize: fontSize.sm,
    fontWeight: "700",
    letterSpacing: 1.2,
  },
  calendarSelected: {
    color: colors.onSurface,
    fontFamily: fonts.display,
    fontSize: fontSize["2xl"],
    fontWeight: "700",
    marginTop: spacing.xs,
  },
  calendarClose: {
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceTertiary,
  },
  calendarMonthRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  calendarArrow: {
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceTertiary,
  },
  calendarMonthTitle: {
    color: colors.onSurface,
    fontFamily: fonts.text,
    fontSize: fontSize.lg,
    fontWeight: "700",
  },
  weekdayRow: { flexDirection: "row", marginBottom: spacing.xs },
  weekday: {
    flex: 1,
    color: colors.muted,
    fontFamily: fonts.text,
    fontSize: fontSize.sm,
    fontWeight: "700",
    textAlign: "center",
    paddingVertical: spacing.sm,
  },
  calendarGrid: { gap: spacing.xs },
  calendarWeek: { flexDirection: "row", gap: spacing.xs },
  calendarDay: {
    flex: 1,
    minHeight: 44,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  calendarDaySelected: { backgroundColor: colors.brand },
  calendarDayText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  calendarDayTextSelected: { color: colors.onBrand, fontWeight: "700" },
  todayButton: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    marginTop: spacing.lg,
    paddingTop: spacing.lg,
  },
  todayButtonText: {
    color: colors.brand,
    fontFamily: fonts.text,
    fontSize: fontSize.base,
    fontWeight: "700",
  },
});
