import { useEffect, useState } from "react";
import { useRouter } from "expo-router";
import Head from "expo-router/head";
import { Platform, Pressable, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { H1, H2, H3, P, A, Section, Footer } from "@expo/html-elements";

import { Button } from "@/src/components/ui";
import HeroShowcase from "@/src/components/HeroShowcase";
import { Reveal, RevealScroll } from "@/src/components/Reveal";
import { HERO_PALETTE as PAL } from "@/src/config/hero";
import { useAuth } from "@/src/context/AuthContext";
import { fonts, fontSize, radius, spacing } from "@/src/theme";
import { getAppSurface } from "@/src/navigation/host-routing";

const SITE = "https://www.pikconnect.com";
const OG_IMAGE = `${SITE}/pik-connect-share-card.png`;
const TITLE = "PIK Connect | Photo Gallery, AI Face Search & CRM for Photographers";
const DESC =
  "PIK Connect gives photographers a private photo gallery, AI face search, digital albums, effortless photo sharing and client management in one lightweight workspace.";
const KEYWORDS =
  "photo gallery for photographers, AI face search, photo sharing, digital albums, photography CRM, client management, PIK Connect";

const STEPS = [
  { icon: "camera-outline", title: "Snap a selfie", text: "Open your private digital album and take one quick selfie." },
  { icon: "sparkles-outline", title: "AI face search finds you", text: "Our AI face search finds your face across the entire gallery." },
  { icon: "cloud-download-outline", title: "Your photos", text: "View, save and share every photo of you in full quality." },
];

const FAQS = [
  { q: "How do I find my photos?", a: "Open the gallery link from PK Photography, take a selfie, and PIK Connect surfaces every photo of you instantly." },
  { q: "Is my gallery private?", a: "Yes — every gallery is a private, secure link, and your selfie is used only to match your photos." },
  { q: "Which cities do you cover?", a: "Studios in Andheri West, Mumbai and Morjim, Goa — plus destination and pan-India shoots." },
];

const BADGES = [
  { icon: "scan-outline", title: "AI Face Search", text: "Smart & accurate" },
  { icon: "shield-checkmark-outline", title: "Private & Secure", text: "Your data stays safe" },
  { icon: "flash-outline", title: "Instant Delivery", text: "Results in seconds" },
  { icon: "albums-outline", title: "Digital Album", text: "Your private album" },
];

const NAV_ITEMS = [
  { label: "How it works", route: "/how-it-works" },
  { label: "Features", route: "/features" },
  { label: "For Photographers", route: "/for-photographers" },
  { label: "Pricing", route: "/pricing" },
];

function BadgeCard({ icon, title, text, style }: { icon: string; title: string; text: string; style?: object }) {
  return (
    <View style={[styles.badge, style]}>
      <View style={styles.badgeIcon}>
        <Ionicons name={icon as any} size={16} color={PAL.accent} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.badgeTitle}>{title}</Text>
        <Text style={styles.badgeText}>{text}</Text>
      </View>
    </View>
  );
}

