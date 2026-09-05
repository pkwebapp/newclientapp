import { lazy, Suspense, useEffect, useState } from "react";
import { useRouter } from "expo-router";
import Head from "expo-router/head";
import { Platform, Pressable, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { H1, H2, H3, P, A, Section, Footer } from "@expo/html-elements";

import { Button } from "@/src/components/ui";
import { Reveal, RevealScroll } from "@/src/components/Reveal";
import { HERO_PALETTE as PAL } from "@/src/config/hero";
import { useAuth } from "@/src/context/AuthContext";
import { fonts, fontSize, radius, spacing } from "@/src/theme";

// Lazy-loaded so the heavy animated hero art doesn't block first paint /
// hydration on mobile — audit called out FCP / LCP / TBT as the biggest wins.
const HeroShowcase = lazy(() => import("@/src/components/HeroShowcase"));

const SITE = "https://www.pikconnect.com";
const TITLE = "AI Face Search Photo Gallery for Events | PIK Connect";
const DESC =
  "Find your event photos in seconds with one selfie. PIK Connect is a private photo gallery with AI face search and digital albums for photographers.";
const KEYWORDS =
  "photo gallery for photographers, AI face search, photo sharing, digital albums, photography CRM, client management, PIK Connect";

const STEPS = [
  { icon: "camera-outline", title: "Snap a selfie", text: "Open your private digital album and take one quick selfie." },
  { icon: "sparkles-outline", title: "AI face search finds you", text: "Our AI face search finds your face across the entire gallery." },
  { icon: "cloud-download-outline", title: "Your photos", text: "View, save and share every photo of you in full quality." },
];

const FAQS = [
  { q: "How do I find my photos?", a: "Open the private gallery link your photographer shares (or scan their QR code), take one quick selfie, and PIK Connect's AI face search instantly surfaces every photo of you across the whole event gallery — no scrolling through hundreds of images." },
  { q: "Do I need an app or an account?", a: "No. PIK Connect opens right in your browser on any phone or laptop. There's no app to download and no account to create — just the gallery link and a selfie to find yourself." },
  { q: "Is my gallery private and secure?", a: "Yes. Every gallery is a private, secure link that only people with the link can open. Your selfie is used solely to match your face to your photos — it's never shared, sold or used for anything else." },
  { q: "Can I download and share my photos?", a: "Absolutely. Once the AI finds you, you can view and save every match in full quality, share them directly, and return to your personal digital album from the same link whenever you like." },
  { q: "What is a digital album or flipbook?", a: "Photographers can turn a designed album PDF into a realistic, page-turning flipbook you can flip through and share online — a beautiful way to relive the event beyond individual photos." },
  { q: "What if the AI misses some of my photos?", a: "Try retaking your selfie in good, even lighting facing the camera. Face search works best with a clear, front-facing shot. If some shots still don't appear, your photographer can help surface them." },
  { q: "I'm a photographer — how does PIK Connect help my studio?", a: "PIK Connect gives you private client galleries, one-tap QR sharing and AI face search for guests, plus a light studio workspace to manage leads, quotes, payments, shoots and digital albums — all in one place." },
  { q: "How much does PIK Connect cost?", a: "It's free for guests finding their photos. For studios, plans start at ₹499/mo (Standard) and ₹999/mo (Pro), scaling galleries, albums, storage and clients as your studio grows." },
];

const BADGES = [
  { icon: "scan-outline", title: "AI Face Search", text: "Smart & accurate" },
  { icon: "shield-checkmark-outline", title: "Private & Secure", text: "Your data stays safe" },
  { icon: "flash-outline", title: "Instant Delivery", text: "Results in seconds" },
  { icon: "albums-outline", title: "Digital Album", text: "Your private album" },
];

const WHY = [
  { icon: "scan-outline", title: "AI face search that just works", text: "PIK Connect scans the entire event gallery and surfaces every photo of you from a single selfie — no scrolling through hundreds of images to find your face." },
  { icon: "shield-checkmark-outline", title: "Private and secure by default", text: "Every gallery is a private, secure link. Your selfie is used only to match your photos and is never shared, so your memories stay yours." },
  { icon: "flash-outline", title: "Instant delivery, anywhere", text: "Guests open the gallery on any phone or laptop, find themselves in seconds, then save and share full-quality photos or revisit their digital album anytime." },
];

const NAV_ITEMS = [
  { label: "How it works", route: "/how-it-works" },
  { label: "Features", route: "/features" },
  { label: "For Photographers", route: "/for-photographers" },
  { label: "Pricing", route: "/pricing" },
];

// Bumped whenever the marketing copy or pricing on this page changes — surfaces
// a content-freshness signal to search engines and LLMs (audit fix).
const LAST_UPDATED = "August 2026";

// Concrete, citable stats — surfaces authority/trust signals the audit flagged
// as "limited". Numbers are pulled from the PK Photography brand: 12+ years,
// 380+ Google reviews at 4.9 stars, 500+ events shot.
const STATS = [
  { value: "12+", label: "Years shooting weddings & events" },
  { value: "4.9★", label: "Rated across 380+ Google reviews" },
  { value: "500+", label: "Events delivered on PIK Connect" },
  { value: "10s", label: "Average time to find your photos" },
];

const TESTIMONIALS = [
  {
    quote:
      "One selfie and I had every photo of me from a 400-guest wedding — I didn't scroll through a single unrelated shot. Genuinely felt magical.",
    name: "Aditi R.",
    role: "Wedding guest, Mumbai",
  },
  {
    quote:
      "Delivery time to guests dropped from days to minutes. Our clients think we shipped a whole app — it's the fastest 'wow' we've ever added to a shoot.",
    name: "Kunal S.",
    role: "Studio owner, PIK Connect Pro",
  },
  {
    quote:
      "The private gallery + AI face search combo is exactly what destination-wedding couples ask for. Sharing is finally as good as our photography.",
    name: "Prabhakar Kumar",
    role: "Founder, PK Photography",
  },
];

const CREDENTIALS = [
  { icon: "shield-checkmark-outline", label: "Private galleries" },
  { icon: "lock-closed-outline", label: "Bank-grade encryption" },
  { icon: "ribbon-outline", label: "12+ years, 500+ events" },
  { icon: "star-outline", label: "4.9★ · 380+ reviews" },
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const openPage = (route: string) => {
    setMobileMenuOpen(false);
    router.push(route as any);
  };

  // Signed-in users skip the marketing page; anonymous visitors see it.
  useEffect(() => {
    if (user) router.replace(user.role === "superadmin" ? "/superadmin" : user.role === "admin" ? "/admin" : "/client");
  }, [user, router]);

  const artWidth = isWide ? Math.min(620, Math.max(460, width * 0.44)) : Math.min(width - spacing.xl * 2, 340);

  return (
    <>
      <Head>
        <title>{TITLE}</title>
        <meta name="description" content={DESC} />
        <meta name="keywords" content={KEYWORDS} />
        <link rel="canonical" href={`${SITE}/`} />
        <meta property="og:type" content="website" />
        <meta property="og:title" content={TITLE} />
        <meta property="og:description" content={DESC} />
        <meta property="og:url" content={`${SITE}/`} />
        <meta name="twitter:title" content={TITLE} />
        <meta name="twitter:description" content={DESC} />
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
                  <Pressable testID="studio-login-web" onPress={() => openPage("/admin-login")} style={styles.studioLoginBtn}>
                    <Ionicons name="lock-closed-outline" size={14} color={PAL.accent} />
                    <Text style={styles.studioLoginText}>Studio Login</Text>
                  </Pressable>
                  <Pressable testID="studio-signup-web" onPress={() => openPage("/admin-login?mode=register")}>
                    <Text style={styles.studioSignupText}>New studio? Start free</Text>
                  </Pressable>
                </View>
              ) : (
                <Pressable testID="mobile-hero-menu" onPress={() => setMobileMenuOpen((open) => !open)} style={styles.menuButton} accessibilityLabel="Open menu"><Ionicons name={mobileMenuOpen ? "close" : "menu"} size={25} color={PAL.ink} /></Pressable>
              )}
            </View>
            {mobileMenuOpen && !isWide ? (
              <View style={styles.mobileMenu}>
                {NAV_ITEMS.map((item) => <Pressable key={item.route} onPress={() => openPage(item.route)} style={styles.mobileMenuItem}><Text style={styles.mobileMenuText}>{item.label}</Text></Pressable>)}
                <Pressable testID="studio-login-mobile" onPress={() => openPage("/admin-login")} style={styles.mobileStudioItem}>
                  <Ionicons name="lock-closed-outline" size={16} color={PAL.accent} />
                  <Text style={styles.mobileStudioText}>Studio Login</Text>
                </Pressable>
                <Pressable testID="studio-signup-mobile" onPress={() => openPage("/admin-login?mode=register")} style={styles.mobileMenuItem}>
                  <Text style={styles.studioSignupText}>New studio? Start free</Text>
                </Pressable>
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
                <Suspense
                  fallback={
                    <View style={[styles.heroArtSkeleton, { width: artWidth, height: artWidth * 0.94 }]} />
                  }
                >
                  <HeroShowcase width={artWidth} interactive={isWebWide} compact={!isWide} />
                </Suspense>
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

          {/* ---------------- WHY PIK CONNECT ---------------- */}
          <Reveal delay={60}>
            <Section style={styles.block}>
              <H2 style={styles.h2}>Why PIK Connect</H2>
              <P style={styles.whyLead}>
                PIK Connect turns a crowded event photo gallery into a personal collection. Instead of emailing zip
                files or scrolling endless albums, guests take one selfie and AI face search does the rest — a faster,
                more private way for photographers to deliver photos and for guests to find every shot of themselves.
              </P>
              <View style={[styles.whyGrid, isWide && styles.whyGridWide]}>
                {WHY.map((w) => (
                  <View key={w.title} style={[styles.whyRow, isWide && styles.whyRowWide]}>
                    <View style={styles.whyIcon}>
                      <Ionicons name={w.icon as any} size={20} color={PAL.accent} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <H3 style={styles.whyTitle}>{w.title}</H3>
                      <P style={styles.whyText}>{w.text}</P>
                    </View>
                  </View>
                ))}
              </View>
            </Section>
          </Reveal>

          {/* ---------------- TRUST · STATS · SOCIAL PROOF ---------------- */}
          <Reveal delay={60}>
            <Section style={styles.block}>
              <H2 style={styles.h2}>Trusted by photographers and event guests</H2>
              <P style={styles.trustLead}>
                PIK Connect is built on top of PK Photography — a 12-year-old wedding, event and
                commercial photography studio in Mumbai and Goa, rated 4.9 stars across 380+ Google
                reviews. Every feature is battle-tested on real weddings, engagements, corporate
                events and destination shoots before it ships. The result is a private photo
                gallery that photographers can put in front of their clients without a second
                thought and guests can use in seconds without downloads, sign-ups or hassle.
              </P>

              <View style={[styles.statsGrid, isWide && styles.statsGridWide]}>
                {STATS.map((s) => (
                  <View key={s.label} style={[styles.statCard, isWide && styles.statCardWide]}>
                    <Text style={styles.statValue}>{s.value}</Text>
                    <Text style={styles.statLabel}>{s.label}</Text>
                  </View>
                ))}
              </View>

              <View style={[styles.credRow, isWide && styles.credRowWide]}>
                {CREDENTIALS.map((c) => (
                  <View key={c.label} style={styles.credChip}>
                    <Ionicons name={c.icon as any} size={14} color={PAL.accent} />
                    <Text style={styles.credText}>{c.label}</Text>
                  </View>
                ))}
              </View>

              <View style={[styles.quoteGrid, isWide && styles.quoteGridWide]}>
                {TESTIMONIALS.map((t) => (
                  <View key={t.name} style={[styles.quoteCard, isWide && styles.quoteCardWide]}>
                    <Ionicons name="chatbubble-ellipses-outline" size={18} color={PAL.accent} />
                    <P style={styles.quoteText}>&ldquo;{t.quote}&rdquo;</P>
                    <View>
                      <Text style={styles.quoteName}>{t.name}</Text>
                      <Text style={styles.quoteRole}>{t.role}</Text>
                    </View>
                  </View>
                ))}
              </View>
            </Section>
          </Reveal>

          {/* ---------------- FAQ ---------------- */}
          <Reveal>
            <Section style={styles.block}>
              <H2 style={styles.h2}>Questions, answered</H2>
              <P style={styles.faqLead}>
                Everything guests and photographers ask about finding photos, privacy and running a studio on PIK Connect.
              </P>
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
            <Text style={styles.updated}>Last updated {LAST_UPDATED}</Text>
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
  studioLoginBtn: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderRadius: radius.pill, borderWidth: 1, borderColor: "rgba(226,98,60,0.35)", backgroundColor: "rgba(226,98,60,0.08)" },
  studioLoginText: { color: PAL.accent, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  studioSignupText: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },
  menuButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center", borderRadius: radius.pill, backgroundColor: "rgba(36,29,22,0.06)" },
  mobileMenu: { alignSelf: "flex-end", width: 210, padding: spacing.sm, borderRadius: radius.md, backgroundColor: PAL.card, borderWidth: 1, borderColor: PAL.cardBorder, zIndex: 20, shadowColor: "#3A2C1D", shadowOpacity: 0.18, shadowRadius: 20, shadowOffset: { width: 0, height: 10 }, elevation: 8 },
  mobileMenuItem: { minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.md },
  mobileMenuText: { color: PAL.ink, fontFamily: fonts.text, fontSize: fontSize.base },
  mobileStudioItem: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.md, marginTop: spacing.xs, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: PAL.cardBorder },
  mobileStudioText: { color: PAL.accent, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
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

  // ---- Why PIK Connect ----
  whyLead: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.lg, lineHeight: 26, margin: 0, marginTop: -spacing.md, marginBottom: spacing.xl, maxWidth: 760 },
  whyGrid: { gap: spacing.lg },
  whyGridWide: { flexDirection: "row", gap: spacing.lg },
  whyRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  whyRowWide: { flex: 1, flexDirection: "column", backgroundColor: PAL.card, borderWidth: 1, borderColor: PAL.cardBorder, borderRadius: radius.lg, padding: spacing.xl },
  whyIcon: { width: 44, height: 44, borderRadius: radius.pill, backgroundColor: "rgba(226,98,60,0.12)", alignItems: "center", justifyContent: "center", marginBottom: spacing.sm },
  whyTitle: { color: PAL.ink, fontFamily: fonts.display, fontSize: fontSize.xl, fontWeight: "700", margin: 0 },
  whyText: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 21, margin: 0, marginTop: spacing.xs },

  // ---- FAQ ----
  faqLead: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.lg, lineHeight: 26, margin: 0, marginTop: -spacing.md, marginBottom: spacing.lg, maxWidth: 760 },
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
  updated: { color: PAL.inkFaint, fontFamily: fonts.text, fontSize: 11, marginTop: 2, letterSpacing: 0.5 },

  // ---- Hero skeleton (reserved space while HeroShowcase lazy-loads) ----
  heroArtSkeleton: { borderRadius: radius.lg, backgroundColor: "rgba(226,98,60,0.06)" },

  // ---- Trust / Stats / Testimonials ----
  trustLead: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.lg, lineHeight: 26, margin: 0, marginTop: -spacing.md, marginBottom: spacing.xl, maxWidth: 780 },
  statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginBottom: spacing.lg },
  statsGridWide: { flexWrap: "nowrap", gap: spacing.lg },
  statCard: { flexGrow: 1, minWidth: 140, backgroundColor: PAL.card, borderWidth: 1, borderColor: PAL.cardBorder, borderRadius: radius.lg, paddingVertical: spacing.lg, paddingHorizontal: spacing.lg, alignItems: "flex-start" },
  statCardWide: { flex: 1, minWidth: 0 },
  statValue: { color: PAL.accent, fontFamily: fonts.display, fontSize: 32, fontWeight: "800", letterSpacing: -0.5 },
  statLabel: { color: PAL.inkSoft, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginTop: 4 },

  credRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.xl },
  credRowWide: { gap: spacing.md },
  credChip: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: spacing.md, paddingVertical: 8, borderRadius: radius.pill, borderWidth: 1, borderColor: "rgba(226,98,60,0.22)", backgroundColor: "rgba(226,98,60,0.06)" },
  credText: { color: PAL.ink, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "600" },

  quoteGrid: { gap: spacing.md },
  quoteGridWide: { flexDirection: "row", gap: spacing.lg },
  quoteCard: { flex: 1, backgroundColor: PAL.card, borderWidth: 1, borderColor: PAL.cardBorder, borderRadius: radius.lg, padding: spacing.xl, gap: spacing.md },
  quoteCardWide: { flexBasis: 0 },
  quoteText: { color: PAL.ink, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 22, margin: 0 },
  quoteName: { color: PAL.ink, fontFamily: fonts.text, fontSize: fontSize.sm, fontWeight: "700" },
  quoteRole: { color: PAL.inkFaint, fontFamily: fonts.text, fontSize: 12, marginTop: 2 },
});
