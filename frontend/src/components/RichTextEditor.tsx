import { useEffect, useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";
import { MaterialIcons } from "@expo/vector-icons";

import { RichPalette } from "./paper-theme";
import { htmlToPlain, plainToHtml, isHtml } from "@/src/utils/richtext";
import { radius, spacing } from "@/src/theme";

/**
 * Native fallback for the quotation body editor. The full formatting toolbar
 * (headings, bold, tables, paste-with-formatting) is a web feature; on the
 * phone we edit readable plain text and store it as paragraphs. The original
 * HTML is kept untouched unless the text is actually changed.
 */
export type RichEditorHandle = {
  text: string;
  setText: (t: string) => void;
  richSource: boolean;
} | null;

export function useRichEditor({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
}): RichEditorHandle {
  const [text, setTextState] = useState(() => htmlToPlain(value));
  const [seen, setSeen] = useState(value);
  useEffect(() => {
    if (value !== seen) {
      setSeen(value);
      setTextState(htmlToPlain(value));
    }
  }, [value, seen]);
  const setText = (t: string) => {
    setTextState(t);
    const html = t.trim() ? plainToHtml(t) : "";
    setSeen(html);
    onChange(html);
  };
  void placeholder;
  return { text, setText, richSource: isHtml(value) };
}

export function RichEditorContent({
  editor,
  palette,
  minHeight = 320,
  fontSize = 15,
  lineHeight = 24,
}: {
  editor: RichEditorHandle;
  palette: RichPalette;
  minHeight?: number;
  fontSize?: number;
  lineHeight?: number;
}) {
  if (!editor) return null;
  return (
    <TextInput
      testID="quote-body-editor"
      value={editor.text}
      onChangeText={editor.setText}
      multiline
      placeholder="Write your quotation here…"
      placeholderTextColor={palette.sub || palette.text}
      textAlignVertical="top"
      style={[styles.input, { minHeight, fontSize, lineHeight, color: palette.text }]}
    />
  );
}

export function RichToolbar({ editor, palette }: { editor: RichEditorHandle; palette: RichPalette }) {
  if (!editor) return null;
  return (
    <View style={[styles.hint, { borderColor: palette.line, backgroundColor: palette.accentSoft }]} testID="rich-toolbar">
      <MaterialIcons name="info-outline" size={16} color={palette.accent} />
      <Text style={[styles.hintText, { color: palette.ink }]}>
        {editor.richSource
          ? "This body has rich formatting (headings, tables). Editing here keeps the text but simplifies the layout — use the web app to keep formatting."
          : "Bold, headings, lists and tables are available in the web app editor."}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  input: { padding: 0 },
  hint: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md, borderBottomWidth: 1, borderRadius: radius.sm },
  hintText: { flex: 1, fontSize: 12, lineHeight: 17 },
});
