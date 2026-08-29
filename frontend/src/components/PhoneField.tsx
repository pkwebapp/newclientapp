import { useEffect, useMemo, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Palette, fonts, fontSize, radius, spacing } from "@/src/theme";
import { usePalette, useThemedStyles } from "@/src/theme-context";

export type PhoneCountry = { name: string; code: string; lengths: number[] };

export const PHONE_COUNTRIES: PhoneCountry[] = [
  { name: "India", code: "91", lengths: [10] },
  { name: "United States", code: "1", lengths: [10] },
  { name: "Canada", code: "1", lengths: [10] },
  { name: "United Kingdom", code: "44", lengths: [10] },
  { name: "Australia", code: "61", lengths: [9] },
  { name: "United Arab Emirates", code: "971", lengths: [9] },
  { name: "Singapore", code: "65", lengths: [8] },
  { name: "Malaysia", code: "60", lengths: [9, 10] },
  { name: "Germany", code: "49", lengths: [10, 11] },
  { name: "France", code: "33", lengths: [9] },
  { name: "Italy", code: "39", lengths: [9, 10] },
  { name: "Spain", code: "34", lengths: [9] },
  { name: "Japan", code: "81", lengths: [10] },
  { name: "China", code: "86", lengths: [11] },
  { name: "New Zealand", code: "64", lengths: [9] },
  { name: "South Africa", code: "27", lengths: [9] },
  { name: "Saudi Arabia", code: "966", lengths: [9] },
  { name: "Qatar", code: "974", lengths: [8] },
  { name: "Bangladesh", code: "880", lengths: [10] },
  { name: "Nepal", code: "977", lengths: [10] },
  { name: "Sri Lanka", code: "94", lengths: [9] },
];

const sortedCountries = [...PHONE_COUNTRIES].sort((a, b) => b.code.length - a.code.length);

function parseValue(value: string) {
  const raw = (value || "").trim();
  const digits = raw.replace(/\D/g, "");
  if (!digits) return { country: PHONE_COUNTRIES[0], local: "" };
  const country = raw.startsWith("+")
    ? sortedCountries.find((item) => digits.startsWith(item.code)) || PHONE_COUNTRIES[0]
    : PHONE_COUNTRIES[0];
  const local = raw.startsWith("+") && digits.startsWith(country.code)
    ? digits.slice(country.code.length)
    : digits.length === 10
    ? digits
    : digits;
  return { country, local };
}

function isRepeated(local: string) {
  return local.length > 0 && new Set(local).size === 1;
}

export function isPhoneNumberValid(value: string) {
  const { country, local } = parseValue(value);
  return country.lengths.includes(local.length) && !isRepeated(local);
}

export function PhoneField({
  label = "Mobile number",
  value,
  onChangeText,
  placeholder = "Enter mobile number",
  testID,
  required = true,
  editable = true,
}: {
  label?: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder?: string;
  testID?: string;
  required?: boolean;
  editable?: boolean;
}) {
  const { colors } = usePalette();
  const styles = useThemedStyles(makeStyles);
  const parsed = useMemo(() => parseValue(value), [value]);
  const [country, setCountry] = useState<PhoneCountry>(parsed.country);
  const [countryOpen, setCountryOpen] = useState(false);
  const [touched, setTouched] = useState(false);
  const parsedCountryCode = parsed.country.code;
  useEffect(() => {
    if (value && parsedCountryCode !== country.code) setCountry(parsed.country);
  }, [value, parsedCountryCode, country.code, parsed.country]);
  const local = parsedCountryCode === country.code ? parsed.local : "";
  const maxLength = Math.max(...country.lengths);
  const showError = touched && required && local.length > 0 && !isPhoneNumberValid(`+${country.code}${local}`);
  const errorText = isRepeated(local)
    ? "Mobile number cannot repeat the same digit"
    : `Use ${country.lengths.join(" or ")} digits for ${country.name}`;

  const selectCountry = (next: PhoneCountry) => {
    setCountry(next);
    setCountryOpen(false);
    onChangeText(local ? `+${next.code}${local}` : "");
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}{required ? " *" : ""}</Text>
      <View style={[styles.inputRow, showError && styles.inputError]}>
        <Pressable testID={`${testID || "phone"}-country`} onPress={() => setCountryOpen(true)} style={styles.countryButton} accessibilityRole="button">
          <Text style={styles.countryCode}>+{country.code}</Text>
          <Ionicons name="chevron-down" size={14} color={colors.muted} />
        </Pressable>
        <TextInput
          testID={testID}
          value={local}
          onChangeText={(next) => onChangeText(`+${country.code}${next.replace(/\D/g, "").slice(0, maxLength)}`)}
          onBlur={() => setTouched(true)}
          placeholder={placeholder}
          placeholderTextColor={colors.muted}
          editable={editable}
          keyboardType="phone-pad"
          maxLength={maxLength}
          style={styles.input}
        />
      </View>
      <Text style={styles.helper}>{showError ? errorText : `${country.name} · ${country.lengths.join(" or ")} digits`}</Text>

      <Modal visible={countryOpen} transparent animationType="slide" onRequestClose={() => setCountryOpen(false)}>
        <View style={styles.modalBackdrop}>
          <View style={styles.countrySheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>Select country</Text>
              <Pressable testID={`${testID || "phone"}-country-close`} onPress={() => setCountryOpen(false)} style={styles.closeButton}>
                <Ionicons name="close" size={20} color={colors.onSurfaceTertiary} />
              </Pressable>
            </View>
            <ScrollView>
              {PHONE_COUNTRIES.map((item) => (
                <Pressable
                  key={`${item.name}-${item.code}`}
                  testID={`${testID || "phone"}-country-${item.code}-${item.name.replace(/[^a-z]/gi, "-").toLowerCase()}`}
                  onPress={() => selectCountry(item)}
                  style={[styles.countryRow, item.name === country.name && styles.countryRowActive]}
                >
                  <Text style={styles.countryName}>{item.name}</Text>
                  <Text style={styles.countryMeta}>+{item.code}</Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const makeStyles = (colors: Palette) => StyleSheet.create({
  wrap: { marginBottom: spacing.lg },
  label: { color: colors.onSurfaceSecondary, fontSize: fontSize.sm, marginBottom: spacing.sm, fontFamily: fonts.text, letterSpacing: 0.5, textTransform: "uppercase" },
  inputRow: { flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, minHeight: 52 },
  inputError: { borderColor: colors.onError },
  countryButton: { minHeight: 50, flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: spacing.md, borderRightWidth: 1, borderRightColor: colors.border },
  countryCode: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  input: { flex: 1, height: 50, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, paddingHorizontal: spacing.md },
  helper: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.xs },
  modalBackdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.72)", justifyContent: "flex-end" },
  countrySheet: { maxHeight: "78%", backgroundColor: colors.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: spacing.lg },
  sheetHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  sheetTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  closeButton: { width: 44, height: 44, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceTertiary },
  countryRow: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, borderRadius: radius.sm },
  countryRowActive: { backgroundColor: colors.brandTertiary },
  countryName: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base },
  countryMeta: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base },
});
