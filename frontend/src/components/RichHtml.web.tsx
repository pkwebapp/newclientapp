import { useEffect } from "react";
import { View } from "react-native";

import { RichPalette } from "./paper-theme";

const STYLE_ID = "pk-rich-css";

const CSS = `
.pk-rich { word-break: break-word; overflow-wrap: anywhere; }
.pk-rich > :first-child { margin-top: 0 !important; }
.pk-rich > :last-child { margin-bottom: 0 !important; }
.pk-rich p { margin: 0 0 0.6em 0; }
.pk-rich h1, .pk-rich h2, .pk-rich h3, .pk-rich h4 { color: var(--pk-ink); font-weight: 800; line-height: 1.3; margin: 1.1em 0 0.4em 0; }
.pk-rich h1 { font-size: 1.5em; }
.pk-rich h2 { font-size: 1.3em; }
.pk-rich h3 { font-size: 1.12em; }
.pk-rich h4 { font-size: 1em; }
.pk-rich ul, .pk-rich ol { margin: 0.3em 0 0.8em 0; padding-left: 1.5em; }
.pk-rich li { margin: 0.15em 0; }
.pk-rich li p { margin: 0; }
.pk-rich table { width: 100%; border-collapse: collapse; margin: 0.6em 0 1em 0; table-layout: fixed; }
.pk-rich th { background: var(--pk-accent-soft); color: var(--pk-ink); font-weight: 700; text-align: left; }
.pk-rich th, .pk-rich td { border: 1px solid var(--pk-line); padding: 6px 8px; vertical-align: top; }
.pk-rich td p, .pk-rich th p { margin: 0; }
.pk-rich blockquote { border-left: 3px solid var(--pk-accent); margin: 0.6em 0; padding: 2px 12px; opacity: 0.92; }
.pk-rich hr { border: 0; border-top: 1px solid var(--pk-line); margin: 1em 0; }
.pk-rich a { color: var(--pk-accent); }
.pk-rich strong, .pk-rich b { font-weight: 700; color: var(--pk-ink); }
.pk-rich u { text-decoration: underline; }
.pk-rich s { text-decoration: line-through; }
.pk-rich mark { background: var(--pk-accent-soft); padding: 0 2px; }
`;

export function ensureRichCss() {
  if (typeof document === "undefined" || document.getElementById(STYLE_ID)) return;
  const el = document.createElement("style");
  el.id = STYLE_ID;
  el.textContent = CSS;
  document.head.appendChild(el);
}

export function richCssVars(p: RichPalette): Record<string, string> {
  return {
    "--pk-ink": p.ink,
    "--pk-accent": p.accent,
    "--pk-accent-soft": p.accentSoft,
    "--pk-line": p.line,
    "--pk-sub": p.sub || p.text,
  };
}

/** Renders sanitised quotation HTML (from the API) with document typography. Web build. */
export default function RichHtml({
  html,
  palette,
  fontSize = 14,
  lineHeight = 22,
  testID,
}: {
  html: string;
  palette: RichPalette;
  fontSize?: number;
  lineHeight?: number;
  testID?: string;
}) {
  useEffect(ensureRichCss, []);
  return (
    <View testID={testID}>
      <div
        className="pk-rich"
        style={{
          color: palette.text,
          fontSize,
          lineHeight: `${lineHeight}px`,
          fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
          ...(richCssVars(palette) as any),
        }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </View>
  );
}
