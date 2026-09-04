import { useEffect, useRef, useState } from "react";
import { Animated, Easing, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { colors, fonts, radius, spacing } from "@/src/theme";

const CANVAS = 560;
const RETICLE = { x: 420, y: 130, size: 96 };
const CENTER = { x: 232, y: 318, size: 232 };

type Tile = { x: number; y: number; s: number; depth: number; icon: string; tint: [string, string] };

const TILES: Tile[] = [
  { x: 22, y: 44, s: 84, depth: 1.7, icon: "person", tint: ["#3a2b21", "#221913"] },
  { x: 302, y: 14, s: 64, depth: 1.2, icon: "people", tint: ["#33241d", "#1d1511"] },
  { x: 462, y: 236, s: 88, depth: 1.5, icon: "person", tint: ["#3d2c1f", "#241a12"] },
  { x: 436, y: 430, s: 72, depth: 1.9, icon: "people", tint: ["#35261c", "#1f1610"] },
  { x: 44, y: 428, s: 78, depth: 1.4, icon: "person", tint: ["#38281e", "#211812"] },
];

function tileCenter(t: Tile) {
  return { x: t.x + t.s / 2, y: t.y + t.s / 2 };
}

function lineBetween(from: { x: number; y: number }, to: { x: number; y: number }) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.hypot(dx, dy);
  const angle = Math.atan2(dy, dx);
  return {
    left: (from.x + to.x) / 2 - len / 2,
    top: (from.y + to.y) / 2,
    width: len,
    transform: [{ rotate: `${angle}rad` }],
  };
}

const RETICLE_CENTER = { x: RETICLE.x + RETICLE.size / 2, y: RETICLE.y + RETICLE.size / 2 };
const CENTER_POINT = { x: CENTER.x + CENTER.size / 2, y: CENTER.y + CENTER.size / 2 };

const LINES = [
  ...TILES.map((t) => lineBetween(tileCenter(t), RETICLE_CENTER)),
  lineBetween(CENTER_POINT, RETICLE_CENTER),
];

type Props = {
  /** Rendered width/height in px. Internal 560px canvas is scaled to fit. */
  size: number;
  /** Enable mouse parallax (desktop web). */
  interactive?: boolean;
};

