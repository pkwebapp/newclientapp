import { Platform, Linking } from "react-native";

const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

let authToken: string | null = null;
export function setAuthToken(t: string | null) {
  authToken = t;
}
export function getAuthToken() {
  return authToken;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Auth-aware URL for serving an image (works on web <img> and native). */
export function fileUrl(path?: string | null): string | undefined {
  if (!path) return undefined;
  return `${BASE}/files/${path}?token=${authToken ?? ""}`;
}

/**
 * Resolve an image source. Prefers a direct CDN url (e.g. Cloudinary) supplied
 * by the backend so bytes are served straight from the CDN edge; falls back to
 * the authenticated /api/files proxy when no direct url is available.
 */
export function imgUrl(direct?: string | null, path?: string | null): string | undefined {
  return direct || fileUrl(path);
}

/** Download the original image. Web = blob download; native = open in browser. */
export async function downloadPhoto(photo: {
  url?: string | null;
  thumb_url?: string | null;
  storage_path?: string | null;
  thumb_path?: string | null;
  filename?: string | null;
  photo_id: string;
}): Promise<void> {
  const url =
    photo.url || photo.thumb_url || fileUrl(photo.storage_path || photo.thumb_path);
  if (!url) return;
  const name = photo.filename || `${photo.photo_id}.jpg`;
  if (Platform.OS === "web") {
    try {
      const res = await fetch(url);
      const blob = await res.blob();
      const href = window.URL.createObjectURL(blob);
      const a = window.document.createElement("a");
      a.href = href;
      a.download = name;
      window.document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(href), 1000);
    } catch {
      window.open(url, "_blank");
    }
  } else {
    Linking.openURL(url).catch(() => {});
  }
}

async function request(path: string, opts: any = {}) {
  const headers: Record<string, string> = { ...(opts.headers || {}) };
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  let body = opts.body;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }
  const res = await fetch(BASE + path, { method: opts.method || "GET", headers, body });
  const text = await res.text();
  let data: any = text;
  try {
    data = JSON.parse(text);
  } catch {}
  if (!res.ok) {
    const msg = (data && data.detail) || (typeof data === "string" ? data : "Something went wrong");
    throw new ApiError(res.status, msg);
  }
  return data;
}

/** Multipart upload with platform branching (per storage playbook). */
async function upload(path: string, uri: string, name: string, type: string) {
  const form = new FormData();
  if (Platform.OS === "web") {
    const blob = await (await fetch(uri)).blob();
    form.append("file", blob, name);
  } else {
    form.append("file", { uri, name, type } as any);
  }
  const headers: Record<string, string> = {};
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  const res = await fetch(BASE + path, { method: "POST", headers, body: form });
  const text = await res.text();
  let data: any = text;
  try {
    data = JSON.parse(text);
  } catch {}
  if (!res.ok) {
    const msg = (data && data.detail) || "Upload failed";
    throw new ApiError(res.status, msg);
  }
  return data;
}

export const api = {
  get: (p: string) => request(p),
  post: (p: string, json?: any) => request(p, { method: "POST", json }),
  patch: (p: string, json?: any) => request(p, { method: "PATCH", json }),
  del: (p: string) => request(p, { method: "DELETE" }),
  upload,
  uploadBulk,
};

export type UploadItem = { uri?: string; name: string; type: string; file?: any };

/** Upload many files in one multipart request (field name "files"). */
async function uploadBulk(path: string, items: UploadItem[]) {
  const form = new FormData();
  for (const it of items) {
    if (Platform.OS === "web") {
      const blob = it.file ?? (await (await fetch(it.uri!)).blob());
      form.append("files", blob, it.name);
    } else {
      form.append("files", { uri: it.uri, name: it.name, type: it.type } as any);
    }
  }
  const headers: Record<string, string> = {};
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  const res = await fetch(BASE + path, { method: "POST", headers, body: form });
  const text = await res.text();
  let data: any = text;
  try {
    data = JSON.parse(text);
  } catch {}
  if (!res.ok) {
    const msg = (data && data.detail) || "Upload failed";
    throw new ApiError(res.status, msg);
  }
  return data;
}

/** No-auth request for public shareable-gallery endpoints. */
async function publicRequest(path: string, opts: any = {}) {
  const headers: Record<string, string> = { ...(opts.headers || {}) };
  let body = opts.body;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }
  const res = await fetch(BASE + path, { method: opts.method || "GET", headers, body });
  const text = await res.text();
  let data: any = text;
  try {
    data = JSON.parse(text);
  } catch {}
  if (!res.ok) {
    const msg = (data && data.detail) || (typeof data === "string" ? data : "Something went wrong");
    throw new ApiError(res.status, msg);
  }
  return data;
}

export const publicApi = {
  get: (p: string) => publicRequest(p),
  post: (p: string, json?: any) => publicRequest(p, { method: "POST", json }),
};
