/** Helpers for the rich-text (HTML) quotation body. */

export const isHtml = (s?: string | null): boolean => !!s && /<\s*\/?\s*[a-zA-Z][^>]*>/.test(s);

const escapeHtml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** Legacy plain-text body → paragraphs (blank line = new paragraph, newline = line break). */
export function plainToHtml(text: string): string {
  const paras = (text || "").replace(/\r\n/g, "\n").trim().split(/\n\s*\n/);
  return paras
    .filter((p) => p.trim())
    .map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br/>")}</p>`)
    .join("");
}

/** Best-effort HTML → readable plain text (native fallback rendering / editing). */
export function htmlToPlain(html: string): string {
  if (!html) return "";
  if (!isHtml(html)) return html;
  return html
    .replace(/\r?\n/g, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|h[1-6]|blockquote|tr|table|ul|ol)>/gi, "\n")
    .replace(/<li[^>]*>/gi, "• ")
    .replace(/<\/li>/gi, "\n")
    .replace(/<\/t[dh]>/gi, "\t")
    .replace(/<hr\s*\/?>/gi, "\n———\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Merge fields that the backend substitutes when the quotation is rendered. */
export const QUOTE_FIELDS: { key: string; label: string }[] = [
  { key: "client_name", label: "Client name" },
  { key: "client_phone", label: "Client phone" },
  { key: "client_email", label: "Client email" },
  { key: "quotation_number", label: "Quotation number" },
  { key: "issue_date", label: "Quotation date" },
  { key: "valid_until", label: "Valid until" },
  { key: "subject", label: "Subject" },
  { key: "total", label: "Estimated total (₹)" },
  { key: "total_in_words", label: "Total in words" },
  { key: "studio_name", label: "Studio name" },
];
