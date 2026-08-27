import { useCallback, useMemo, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { Image } from "expo-image";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { Button, GlassHeader, TextField, useToast } from "@/src/components/ui";
import DatePickerField, { isValidIsoDate } from "@/src/components/DatePickerField";
import { PhoneField, isPhoneNumberValid } from "@/src/components/PhoneField";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const GENDERS = ["Male", "Female", "Non-binary", "Prefer not to say"];

export default function ClientProfileScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [profilePhoto, setProfilePhoto] = useState<string | null>(null);
  const [fullName, setFullName] = useState("");
  const [gender, setGender] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [city, setCity] = useState("");
  const [dob, setDob] = useState("");
  const [profession, setProfession] = useState("");
  const [company, setCompany] = useState("");
  const [about, setAbout] = useState("");
  const [instagram, setInstagram] = useState("");
  const [website, setWebsite] = useState("");
  const [verifiedPhone, setVerifiedPhone] = useState(false);
  const [verifiedEmail, setVerifiedEmail] = useState(false);
  const [emailCode, setEmailCode] = useState("");
  const [phoneCode, setPhoneCode] = useState("");
  const [emailCodeSent, setEmailCodeSent] = useState(false);
  const [phoneCodeSent, setPhoneCodeSent] = useState(false);
  const [verifying, setVerifying] = useState<"email" | "phone" | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.get("/client/profile");
      setProfilePhoto(data.profile_photo_base64 || null);
      setFullName(data.full_name || "");
      setGender(data.gender || "");
      setPhone(data.phone || "");
      setEmail(data.email || "");
      setCity(data.city || "");
      setDob(isValidIsoDate(data.dob || "") ? data.dob : "");
      setProfession(data.profession || "");
      setCompany(data.company || "");
      setAbout(data.about || "");
      setInstagram(data.instagram || "");
      setWebsite(data.website || "");
      setVerifiedPhone(!!data.verified_phone);
      setVerifiedEmail(!!data.verified_email);
    } catch (error) {
      toast.show(error instanceof ApiError ? error.message : "Could not load your profile", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const dobLooksValid = /^\d{4}-\d{2}-\d{2}$/.test(dob.trim());
  const canSave = useMemo(
    () =>
      !!fullName.trim() &&
      !!gender &&
      isPhoneNumberValid(phone) &&
      verifiedPhone &&
      !!email.trim() &&
      verifiedEmail &&
      !!city.trim() &&
      dobLooksValid,
    [fullName, gender, phone, verifiedPhone, email, verifiedEmail, city, dobLooksValid]
  );

  const choosePhoto = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      toast.show("Photo access is needed to choose a profile photo", "error");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
      base64: true,
    });
    const asset = result.canceled ? null : result.assets?.[0];
    if (asset?.base64) {
      setProfilePhoto(`data:${asset.mimeType || "image/jpeg"};base64,${asset.base64}`);
    }
  };

  const sendVerification = async (channel: "email" | "phone") => {
    try {
      await api.post("/client/profile/request-otp", {
        channel,
        email: channel === "email" ? email.trim() : undefined,
        phone: channel === "phone" ? phone.trim() : undefined,
      });
      if (channel === "email") setEmailCodeSent(true);
      else setPhoneCodeSent(true);
      toast.show(`Verification code sent to your ${channel}`, "success");
    } catch (error) {
      toast.show(error instanceof ApiError ? error.message : "Could not send verification code", "error");
    }
  };

  const verifyContact = async (channel: "email" | "phone") => {
    const code = channel === "email" ? emailCode.trim() : phoneCode.trim();
    if (!code) {
      toast.show("Enter the verification code", "error");
      return;
    }
    setVerifying(channel);
    try {
      const data = await api.post("/client/profile/verify-otp", {
        channel,
        email: channel === "email" ? email.trim() : undefined,
        phone: channel === "phone" ? phone.trim() : undefined,
        code,
      });
      setEmail(data.email || email);
      setPhone(data.phone || phone);
      setVerifiedEmail(!!data.verified_email);
      setVerifiedPhone(!!data.verified_phone);
      if (channel === "email") setEmailCodeSent(false);
      else setPhoneCodeSent(false);
      toast.show(`${channel === "email" ? "Email" : "Mobile number"} verified`, "success");
    } catch (error) {
      toast.show(error instanceof ApiError ? error.message : "Could not verify contact", "error");
    } finally {
      setVerifying(null);
    }
  };

  const save = async () => {
    if (!canSave) {
      toast.show("Complete and verify all required fields first", "error");
      return;
    }
    setSaving(true);
    try {
      await api.patch("/client/profile", {
        full_name: fullName.trim(),
        gender,
        phone: phone.trim(),
        email: email.trim(),
        city: city.trim(),
        dob: dob.trim(),
        profile_photo_base64: profilePhoto,
        profession: profession.trim() || null,
        company: company.trim() || null,
        about: about.trim() || null,
        instagram: instagram.trim() || null,
        website: website.trim() || null,
      });
      toast.show("Profile saved", "success");
      router.back();
    } catch (error) {
      toast.show(error instanceof ApiError ? error.message : "Could not save your profile", "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center} testID="client-profile-loading">
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }

  return (
    <View style={styles.container} testID="client-profile-screen">
      <GlassHeader title="My Profile" subtitle="Your details for a better studio experience" onBack={() => router.back()} topInset={insets.top} />
      <KeyboardAwareScrollView
        contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing["3xl"] }]}
        bottomOffset={24}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.photoSection}>
          <Pressable testID="profile-photo-picker" onPress={choosePhoto} style={styles.photoButton}>
            {profilePhoto ? (
              <Image source={{ uri: profilePhoto }} style={styles.photo} contentFit="cover" />
            ) : (
              <Ionicons name="camera-outline" size={30} color={colors.brand} />
            )}
            <View style={styles.photoBadge}>
              <Ionicons name="add" size={14} color={colors.onBrand} />
            </View>
          </Pressable>
          <Text style={styles.photoTitle}>Add a profile photo</Text>
          <Text style={styles.photoSub}>Optional · visible to your studio</Text>
        </View>

        <Text style={styles.sectionLabel}>Required details</Text>
        <TextField testID="profile-full-name" label="Full name" value={fullName} onChangeText={setFullName} placeholder="Your full name" autoCapitalize="words" />

        <Text style={styles.fieldLabel}>Gender</Text>
        <View style={styles.chipRow}>
          {GENDERS.map((item) => (
            <Pressable key={item} testID={`profile-gender-${item}`} onPress={() => setGender(item)} style={[styles.chip, gender === item && styles.chipActive]}>
              <Text style={[styles.chipText, gender === item && styles.chipTextActive]}>{item}</Text>
            </Pressable>
          ))}
        </View>

        <ContactField
          channel="phone"
          value={phone}
          verified={verifiedPhone}
          code={phoneCode}
          codeSent={phoneCodeSent}
          verifying={verifying === "phone"}
          onChange={setPhone}
          onCodeChange={setPhoneCode}
          onSend={() => sendVerification("phone")}
          onVerify={() => verifyContact("phone")}
        />
        <ContactField
          channel="email"
          value={email}
          verified={verifiedEmail}
          code={emailCode}
          codeSent={emailCodeSent}
          verifying={verifying === "email"}
          onChange={setEmail}
          onCodeChange={setEmailCode}
          onSend={() => sendVerification("email")}
          onVerify={() => verifyContact("email")}
        />

        <View style={styles.row}>
          <View style={styles.rowItem}>
            <TextField testID="profile-city" label="City" value={city} onChangeText={setCity} placeholder="e.g. Goa" autoCapitalize="words" />
          </View>
          <View style={styles.rowItem}>
            <DatePickerField testID="profile-dob" label="Date of birth" value={dob} onChange={setDob} emptyLabel="Choose date of birth" />
          </View>
        </View>

        <Text style={styles.sectionLabel}>About you</Text>
        <TextField testID="profile-profession" label="Profession" value={profession} onChangeText={setProfession} placeholder="e.g. Architect" />
        <TextField testID="profile-company" label="Company / organization" value={company} onChangeText={setCompany} placeholder="e.g. Acme Studio" />
        <Text style={styles.fieldLabel}>About me</Text>
        <TextInput testID="profile-about" value={about} onChangeText={setAbout} placeholder="Tell your studio a little about you" placeholderTextColor={colors.muted} multiline maxLength={1000} style={styles.aboutInput} />

        <Text style={styles.sectionLabel}>Online profiles <Text style={styles.optional}>(optional)</Text></Text>
        <TextField testID="profile-instagram" label="Instagram" value={instagram} onChangeText={setInstagram} placeholder="@yourhandle" autoCapitalize="none" />
        <TextField testID="profile-website" label="Website" value={website} onChangeText={setWebsite} placeholder="www.example.com" autoCapitalize="none" keyboardType="url" />

        <Button testID="profile-save" title="Save profile" icon="checkmark" loading={saving} disabled={!canSave} onPress={save} style={styles.saveButton} />
        {!canSave ? <Text style={styles.saveHint}>Verify your mobile and email, then complete the required fields.</Text> : null}
      </KeyboardAwareScrollView>
    </View>
  );
}

