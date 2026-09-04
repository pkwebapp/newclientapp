import { Image, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { paper, paperPalette } from "./paper-theme";
import { RichEditorContent, RichToolbar, useRichEditor } from "./RichTextEditor";
import { colors, fonts, fontSize, radius, spacing } from "@/src/theme";

export type StudioLetterhead = {
  name?: string;
  address?: string;
  phone?: string;
  email?: string;
  website?: string;
  gstin?: string;
  logo_base64?: string;
};

/**
 * Full-page WYSIWYG editor for the quotation body. The body is edited in place
 * on a white "paper" that mirrors the final document (letterhead, number,
 * client, subject) so what the studio sees is what the client gets.
 */
export default function QuoteBodyEditorModal({
  visible,
  onClose,
  value,
  onChange,
  studio,
  clientName,
  subject,
  numberLabel,
  issueDate,
}: {
  visible: boolean;
  onClose: () => void;
  value: string;
  onChange: (html: string) => void;
  studio: StudioLetterhead;
  clientName?: string;
  subject?: string;
  numberLabel: string;
  issueDate?: string;
}) {
  const insets = useSafeAreaInsets();
  const editor = useRichEditor({ value, onChange, placeholder: "Write your quotation here…\n\nDear …,\n\nThank you for the opportunity." });
  const hasLogo = typeof studio.logo_base64 === "string" && studio.logo_base64.startsWith("data:image");
  const contact = [studio.address, studio.phone ? `Ph: ${studio.phone}` : "", studio.email, studio.website, studio.gstin ? `GSTIN: ${studio.gstin}` : ""].filter(Boolean);

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose} presentationStyle="fullScreen">
      <View style={styles.screen} testID="body-editor-modal">
        <View style={[styles.bar, { paddingTop: insets.top + spacing.sm }]}>
          <Pressable testID="body-editor-close" onPress={onClose} hitSlop={10} style={styles.barBtn}>
            <Ionicons name="close" size={24} color={colors.onSurface} />
          </Pressable>
          <View style={{ flex: 1 }}>
            <Text style={styles.barTitle}>Quotation body</Text>
            <Text style={styles.barSub} numberOfLines={1}>Saves as you type · pasting from Word or Docs keeps formatting</Text>
          </View>
          <Pressable testID="body-editor-done" onPress={onClose} style={styles.doneBtn}>
            <Ionicons name="checkmark" size={18} color={colors.onBrand} />
            <Text style={styles.doneText}>Done</Text>
          </Pressable>
        </View>

        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={[styles.scroll, { paddingBottom: insets.bottom + 120 }]}
          stickyHeaderIndices={[1]}
          keyboardShouldPersistTaps="handled"
        >
          {/* 0 — document head (read-only context) */}
          <View style={[styles.sheet, styles.sheetTop]}>
            <View style={styles.letterhead}>
              {hasLogo && <Image source={{ uri: studio.logo_base64 }} style={styles.logo} resizeMode="contain" />}
              <View style={{ flex: 1 }}>
                <Text style={styles.studio}>{studio.name || "Your Studio"}</Text>
                {contact.length > 0 && <Text style={styles.contact}>{contact.join("  ·  ")}</Text>}
              </View>
            </View>
            <View style={styles.rule} />
            <View style={styles.head}>
              <Text style={styles.qTitle}>QUOTATION</Text>
              <View style={{ alignItems: "flex-end" }}>
                <Text style={styles.qNo}>{numberLabel}</Text>
                {!!issueDate && <Text style={styles.small}>Date: {issueDate}</Text>}
              </View>
            </View>
            <View style={styles.party}>
              <Text style={styles.label}>PREPARED FOR</Text>
              <Text style={styles.clientName}>{clientName?.trim() || "Client name"}</Text>
            </View>
            <Text style={[styles.subject, !subject?.trim() && { color: paper.sub }]}>{subject?.trim() || "Subject / title"}</Text>
          </View>

          {/* 1 — sticky formatting toolbar */}
          <View style={[styles.sheet, styles.toolbarWrap]}>
            <RichToolbar editor={editor} palette={paperPalette} />
          </View>

          {/* 2 — editable body */}
          <Pressable style={[styles.sheet, styles.sheetBottom]} onPress={() => Platform.OS === "web" && (editor as any)?.commands?.focus?.()}>
            <RichEditorContent editor={editor} palette={paperPalette} minHeight={420} />
          </Pressable>
        </ScrollView>
      </View>
    </Modal>
  );
}

const SHEET_W = 820;

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: paper.bg },
  bar: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingBottom: spacing.md, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  barBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  barTitle: { color: colors.onSurface, fontFamily: fonts.display, fontSize: fontSize.lg },
  barSub: { color: colors.muted, fontFamily: fonts.text, fontSize: fontSize.sm, marginTop: 2 },
  doneBtn: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: colors.brand, borderRadius: radius.pill, paddingHorizontal: spacing.lg, height: 40 },
  doneText: { color: colors.onBrand, fontFamily: fonts.text, fontSize: fontSize.base, fontWeight: "800" },
  scroll: { paddingHorizontal: spacing.md, paddingTop: spacing.xl },
  sheet: { width: "100%", maxWidth: SHEET_W, alignSelf: "center", backgroundColor: paper.card, paddingHorizontal: Platform.select({ web: 40, default: spacing.xl }) as number },
  sheetTop: { borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, paddingTop: Platform.select({ web: 40, default: spacing.xl }) as number, paddingBottom: spacing.lg },
  toolbarWrap: { paddingHorizontal: spacing.sm, paddingTop: spacing.xs, borderBottomWidth: 0 },
  sheetBottom: { borderBottomLeftRadius: radius.lg, borderBottomRightRadius: radius.lg, paddingTop: spacing.xl, paddingBottom: 64, minHeight: 480 },
  letterhead: { flexDirection: "row", alignItems: "center", gap: spacing.lg },
  logo: { width: 60, height: 60, borderRadius: radius.sm },
  studio: { color: paper.ink, fontSize: 22, fontWeight: "800", letterSpacing: 0.3 },
  contact: { color: paper.sub, fontSize: 12, marginTop: 4, lineHeight: 18 },
  rule: { height: 3, backgroundColor: paper.brand, marginVertical: 14, borderRadius: 2 },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: spacing.lg },
  qTitle: { color: paper.brand, fontSize: 20, fontWeight: "800", letterSpacing: 3 },
  qNo: { color: paper.ink, fontSize: 15, fontWeight: "700" },
  small: { color: paper.sub, fontSize: 13, marginTop: 2 },
  party: { borderTopWidth: 1, borderTopColor: paper.line, paddingTop: 14, marginTop: 14 },
  label: { color: paper.sub, fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  clientName: { color: paper.ink, fontSize: 18, fontWeight: "700", marginTop: 4 },
  subject: { color: paper.ink, fontSize: 18, fontWeight: "800", marginTop: 18 },
});
