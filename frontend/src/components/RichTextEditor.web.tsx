import React, { useEffect, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { MaterialIcons } from "@expo/vector-icons";
import { EditorContent, useEditor, useEditorState, type Editor } from "@tiptap/react";
import { StarterKit } from "@tiptap/starter-kit";
import { TableKit } from "@tiptap/extension-table";
import { TextAlign } from "@tiptap/extension-text-align";
import { Placeholder } from "@tiptap/extensions";

import { ensureRichCss, richCssVars } from "./RichHtml.web";
import { RichPalette } from "./paper-theme";
import { isHtml, plainToHtml, QUOTE_FIELDS } from "@/src/utils/richtext";
import { radius, spacing } from "@/src/theme";

export type RichEditorHandle = Editor | null;

const EDITOR_STYLE_ID = "pk-editor-css";
const EDITOR_CSS = `
.pk-editor .ProseMirror { outline: none; min-height: var(--pk-min-h, 320px); caret-color: var(--pk-accent); }
.pk-editor .ProseMirror p.is-editor-empty:first-child::before { content: attr(data-placeholder); color: var(--pk-sub); float: left; height: 0; pointer-events: none; }
.pk-editor .ProseMirror td, .pk-editor .ProseMirror th { position: relative; min-width: 48px; }
.pk-editor .ProseMirror .selectedCell::after { content: ""; position: absolute; inset: 0; background: var(--pk-accent-soft); opacity: 0.55; pointer-events: none; z-index: 2; }
.pk-editor .ProseMirror ::selection { background: var(--pk-accent-soft); }
.pk-editor .ProseMirror .column-resize-handle { display: none; }
`;

function ensureEditorCss() {
  ensureRichCss();
  if (typeof document === "undefined" || document.getElementById(EDITOR_STYLE_ID)) return;
  const el = document.createElement("style");
  el.id = EDITOR_STYLE_ID;
  el.textContent = EDITOR_CSS;
  document.head.appendChild(el);
}

const toDoc = (value: string) => (!value ? "" : isHtml(value) ? value : plainToHtml(value));

export function useRichEditor({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
}): RichEditorHandle {
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3] }, link: { openOnClick: false } }),
      TableKit.configure({ table: { resizable: false } }),
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Placeholder.configure({ placeholder: placeholder || "Write your quotation here…" }),
    ],
    content: toDoc(value),
    editorProps: { attributes: { class: "pk-rich", "data-testid": "quote-body-editor" } },
    onUpdate: ({ editor: e }) => onChangeRef.current(e.isEmpty ? "" : e.getHTML()),
  });

  // Keep the document in sync when the value is replaced from outside (template applied, quotation loaded).
  useEffect(() => {
    if (!editor) return;
    const current = editor.isEmpty ? "" : editor.getHTML();
    const next = toDoc(value);
    if (next !== current) editor.commands.setContent(next, { emitUpdate: false });
  }, [value, editor]);

  return editor;
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
  useEffect(ensureEditorCss, []);
  if (!editor) return null;
  return (
    <div
      className="pk-editor"
      style={{
        color: palette.text,
        fontSize,
        lineHeight: `${lineHeight}px`,
        fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        cursor: "text",
        ...(richCssVars(palette) as any),
        ["--pk-min-h" as any]: `${minHeight}px`,
      }}
      onClick={() => editor.commands.focus()}
    >
      <EditorContent editor={editor} />
    </div>
  );
}

type Btn = { key: string; icon?: keyof typeof MaterialIcons.glyphMap; label?: string; active?: boolean; disabled?: boolean; onPress: () => void; hint: string; italic?: boolean; underline?: boolean; strike?: boolean };

