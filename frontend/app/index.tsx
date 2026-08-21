import { useEffect } from "react";
import { useRouter } from "expo-router";
import Head from "expo-router/head";
import { ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { H1, H2, H3, P, A, UL, LI, Section, Footer } from "@expo/html-elements";

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
  { icon: "camera", title: "Take a selfie", text: "Open your event link and snap a quick selfie — no login or app download needed." },
  { icon: "sparkles", title: "We find your face", text: "PIK Connect uses face recognition to instantly match you across the entire event gallery." },
  { icon: "download", title: "View & download", text: "Get every photo of you in full resolution, ready to save and share with family." },
];

const SERVICES = [
  "Wedding photography & videography in Mumbai & Goa",
  "Pre-wedding & destination weddings across Goa",
  "Corporate & event photography and videography",
  "Portraits, headshots & editorial portfolios",
  "Product, fashion & brand photography",
  "Drone / aerial photography and live streaming",
];

const FAQS = [
  { q: "How do I find my photos on PIK Connect?", a: "Open the gallery link shared by PK Photography, take a selfie, and PIK Connect instantly surfaces every photo of you from the event using face recognition." },
  { q: "Is my photo gallery private and secure?", a: "Yes. Every gallery is a private, secure link. Only people with the link can access it, and your selfie is used solely to match your photos." },
  { q: "Which cities does PK Photography cover?", a: "We are based in Andheri West, Mumbai and in Morjim, Goa, and shoot weddings and events across Mumbai, Goa and pan-India destination locations." },
  { q: "How soon do I get my event gallery?", a: "Highlights are shared quickly and the full edited gallery is delivered on the timeline agreed before your shoot — ready to view, download and share." },
  { q: "How do I book a wedding or event shoot?", a: "Tap “Studio sign in” to reach us, message us on WhatsApp at +91 88887 66739, or email prabhakar@pkphotography.in to plan your shoot." },
];

