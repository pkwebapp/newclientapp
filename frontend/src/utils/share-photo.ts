import { Platform } from "react-native";
import * as FileSystem from "expo-file-system/legacy";
import * as ImageManipulator from "expo-image-manipulator";
import * as Sharing from "expo-sharing";
import { fileUrl } from "@/src/api/client";

const MAX_SHARE_BYTES = 2 * 1024 * 1024;
const FIRST_COMPRESSION = 0.78;
const SECOND_COMPRESSION = 0.62;

type SharePhoto = {
  photo_id: string;
  url?: string | null;
  thumb_url?: string | null;
  storage_path?: string | null;
  thumb_path?: string | null;
  filename?: string | null;
};

function photoUrl(photo: SharePhoto): string | undefined {
  return photo.url || photo.thumb_url || fileUrl(photo.storage_path || photo.thumb_path);
}

function photoName(photo: SharePhoto): string {
  const raw = (photo.filename || `pik-connect-${photo.photo_id}.jpg`).trim();
  const stem = raw.replace(/\.[^/.]+$/, "").replace(/[^a-z0-9-_]+/gi, "-") || `pik-connect-${photo.photo_id}`;
  return `${stem}.jpg`;
}

async function fileSize(uri: string): Promise<number> {
  const info = await FileSystem.getInfoAsync(uri);
  return info.exists && typeof info.size === "number" ? info.size : 0;
}

async function compressNativeIfNeeded(uri: string): Promise<{ uri: string; created: string[] }> {
  const created: string[] = [];
  if ((await fileSize(uri)) <= MAX_SHARE_BYTES) return { uri, created };

  let result = await ImageManipulator.manipulateAsync(uri, [], {
    compress: FIRST_COMPRESSION,
    format: ImageManipulator.SaveFormat.JPEG,
  });
  created.push(result.uri);
  if ((await fileSize(result.uri)) <= MAX_SHARE_BYTES) return { uri: result.uri, created };

  result = await ImageManipulator.manipulateAsync(
    result.uri,
    [{ resize: { width: 2000 } }],
    { compress: SECOND_COMPRESSION, format: ImageManipulator.SaveFormat.JPEG },
  );
  created.push(result.uri);
  return { uri: result.uri, created };
}

async function compressWebIfNeeded(blob: Blob): Promise<Blob> {
  if (blob.size <= MAX_SHARE_BYTES) return blob;

  const sourceUrl = URL.createObjectURL(blob);
  try {
    let result = await ImageManipulator.manipulateAsync(sourceUrl, [], {
      compress: FIRST_COMPRESSION,
      format: ImageManipulator.SaveFormat.JPEG,
    });
    let compressed = await (await fetch(result.uri)).blob();
    if (compressed.size <= MAX_SHARE_BYTES) return compressed;

    result = await ImageManipulator.manipulateAsync(
      result.uri,
      [{ resize: { width: 2000 } }],
      { compress: SECOND_COMPRESSION, format: ImageManipulator.SaveFormat.JPEG },
    );
    compressed = await (await fetch(result.uri)).blob();
    return compressed;
  } finally {
    URL.revokeObjectURL(sourceUrl);
  }
}

async function shareOnWeb(url: string, name: string): Promise<"shared" | "downloaded"> {
  const response = await fetch(url);
  if (!response.ok) throw new Error("Could not download this photo for sharing");
  const blob = await compressWebIfNeeded(await response.blob());
  const file = typeof File !== "undefined" ? new File([blob], name, { type: "image/jpeg" }) : null;
  const webNavigator = typeof navigator !== "undefined" ? (navigator as any) : null;

  if (file && webNavigator?.share && webNavigator?.canShare?.({ files: [file] })) {
    await webNavigator.share({ files: [file], title: "PIK Connect photo" });
    return "shared";
  }

  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
  return "downloaded";
}

/** Shares the image bytes through the native share sheet, not a PIK Connect link. */
export async function sharePhotoFile(photo: SharePhoto): Promise<"shared" | "downloaded"> {
  const url = photoUrl(photo);
  if (!url) throw new Error("This photo is unavailable for sharing");
  const name = photoName(photo);

  if (Platform.OS === "web") return shareOnWeb(url, name);

  if (!(await Sharing.isAvailableAsync())) {
    throw new Error("Photo sharing is not available on this device");
  }
  if (!FileSystem.cacheDirectory) throw new Error("Temporary photo storage is unavailable");

  const sourceUri = `${FileSystem.cacheDirectory}pik-share-${photo.photo_id}.jpg`;
  const downloaded = await FileSystem.downloadAsync(url, sourceUri);
  const compressed = await compressNativeIfNeeded(downloaded.uri);
  try {
    await Sharing.shareAsync(compressed.uri, {
      mimeType: "image/jpeg",
      UTI: "public.jpeg",
      dialogTitle: "Share photo",
    });
    return "shared";
  } finally {
    for (const uri of [downloaded.uri, ...compressed.created]) {
      await FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {});
    }
  }
}
