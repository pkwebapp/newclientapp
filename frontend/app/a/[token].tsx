import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Platform, StyleSheet, Text, View } from "react-native";
import { WebView } from "react-native-webview";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import * as ScreenOrientation from "expo-screen-orientation";

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

  const goBack = useCallback(() => {
    if (router.canGoBack()) router.back();
    else router.replace("/");
  }, [router]);

  // Native: full-screen landscape while the album is open; restore on exit.
  useFocusEffect(
    useCallback(() => {
      if (Platform.OS === "web") return;
      ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.LANDSCAPE).catch(() => {});
      return () => {
        ScreenOrientation.unlockAsync().catch(() => {});
      };
    }, [])
  );

  // Web: the embedded viewer posts {type:'album-close'} when Exit is tapped.
  useEffect(() => {
    if (Platform.OS !== "web") return;
    const onMsg = (e: MessageEvent) => {
      if (e?.data?.type === "album-close") goBack();
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, [goBack]);

  return (
    <View style={styles.container} testID="album-viewer-route">
      {Platform.OS === "web" ? (
        // react-native-web has no WebView DOM node; use a native iframe.
        // @ts-ignore - iframe is valid on web only
        <iframe
          src={src}
          onLoad={() => setLoading(false)}
          style={{ border: "none", width: "100%", height: "100%", backgroundColor: "#0b0b0d" }}
          allow="fullscreen; accelerometer; gyroscope; autoplay"
          allowFullScreen
        />
      ) : (
        <WebView
          source={{ uri: src }}
          onLoadEnd={() => setLoading(false)}
          onMessage={(e) => {
            if (e.nativeEvent.data === "album-close") goBack();
          }}
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
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0b0b0d" },
  web: { flex: 1, backgroundColor: "#0b0b0d" },
  loader: { ...StyleSheet.absoluteFillObject, alignItems: "center", justifyContent: "center", gap: 12, backgroundColor: "#0b0b0d" },
  loaderText: { color: "rgba(233,228,216,0.6)", fontSize: 13, letterSpacing: 0.4 },
});
