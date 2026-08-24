import { Redirect, Stack } from "expo-router";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { useAuth } from "@/src/context/AuthContext";
import { SuperAdminShell } from "@/src/components/SuperAdminShell";

export default function SuperAdminLayout() {
  const { user, loading } = useAuth();
  if (loading) return <View style={styles.loading}><ActivityIndicator /></View>;
  if (!user) return <Redirect href="/superadmin-login" />;
  if (user.role !== "superadmin") return <Redirect href="/" />;
  return <SuperAdminShell><Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: "#F7F8FA" } }} /></SuperAdminShell>;
}

const styles = StyleSheet.create({ loading: { flex: 1, alignItems: "center", justifyContent: "center" } });
