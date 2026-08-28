import { useRouter } from "expo-router";
import Head from "expo-router/head";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

type PageKind = "how-it-works" | "features" | "for-photographers" | "pricing";

type Feature = { icon: keyof typeof Ionicons.glyphMap; title: string; text: string };

const PLANS = [
  { name: "Standard", price: "₹499", note: "For growing studios", features: ["20 galleries", "30 Google Drive galleries", "10 albums", "5 GB storage", "500 clients"] },
  { name: "Pro", price: "₹999", note: "For busy photography teams", features: ["50 galleries", "100 Google Drive galleries", "50 albums", "15 GB storage", "Unlimited clients"] },
];

const FEATURES: Feature[] = [
  { icon: "scan-outline", title: "AI face search", text: "Guests take one selfie and PIK Connect surfaces their photos across the gallery." },
  { icon: "qr-code-outline", title: "QR share galleries", text: "Give every event a beautiful, private link and printable QR code." },
  { icon: "book-outline", title: "Digital flipbooks", text: "Turn a designed album PDF into a shareable, realistic page-turning album." },
  { icon: "people-outline", title: "Client management", text: "Track enquiries, quotes, payments, shoots, galleries and client activity in one place." },
];

const COPY: Record<PageKind, { eyebrow: string; title: string; intro: string }> = {
  "how-it-works": { eyebrow: "A SIMPLER WAY TO DELIVER PHOTOS", title: "From shutter to share, without the scramble.", intro: "PIK Connect brings the quiet confidence of a well-run studio to every gallery and every client." },
  features: { eyebrow: "THE PIK CONNECT TOOLKIT", title: "The technology disappears. The experience stays.", intro: "Thoughtful tools for the moments after the shoot: discovery, delivery, albums and relationships." },
  "for-photographers": { eyebrow: "FOR PHOTOGRAPHERS", title: "More time behind the camera.", intro: "Run a polished photo delivery workflow without stitching together five different tools." },
  pricing: { eyebrow: "SIMPLE STUDIO PLANS", title: "Choose the room you need to grow.", intro: "Start with the essentials and move up when your galleries, albums and client list do." },
};

export default function MarketingPage({ kind }: { kind: PageKind }) {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const copy = COPY[kind];
  return (
    <View style={styles.container}>
      <Head>
        <title>{`${copy.title} | PIK Connect`}</title>
        <meta name="description" content={copy.intro} />
      </Head>
      <ScrollView contentContainerStyle={[styles.page, { paddingTop: insets.top + spacing.lg, paddingBottom: insets.bottom + spacing["3xl"] }]} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Pressable testID="marketing-back" onPress={() => router.back()} style={styles.backButton} accessibilityLabel="Go back"><Ionicons name="arrow-back" size={20} color={colors.onSurface} /></Pressable>
          <View style={styles.brand}><Ionicons name="aperture-outline" size={20} color={colors.brand} /><Text style={styles.brandText}>PIK CONNECT</Text></View>
          <Button title="Find my photos" onPress={() => router.push("/client-login")} style={styles.headerCta} />
        </View>
        <View style={styles.hero}>
          <Text style={styles.eyebrow}>{copy.eyebrow}</Text>
          <Text style={styles.title}>{copy.title}</Text>
          <Text style={styles.intro}>{copy.intro}</Text>
        </View>
        {kind === "how-it-works" ? <HowItWorks /> : null}
        {kind === "features" ? <FeatureGrid /> : null}
        {kind === "for-photographers" ? <PhotographerWorkflow /> : null}
        {kind === "pricing" ? <Pricing /> : null}
        <View style={styles.bottomCta}><Text style={styles.bottomTitle}>Ready when your next gallery is?</Text><Button title="Find my photos" icon="sparkles" onPress={() => router.push("/client-login")} /></View>
      </ScrollView>
    </View>
  );
}