function ContactField({ channel, value, verified, code, codeSent, verifying, onChange, onCodeChange, onSend, onVerify }: {
  channel: "email" | "phone";
  value: string;
  verified: boolean;
  code: string;
  codeSent: boolean;
  verifying: boolean;
  onChange: (value: string) => void;
  onCodeChange: (value: string) => void;
  onSend: () => void;
  onVerify: () => void;
}) {
  const label = channel === "email" ? "Email address" : "Mobile number";
  return (
    <View style={styles.contactBlock}>
      {channel === "phone" ? (
        <PhoneField testID="profile-phone" label={label} value={value} onChangeText={onChange} placeholder="Enter mobile number" required editable={!verified} />
      ) : (
        <TextField testID="profile-email" label={label} value={value} onChangeText={onChange} placeholder="name@example.com" keyboardType="email-address" autoCapitalize="none" editable={!verified} />
      )}
      {verified ? (
        <View style={styles.verifiedRow}>
          <Ionicons name="checkmark-circle" size={17} color={colors.success} />
          <Text style={styles.verifiedText}>Verified</Text>
        </View>
      ) : (
        <>
          <Button title={codeSent ? "Code sent" : `Verify ${channel}`} variant="secondary" icon="shield-checkmark-outline" onPress={onSend} disabled={!value.trim() || (channel === "phone" && !isPhoneNumberValid(value))} style={styles.verifyButton} />
          {codeSent ? (
            <View style={styles.codeRow}>
              <View style={{ flex: 1 }}>
                <TextField testID={`profile-${channel}-code`} label="Verification code" value={code} onChangeText={onCodeChange} placeholder="Enter code" keyboardType="number-pad" maxLength={8} />
              </View>
              <Button title="Confirm" loading={verifying} onPress={onVerify} style={styles.confirmButton} />
            </View>
          ) : null}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
  body: { padding: spacing.lg, paddingBottom: spacing["3xl"] },
  photoSection: { alignItems: "center", paddingVertical: spacing.lg },
  photoButton: { width: 96, height: 96, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, borderWidth: 1, borderColor: colors.brand, alignItems: "center", justifyContent: "center", overflow: "visible" },
  photo: { width: 94, height: 94, borderRadius: radius.pill },
  photoBadge: { position: "absolute", right: -2, bottom: -2, width: 30, height: 30, borderRadius: radius.pill, backgroundColor: colors.brand, alignItems: "center", justifyContent: "center", borderWidth: 2, borderColor: colors.surface },
  photoTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600", marginTop: spacing.md },
  photoSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 3 },
  sectionLabel: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700", letterSpacing: 1, textTransform: "uppercase", marginTop: spacing.xl, marginBottom: spacing.lg },
  optional: { color: colors.muted, fontWeight: "400", letterSpacing: 0, textTransform: "none" },
  fieldLabel: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, marginBottom: spacing.sm },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.lg },
  chip: { paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, minHeight: 42, justifyContent: "center" },
  chipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipText: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base },
  chipTextActive: { color: colors.onBrand, fontWeight: "600" },
  contactBlock: { marginBottom: spacing.sm },
  verifiedRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs, marginTop: -spacing.sm, marginBottom: spacing.md },
  verifiedText: { color: colors.success, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
  verifyButton: { alignSelf: "flex-start", height: 44, marginTop: -spacing.xs, marginBottom: spacing.sm },
  codeRow: { flexDirection: "row", alignItems: "flex-end", gap: spacing.sm },
  confirmButton: { width: 110, marginBottom: spacing.lg },
  row: { flexDirection: "row", gap: spacing.md },
  rowItem: { flex: 1 },
  aboutInput: { minHeight: 112, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, padding: spacing.lg, textAlignVertical: "top", marginBottom: spacing.lg },
  saveButton: { marginTop: spacing.lg },
  saveHint: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, textAlign: "center", marginTop: spacing.md },
});