export default function HeroConstellation({ size, interactive = false }: Props) {
  const scale = size / CANVAS;
  const pointer = useRef(new Animated.ValueXY({ x: 0, y: 0 })).current;
  const ambient = useRef(new Animated.Value(0)).current;
  const scanProgress = useRef(new Animated.Value(0)).current;
  const reticlePulse = useRef(new Animated.Value(0)).current;
  const [matched, setMatched] = useState(false);

  useEffect(() => {
    const float = Animated.loop(
      Animated.sequence([
        Animated.timing(ambient, { toValue: 1, duration: 4200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(ambient, { toValue: 0, duration: 4200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ])
    );
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(reticlePulse, { toValue: 1, duration: 1400, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
        Animated.timing(reticlePulse, { toValue: 0, duration: 1400, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      ])
    );
    float.start();
    pulse.start();
    return () => {
      float.stop();
      pulse.stop();
    };
  }, [ambient, reticlePulse]);

  const runScan = () => {
    setMatched(false);
    scanProgress.setValue(0);
    Animated.timing(scanProgress, { toValue: 1, duration: 1400, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start(({ finished }) => {
      if (finished) setMatched(true);
    });
  };

  useEffect(() => {
    const t = setTimeout(runScan, 900);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleMove = (e: any) => {
    const ne = e?.nativeEvent ?? {};
    const px = ne.offsetX ?? ne.locationX;
    const py = ne.offsetY ?? ne.locationY;
    if (typeof px !== "number" || typeof py !== "number") return;
    pointer.setValue({ x: Math.max(-1, Math.min(1, (px / size) * 2 - 1)), y: Math.max(-1, Math.min(1, (py / size) * 2 - 1)) });
  };

  const resetPointer = () => {
    Animated.spring(pointer, { toValue: { x: 0, y: 0 }, useNativeDriver: true, speed: 12, bounciness: 6 }).start();
  };

  const webHandlers = interactive && Platform.OS === "web" ? ({ onMouseMove: handleMove, onMouseLeave: resetPointer } as any) : {};

  const parallax = (depth: number) => [
    { translateX: Animated.multiply(pointer.x, depth * 9) },
    { translateY: Animated.add(Animated.multiply(pointer.y, depth * 7), ambient.interpolate({ inputRange: [0, 1], outputRange: [0, -5 * depth] })) },
  ];

  return (
    <Animated.View {...webHandlers} style={{ width: size, height: size }}>
      <View style={[styles.canvas, { left: (size - CANVAS) / 2, top: (size - CANVAS) / 2, transform: [{ scale }] }]} pointerEvents="box-none">
        {/* connecting lines */}
        {LINES.map((l, i) => (
          <View key={`line-${i}`} pointerEvents="none" style={[styles.line, l]} />
        ))}

        {/* scattered gallery tiles (abstract silhouettes, no real faces) */}
        {TILES.map((t, i) => (
          <Animated.View key={`tile-${i}`} pointerEvents="none" style={[styles.tile, { left: t.x, top: t.y, width: t.s, height: t.s, transform: parallax(t.depth) }]}>
            <LinearGradient colors={t.tint} style={StyleSheet.absoluteFill} />
            <Ionicons name={t.icon as any} size={t.s * 0.44} color="rgba(255,232,214,0.30)" />
            <View style={styles.tileNode} />
          </Animated.View>
        ))}

        {/* central "selfie" circle */}
        <Animated.View style={[styles.centerWrap, { left: CENTER.x, top: CENTER.y, width: CENTER.size, height: CENTER.size, transform: parallax(0.6) }]}>
          <Pressable
            testID="hero-scan-preview"
            accessibilityRole="button"
            accessibilityLabel="Preview AI face scan"
            onPress={runScan}
            onHoverIn={Platform.OS === "web" ? runScan : undefined}
            style={styles.centerCircle}
          >
            <LinearGradient colors={["#4a3323", "#241811"]} style={StyleSheet.absoluteFill} />
            <Ionicons name="person" size={CENTER.size * 0.56} color="rgba(255,236,220,0.22)" style={styles.centerSilhouette} />
            {/* face mesh dots */}
            <View style={[styles.meshDot, { top: "34%", left: "40%" }]} />
            <View style={[styles.meshDot, { top: "34%", left: "58%" }]} />
            <View style={[styles.meshDot, { top: "48%", left: "49%" }]} />
            <View style={[styles.meshDot, { top: "58%", left: "42%" }]} />
            <View style={[styles.meshDot, { top: "58%", left: "56%" }]} />
            <Animated.View
              pointerEvents="none"
              style={[
                styles.scanLine,
                {
                  opacity: scanProgress.interpolate({ inputRange: [0, 0.05, 0.95, 1], outputRange: [0, 1, 1, 0] }),
                  transform: [{ translateY: scanProgress.interpolate({ inputRange: [0, 1], outputRange: [-CENTER.size * 0.42, CENTER.size * 0.42] }) }],
                },
              ]}
            />
          </Pressable>
          <View pointerEvents="none" style={styles.centerRing} />
        </Animated.View>

        {/* scanning reticle */}
        <Animated.View
          pointerEvents="none"
          style={[
            styles.reticle,
            { left: RETICLE.x, top: RETICLE.y, width: RETICLE.size, height: RETICLE.size },
            { opacity: reticlePulse.interpolate({ inputRange: [0, 1], outputRange: [0.6, 1] }), transform: parallax(1.1) },
          ]}
        >
          <View style={[styles.corner, styles.cornerTL]} />
          <View style={[styles.corner, styles.cornerTR]} />
          <View style={[styles.corner, styles.cornerBL]} />
          <View style={[styles.corner, styles.cornerBR]} />
          <Ionicons name="scan-outline" size={30} color={colors.brand} />
        </Animated.View>

        {/* match result badge */}
        <Animated.View
          pointerEvents="none"
          style={[styles.matchBadge, { opacity: matched ? 1 : scanProgress.interpolate({ inputRange: [0, 0.7, 1], outputRange: [0, 0.15, 1] }) }]}
        >
          <View style={styles.matchPulse} />
          <View>
            <Text style={styles.matchEyebrow}>FACE MATCHED</Text>
            <Text style={styles.matchTitle}>24 photos of you found</Text>
          </View>
          <Ionicons name="images-outline" size={16} color={colors.brand} />
        </Animated.View>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  canvas: { position: "absolute", width: CANVAS, height: CANVAS },
  line: { position: "absolute", height: 1, backgroundColor: "rgba(244,123,74,0.28)" },
  tile: {
    position: "absolute",
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: "rgba(255,235,220,0.12)",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  tileNode: { position: "absolute", top: 6, right: 6, width: 6, height: 6, borderRadius: radius.pill, backgroundColor: colors.brand, opacity: 0.85 },
  centerWrap: { position: "absolute", alignItems: "center", justifyContent: "center" },
  centerCircle: {
    width: "100%",
    height: "100%",
    borderRadius: radius.pill,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  centerSilhouette: { marginTop: 24 },
  centerRing: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    borderRadius: radius.pill,
    borderWidth: 2,
    borderColor: "rgba(244,123,74,0.75)",
    shadowColor: colors.brand,
    shadowOpacity: 0.4,
    shadowRadius: 30,
  },
  meshDot: { position: "absolute", width: 4, height: 4, borderRadius: radius.pill, backgroundColor: "rgba(244,123,74,0.8)" },
  scanLine: {
    position: "absolute",
    left: 14,
    right: 14,
    top: "50%",
    height: 2,
    backgroundColor: colors.brand,
    shadowColor: colors.brand,
    shadowOpacity: 0.9,
    shadowRadius: 10,
  },
  reticle: { position: "absolute", alignItems: "center", justifyContent: "center" },
  corner: { position: "absolute", width: 18, height: 18, borderColor: colors.brand },
  cornerTL: { top: 0, left: 0, borderTopWidth: 2, borderLeftWidth: 2 },
  cornerTR: { top: 0, right: 0, borderTopWidth: 2, borderRightWidth: 2 },
  cornerBL: { bottom: 0, left: 0, borderBottomWidth: 2, borderLeftWidth: 2 },
  cornerBR: { bottom: 0, right: 0, borderBottomWidth: 2, borderRightWidth: 2 },
  matchBadge: {
    position: "absolute",
    left: 6,
    top: 210,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: "rgba(14,12,10,0.9)",
    borderWidth: 1,
    borderColor: "rgba(244,123,74,0.4)",
  },
  matchPulse: { width: 8, height: 8, borderRadius: radius.pill, backgroundColor: colors.brand },
  matchEyebrow: { color: colors.brand, fontFamily: fonts.text, fontSize: 9, letterSpacing: 1.4, fontWeight: "700" },
  matchTitle: { color: colors.onSurface, fontFamily: fonts.text, fontSize: 13, marginTop: 2 },
});