const STATS = [
  { value: "12+", label: "Years of craft" },
  { value: "380+", label: "Google reviews" },
  { value: "4.9★", label: "Average rating" },
  { value: "98%", label: "Repeat & referral" },
];

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
        <meta property="og:site_name" content="PIK Connect" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={TITLE} />
        <meta name="twitter:description" content={DESC} />
        <meta name="twitter:image" content={OG_IMAGE} />
      </Head>

      <ScrollView style={styles.page} contentContainerStyle={styles.pageContent}>
        {/* ---------------- HERO ---------------- */}
        <View style={[styles.hero, { minHeight: Math.max(540, height * 0.82) }]}>
          <Image source={{ uri: HERO }} style={StyleSheet.absoluteFill} contentFit="cover" />
          <LinearGradient
            colors={["rgba(14,13,12,0.25)", "rgba(14,13,12,0.75)", "rgba(14,13,12,0.99)"]}
            locations={[0, 0.55, 1]}
            style={StyleSheet.absoluteFill}
          />
          <View style={[styles.heroInner, isWide && styles.heroInnerWide]}>
            <View style={styles.logoRow}>
              <Ionicons name="aperture-outline" size={26} color={colors.brand} />
              <Text style={styles.logo}>PIK CONNECT</Text>
            </View>
            <View style={[styles.heroCopy, isWide && { maxWidth: 620 }]}>
              <H1 style={[styles.h1, isWide && styles.h1Wide]}>Your event photos, found in an instant.</H1>
              <P style={styles.heroSub}>
                Take a selfie and PIK Connect surfaces every photo of you from your PK Photography event
                gallery — wedding & event photography across Mumbai and Goa.
              </P>
              <View style={[styles.ctaRow, isWide && { maxWidth: 420 }]}>
                <Button testID="continue-client-btn" title="Find my photos" icon="sparkles" onPress={() => router.push("/client-login")} />
                <Button testID="continue-admin-btn" title="Studio sign in" variant="ghost" icon="briefcase-outline" onPress={() => router.push("/admin-login")} />
              </View>
            </View>
          </View>
        </View>

        <View style={styles.container}>
          {/* ---------------- HOW IT WORKS ---------------- */}
          <Section style={styles.section}>
            <Text style={styles.kicker}>How it works</Text>
            <H2 style={styles.h2}>Find your photos in three steps.</H2>
            <View style={[styles.grid, isWide && styles.grid3]}>
              {STEPS.map((s, i) => (
                <View key={s.title} style={[styles.card, isWide && styles.cardThird]}>
                  <View style={styles.cardIcon}>
                    <Ionicons name={s.icon as any} size={22} color={colors.brand} />
                  </View>
                  <H3 style={styles.h3}>{`${i + 1}. ${s.title}`}</H3>
                  <P style={styles.body}>{s.text}</P>
                </View>
              ))}
            </View>
          </Section>

          {/* ---------------- ABOUT ---------------- */}
          <Section style={styles.section}>
            <Text style={styles.kicker}>What is PIK Connect</Text>
            <H2 style={styles.h2}>Private photo galleries for PK Photography clients.</H2>
            <P style={styles.body}>
              PIK Connect is the official client gallery and photo-delivery platform of PK Photography. Instead of
              scrolling through thousands of images, guests simply take a selfie and receive every photo of
              themselves in seconds. Couples and companies get one secure link to view, download and share their
              full wedding or event gallery in high resolution — anywhere, on any device.
            </P>
          </Section>

          {/* ---------------- SERVICES ---------------- */}
          <Section style={styles.section}>
            <Text style={styles.kicker}>Mumbai · Goa · Pan India</Text>
            <H2 style={styles.h2}>Photography & videography services.</H2>
            <P style={styles.body}>
              For over 12 years, PK Photography has created natural, cinematic visuals for couples, families and
              brands — trusted by 380+ five-star-rated clients across Mumbai and Goa.
            </P>
            <UL style={styles.list}>
              {SERVICES.map((s) => (
                <LI key={s} style={styles.li}>{s}</LI>
              ))}
            </UL>
          </Section>

          {/* ---------------- STATS ---------------- */}
          <View style={styles.statsRow}>
            {STATS.map((s) => (
              <View key={s.label} style={styles.stat}>
                <Text style={styles.statValue}>{s.value}</Text>
                <Text style={styles.statLabel}>{s.label}</Text>
              </View>
            ))}
          </View>

          {/* ---------------- FAQ ---------------- */}
          <Section style={styles.section}>
            <Text style={styles.kicker}>FAQ</Text>
            <H2 style={styles.h2}>Questions, answered.</H2>
            {FAQS.map((f) => (
              <View key={f.q} style={styles.faqItem}>
                <H3 style={styles.faqQ}>{f.q}</H3>
                <P style={styles.body}>{f.a}</P>
              </View>
            ))}
          </Section>

          {/* ---------------- FOOTER / NAP ---------------- */}
          <Footer style={styles.footer}>
            <H2 style={styles.footerBrand}>PK Photography</H2>
            <P style={styles.body}>
              Wedding, pre-wedding, event, corporate, portrait, drone photography & videography in Mumbai & Goa.
            </P>
            <View style={[styles.studios, isWide && styles.studiosWide]}>
              <View style={styles.studio}>
                <H3 style={styles.h3}>Mumbai Studio</H3>
                <P style={styles.addr}>
                  C1302, Evershine Cosmic, Opp. Infiniti Mall, Veera Desai Industrial Estate, Andheri West,
                  Mumbai, Maharashtra 400053
                </P>
                <A href="tel:+918888766739" style={styles.link}>+91 88887 66739</A>
              </View>
              <View style={styles.studio}>
                <H3 style={styles.h3}>Goa Studio</H3>
                <P style={styles.addr}>House No. 1053 A, Madhlavaddo, Morjim, Goa 403512</P>
                <A href="tel:+918188881165" style={styles.link}>+91 81888 81165</A>
              </View>
            </View>
            <View style={styles.footerLinks}>
              <A href="mailto:prabhakar@pkphotography.in" style={styles.link}>prabhakar@pkphotography.in</A>
              <A href="https://wa.me/918888766739" style={styles.link}>WhatsApp</A>
              <A href="https://g.page/r/CVhvUcwRhP2GEAE/review" style={styles.link}>Google Reviews</A>
              <A href="https://www.pkphotography.in" style={styles.link}>pkphotography.in</A>
            </View>
            <P style={styles.copy}>© 2026 PK Photography · Powered by PIK Connect · Updated August 2026</P>
          </Footer>
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.surface },
  pageContent: { paddingBottom: 0 },
  hero: { justifyContent: "flex-end" },
  heroInner: { padding: spacing.xl, paddingBottom: spacing["3xl"], gap: spacing.xl },
  heroInnerWide: { maxWidth: 1120, width: "100%", alignSelf: "center", paddingHorizontal: spacing["3xl"] },
  logoRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  logo: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, letterSpacing: 4, fontWeight: "600" },
  heroCopy: { gap: spacing.md },
  h1: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.hero, lineHeight: 46, margin: 0 },
  h1Wide: { fontSize: 60, lineHeight: 66 },
  heroSub: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.lg, lineHeight: 26, marginTop: spacing.sm, maxWidth: 460 },
  ctaRow: { gap: spacing.md, marginTop: spacing.lg },

  container: { width: "100%", maxWidth: 1120, alignSelf: "center", paddingHorizontal: spacing.xl },
  section: { paddingVertical: spacing["3xl"], borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  kicker: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.sm, letterSpacing: 2, textTransform: "uppercase", marginBottom: spacing.sm },
  h2: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], lineHeight: 36, margin: 0, marginBottom: spacing.lg },
  h3: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, margin: 0, marginBottom: spacing.xs },
  body: { color: colors.onSurfaceTertiary, fontFamily: fonts.text, fontSize: fontSize.lg, lineHeight: 26, margin: 0, maxWidth: 760 },

  grid: { gap: spacing.md },
  grid3: { flexDirection: "row" },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, padding: spacing.xl, gap: spacing.sm },
  cardThird: { flex: 1 },
  cardIcon: { width: 46, height: 46, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", marginBottom: spacing.sm },

  list: { marginTop: spacing.md, gap: spacing.sm },
  li: { color: colors.onSurfaceSecondary, fontFamily: fonts.text, fontSize: fontSize.lg, lineHeight: 26 },

  statsRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, paddingVertical: spacing["2xl"] },
  stat: { flexGrow: 1, minWidth: 140, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingVertical: spacing.xl, alignItems: "center" },
  statValue: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize["2xl"] },
  statLabel: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 4 },

  faqItem: { marginBottom: spacing.xl },
  faqQ: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.lg, margin: 0, marginBottom: spacing.xs },

  footer: { paddingVertical: spacing["3xl"], borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, gap: spacing.md },
  footerBrand: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl, margin: 0 },
  studios: { gap: spacing.xl, marginTop: spacing.md },
  studiosWide: { flexDirection: "row" },
  studio: { flex: 1, gap: 4 },
  addr: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 22, margin: 0, maxWidth: 360 },
  footerLinks: { flexDirection: "row", flexWrap: "wrap", gap: spacing.lg, marginTop: spacing.md },
  link: { color: colors.brand, fontFamily: fonts.text, fontSize: fontSize.base, textDecorationLine: "none" },
  copy: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.lg },
});
