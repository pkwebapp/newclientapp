import { useState } from "react";
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { WebView } from "react-native-webview";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

/**
 * Public Album Flipbook viewer route: /a/:token (mirrors the gallery share flow).
 *
 * The premium 3D flipbook is a self-contained WebGL/Three.js page served by the
 * backend. We embed it here so the SAME experience renders on web (iframe) and
 * natively inside Expo Go (WebView) — no watered-down RN reimplementation.
 */
export default function AlbumViewerRoute() {
  const { token, k } = useLocalSearchParams<{ token: string; k?: string }>();
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  const base = process.env.EXPO_PUBLIC_BACKEND_URL;
  const src = `${base}/api/albums/public/${token}/view${k ? `?k=${k}` : ""}`;

  return (
    <View style={styles.container} testID="album-viewer-route">
      {Platform.OS === "web" ? (
        // react-native-web has no WebView DOM node; use a native iframe.
        // @ts-ignore - iframe is valid on web only
        <iframe
          src={src}
          onLoad={() => setLoading(false)}
          style={{ border: "none", width: "100%", height: "100%", backgroundColor: "#0b0b0d" }}
          allow="fullscreen; accelerometer; gyroscope"
          allowFullScreen
        />
      ) : (
        <WebView
          source={{ uri: src }}
          onLoadEnd={() => setLoading(false)}
          originWhitelist={["*"]}
          javaScriptEnabled
          domStorageEnabled
          allowsInlineMediaPlayback
          mediaPlaybackRequiresUserAction={false}
          allowsFullscreenVideo
          style={styles.web}
          containerStyle={styles.web}
        />
      )}

      {loading ? (
        <View style={styles.loader} pointerEvents="none">
          <ActivityIndicator color="#c8a86a" />
          <Text style={styles.loaderText}>Preparing your album…</Text>
        </View>
      ) : null}

      {router.canGoBack() ? (
        <Pressable style={styles.back} onPress={() => router.back()} hitSlop={12} testID="album-viewer-back">
          <Ionicons name="chevron-back" size={22} color="#e9e4d8" />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0b0b0d" },
  web: { flex: 1, backgroundColor: "#0b0b0d" },
  loader: { ...StyleSheet.absoluteFillObject, alignItems: "center", justifyContent: "center", gap: 12, backgroundColor: "#0b0b0d" },
  loaderText: { color: "rgba(233,228,216,0.6)", fontSize: 13, letterSpacing: 0.4 },
  back: {
    position: "absolute", top: 44, left: 16, width: 40, height: 40, borderRadius: 20,
    alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(20,20,24,0.55)", borderWidth: 1, borderColor: "rgba(255,255,255,0.14)",
  },
});
