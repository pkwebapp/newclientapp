import { colors } from "@/src/theme";

/**
 * A quotation is a printed document: it is always rendered on white "paper"
 * regardless of the app theme (same palette the public /q/[token] page uses).
 */
export const paper = {
  bg: "#EDE7DC",
  card: "#FFFFFF",
  ink: "#1A1A1A",
  text: "#374151",
  sub: "#6B6459",
  line: "#E6E0D6",
  brand: colors.brand,
  brandSoft: "#F6E5DC",
};

export type PaperTheme = typeof paper;

/** Colours the RichHtml / editor need; lets the admin (dark) screens pass theme colours instead. */
export type RichPalette = {
  text: string;
  ink: string;
  accent: string;
  accentSoft: string;
  line: string;
  sub?: string;
};

export const paperPalette: RichPalette = {
  text: paper.text,
  ink: paper.ink,
  accent: paper.brand,
  accentSoft: paper.brandSoft,
  line: paper.line,
  sub: paper.sub,
};