function HowItWorks() {
  const steps: Feature[] = [
    { icon: "cloud-upload-outline", title: "Create a private gallery", text: "Upload from your studio workflow and keep originals where they already live." },
    { icon: "qr-code-outline", title: "Share one QR code", text: "Guests scan a clean event link from a table card, screen or thank-you message." },
    { icon: "scan-outline", title: "Let guests find themselves", text: "AI face search turns a crowded gallery into a personal collection in seconds." },
    { icon: "download-outline", title: "Deliver beautifully", text: "Guests save, share and return to their digital album whenever they like." },
  ];
  return <View style={styles.section}>{steps.map((item, index) => <View key={item.title} style={styles.step}><View style={styles.stepIndex}><Text style={styles.stepIndexText}>{String(index + 1).padStart(2, "0")}</Text></View><View style={{ flex: 1 }}><Text style={styles.itemTitle}>{item.title}</Text><Text style={styles.itemText}>{item.text}</Text></View><Ionicons name={item.icon} size={22} color={colors.brand} /></View>)}</View>;
}

function FeatureGrid() {
  return <View style={styles.section}>{FEATURES.map((item) => <View key={item.title} style={styles.feature}><View style={styles.iconCircle}><Ionicons name={item.icon} size={22} color={colors.brand} /></View><Text style={styles.itemTitle}>{item.title}</Text><Text style={styles.itemText}>{item.text}</Text></View>)}</View>;
}

function PhotographerWorkflow() {
  return <View style={styles.section}><Text style={styles.sectionLead}>One calm workspace for the parts of the job that happen after the camera stops.</Text>{["Capture enquiries as Leads", "Build and send detailed quotes", "Collect booking payments", "Schedule shoots and track the calendar", "Deliver private galleries and flipbooks"].map((item, index) => <View key={item} style={styles.workflowRow}><Ionicons name="checkmark-circle" size={20} color={colors.brand} /><Text style={styles.workflowText}>{item}</Text><Text style={styles.workflowNumber}>{String(index + 1).padStart(2, "0")}</Text></View>)}</View>;
}

function Pricing() {
  return <View style={styles.section}>{PLANS.map((plan) => <View key={plan.name} style={styles.plan}><View style={styles.planHead}><View><Text style={styles.planName}>{plan.name}</Text><Text style={styles.planNote}>{plan.note}</Text></View><Text style={styles.planPrice}>{plan.price}<Text style={styles.planPer}> /mo</Text></Text></View>{plan.features.map((feature) => <View key={feature} style={styles.planFeature}><Ionicons name="checkmark" size={16} color={colors.brand} /><Text style={styles.itemText}>{feature}</Text></View>)}</View>)}</View>;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  page: { width: "100%", maxWidth: 980, alignSelf: "center", paddingHorizontal: spacing.lg },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 48 },
  backButton: { width: 44, height: 44, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center" },
  brand: { flexDirection: "row", alignItems: "center", gap: spacing.sm, flex: 1, marginLeft: spacing.md },
  brandText: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700", letterSpacing: 2.5 },
  headerCta: { minWidth: 140 },
  hero: { paddingVertical: spacing["3xl"], maxWidth: 720 },
  eyebrow: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700", letterSpacing: 2 },
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: 48, lineHeight: 54, fontWeight: "700", marginTop: spacing.lg },
  intro: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.lg, lineHeight: 27, marginTop: spacing.lg, maxWidth: 620 },
  section: { gap: spacing.md },
  sectionLead: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], lineHeight: 34, marginBottom: spacing.lg, maxWidth: 680 },
  step: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.lg, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  stepIndex: { width: 42, height: 42, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  stepIndexText: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  itemTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "700" },
  itemText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 21, marginTop: spacing.xs },
  feature: { padding: spacing.xl, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border },
  iconCircle: { width: 48, height: 48, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.brandTertiary, marginBottom: spacing.md },
  workflowRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingVertical: spacing.lg },
  workflowText: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.lg, flex: 1 },
  workflowNumber: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  plan: { padding: spacing.xl, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border },
  planHead: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", marginBottom: spacing.lg },
  planName: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  planNote: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.xs },
  planPrice: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  planPer: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm },
  planFeature: { flexDirection: "row", gap: spacing.sm, alignItems: "center", marginTop: spacing.sm },
  bottomCta: { alignItems: "center", paddingVertical: spacing["3xl"], marginTop: spacing["3xl"], borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  bottomTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], marginBottom: spacing.lg, textAlign: "center" },
});
