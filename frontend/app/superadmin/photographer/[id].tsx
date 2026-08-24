import { useCallback, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import { api } from "@/src/api/client";
import { Button } from "@/src/components/ui";
import { ProgressBar, StatusBadge, SuperAdminHeader, formatBytes } from "@/src/components/SuperAdminShell";
import { goBackOr } from "@/src/navigation/back";
import { colors, fonts, radius, spacing } from "@/src/theme";

export default function SuperadminPhotographerDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [row, setRow] = useState<any>(null);
  const [confirmUploads, setConfirmUploads] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => { setRow(await api.get(`/superadmin/photographers/${id}`)); }, [id]);
  useFocusEffect(useCallback(() => { load().catch(() => setRow(null)); }, [load]));

  const update = async (updates: any) => {
    setBusy(true);
    try { setRow(await api.patch(`/superadmin/photographers/${id}`, updates)); } finally { setBusy(false); }
  };

  const toggleUploads = async () => {
    setConfirmUploads(false);
    await update({ uploads_disabled: !row.uploads_disabled });
  };

  if (!row) return <View style={styles.loading}><ActivityIndicator color={colors.brand} /></View>;
  const storageGb = row.storage_bytes / (1024 ** 3);
  const usage = row.storage_limit_gb ? (storageGb / row.storage_limit_gb) * 100 : 0;

  return (
    <ScrollView testID="superadmin-photographer-detail" contentContainerStyle={styles.page}>
      <View style={styles.top}><Pressable testID="superadmin-detail-back" onPress={() => goBackOr(router, "/superadmin/photographers")} style={styles.back}><Text style={styles.backText}>‹ Back to photographers</Text></Pressable><SuperAdminHeader title={row.name} subtitle={row.email} /></View>
      <View style={styles.identity}><View style={styles.avatar}><Text style={styles.avatarText}>{row.name.charAt(0).toUpperCase()}</Text></View><View style={{ flex: 1 }}><View style={styles.identityTitle}><Text style={styles.identityName}>{row.name}</Text><StatusBadge status={row.uploads_disabled ? "Uploads disabled" : row.status} /></View><Text style={styles.identityEmail}>{row.email}</Text></View><Button title={row.uploads_disabled ? "Enable uploads" : "Disable uploads"} variant={row.uploads_disabled ? "primary" : "secondary"} icon={row.uploads_disabled ? "cloud-upload-outline" : "cloud-offline-outline"} onPress={() => row.uploads_disabled ? toggleUploads() : setConfirmUploads(true)} style={styles.actionButton} /></View>

      <View style={styles.stats}><MiniStat label="Galleries" value={row.galleries} /><MiniStat label="Images" value={row.images.toLocaleString("en-IN")} /><MiniStat label="Clients" value={row.clients} /><MiniStat label="Storage" value={formatBytes(row.storage_bytes)} /></View>
      <View style={styles.panel}><Text style={styles.panelTitle}>Membership</Text><View style={styles.membershipRow}><View><Text style={styles.plan}>{row.membership} plan</Text><Text style={styles.price}>₹{row.membership_key === "free" ? 0 : row.membership_key === "basic" ? 499 : row.membership_key === "business" ? "1,999" : "999"}/month</Text></View><StatusBadge status={row.status} /></View><View style={styles.divider} /><Text style={styles.hint}>Plan and renewal controls can be connected to billing in a future version.</Text></View>
      <View style={styles.panel}><Text style={styles.panelTitle}>Usage</Text><View style={styles.usageHeader}><Text style={styles.usageLabel}>Storage</Text><Text style={styles.usageValue}>{formatBytes(row.storage_bytes)} / {row.storage_limit_gb} GB</Text></View><ProgressBar value={usage} /><Text style={styles.hint}>{usage.toFixed(1)}% used · storage values are estimated until provider-level usage is connected.</Text><View style={styles.usageLine}><Text style={styles.usageLabel}>Galleries</Text><Text style={styles.usageValue}>{row.galleries}</Text></View><View style={styles.usageLine}><Text style={styles.usageLabel}>Images</Text><Text style={styles.usageValue}>{row.images.toLocaleString("en-IN")}</Text></View></View>
      <View style={styles.panel}><Text style={styles.panelTitle}>Account controls</Text><Control label="Account active" value={row.status !== "suspended"} onChange={() => update({ status: row.status === "suspended" ? "active" : "suspended" })} /><Control label="Client gallery access" value={row.status !== "suspended"} onChange={() => {}} disabled /><Control label="New gallery creation" value={row.status !== "suspended"} onChange={() => {}} disabled /><Control label="Uploads" value={!row.uploads_disabled} onChange={() => row.uploads_disabled ? toggleUploads() : setConfirmUploads(true)} /></View>
      <Button title={row.status === "suspended" ? "Restore account" : "Suspend account"} variant="danger" icon={row.status === "suspended" ? "checkmark-circle-outline" : "pause-circle-outline"} onPress={() => update({ status: row.status === "suspended" ? "active" : "suspended" })} loading={busy} style={styles.suspendButton} />

      <Modal visible={confirmUploads} transparent animationType="fade" onRequestClose={() => setConfirmUploads(false)}><View style={styles.modalBg}><View style={styles.modalCard}><Text style={styles.modalTitle}>Disable uploads for this photographer?</Text><Text style={styles.modalText}>Existing galleries will remain available, but the photographer will not be able to upload new images.</Text><View style={styles.modalActions}><Button title="Cancel" variant="secondary" onPress={() => setConfirmUploads(false)} style={{ flex: 1 }} /><Button title="Disable uploads" variant="danger" onPress={toggleUploads} style={{ flex: 1 }} /></View></View></View></Modal>
    </ScrollView>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) { return <View style={styles.miniStat}><Text style={styles.miniLabel}>{label}</Text><Text style={styles.miniValue}>{value}</Text></View>; }
