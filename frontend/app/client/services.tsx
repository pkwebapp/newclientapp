import { useRouter } from "expo-router";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { Button, GlassHeader } from "@/src/components/ui";
import { HeaderMenuButton } from "@/src/components/MobileShell";
import { goBackOr } from "@/src/navigation/back";
import { lightColors as colors, fonts, fontSize, radius, spacing } from "@/src/theme";

type Service = {
  title: string;
  detail: string;
  icon: keyof typeof Ionicons.glyphMap;
};

const SERVICES: Service[] = [
  { title: "Wedding Photography & Videography", detail: "Natural photographs and cinematic films for intimate ceremonies, celebrations and destination weddings.", icon: "heart-outline" },
  { title: "Event Photography & Videography", detail: "Professional coverage for conferences, launches, award nights and private events.", icon: "calendar-outline" },
  { title: "Portraits & Headshots", detail: "Modern portraits and polished headshots for professionals, founders, artists and teams.", icon: "person-outline" },
  { title: "Editorial & Portfolio", detail: "Creative portfolio images for models, creators, designers and personal brands.", icon: "sparkles-outline" },
  { title: "Live Streaming", detail: "Multi-camera live coverage for weddings, conferences and events with private viewing links.", icon: "videocam-outline" },
  { title: "Family & Kids", detail: "Warm family, maternity, newborn and kids photography for meaningful milestones.", icon: "people-outline" },
  { title: "Fashion Shoots & Lookbooks", detail: "Campaign, lookbook and portfolio-ready visuals for designers, labels and models.", icon: "shirt-outline" },
  { title: "Boudoir Shoots", detail: "Private, tasteful sessions with comfortable direction and polished retouching.", icon: "moon-outline" },
  { title: "Brand & Content", detail: "Photo, video and short-form content for websites, social media and advertising.", icon: "megaphone-outline" },
  { title: "Product & E-Commerce", detail: "Clean product images for online stores, catalogues, marketplaces and campaigns.", icon: "cube-outline" },
  { title: "Food Photography", detail: "Appetite-worthy images for restaurants, cafés, cloud kitchens and hospitality brands.", icon: "restaurant-outline" },
  { title: "Corporate & Industrial", detail: "Professional coverage for offices, businesses, facilities and industrial projects.", icon: "business-outline" },
  { title: "Real Estate & Architectural", detail: "Photo, video and drone coverage for homes, hotels, commercial spaces and properties.", icon: "home-outline" },
  { title: "Influencer & Celebrity Content", detail: "Lifestyle photography and social-first video for creators, public figures and talent teams.", icon: "camera-outline" },
  { title: "Podcast Production", detail: "Multi-camera podcast production with professional lighting, audio and editing.", icon: "mic-outline" },
  { title: "Photo & Video Editing", detail: "Professional retouching, colour work, reels, teasers and polished campaign delivery.", icon: "color-wand-outline" },
  { title: "Album Design & Printing", detail: "Premium handcrafted albums designed to preserve memories for generations.", icon: "book-outline" },
  { title: "Drone Photography & Videography", detail: "Cinematic aerial footage for weddings, events, real estate and commercial projects.", icon: "airplane-outline" },
  { title: "Design Services", detail: "Creative design for website design, print, digital marketing, branding and promotional materials.", icon: "brush-outline" },
];

export default function ClientServices() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const askAboutService = (serviceTitle?: string) => {
    const message = serviceTitle
      ? `Hi PK Photography, I’d like to enquire about ${serviceTitle}.`
      : "Hi PK Photography, I’d like to explore your services.";
    const url = `https://wa.me/918888766739?text=${encodeURIComponent(message)}`;
    Linking.openURL(url).catch(() => {});
  };

  return (
    <View style={styles.container} testID="client-services-screen">
      <GlassHeader
        title="Explore Services"
        subtitle="Simple ideas for your next shoot"
        onBack={() => goBackOr(router, "/client")}
        left={<HeaderMenuButton />}
        topInset={insets.top}
      />
      <ScrollView
        contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + spacing["3xl"] }]}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.intro}>
          <View style={styles.introIcon}>
            <Ionicons name="sparkles-outline" size={24} color={colors.brand} />
          </View>
          <Text style={styles.title}>What can we create for you?</Text>
          <Text style={styles.subtitle}>Photography, films and visual content across Mumbai, Goa and beyond.</Text>
        </View>

        <View style={styles.list}>
          {SERVICES.map((service, index) => (
            <Pressable key={service.title} testID={`service-card-${index + 1}`} style={styles.serviceCard} onPress={() => askAboutService(service.title)}>
              <View style={styles.serviceIcon}>
                <Ionicons name={service.icon} size={20} color={colors.brand} />
              </View>
              <View style={styles.serviceCopy}>
                <Text style={styles.serviceTitle}>{service.title}</Text>
                <Text style={styles.serviceDetail}>{service.detail}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </Pressable>
          ))}
        </View>

        <View style={styles.cta}>
          <Text style={styles.ctaTitle}>Have something specific in mind?</Text>
          <Text style={styles.ctaText}>Tell us what you are planning and we’ll suggest the right coverage.</Text>
          <Button testID="services-whatsapp-btn" title="Ask on WhatsApp" icon="logo-whatsapp" onPress={() => askAboutService()} />
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  content: { padding: spacing.lg },
  intro: { alignItems: "center", paddingVertical: spacing.lg, marginBottom: spacing.md },
  introIcon: { width: 52, height: 52, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", marginBottom: spacing.md },
  title: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize["2xl"], textAlign: "center" },
  subtitle: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 21, textAlign: "center", marginTop: spacing.sm, maxWidth: 520 },
  list: { gap: spacing.sm },
  serviceCard: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, minHeight: 84 },
  serviceIcon: { width: 42, height: 42, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  serviceCopy: { flex: 1 },
  serviceTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "600" },
  serviceDetail: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginTop: 4 },
  cta: { backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.brandTertiary, borderRadius: radius.lg, padding: spacing.xl, marginTop: spacing.xl },
  ctaTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.xl },
  ctaText: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.base, lineHeight: 20, marginTop: spacing.xs, marginBottom: spacing.lg },
});
