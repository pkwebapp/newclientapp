import { Platform } from "react-native";
import { getAuthToken } from "./client";

const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

export type GstMode = "none" | "cgst_sgst" | "igst";

export type LineItem = {
  description: string;
  hsn_sac?: string;
  qty: number;
  rate: number;
  gst_rate: number;
  amount?: number;
  taxable?: number;
  cgst?: number;
  sgst?: number;
  igst?: number;
  tax?: number;
};

export type Invoice = {
  invoice_id: string;
  invoice_number: string;
  doc_type?: "invoice" | "proforma";
  status: "draft" | "sent" | "partial" | "paid" | "cancelled";
  client?: any;
  studio?: any;
  event_id?: string | null;
  event_name?: string | null;
  issue_date?: string;
  due_date?: string | null;
  place_of_supply?: string;
  gst_mode: GstMode;
  line_items: LineItem[];
  subtotal: number;
  discount_amount: number;
  taxable_total: number;
  cgst_total: number;
  sgst_total: number;
  igst_total: number;
  tax_total: number;
  round_off: number;
  total: number;
  amount_in_words?: string;
  advance_amount?: number;
  payments?: any[];
  amount_received: number;
  balance_due: number;
  share_enabled?: boolean;
  share_url?: string;
  notes?: string | null;
  terms?: string | null;
};

export const STATUS_META: Record<string, { label: string; tone: "neutral" | "gold" | "success" | "warning" }> = {
  draft: { label: "Draft", tone: "neutral" },
  sent: { label: "Sent", tone: "gold" },
  partial: { label: "Partial", tone: "warning" },
  paid: { label: "Paid", tone: "success" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  received: { label: "Received", tone: "success" },
};

const r2 = (x: number) => Math.round((Number(x) || 0) * 100) / 100;

/** Client-side mirror of the backend GST math — used for live totals preview. */
export function computeTotals(items: LineItem[], gstMode: GstMode, discount = 0) {
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
  const preRound = r2(taxable + taxTotal);
  const total = Math.round(preRound);
  return {
    subtotal,
    discount_amount: disc,
    taxable_total: taxable,
    cgst_total: cgst,
    sgst_total: sgst,
    igst_total: igst,
    tax_total: taxTotal,
    round_off: r2(total - preRound),
    total: r2(total),
  };
}

/** Download / open an invoice PDF (authenticated admin endpoint). */
export async function openInvoicePdf(invoiceId: string, number?: string): Promise<void> {
  const url = `${BASE}/invoices/${invoiceId}/pdf`;
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
  // Native: download with auth header, then share/open.
  const FileSystem = await import("expo-file-system");
  const Sharing = await import("expo-sharing");
  const dir = (FileSystem as any).cacheDirectory || (FileSystem as any).documentDirectory || "";
  const fileUri = `${dir}${(number || "invoice").replace(/[^a-zA-Z0-9-_]/g, "_")}.pdf`;
  const dl = await (FileSystem as any).downloadAsync(url, fileUri, { headers });
  if (await (Sharing as any).isAvailableAsync()) {
    await (Sharing as any).shareAsync(dl.uri, { mimeType: "application/pdf" });
  }
}

export function monthLabel(ym: string): string {
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const m = parseInt((ym || "").split("-")[1] || "1", 10);
  return names[(m - 1 + 12) % 12] || "";
}