export function RichToolbar({ editor, palette }: { editor: RichEditorHandle; palette: RichPalette }) {
  const [fieldsOpen, setFieldsOpen] = useState(false);
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) =>
      e
        ? {
            bold: e.isActive("bold"),
            italic: e.isActive("italic"),
            underline: e.isActive("underline"),
            strike: e.isActive("strike"),
            h1: e.isActive("heading", { level: 1 }),
            h2: e.isActive("heading", { level: 2 }),
            h3: e.isActive("heading", { level: 3 }),
            bullet: e.isActive("bulletList"),
            ordered: e.isActive("orderedList"),
            quote: e.isActive("blockquote"),
            left: e.isActive({ textAlign: "left" }),
            center: e.isActive({ textAlign: "center" }),
            right: e.isActive({ textAlign: "right" }),
            table: e.isActive("table"),
            canUndo: e.can().undo(),
            canRedo: e.can().redo(),
          }
        : null,
  });
  if (!editor || !state) return null;
  const run = (fn: (c: ReturnType<Editor["chain"]>) => any) => () => fn(editor.chain().focus()).run();

  const groups: Btn[][] = [
    [
      { key: "undo", icon: "undo", hint: "Undo", disabled: !state.canUndo, onPress: run((c) => c.undo()) },
      { key: "redo", icon: "redo", hint: "Redo", disabled: !state.canRedo, onPress: run((c) => c.redo()) },
    ],
    [
      { key: "h1", label: "H1", hint: "Heading 1", active: state.h1, onPress: run((c) => c.toggleHeading({ level: 1 })) },
      { key: "h2", label: "H2", hint: "Heading 2", active: state.h2, onPress: run((c) => c.toggleHeading({ level: 2 })) },
      { key: "h3", label: "H3", hint: "Heading 3", active: state.h3, onPress: run((c) => c.toggleHeading({ level: 3 })) },
    ],
    [
      { key: "bold", icon: "format-bold", hint: "Bold", active: state.bold, onPress: run((c) => c.toggleBold()) },
      { key: "italic", icon: "format-italic", hint: "Italic", active: state.italic, onPress: run((c) => c.toggleItalic()) },
      { key: "underline", icon: "format-underlined", hint: "Underline", active: state.underline, onPress: run((c) => c.toggleUnderline()) },
      { key: "strike", icon: "format-strikethrough", hint: "Strikethrough", active: state.strike, onPress: run((c) => c.toggleStrike()) },
    ],
    [
      { key: "left", icon: "format-align-left", hint: "Align left", active: state.left, onPress: run((c) => c.setTextAlign("left")) },
      { key: "center", icon: "format-align-center", hint: "Align centre", active: state.center, onPress: run((c) => c.setTextAlign("center")) },
      { key: "right", icon: "format-align-right", hint: "Align right", active: state.right, onPress: run((c) => c.setTextAlign("right")) },
    ],
    [
      { key: "bullet", icon: "format-list-bulleted", hint: "Bullet list", active: state.bullet, onPress: run((c) => c.toggleBulletList()) },
      { key: "ordered", icon: "format-list-numbered", hint: "Numbered list", active: state.ordered, onPress: run((c) => c.toggleOrderedList()) },
      { key: "quote", icon: "format-quote", hint: "Quote", active: state.quote, onPress: run((c) => c.toggleBlockquote()) },
      { key: "hr", icon: "horizontal-rule", hint: "Divider", onPress: run((c) => c.setHorizontalRule()) },
    ],
    state.table
      ? [
          { key: "row+", icon: "playlist-add", hint: "Add row below", onPress: run((c) => c.addRowAfter()) },
          { key: "col+", icon: "view-column", hint: "Add column right", onPress: run((c) => c.addColumnAfter()) },
          { key: "row-", icon: "remove", hint: "Delete row", onPress: run((c) => c.deleteRow()) },
          { key: "col-", icon: "remove-circle-outline", hint: "Delete column", onPress: run((c) => c.deleteColumn()) },
          { key: "hdr", icon: "view-headline", hint: "Toggle header row", onPress: run((c) => c.toggleHeaderRow()) },
          { key: "tbl-", icon: "delete-outline", hint: "Delete table", onPress: run((c) => c.deleteTable()) },
        ]
      : [{ key: "tbl", icon: "table-chart", hint: "Insert table", onPress: run((c) => c.insertTable({ rows: 3, cols: 3, withHeaderRow: true })) }],
    [
      { key: "clear", icon: "format-clear", hint: "Clear formatting", onPress: run((c) => c.clearNodes().unsetAllMarks()) },
    ],
  ];

  return (
    <View style={[styles.wrap, { borderColor: palette.line }]} testID="rich-toolbar">
      <View style={styles.row} testID="rich-toolbar-row">
        {groups.map((g, gi) => (
          <View key={gi} style={styles.group}>
            {g.map((b) => (
              <button
                key={b.key}
                type="button"
                data-testid={`rt-${b.key}`}
                aria-label={b.hint}
                title={b.hint}
                disabled={b.disabled}
                onMouseDown={(e) => e.preventDefault()}
                onClick={b.onPress}
                style={{
                  ...BTN_CSS,
                  background: b.active ? palette.accentSoft : "transparent",
                  opacity: b.disabled ? 0.35 : 1,
                  cursor: b.disabled ? "default" : "pointer",
                }}
              >
                {b.icon ? (
                  <MaterialIcons name={b.icon} size={20} color={b.active ? palette.accent : palette.ink} />
                ) : (
                  <Text style={[styles.btnLabel, { color: b.active ? palette.accent : palette.ink }]}>{b.label}</Text>
                )}
              </button>
            ))}
            {gi < groups.length - 1 && <View style={[styles.sep, { backgroundColor: palette.line }]} />}
          </View>
        ))}
        <View style={styles.group}>
          <button
            type="button"
            data-testid="rt-fields"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setFieldsOpen((v) => !v)}
            style={{ ...BTN_CSS, gap: 4, padding: "0 8px", background: fieldsOpen ? palette.accentSoft : "transparent", cursor: "pointer" }}
          >
            <MaterialIcons name="data-object" size={18} color={palette.accent} />
            <Text style={[styles.fieldBtnText, { color: palette.accent }]}>Insert field</Text>
            <MaterialIcons name={fieldsOpen ? "expand-less" : "expand-more"} size={18} color={palette.accent} />
          </button>
        </View>
      </View>
      {fieldsOpen && (
        <View style={[styles.fields, { borderColor: palette.line }]} testID="rt-fields-menu">
          <Text style={[styles.fieldsHint, { color: palette.sub || palette.text }]}>Fields are filled in automatically when the quotation is viewed, printed or shared — perfect for templates.</Text>
          <View style={styles.fieldsGrid}>
            {QUOTE_FIELDS.map((f) => (
              <button
                key={f.key}
                type="button"
                data-testid={`rt-field-${f.key}`}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => { editor.chain().focus().insertContent(`{{${f.key}}}`).run(); setFieldsOpen(false); }}
                style={{ ...CHIP_CSS, borderColor: palette.line, background: palette.accentSoft, color: palette.ink }}
              >
                {f.label}
              </button>
            ))}
          </View>
        </View>
      )}
    </View>
  );
}

