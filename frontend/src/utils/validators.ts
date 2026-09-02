// Shared input validators for form fields (Hermes-safe, no Intl dependency).
const GSTIN_RE = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
const PHONE_DIGITS_RE = /^[6-9]\d{9}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Returns an error message if the GSTIN is non-empty and invalid (GSTIN itself is optional). */
export function gstinError(value?: string | null): string | null { const v = (value || "").trim().toUpperCase(); if (!v) return null; return GSTIN_RE.test(v) ? null : "Enter a valid 15-character GSTIN (e.g. 29ABCDE1234F1Z5)"; }

/** Returns an error message if the phone is non-empty and not a valid 10-digit Indian mobile number. */
export function phoneError(value?: string | null): string | null { const digits = (value || "").replace(/\D/g, "").replace(/^91(?=\d{10}$)/, ""); if (!digits) return null; return PHONE_DIGITS_RE.test(digits) ? null : "Enter a valid 10-digit mobile number"; }

/** Returns an error message if the email is non-empty and not a plausible email address. */
export function emailError(value?: string | null): string | null { const v = (value || "").trim(); if (!v) return null; return EMAIL_RE.test(v) ? null : "Enter a valid email address"; }

const TIME_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;

/** Returns an error message if the time is non-empty and not a valid 24-hour HH:MM time. */
export function timeError(value?: string | null): string | null { const v = (value || "").trim(); if (!v) return null; return TIME_RE.test(v) ? null : "Use 24-hour HH:MM (e.g. 14:30)"; }

/** Returns an error message if the value is non-empty and not a relative path or a full http(s) URL. */
export function urlError(value?: string | null): string | null { const v = (value || "").trim(); if (!v) return null; if (v.startsWith("/")) return null; return /^https?:\/\/.+/i.test(v) ? null : "Use a relative path (/...) or a full https:// link"; }
