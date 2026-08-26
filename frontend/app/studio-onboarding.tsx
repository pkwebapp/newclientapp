import { useMemo, useState } from "react";
import { Redirect, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { useAuth } from "@/src/context/AuthContext";
import { Button, TextField, useToast } from "@/src/components/ui";
import { useResponsive } from "@/src/hooks/use-responsive";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const PURPOSES = [
  "Weddings",
  "Events",
  "Portraits",
  "Newborn / Maternity",
  "Real estate",
  "Commercial / Product",
  "Other",
];
const TEAM_SIZES = ["Solo", "2–5", "6+"];
const GALLERY_VOLUMES = ["Under 5", "5–20", "20+"];

function ChipRow({
  options,
  value,
  onChange,
  testIDPrefix,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
  testIDPrefix: string;
}) {
  return (
    <View style={styles.chipRow}>
      {options.map((opt) => {
        const active = value === opt;
        return (
          <Pressable
            key={opt}
            testID={`${testIDPrefix}-${opt}`}
            onPress={() => onChange(opt)}
            style={[styles.chip, active && styles.chipActive]}
          >
            <Text style={[styles.chipText, active && styles.chipTextActive]}>{opt}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export default function StudioOnboarding() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, loading, refresh, signOut } = useAuth();
  const toast = useToast();
  const { isDesktop } = useResponsive();

  const [contactName, setContactName] = useState(user?.name || "");
  const [studioName, setStudioName] = useState("");
  const [phone, setPhone] = useState(user?.phone || "");
  const [purpose, setPurpose] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [website, setWebsite] = useState("");
  const [teamSize, setTeamSize] = useState("");
  const [galleriesPerMonth, setGalleriesPerMonth] = useState("");
  const [referralSource, setReferralSource] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = useMemo(
    () =>
      !!contactName.trim() &&
      !!studioName.trim() &&
      phone.trim().length >= 6 &&
      !!purpose &&
      !!city.trim() &&
      !!country.trim(),
    [contactName, studioName, phone, purpose, city, country]
  );

  // ---- Guards (after hooks) ----
  if (loading) {
    return (
      <View style={styles.center} testID="onboarding-loading">
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }
  if (!user) return <Redirect href="/admin-login" />;
  if (user.role !== "admin") return <Redirect href="/" />;
  if (user.profile_complete) return <Redirect href="/admin" />;

  const submit = async () => {
    if (!canSubmit) {
      toast.show("Please complete all required fields", "error");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/auth/admin/profile", {
        contact_name: contactName.trim(),
        studio_name: studioName.trim(),
        phone: phone.trim(),
        purpose,
        city: city.trim(),
        country: country.trim(),
        website: website.trim() || null,
        team_size: teamSize || null,
        galleries_per_month: galleriesPerMonth || null,
        referral_source: referralSource.trim() || null,
      });
      await refresh();
      router.replace("/admin");
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not save your details", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <View style={styles.container} testID="studio-onboarding-screen">
      <KeyboardAwareScrollView
        contentContainerStyle={[
          styles.body,
          isDesktop && styles.bodyDesktop,
          { paddingTop: insets.top + spacing["2xl"], paddingBottom: insets.bottom + spacing["3xl"] },
        ]}
        bottomOffset={24}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.iconWrap}>
          <Ionicons name="briefcase" size={26} color={colors.brand} />
        </View>
        <Text style={styles.title}>Complete your studio profile</Text>
        <Text style={styles.sub}>
          Tell us a little about your studio. We use this to set up your galleries and support your account.
        </Text>

        <Text style={styles.sectionLabel}>Required</Text>

        <TextField
          testID="onb-contact-name"
          label="Your name"
          value={contactName}
          onChangeText={setContactName}
          placeholder="e.g. Prabhakar Kumar"
          autoCapitalize="words"
        />
        <TextField
          testID="onb-studio-name"
          label="Studio / business name"
          value={studioName}
          onChangeText={setStudioName}
          placeholder="e.g. PK Photography"
          autoCapitalize="words"
        />
        <TextField
          testID="onb-phone"
          label="Phone number"
          value={phone}
          onChangeText={setPhone}
          placeholder="e.g. +91 98765 43210"
          keyboardType="phone-pad"
        />

        <Text style={styles.fieldLabel}>What do you mainly shoot?</Text>
        <ChipRow options={PURPOSES} value={purpose} onChange={setPurpose} testIDPrefix="onb-purpose" />

        <View style={styles.row}>
          <View style={styles.rowItem}>
            <TextField
              testID="onb-city"
              label="City"
              value={city}
              onChangeText={setCity}
              placeholder="e.g. Mumbai"
              autoCapitalize="words"
            />
          </View>
          <View style={styles.rowItem}>
            <TextField
              testID="onb-country"
              label="Country"
              value={country}
              onChangeText={setCountry}
              placeholder="e.g. India"
              autoCapitalize="words"
            />
          </View>
        </View>

        <View style={styles.divider} />
        <Text style={styles.sectionLabel}>Optional</Text>

        <TextField
          testID="onb-website"
          label="Website or Instagram"
          value={website}
          onChangeText={setWebsite}
          placeholder="e.g. instagram.com/yourstudio"
          autoCapitalize="none"
          keyboardType="url"
        />

        <Text style={styles.fieldLabel}>Team size</Text>
        <ChipRow options={TEAM_SIZES} value={teamSize} onChange={setTeamSize} testIDPrefix="onb-team" />

        <Text style={styles.fieldLabel}>Galleries per month</Text>
        <ChipRow
          options={GALLERY_VOLUMES}
          value={galleriesPerMonth}
          onChange={setGalleriesPerMonth}
          testIDPrefix="onb-volume"
        />

        <TextField
          testID="onb-referral"
          label="How did you hear about us?"
          value={referralSource}
          onChangeText={setReferralSource}
          placeholder="e.g. Instagram, a friend, Google"
        />

        <Button
          testID="onb-submit"
          title="Continue to dashboard"
          icon="arrow-forward"
          loading={submitting}
          disabled={!canSubmit}
          onPress={submit}
          style={{ marginTop: spacing.md }}
        />

        <Pressable
          testID="onb-signout"
          onPress={signOut}
          style={{ marginTop: spacing.xl, alignItems: "center", minHeight: 44, justifyContent: "center" }}
        >
          <Text style={styles.signout}>Sign out</Text>
        </Pressable>
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  body: { paddingHorizontal: spacing.xl },
  bodyDesktop: { maxWidth: 560, width: "100%", alignSelf: "center" },
  iconWrap: {
    width: 60,
    height: 60,
    borderRadius: radius.pill,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  sub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, marginTop: spacing.xs, lineHeight: 21 },
  sectionLabel: {
    color: colors.brand,
    fontFamily: fonts.text,
    fontSize: fontSize.sm,
    fontWeight: "700",
    letterSpacing: 1,
    textTransform: "uppercase",
    marginTop: spacing["2xl"],
    marginBottom: spacing.lg,
  },
  fieldLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, marginBottom: spacing.sm },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.lg },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 40,
    justifyContent: "center",
  },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  chipTextActive: { color: colors.onBrand, fontWeight: "600" },
  row: { flexDirection: "row", gap: spacing.md },
  rowItem: { flex: 1 },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: colors.borderStrong, marginTop: spacing.sm, marginBottom: spacing.xs },
  signout: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base },
});
