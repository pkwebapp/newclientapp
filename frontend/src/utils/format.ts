// Small formatting helpers (Hermes-safe, no Intl dependency).

/** Format a number as Indian Rupees with lakh/crore grouping, e.g. 120000 -> "₹1,20,000". */
export function formatINR(value?: number | null): string {
  const n = Math.round(Number(value) || 0);
  const s = String(Math.abs(n));
  let out: string;
  if (s.length <= 3) {
    out = s;
  } else {
    const last3 = s.slice(-3);
    let rest = s.slice(0, -3);
    const parts: string[] = [];
    while (rest.length > 2) {
      parts.unshift(rest.slice(-2));
      rest = rest.slice(0, -2);
    }
    if (rest.length) parts.unshift(rest);
    out = parts.join(",") + "," + last3;
  }
  return (n < 0 ? "-₹" : "₹") + out;
}

/** Compact rupees for tight spaces: ₹1.2L, ₹2.85L, ₹1.5Cr. */
export function formatINRCompact(value?: number | null): string {
  const n = Math.round(Number(value) || 0);
  if (n >= 10000000) return "₹" + (n / 10000000).toFixed(n % 10000000 === 0 ? 0 : 2).replace(/\.00$/, "") + "Cr";
  if (n >= 100000) return "₹" + (n / 100000).toFixed(n % 100000 === 0 ? 0 : 2).replace(/\.00$/, "") + "L";
  return formatINR(n);
}
