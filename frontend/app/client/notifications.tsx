import { useRouter } from "expo-router";
import { ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { GlassHeader } from "@/src/components/ui";
import { NotificationPrefs } from "@/src/components/NotificationPrefs";
import { lightColors as colors, spacing } from "@/src/theme";
import { goBackOr } from "@/src/navigation/back";

export default function ClientNotificationsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  return (
    <View style={styles.container} testID="client-notifications-screen">
      <GlassHeader title="Notifications" onBack={() => goBackOr(router, "/client")} topInset={insets.top} />
      <ScrollView
        contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing["2xl"] }]}
        keyboardShouldPersistTaps="handled"
      >
        <NotificationPrefs testID="client-notification-prefs" />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  body: { padding: spacing.xl },
});