// Toolbar buttons are real DOM buttons so `onMouseDown.preventDefault()` keeps the
// caret inside the editor while formatting (no focus ping-pong, no lost keystrokes).
const BTN_CSS: React.CSSProperties = {
  display: "inline-flex", alignItems: "center", justifyContent: "center", minWidth: 36, height: 36,
  border: "none", borderRadius: radius.sm, padding: "0 6px", margin: "0 1px", font: "inherit",
};
const CHIP_CSS: React.CSSProperties = {
  borderWidth: 1, borderStyle: "solid", borderRadius: radius.pill, padding: "6px 12px", minHeight: 32,
  font: "inherit", fontSize: 13, fontWeight: 600, cursor: "pointer",
};

const styles = StyleSheet.create({
  wrap: { borderBottomWidth: 1 },
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", paddingHorizontal: spacing.sm, paddingVertical: spacing.xs, rowGap: 2 },
  group: { flexDirection: "row", alignItems: "center" },
  sep: { width: 1, height: 22, marginHorizontal: spacing.xs },
  btnLabel: { fontSize: 13, fontWeight: "800" },
  fieldBtnText: { fontSize: 13, fontWeight: "700" },
  fields: { borderTopWidth: 1, padding: spacing.md },
  fieldsHint: { fontSize: 12, lineHeight: 17, marginBottom: spacing.sm },
  fieldsGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
});