function FaqRow({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={styles.faqItem}>
      <Pressable onPress={() => setOpen((o) => !o)} style={styles.faqHead} accessibilityRole="button">
        <H3 style={styles.faqQ}>{q}</H3>
        <Ionicons name={open ? "remove" : "add"} size={18} color={PAL.accent} />
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
  const insets = useSafeAreaInsets();
  const isWide = width >= 900;
  const isWebWide = Platform.OS === "web" && isWide;
  const surface = getAppSurface();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const openPage = (route: string) => {
    setMobileMenuOpen(false);
    router.push(route as any);
  };

  useEffect(() => {
    if (surface === "client") {
      router.replace(user?.role === "client" ? "/client" : "/client-login");
      return;
    }
    if (surface === "studio") {
      router.replace(user?.role === "admin" ? "/admin" : "/admin-login");
      return;
    }
    if (surface === "superadmin") {
      router.replace(user?.role === "superadmin" ? "/superadmin" : "/superadmin-login");
      return;
    }
    if (user) router.replace(user.role === "superadmin" ? "/superadmin" : user.role === "admin" ? "/admin" : "/client");
  }, [surface, user, router]);

  const artWidth = isWide ? Math.min(620, Math.max(460, width * 0.44)) : Math.min(width - spacing.xl * 2, 340);

  return (
    <>
      <Head>
        <title>{TITLE}</title>
        <meta name="description" content={DESC} />
        <meta name="keywords" content={KEYWORDS} />
        <meta name="robots" content="index, follow" />
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

      <RevealScroll style={styles.page} contentContainerStyle={styles.pageContent} showsVerticalScrollIndicator={false}>
        {/* ---------------- HERO ---------------- */}
        <View style={[styles.hero, isWebWide && { minHeight: height }]}>
          <View pointerEvents="none" style={styles.heroGlow} />
          <View pointerEvents="box-none" style={[styles.heroInner, { paddingTop: insets.top + spacing.lg }, isWide && styles.heroInnerWide]}>
            <View style={styles.topBar}>
              <View style={styles.logoRow}><Ionicons name="aperture-outline" size={24} color={PAL.accent} /><Text style={styles.logo}>PIK CONNECT</Text></View>
              {isWide ? (
                <View style={styles.navLinks}>
                  {NAV_ITEMS.map((item) => <Pressable key={item.route} onPress={() => openPage(item.route)}><Text style={styles.navLink}>{item.label}</Text></Pressable>)}
                </View>
              ) : (
                <Pressable testID="mobile-hero-menu" onPress={() => setMobileMenuOpen((open) => !open)} style={styles.menuButton} accessibilityLabel="Open menu"><Ionicons name={mobileMenuOpen ? "close" : "menu"} size={25} color={PAL.ink} /></Pressable>
              )}
            </View>
            {mobileMenuOpen && !isWide ? (
              <View style={styles.mobileMenu}>
                {NAV_ITEMS.map((item) => <Pressable key={item.route} onPress={() => openPage(item.route)} style={styles.mobileMenuItem}><Text style={styles.mobileMenuText}>{item.label}</Text></Pressable>)}
              </View>
            ) : null}
            <View style={[styles.heroBody, isWide && styles.heroBodyWide]}>
              <View style={[styles.heroCopy, isWide && styles.heroCopyWide]}>
                <View style={styles.eyebrowPill}><Ionicons name="sparkles" size={12} color={PAL.accent} /><Text style={styles.eyebrow}>AI-POWERED FACE SEARCH</Text></View>
                <H1 style={[styles.h1, isWide && styles.h1Wide]}>Your event photos,{"\n"}found in an <Text style={styles.h1Accent}>instant.</Text></H1>
                <P style={styles.heroSub}>Take one selfie — our AI scans your face and finds every photo of you across the entire event gallery, in seconds.</P>
                <View style={[styles.ctaRow, isWide && styles.ctaRowWide]}>
                  <Button testID="continue-client-btn" title="Find my photos" icon="sparkles" onPress={() => router.push("/client-login")} style={isWide ? styles.ctaBtnWide : styles.ctaBtnMobile} />
                  <Pressable testID="see-how-it-works-btn" onPress={() => openPage("/how-it-works")} style={styles.secondaryCta}><View style={styles.playDot}><Ionicons name="play" size={10} color={PAL.ink} /></View><Text style={styles.secondaryCtaText}>See how it works</Text></Pressable>
                </View>
              </View>
              <View style={styles.heroArt}>
                <HeroShowcase width={artWidth} interactive={isWebWide} compact={!isWide} />
              </View>
            </View>
          </View>
        </View>

        <View style={styles.container}>
          {/* ---------------- TRUST BADGES ---------------- */}
          <Reveal>
            <Section style={styles.badgeSection}>
              <View style={[styles.badgeStrip, isWide && styles.badgeStripWide]}>
                {BADGES.map((b, i) => <BadgeCard key={b.title} {...b} style={isWide ? [styles.badgeWide, i > 0 && styles.badgeDivider] : styles.badgeMobile} />)}
              </View>
            </Section>
          </Reveal>

          {/* ---------------- HOW IT WORKS ---------------- */}
          <Reveal delay={60}>
            <Section style={styles.block}>
              <H2 style={styles.h2}>Hundreds of photos. One selfie.</H2>
              <View style={[styles.steps, isWide && styles.stepsWide]}>
                {STEPS.map((s, i) => (
                  <View key={i} style={[styles.stepCard, isWide && styles.stepCardWide]}>
                    <View style={styles.stepIcon}>
                      <Ionicons name={s.icon as any} size={20} color={PAL.accent} />
                    </View>
                    <H3 style={styles.stepTitle}>{s.title}</H3>
                    <P style={styles.stepText}>{s.text}</P>
                  </View>
                ))}
              </View>
            </Section>
          </Reveal>

          {/* ---------------- FAQ ---------------- */}
          <Reveal>
            <Section style={styles.block}>
              <H2 style={styles.h2}>Questions, answered</H2>
              <View style={styles.faqWrap}>
                {FAQS.map((f) => (
                  <FaqRow key={f.q} q={f.q} a={f.a} />
                ))}
              </View>
            </Section>
          </Reveal>

          {/* ---------------- FOOTER / NAP ---------------- */}
          <Reveal>
          <Footer style={styles.footer}>
            <P style={styles.addr}>Mumbai · C1302, Evershine Cosmic, Andheri West 400053 · +91 88887 66739</P>
            <P style={styles.addr}>Goa · House No. 1053 A, Morjim 403512 · +91 81888 81165</P>
            <View style={styles.social}>
              <A href="https://www.instagram.com/itspkphotography.in/" style={styles.socialBtn}>
                <Ionicons name="logo-instagram" size={24} color={PAL.inkSoft} />
              </A>
              <A href="https://www.facebook.com/pkfashionphotography" style={styles.socialBtn}>
                <Ionicons name="logo-facebook" size={24} color={PAL.inkSoft} />
              </A>
              <A href="https://www.linkedin.com/company/pkphotography/" style={styles.socialBtn}>
                <Ionicons name="logo-linkedin" size={24} color={PAL.inkSoft} />
              </A>
              <A href="https://x.com/pkphotographym" style={styles.socialBtn}>
                <Ionicons name="logo-twitter" size={24} color={PAL.inkSoft} />
              </A>
              <A href="https://www.youtube.com/@itspkphotography" style={styles.socialBtn}>
                <Ionicons name="logo-youtube" size={24} color={PAL.inkSoft} />
              </A>
              <A href="https://wa.me/918888766739" style={styles.socialBtn}>
                <Ionicons name="logo-whatsapp" size={24} color={PAL.inkSoft} />
              </A>
              <A href="mailto:prabhakar@pkphotography.in" style={styles.socialBtn}>
                <Ionicons name="mail-outline" size={24} color={PAL.inkSoft} />
              </A>
            </View>
            <Text style={styles.copy}>© 2026 PK Photography · PIK Connect</Text>
          </Footer>
          </Reveal>
        </View>
      </RevealScroll>
    </>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: PAL.bg },
  pageContent: { backgroundColor: PAL.bg },

  // ---- Mid-tone minimal hero ----
  hero: { overflow: "hidden", backgroundColor: PAL.bg },
  heroGlow: { position: "absolute", top: -260, right: -160, width: 620, height: 620, borderRadius: 310, backgroundColor: "rgba(226,98,60,0.08)" },
  heroInner: { flex: 1, padding: spacing.xl, paddingBottom: spacing.xl, gap: spacing.lg },
  heroInnerWide: { maxWidth: 1240, width: "100%", alignSelf: "center", paddingHorizontal: spacing["3xl"], paddingBottom: spacing["2xl"] },
  topBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 44, zIndex: 20 },
  logoRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  logo: { color: PAL.ink, fontFamily: fonts.text, fontSize: fontSize.sm, letterSpacing: 4, fontWeight: "700" },
  navLinks: { flexDirection: "row", alignItems: "center", gap: spacing.xl },
  navLink: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "500" },
  menuButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center", borderRadius: radius.pill, backgroundColor: "rgba(36,29,22,0.06)" },
  mobileMenu: { alignSelf: "flex-end", width: 210, padding: spacing.sm, borderRadius: radius.md, backgroundColor: PAL.card, borderWidth: 1, borderColor: PAL.cardBorder, zIndex: 20, shadowColor: "#3A2C1D", shadowOpacity: 0.18, shadowRadius: 20, shadowOffset: { width: 0, height: 10 }, elevation: 8 },
  mobileMenuItem: { minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.md },
  mobileMenuText: { color: PAL.ink, fontFamily: fonts.text, fontSize: fontSize.base },
  heroBody: { gap: spacing.xl, marginTop: spacing.lg },
  heroBodyWide: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing["2xl"], marginTop: 0 },
  heroCopy: { gap: spacing.md },
  heroCopyWide: { flex: 1, maxWidth: 600 },
  heroArt: { alignItems: "center", justifyContent: "center", marginTop: spacing.md },
  eyebrowPill: { flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start", paddingHorizontal: spacing.md, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: "rgba(226,98,60,0.10)", borderWidth: 1, borderColor: "rgba(226,98,60,0.22)" },
  eyebrow: { color: PAL.accent, fontFamily: fonts.text, fontSize: 11, fontWeight: "700", letterSpacing: 2 },
  h1: { color: PAL.ink, fontFamily: fonts.display, fontSize: 40, lineHeight: 45, fontWeight: "700", letterSpacing: -0.5, margin: 0, marginTop: spacing.sm, maxWidth: 520 },
  h1Wide: { fontSize: 58, lineHeight: 63, maxWidth: 620 },
  h1Accent: { color: PAL.accent, fontStyle: "italic" },
  heroSub: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.lg, lineHeight: 25, marginTop: spacing.xs, maxWidth: 430 },
  ctaRow: { gap: spacing.md, marginTop: spacing.lg, alignItems: "flex-start" },
  ctaRowWide: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", maxWidth: 560 },
  ctaBtnWide: { minWidth: 224, paddingHorizontal: spacing.xl },
  ctaBtnMobile: { alignSelf: "stretch", minWidth: 240 },
  secondaryCta: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.sm },
  playDot: { width: 30, height: 30, borderRadius: radius.pill, borderWidth: 1.5, borderColor: "rgba(36,29,22,0.35)", alignItems: "center", justifyContent: "center", paddingLeft: 2 },
  secondaryCtaText: { color: PAL.ink, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "500" },

  // ---- Trust badge strip (first scroll section) ----
  badgeSection: { paddingTop: spacing.xl, paddingBottom: spacing.md },
  badgeStrip: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  badgeStripWide: { flexWrap: "nowrap", backgroundColor: PAL.card, borderRadius: radius.lg, borderWidth: 1, borderColor: PAL.cardBorder, paddingVertical: spacing.md, paddingHorizontal: spacing.lg, gap: 0 },
  badge: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  badgeWide: { flex: 1 },
  badgeDivider: { borderLeftWidth: 1, borderLeftColor: PAL.cardBorder },
  badgeMobile: { width: "47%", flexGrow: 1, backgroundColor: PAL.card, borderRadius: radius.md, borderWidth: 1, borderColor: PAL.cardBorder },
  badgeIcon: { width: 32, height: 32, borderRadius: radius.sm, backgroundColor: "rgba(226,98,60,0.12)", alignItems: "center", justifyContent: "center" },
  badgeTitle: { color: PAL.ink, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  badgeText: { color: PAL.inkFaint, fontFamily: fonts.text, fontSize: 11, marginTop: 1 },

  // ---- Shared container ----
  container: { width: "100%", maxWidth: 1160, alignSelf: "center", paddingHorizontal: spacing.xl },
  block: { paddingVertical: spacing["2xl"], borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "rgba(36,29,22,0.12)" },
  h2: { color: PAL.ink, fontFamily: fonts.display, fontSize: fontSize["2xl"], fontWeight: "700", margin: 0, marginBottom: spacing.xl },

  // ---- How it works cards ----
  steps: { gap: spacing.md },
  stepsWide: { flexDirection: "row", gap: spacing.lg },
  stepCard: { backgroundColor: PAL.card, borderWidth: 1, borderColor: PAL.cardBorder, borderRadius: radius.lg, padding: spacing.xl, gap: spacing.xs },
  stepCardWide: { flex: 1 },
  stepIcon: { width: 44, height: 44, borderRadius: radius.pill, backgroundColor: "rgba(226,98,60,0.12)", alignItems: "center", justifyContent: "center", marginBottom: spacing.sm },
  stepTitle: { color: PAL.ink, fontFamily: fonts.display, fontSize: fontSize.xl, fontWeight: "700", margin: 0 },
  stepText: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 21, margin: 0 },

  // ---- FAQ ----
  faqWrap: { maxWidth: 760 },
  faqItem: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "rgba(36,29,22,0.14)" },
  faqHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: spacing.lg, gap: spacing.md },
  faqQ: { flex: 1, color: PAL.ink, fontFamily: fonts.text, fontSize: fontSize.lg, fontWeight: "600", margin: 0 },
  faqAnswerWrap: { overflow: "hidden" },
  collapsed: { height: 0 },
  faqA: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 22, margin: 0, paddingBottom: spacing.lg },

  // ---- Footer ----
  footer: { paddingVertical: spacing["2xl"], borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "rgba(36,29,22,0.12)", gap: spacing.xs },
  social: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: spacing.lg, marginTop: spacing.lg },
  socialBtn: { paddingVertical: spacing.xs, alignItems: "center", justifyContent: "center", textDecorationLine: "none" },
  addr: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 20, margin: 0 },
  copy: { color: PAL.inkFaint, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: spacing.lg },
});
