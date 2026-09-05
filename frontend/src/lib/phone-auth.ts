/**
 * Phone OTP authentication helpers — talk to the PIK Connect backend.
 * Backend issues a custom HS256 JWT.
 */
import { api } from "@/src/api/client";

export interface PhoneSendOtpResult {
  message: string;
  /** Present when OTP_DEV_MODE=true on the backend — show to the user for testing. */
  dev_code?: string;
}

export interface PhoneAuthUser {
  user_id: string;
  role: "admin" | "client";
  name?: string;
  phone?: string;
  email?: string;
  profile_complete?: boolean;
  studio_profile?: Record<string, any> | null;
  plan?: string | null;
}

export interface PhoneVerifyResult {
  token: string;
  user: PhoneAuthUser;
  /** True on a user's first sign-in (or before they've set a name/password) —
   * the client login screen uses this to show the one-time setup step. */
  is_new?: boolean;
}

/** Send a 6-digit SMS OTP to ``phone`` via MSG91. */
export async function sendPhoneOtp(
  phone: string,
  role: "admin" | "client" = "client"
): Promise<PhoneSendOtpResult> {
  return api.post("/auth/phone/send-otp", { phone, role });
}

/** Verify the OTP; returns a phone JWT + user on success. */
export async function verifyPhoneOtp(
  phone: string,
  code: string,
  role: "admin" | "client" = "client"
): Promise<PhoneVerifyResult> {
  return api.post("/auth/phone/verify-otp", { phone, code, role });
}

/** Phone + password sign-in (after the user has set a password). */
export async function loginWithPhonePassword(
  phone: string,
  password: string
): Promise<PhoneVerifyResult> {
  return api.post("/auth/phone/login", { phone, password });
}

export interface PhoneCheckResult {
  exists: boolean;
  has_password: boolean;
}

/** Ask the backend how to proceed for a number: existing users with a password
 * enter it; new users (or no password yet) use OTP. */
export async function checkPhone(phone: string): Promise<PhoneCheckResult> {
  return api.post("/auth/phone/check", { phone });
}

/** Set a password for the currently signed-in phone user. */
export async function setPhonePassword(
  password: string
): Promise<{ message: string }> {
  return api.post("/auth/phone/set-password", { password });
}

/** One-time onboarding for a new phone user: save their name (asked at sign-in)
 * and, optionally, a password and/or email. Requires the phone JWT as auth token. */
export async function completePhoneSetup(
  name: string,
  password?: string,
  email?: string
): Promise<{ message: string; user: PhoneAuthUser }> {
  return api.post("/auth/phone/complete-setup", {
    name,
    ...(password ? { password } : {}),
    ...(email ? { email } : {}),
  });
}
