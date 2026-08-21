import { useEffect, useState } from "react";
import { useRouter } from "expo-router";
import Head from "expo-router/head";
import { Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { H1, H2, H3, P, A, Section, Footer } from "@expo/html-elements";

import { Button } from "@/src/components/ui";
import { useAuth } from "@/src/context/AuthContext";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

const SITE = "https://www.pikconnect.com";
const OG_IMAGE = "https://pkphotography.in/pricing/PKP_0763%20cover.jpg";
const HERO =
  "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwxfHxjaW5lbWF0aWMlMjBkYXJrJTIwcGhvdG9ncmFwaHklMjBzdHVkaW8lMjBjYW1lcmF8ZW58MHx8fHwxNzg2ODIzMDE5fDA&ixlib=rb-4.1.0&q=85";

const TITLE = "PIK Connect — Event Photo Galleries by PK Photography";
const DESC =
  "Find your event & wedding photos instantly with a selfie. PIK Connect delivers private photo galleries for PK Photography clients across Mumbai & Goa.";
const KEYWORDS =
  "PIK Connect, PK Photography, wedding photographer Mumbai, event photographer Goa, pre-wedding photography Goa, corporate photography Mumbai, event photo gallery, find my photos selfie, photo delivery app, destination wedding photographer";

const STEPS = [
  { icon: "camera", text: "Open your event link & take a quick selfie" },
  { icon: "sparkles", text: "We match your face across the gallery" },
  { icon: "download", text: "View & download your photos in full quality" },
];

const FAQS = [
  { q: "How do I find my photos?", a: "Open the gallery link from PK Photography, take a selfie, and PIK Connect surfaces every photo of you instantly." },
  { q: "Is my gallery private?", a: "Yes — every gallery is a private, secure link, and your selfie is used only to match your photos." },
  { q: "Which cities do you cover?", a: "Studios in Andheri West, Mumbai and Morjim, Goa — plus destination and pan-India shoots." },
];

function FaqRow({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={styles.faqItem}>
      <Pressable onPress={() => setOpen((o) => !o)} style={styles.faqHead} accessibilityRole="button">
        <H3 style={styles.faqQ}>{q}</H3>
        <Ionicons name={open ? "remove" : "add"} size={18} color={colors.brand} />
      </Pressable>
      <View style={[styles.faqAnswerWrap, !open && styles.collapsed]}>
        <P style={styles.faqA}>{a}</P>
      </View>
    </View>
  );
}

export default function Home() {
  const router = useRouter();
  const { user } = useAuth();
  const { width, height } = useWindowDimensions();
  const isWide = width >= 900;

  // Logged-in users are sent to their dashboard (client-only; crawlers never run this).
  useEffect(() => {
    if (user) router.replace(user.role === "admin" ? "/admin" : "/client");
  }, [user, router]);

  return (
    <>
      <Head>
        <title>{TITLE}</title>
        <meta name="description" content={DESC} />
        <meta name="keywords" content={KEYWORDS} />
        <meta name="robots" content="index, follow" />
        <link rel="canonical" href={`${SITE}/`} />
        <meta property="og:type" content="website" />
        <meta property="og:title" content={TITLE} />
        <meta property="og:description" content={DESC} />
        <meta property="og:url" content={`${SITE}/`} />
        <meta property="og:image" content={OG_IMAGE} />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={TITLE} />
        <meta name="twitter:description" content={DESC} />
        <meta name="twitter:image" content={OG_IMAGE} />
      </Head>

      <ScrollView style={styles.page} showsVerticalScrollIndicator={false}>
        {/* ---------------- HERO ---------------- */}
        <View style={[styles.hero, { minHeight: Math.max(420, height * 0.6) }]}>
          <Image source={{ uri: HERO }} style={StyleSheet.absoluteFill} contentFit="cover" />
          <LinearGradient
            colors={["rgba(14,13,12,0.25)", "rgba(14,13,12,0.78)", "rgba(14,13,12,0.99)"]}
            locations={[0, 0.55, 1]}
            style={StyleSheet.absoluteFill}
          />
          <View style={[styles.heroInner, isWide && styles.heroInnerWide]}>
            <View style={styles.logoRow}>
              <Ionicons name="aperture-outline" size={24} color={colors.brand} />
              <Text style={styles.logo}>PIK CONNECT</Text>
            </View>
            <View style={[styles.heroCopy, isWide && { maxWidth: 600 }]}>
              <H1 style={[styles.h1, isWide && styles.h1Wide]}>Your event photos, found in an instant.</H1>
              <P style={styles.heroSub}>
                Take a selfie and instantly get every photo of you from your PK Photography event gallery.
              </P>
              <View style={[styles.ctaRow, isWide && { maxWidth: 400 }]}>
                <Button testID="continue-client-btn" title="Find my photos" icon="sparkles" onPress={() => router.push("/client-login")} />
                <Button testID="continue-admin-btn" title="Studio sign in" variant="ghost" icon="briefcase-outline" onPress={() => router.push("/admin-login")} />
              </View>
              <Text style={styles.trust}>12+ years · 4.9★ · 380+ Google reviews · Mumbai & Goa</Text>
            </View>
          </View>
        </View>

        <View style={styles.container}>
          {/* ---------------- HOW IT WORKS ---------------- */}
          <Section style={styles.block}>
            <H2 style={styles.h2}>How it works</H2>
            <View style={styles.steps}>
              {STEPS.map((s, i) => (
                <View key={i} style={styles.step}>
                  <View style={styles.stepIcon}>
                    <Ionicons name={s.icon as any} size={18} color={colors.brand} />
                  </View>
                  <P style={styles.stepText}>{s.text}</P>
                </View>
              ))}
            </View>
          </Section>

          {/* ---------------- FAQ ---------------- */}
          <Section style={styles.block}>
            <H2 style={styles.h2}>Questions, answered</H2>
            {FAQS.map((f) => (
              <FaqRow key={f.q} q={f.q} a={f.a} />
            ))}
          </Section>

          {/* ---------------- FOOTER / NAP ---------------- */}
          <Footer style={styles.footer}>
            <View style={styles.footerTop}>
              <Text style={styles.footerBrand}>PK Photography</Text>
              <View style={styles.social}>
                <A href="mailto:prabhakar@pkphotography.in" style={styles.socialBtn}>
                  <Ionicons name="mail-outline" size={17} color={colors.onSurfaceTertiary} />
                </A>
                <A href="https://wa.me/918888766739" style={styles.socialBtn}>
                  <Ionicons name="logo-whatsapp" size={17} color={colors.onSurfaceTertiary} />
                </A>
                <A href="https://g.page/r/CVhvUcwRhP2GEAE/review" style={styles.socialBtn}>
                  <Ionicons name="star-outline" size={17} color={colors.onSurfaceTertiary} />
                </A>
                <A href="https://www.pkphotography.in" style={styles.socialBtn}>
                  <Ionicons name="globe-outline" size={17} color={colors.onSurfaceTertiary} />
                </A>
              </View>
            </View>
            <P style={styles.addr}>Mumbai · C1302, Evershine Cosmic, Andheri West 400053 · +91 88887 66739</P>
            <P style={styles.addr}>Goa · House No. 1053 A, Morjim 403512 · +91 81888 81165</P>
            <Text style={styles.copy}>© 2026 PK Photography · PIK Connect</Text>
          </Footer>
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.surface },
  hero: { justifyContent: "flex-end" },
  heroInner: { padding: spacing.xl, paddingBottom: spacing.xl, gap: spacing.lg },
  heroInnerWide: { maxWidth: 1120, width: "100%", alignSelf: "center", paddingHorizontal: spacing["3xl"] },
  logoRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  logo: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.sm, letterSpacing: 4, fontWeight: "600" },
  heroCopy: { gap: spacing.sm },
  h1: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.hero, lineHeight: 44, margin: 0 },
  h1Wide: { fontSize: 56, lineHeight: 62 },
  heroSub: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 22, marginTop: spacing.xs, maxWidth: 340 },
  ctaRow: { gap: spacing.sm, marginTop: spacing.md },
  trust: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.xs, marginTop: spacing.sm },

  container: { width: "100%", maxWidth: 640, alignSelf: "center", paddingHorizontal: spacing.xl },
  block: { paddingVertical: spacing.lg, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  h2: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.lg, margin: 0, marginBottom: spacing.md },

  steps: { gap: spacing.md },
  step: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  stepIcon: { width: 30, height: 30, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  stepText: { flex: 1, color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 20, margin: 0 },

  faqItem: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.divider },
  faqHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: spacing.md, gap: spacing.md },
  faqQ: { flex: 1, color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600", margin: 0 },
  faqAnswerWrap: { overflow: "hidden" },
  collapsed: { height: 0 },
  faqA: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 21, margin: 0, paddingBottom: spacing.md },

  footer: { paddingVertical: spacing.lg, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, gap: spacing.xs },
  footerTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.xs },
  footerBrand: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.lg },
  social: { flexDirection: "row", gap: spacing.xs },
  socialBtn: { width: 36, height: 36, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary, textDecorationLine: "none" },
  addr: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.xs, lineHeight: 18, margin: 0 },
  copy: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.xs, marginTop: spacing.sm },
});
