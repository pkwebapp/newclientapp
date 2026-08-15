import { Redirect } from "expo-router";
import { ActivityIndicator, StyleSheet, View, Text } from "react-native";
import { useAuth } from "@/src/context/AuthContext";
import { colors, fonts, fontSize } from "@/src/theme";

export default function Index() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <View style={styles.container} testID="boot-loading">
        <Text style={styles.brand}>Lumiere</Text>
        <ActivityIndicator color={colors.brand} style={{ marginTop: 16 }} />
      </View>
    );
  }
  if (!user) return <Redirect href="/login" />;
  if (user.role === "admin") return <Redirect href="/admin" />;
  return <Redirect href="/client" />;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  brand: { color: colors.brand, fontFamily: fonts.display, fontSize: fontSize.hero, letterSpacing: 2 },
});
