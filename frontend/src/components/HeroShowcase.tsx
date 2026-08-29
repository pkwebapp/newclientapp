import { useEffect, useRef, useState } from "react";
import { Animated, Easing, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";

import { HERO_IMAGES, HERO_PALETTE as P } from "@/src/config/hero";
import { fonts, radius, spacing } from "@/src/theme";

const CANVAS_W = 660;
const CANVAS_H = 560;
const PHONE = { x: 30, y: 10, w: 260, h: 540 };

type Tile = { key: string; x: number; y: number; s: number; depth: number; src: string };

const TILES: Tile[] = [
  { key: "a", x: 440, y: 30, s: 150, depth: 1.6, src: HERO_IMAGES.event1 },
  { key: "b", x: 402, y: 238, s: 185, depth: 1.0, src: HERO_IMAGES.event2 },
  { key: "c", x: 468, y: 434, s: 116, depth: 1.9, src: HERO_IMAGES.event3 },
];

const ANCHOR = { x: PHONE.x + PHONE.w - 8, y: PHONE.y + PHONE.h / 2 };

function lineBetween(from: { x: number; y: number }, to: { x: number; y: number }) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.hypot(dx, dy);
  const angle = Math.atan2(dy, dx);
  return { left: (from.x + to.x) / 2 - len / 2, top: (from.y + to.y) / 2, width: len, transform: [{ rotate: `${angle}rad` }] };
}

const LINES = TILES.map((t) => lineBetween(ANCHOR, { x: t.x + 4, y: t.y + t.s / 2 }));

type Props = {
  /** Rendered width in px. */
  width: number;
  /** Enable mouse parallax (desktop web). */
  interactive?: boolean;
  /** Compact, simple composition for mobile. */
  compact?: boolean;
};

