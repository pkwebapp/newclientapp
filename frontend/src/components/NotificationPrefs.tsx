import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, StyleSheet, Switch, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { api, ApiError } from "@/src/api/client";
import { useToast } from "@/src/components/ui";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

type NType = { key: string; label: string; desc: string; group: string; audience: string };

/**
 * Notification preferences panel.
 * Renders a Switch per notification type, grouped by category.
 * All types are ON by default; toggling OFF persists the key to the backend.
 */
export function NotificationPrefs({ testID }: { testID?: string }) {
  const toast = useToast();
  const [types, setTypes] = useState<NType[]>([]);
  const [disabled, setDisabled] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const res: any = await api.get("/notifications/prefs");
      setTypes(res.types || []);
      setDisabled(new Set<string>(res.disabled || []));
    } catch (e: any) {
      toast.show(e instanceof ApiError ? e.message : "Could not load preferences", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const groups = useMemo(() => {
    const map = new Map<string, NType[]>();
    for (const t of types) {
      if (!map.has(t.group)) map.set(t.group, []);
      map.get(t.group)!.push(t);
    }
    return Array.from(map.entries());
  }, [types]);

  const toggle = async (key: string, next: boolean) => {
    const nextSet = new Set(disabled);
    // `next` = the switch's new "enabled" state. If enabled → remove from disabled.
    if (next) nextSet.delete(key);
    else nextSet.add(key);
    setDisabled(nextSet);
    setSaving(true);
    try {
      await api.patch("/notifications/prefs", { disabled: Array.from(nextSet) });
    } catch (e: any) {
      // Roll back on failure so UI stays truthful.
      setDisabled(disabled);
      toast.show(e instanceof ApiError ? e.message : "Save failed", "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }

  return (
    <View testID={testID}>
      <View style={styles.info}>
        <Ionicons name="notifications-outline" size={16} color={colors.brand} />
        <Text style={styles.infoText}>
          All notifications are on by default. Turn off anything you don&apos;t want to hear about.
          {saving ? " · saving…" : ""}
        </Text>
      </View>

      {groups.map(([group, items]) => (
        <View key={group} style={styles.group}>
          <Text style={styles.groupTitle}>{group}</Text>
          {items.map((t) => {
            const enabled = !disabled.has(t.key);
            return (
              <View key={t.key} style={styles.row} testID={`pref-${t.key}`}>
                <View style={{ flex: 1, paddingRight: spacing.md }}>
                  <Text style={styles.rowLabel}>{t.label}</Text>
                  <Text style={styles.rowDesc}>{t.desc}</Text>
                </View>
                <Switch
                  testID={`pref-switch-${t.key}`}
                  value={enabled}
                  onValueChange={(v) => toggle(t.key, v)}
                  trackColor={{ true: colors.brand, false: colors.borderStrong }}
                  thumbColor="#FFFFFF"
                />
              </View>
            );
          })}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  center: { padding: spacing.xl, alignItems: "center" },
  info: {
    flexDirection: "row",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.brandTertiary,
  },
  infoText: { flex: 1, color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18 },

  group: { marginBottom: spacing.xl },
  groupTitle: {
    color: colors.muted,
    fontFamily: fonts.text,
    fontSize: fontSize.sm,
    fontWeight: "800",
    letterSpacing: 1,
    marginBottom: spacing.sm,
    textTransform: "uppercase",
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    minHeight: 60,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  rowLabel: { color: colors.onSurface, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "700" },
  rowDesc: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, lineHeight: 18, marginTop: 3 },
});