function Control({ label, value, onChange, disabled = false }: { label: string; value: boolean; onChange: () => void; disabled?: boolean }) { return <View style={styles.control}><View><Text style={styles.controlLabel}>{label}</Text><Text style={styles.controlHint}>{disabled ? "Managed with account status in V1" : value ? "ON" : "OFF"}</Text></View><Switch value={value} disabled={disabled} onValueChange={onChange} trackColor={{ true: colors.brand, false: "#D0D5DD" }} thumbColor="#FFFFFF" /> </View>; }

const styles = StyleSheet.create({ page: { paddingBottom: spacing["3xl"] }, loading: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#F7F8FA" }, top: { paddingHorizontal: spacing["2xl"] }, back: { marginTop: spacing.xl, minHeight: 44, justifyContent: "center" }, backText: { color: colors.brand, fontFamily: fonts.text, fontSize: 13, fontWeight: "600" }, identity: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginHorizontal: spacing["2xl"], padding: spacing.lg, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.lg }, avatar: { width: 52, height: 52, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: "#FFF1EC" }, avatarText: { color: colors.brand, fontFamily: fonts.display, fontSize: 24, fontWeight: "700" }, identityTitle: { flexDirection: "row", alignItems: "center", gap: spacing.sm }, identityName: { color: "#101828", fontFamily: fonts.display, fontSize: 20, fontWeight: "700" }, identityEmail: { color: "#667085", fontFamily: fonts.text, fontSize: 12, marginTop: 3 }, actionButton: { minWidth: 160 }, stats: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, paddingHorizontal: spacing["2xl"], marginTop: spacing.lg }, miniStat: { flex: 1, minWidth: 130, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.md, padding: spacing.lg }, miniLabel: { color: "#667085", fontFamily: fonts.text, fontSize: 12 }, miniValue: { color: "#101828", fontFamily: fonts.display, fontSize: 23, fontWeight: "700", marginTop: spacing.xs }, panel: { backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#EAECF0", borderRadius: radius.lg, marginHorizontal: spacing["2xl"], marginTop: spacing.lg, padding: spacing.lg }, panelTitle: { color: "#101828", fontFamily: fonts.display, fontSize: 18, fontWeight: "700", marginBottom: spacing.lg }, membershipRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" }, plan: { color: "#344054", fontFamily: fonts.text, fontSize: 16, fontWeight: "700" }, price: { color: colors.brand, fontFamily: fonts.text, fontSize: 14, marginTop: 4 }, divider: { height: 1, backgroundColor: "#EAECF0", marginVertical: spacing.lg }, hint: { color: "#667085", fontFamily: fonts.text, fontSize: 12, lineHeight: 18, marginTop: spacing.sm }, usageHeader: { flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.sm }, usageLabel: { color: "#475467", fontFamily: fonts.text, fontSize: 14 }, usageValue: { color: "#101828", fontFamily: fonts.text, fontSize: 14, fontWeight: "700" }, usageLine: { flexDirection: "row", justifyContent: "space-between", paddingTop: spacing.lg }, control: { minHeight: 60, flexDirection: "row", justifyContent: "space-between", alignItems: "center", borderBottomWidth: 1, borderBottomColor: "#F2F4F7" }, controlLabel: { color: "#344054", fontFamily: fonts.text, fontSize: 14, fontWeight: "600" }, controlHint: { color: "#98A2B3", fontFamily: fonts.text, fontSize: 11, marginTop: 3, textTransform: "uppercase" }, suspendButton: { marginHorizontal: spacing["2xl"], marginTop: spacing.lg }, modalBg: { flex: 1, backgroundColor: "rgba(16,24,40,0.42)", alignItems: "center", justifyContent: "center", padding: spacing.xl }, modalCard: { width: "100%", maxWidth: 460, backgroundColor: "#FFFFFF", borderRadius: radius.lg, padding: spacing.xl }, modalTitle: { color: "#101828", fontFamily: fonts.display, fontSize: 20, fontWeight: "700" }, modalText: { color: "#667085", fontFamily: fonts.text, fontSize: 14, lineHeight: 20, marginTop: spacing.sm, marginBottom: spacing.xl }, modalActions: { flexDirection: "row", gap: spacing.md } });
