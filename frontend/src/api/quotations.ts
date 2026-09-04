import { Platform } from "react-native";
import { getAuthToken } from "./client";

const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

export type QuoteMode = "none" | "cgst_sgst" | "igst";

export type QuoteItem = {
  description: string;
  qty: number;
  rate: number;
  gst_rate: number;
  amount?: number;
};

export type Quotation = {
  quotation_id: string;
  quotation_number: string;
  status: "draft" | "sent" | "accepted" | "revision_requested";
  client?: any;
  studio?: any;
  event_id?: string | null;
  subject?: string;
  body?: string;
  body_html?: string;
  show_pricing?: boolean;
  gst_mode: QuoteMode;
  line_items: QuoteItem[];
  subtotal?: number;
  discount_amount?: number;
  taxable_total?: number;
  cgst_total?: number;
  sgst_total?: number;
  igst_total?: number;
  tax_total?: number;
  total?: number;
  amount_in_words?: string;
  issue_date?: string;
  valid_until?: string | null;
  terms?: string | null;
  notes?: string | null;
  client_response?: { action: string; note?: string; at?: string } | null;
  converted_invoice_id?: string | null;
  converted_target?: "invoice" | "proforma" | null;
  share_enabled?: boolean;
  share_url?: string;
  revision_number?: number;
  revision_of?: string | null;
  root_id?: string | null;
  revision_note?: string | null;
  revisions?: {
    quotation_id: string;
    quotation_number: string;
    revision_number?: number;
    status: string;
    created_at?: string;
    total?: number;
    show_pricing?: boolean;
  }[];
};

export type QuoteTemplate = {
  template_id: string;
  name: string;
  subject?: string;
  body?: string;
  show_pricing?: boolean;
  gst_mode: QuoteMode;
  discount_amount?: number;
  line_items: QuoteItem[];
  terms?: string;
  notes?: string;
  created_at?: string;
  updated_at?: string;
};

export const QUOTE_STATUS_META: Record<string, { label: string; tone: "neutral" | "gold" | "success" | "warning" }> = {
  draft: { label: "Draft", tone: "neutral" },
  sent: { label: "Sent", tone: "gold" },
  accepted: { label: "Accepted", tone: "success" },
  revision_requested: { label: "Revision requested", tone: "warning" },
};

const r2 = (x: number) => Math.round((Number(x) || 0) * 100) / 100;

/** Client-side mirror of the backend quote math — for live totals preview. */
export function computeQuoteTotals(items: QuoteItem[], gstMode: QuoteMode, discount = 0) {
  let subtotal = 0;
  const rows = items.map((li) => {
    const amount = r2((Number(li.qty) || 0) * (Number(li.rate) || 0));
    subtotal += amount;
    return { ...li, amount, gst_rate: gstMode === "none" ? 0 : Number(li.gst_rate) || 0 };
  });
  subtotal = r2(subtotal);
  const disc = Math.min(Math.max(r2(discount), 0), subtotal);
  let taxable = 0;
  let cgst = 0;
  let sgst = 0;
  let igst = 0;
  rows.forEach((row) => {
    const share = subtotal > 0 ? row.amount / subtotal : 0;
    const t = r2(row.amount - disc * share);
    taxable += t;
    const tax = gstMode === "none" ? 0 : r2((t * (row.gst_rate || 0)) / 100);
    if (gstMode === "cgst_sgst") {
      cgst += r2(tax / 2);
      sgst += r2(tax / 2);
    } else if (gstMode === "igst") {
      igst += tax;
    }
  });
  taxable = r2(taxable);
  cgst = r2(cgst);
  sgst = r2(sgst);
  igst = r2(igst);
  const taxTotal = r2(cgst + sgst + igst);
  const total = r2(taxable + taxTotal);
  return {
    subtotal,
    discount_amount: disc,
    taxable_total: taxable,
    cgst_total: cgst,
    sgst_total: sgst,
    igst_total: igst,
    tax_total: taxTotal,
    total,
  };
}

/** Download / open a quotation PDF (authenticated admin endpoint). */
export async function openQuotationPdf(quotationId: string, number?: string): Promise<void> {
  const url = `${BASE}/quotations/${quotationId}/pdf`;
  const token = getAuthToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
  if (Platform.OS === "web") {
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error("Could not generate PDF");
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    if (typeof window !== "undefined") window.open(objectUrl, "_blank");
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    return;
  }
  const FileSystem = await import("expo-file-system");
  const Sharing = await import("expo-sharing");
  const dir = (FileSystem as any).cacheDirectory || (FileSystem as any).documentDirectory || "";
  const fileUri = `${dir}${(number || "quotation").replace(/[^a-zA-Z0-9-_]/g, "_")}.pdf`;
  const dl = await (FileSystem as any).downloadAsync(url, fileUri, { headers });
  if (await (Sharing as any).isAvailableAsync()) {
    await (Sharing as any).shareAsync(dl.uri, { mimeType: "application/pdf" });
  }
}