export default function HeroShowcase({ width, interactive = false, compact = false }: Props) {
  const pointer = useRef(new Animated.ValueXY({ x: 0, y: 0 })).current;
  const ambient = useRef(new Animated.Value(0)).current;
  const scanProgress = useRef(new Animated.Value(0)).current;
  const badgeIn = useRef(new Animated.Value(0)).current;
  const [matched, setMatched] = useState(false);

  useEffect(() => {
    const float = Animated.loop(
      Animated.sequence([
        Animated.timing(ambient, { toValue: 1, duration: 4600, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(ambient, { toValue: 0, duration: 4600, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ])
    );
    float.start();
    return () => float.stop();
  }, [ambient]);

  const runScan = () => {
    setMatched(false);
    badgeIn.setValue(0);
    scanProgress.setValue(0);
    Animated.timing(scanProgress, { toValue: 1, duration: 1500, easing: Easing.inOut(Easing.cubic), useNativeDriver: true }).start(({ finished }) => {
      if (finished) {
        setMatched(true);
        Animated.spring(badgeIn, { toValue: 1, useNativeDriver: true, speed: 14, bounciness: 9 }).start();
      }
    });
  };

  useEffect(() => {
    const t = setTimeout(runScan, 800);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleMove = (e: any) => {
    const ne = e?.nativeEvent ?? {};
    const px = ne.offsetX ?? ne.locationX;
    const py = ne.offsetY ?? ne.locationY;
    if (typeof px !== "number" || typeof py !== "number") return;
    pointer.setValue({ x: Math.max(-1, Math.min(1, (px / width) * 2 - 1)), y: Math.max(-1, Math.min(1, (py / width) * 2 - 1)) });
  };
  const resetPointer = () => {
    Animated.spring(pointer, { toValue: { x: 0, y: 0 }, useNativeDriver: true, speed: 12, bounciness: 6 }).start();
  };
  const webHandlers = interactive && Platform.OS === "web" ? ({ onMouseMove: handleMove, onMouseLeave: resetPointer } as any) : {};

  const parallax = (depth: number) => [
    { translateX: Animated.multiply(pointer.x, depth * 10) },
    { translateY: Animated.add(Animated.multiply(pointer.y, depth * 8), ambient.interpolate({ inputRange: [0, 1], outputRange: [0, -5 * depth] })) },
  ];

  const scanLine = (phoneH: number) => ({
    opacity: scanProgress.interpolate({ inputRange: [0, 0.05, 0.92, 1], outputRange: [0, 1, 1, 0] }),
    transform: [{ translateY: scanProgress.interpolate({ inputRange: [0, 1], outputRange: [phoneH * 0.08, phoneH * 0.86] }) }],
  });

  const matchBadge = (extraStyle?: object) => (
    <Animated.View
      pointerEvents="none"
      style={[
        styles.matchBadge,
        extraStyle,
        { opacity: badgeIn, transform: [{ translateY: badgeIn.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) }] },
      ]}
    >
      <View style={styles.matchPulse} />
      <View>
        <Text style={styles.matchEyebrow}>MATCHED!</Text>
        <Text style={styles.matchTitle}>24 photos of you found</Text>
      </View>
      <Ionicons name="images-outline" size={15} color={P.accent} />
    </Animated.View>
  );

  const phoneBody = (w: number, h: number, showChip = true) => (
    <Pressable
      testID="hero-scan-preview"
      accessibilityRole="button"
      accessibilityLabel="Preview AI face scan"
      onPress={runScan}
      onHoverIn={Platform.OS === "web" ? runScan : undefined}
      style={[styles.phone, { width: w, height: h }]}
    >
      <View style={styles.phoneScreen}>
        <Image source={{ uri: HERO_IMAGES.selfie }} accessibilityLabel="Selfie used for AI face search in the PIK Connect event photo gallery" style={StyleSheet.absoluteFill} contentFit="cover" transition={300} />
        {/* face reticle */}
        <View style={[styles.reticle, { width: w * 0.44, height: w * 0.44, top: h * 0.23, left: w * 0.3 }]} pointerEvents="none">
          <View style={[styles.corner, styles.cornerTL]} />
          <View style={[styles.corner, styles.cornerTR]} />
          <View style={[styles.corner, styles.cornerBL]} />
          <View style={[styles.corner, styles.cornerBR]} />
        </View>
        <Animated.View pointerEvents="none" style={[styles.scanLine, scanLine(h)]} />
        {matched && showChip ? (
          <View style={styles.scanChip} pointerEvents="none">
            <Ionicons name="checkmark-circle" size={13} color="#9CE0AE" />
            <Text style={styles.scanChipText}>Face verified</Text>
          </View>
        ) : null}
      </View>
      <View style={styles.notch} pointerEvents="none" />
    </Pressable>
  );

  // ---------------- Compact (mobile) ----------------
  if (compact) {
    const phoneW = Math.min(200, width * 0.55);
    const phoneH = phoneW * 1.9;
    const tileS = Math.min(104, width * 0.3);
    return (
      <View style={[styles.compactWrap, { width, height: phoneH + 36 }]}>
        <Animated.View style={[styles.compactTile, { width: tileS, height: tileS, left: 0, top: 18, transform: [{ rotate: "-5deg" }] }]}>
          <Image source={{ uri: HERO_IMAGES.event1 }} accessibilityLabel="Event photo matched to a guest by PIK Connect AI face search" style={StyleSheet.absoluteFill} contentFit="cover" transition={300} />
        </Animated.View>
        <Animated.View style={[styles.compactTile, { width: tileS, height: tileS, right: 0, bottom: 46, transform: [{ rotate: "5deg" }] }]}>
          <Image source={{ uri: HERO_IMAGES.event3 }} accessibilityLabel="Wedding event photo found in a private PIK Connect gallery" style={StyleSheet.absoluteFill} contentFit="cover" transition={300} />
        </Animated.View>
        {phoneBody(phoneW, phoneH, false)}
        {matchBadge({ bottom: -6, alignSelf: "center" })}
      </View>
    );
  }

  // ---------------- Desktop ----------------
  const scale = width / CANVAS_W;
  const renderedH = CANVAS_H * scale;
  return (
    <Animated.View {...webHandlers} style={{ width, height: renderedH }}>
      <View style={[styles.canvas, { left: (width - CANVAS_W) / 2, top: (renderedH - CANVAS_H) / 2, transform: [{ scale }] }]} pointerEvents="box-none">
        {LINES.map((l, i) => (
          <View key={`line-${i}`} pointerEvents="none" style={[styles.line, l]} />
        ))}
        {LINES.map((l, i) => (
          <View
            key={`node-${i}`}
            pointerEvents="none"
            style={[styles.lineNode, { left: TILES[i].x - 1, top: TILES[i].y + TILES[i].s / 2 - 3 }]}
          />
        ))}

        <Animated.View style={{ position: "absolute", left: PHONE.x, top: PHONE.y, transform: parallax(0.5) }}>
          {phoneBody(PHONE.w, PHONE.h)}
        </Animated.View>

        {TILES.map((t) => (
          <Animated.View key={t.key} pointerEvents="none" style={[styles.tile, { left: t.x, top: t.y, width: t.s, height: t.s, transform: parallax(t.depth) }]}>
            <Image source={{ uri: t.src }} accessibilityLabel="Event photo discovered with PIK Connect AI face search" style={StyleSheet.absoluteFill} contentFit="cover" transition={300} />
          </Animated.View>
        ))}

        {matchBadge({ left: 318, top: 196 })}
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  canvas: { position: "absolute", width: CANVAS_W, height: CANVAS_H },

  // connection lines
  line: { position: "absolute", height: 1.5, backgroundColor: P.line, borderRadius: 1 },
  lineNode: { position: "absolute", width: 7, height: 7, borderRadius: radius.pill, backgroundColor: P.accent },

  // phone
  phone: {
    borderRadius: 42,
    backgroundColor: "#211A13",
    padding: 9,
    shadowColor: "#3A2C1D",
    shadowOpacity: 0.35,
    shadowRadius: 34,
    shadowOffset: { width: 0, height: 22 },
    elevation: 12,
  },
  phoneScreen: { flex: 1, borderRadius: 33, overflow: "hidden", backgroundColor: "#B8AB9C" },
  notch: { position: "absolute", top: 20, alignSelf: "center", width: 74, height: 20, borderRadius: radius.pill, backgroundColor: "#211A13" },
  reticle: { position: "absolute" },
  corner: { position: "absolute", width: 20, height: 20, borderColor: P.accent },
  cornerTL: { top: 0, left: 0, borderTopWidth: 2.5, borderLeftWidth: 2.5, borderTopLeftRadius: 6 },
  cornerTR: { top: 0, right: 0, borderTopWidth: 2.5, borderRightWidth: 2.5, borderTopRightRadius: 6 },
  cornerBL: { bottom: 0, left: 0, borderBottomWidth: 2.5, borderLeftWidth: 2.5, borderBottomLeftRadius: 6 },
  cornerBR: { bottom: 0, right: 0, borderBottomWidth: 2.5, borderRightWidth: 2.5, borderBottomRightRadius: 6 },
  scanLine: {
    position: "absolute",
    left: 12,
    right: 12,
    top: 0,
    height: 2,
    backgroundColor: P.accent,
    shadowColor: P.accent,
    shadowOpacity: 0.9,
    shadowRadius: 10,
  },
  scanChip: {
    position: "absolute",
    bottom: 14,
    alignSelf: "center",
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacing.md,
    paddingVertical: 5,
    borderRadius: radius.pill,
    backgroundColor: "rgba(20,16,12,0.78)",
  },
  scanChipText: { color: "#F5F1EA", fontFamily: fonts.text, fontSize: 11, fontWeight: "600" },

  // photo tiles
  tile: {
    position: "absolute",
    borderRadius: radius.lg,
    borderWidth: 4,
    borderColor: P.frame,
    overflow: "hidden",
    backgroundColor: P.card,
    shadowColor: "#3A2C1D",
    shadowOpacity: 0.25,
    shadowRadius: 26,
    shadowOffset: { width: 0, height: 14 },
    elevation: 8,
  },
  compactWrap: { alignItems: "center", justifyContent: "center", alignSelf: "center" },
  compactTile: {
    position: "absolute",
    borderRadius: radius.lg,
    borderWidth: 4,
    borderColor: P.frame,
    overflow: "hidden",
    backgroundColor: P.card,
    shadowColor: "#3A2C1D",
    shadowOpacity: 0.22,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 10 },
    elevation: 6,
  },

  // matched badge
  matchBadge: {
    position: "absolute",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: P.chip,
    shadowColor: "#241D16",
    shadowOpacity: 0.3,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 10 },
    elevation: 8,
  },
  matchPulse: { width: 8, height: 8, borderRadius: radius.pill, backgroundColor: P.accent },
  matchEyebrow: { color: P.accent, fontFamily: fonts.text, fontSize: 9, letterSpacing: 1.4, fontWeight: "700" },
  matchTitle: { color: P.onChip, fontFamily: fonts.text, fontSize: 13, marginTop: 2 },
});
