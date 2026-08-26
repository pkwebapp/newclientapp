import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";
import * as FileSystem from "expo-file-system/legacy";

import { imgUrl } from "@/src/api/client";

const CACHE_PREFIX = "pik-offline-gallery-v1:";
const WEB_CACHE_NAME = "pik-offline-photo-previews-v1";

type CachedPhoto = Record<string, any>;
type CachedGallery = {
  event: Record<string, any>;
  photos: CachedPhoto[];
  matchedIds: string[];
  likedIds: string[];
  searched: boolean;
  cachedAt: string;
};
type PendingLike = { eventId: string; photoId: string; liked: boolean };

const metadataKey = (eventId: string) => `${CACHE_PREFIX}${eventId}`;
const localPhotoUri = (eventId: string, photoId: string) => {
  const root = FileSystem.documentDirectory;
  return root ? `${root}pik-offline/${eventId}/${photoId}.jpg` : null;
};

function photoSource(photo: CachedPhoto): string | undefined {
  return imgUrl(photo.thumb_url || photo.url, photo.thumb_path || photo.storage_path);
}

async function cacheNativePhoto(eventId: string, photo: CachedPhoto): Promise<void> {
  const source = photoSource(photo);
  const destination = localPhotoUri(eventId, photo.photo_id);
  if (!source || !destination) return;
  const info = await FileSystem.getInfoAsync(destination);
  if (info.exists) return;
  const directory = destination.slice(0, destination.lastIndexOf("/"));
  await FileSystem.makeDirectoryAsync(directory, { intermediates: true });
  await FileSystem.downloadAsync(source, destination);
}

async function cacheWebPhoto(photo: CachedPhoto): Promise<void> {
  const source = photoSource(photo);
  if (!source || typeof caches === "undefined") return;
  const cache = await caches.open(WEB_CACHE_NAME);
  if (await cache.match(source)) return;
  const response = await fetch(source);
  if (response.ok) await cache.put(source, response.clone());
}

export async function cachePhotoPreview(eventId: string, photo: CachedPhoto): Promise<void> {
  try {
    if (Platform.OS === "web") await cacheWebPhoto(photo);
    else await cacheNativePhoto(eventId, photo);
  } catch {
    // A single failed preview must not interrupt gallery loading or caching.
  }
}

async function cachedPhotoUri(eventId: string, photo: CachedPhoto): Promise<string | undefined> {
  if (Platform.OS !== "web") {
    const local = localPhotoUri(eventId, photo.photo_id);
    if (!local) return undefined;
    const info = await FileSystem.getInfoAsync(local);
    return info.exists ? local : undefined;
  }
  const source = photoSource(photo);
  if (!source || typeof caches === "undefined") return undefined;
  const cache = await caches.open(WEB_CACHE_NAME);
  const response = await cache.match(source);
  if (!response) return undefined;
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function cacheGallery(
  eventId: string,
  event: Record<string, any>,
  photos: CachedPhoto[],
  likedIds: string[] = [],
  matchedIds: string[] = [],
  searched = false,
): Promise<void> {
  try {
    const existing = await AsyncStorage.getItem(metadataKey(eventId));
    const previous: CachedGallery | null = existing ? JSON.parse(existing) : null;
    const byId = new Map<string, CachedPhoto>();
    for (const photo of previous?.photos || []) byId.set(photo.photo_id, photo);
    for (const photo of photos) byId.set(photo.photo_id, photo);
    const payload: CachedGallery = {
      event,
      photos: Array.from(byId.values()),
      matchedIds: matchedIds.length ? matchedIds : previous?.matchedIds || [],
      likedIds: Array.from(new Set(likedIds)),
      searched: searched || previous?.searched || false,
      cachedAt: new Date().toISOString(),
    };
    await AsyncStorage.setItem(metadataKey(eventId), JSON.stringify(payload));

    const list = payload.photos;
    for (let i = 0; i < list.length; i += 4) {
      await Promise.all(list.slice(i, i + 4).map((photo) => cachePhotoPreview(eventId, photo)));
    }
  } catch {
    // Offline caching is best effort and must never block the online gallery.
  }
}

export async function restoreCachedGallery(eventId: string): Promise<CachedGallery | null> {
  try {
    const raw = await AsyncStorage.getItem(metadataKey(eventId));
    if (!raw) return null;
    const payload = JSON.parse(raw) as CachedGallery;
    const photos = await Promise.all(
      payload.photos.map(async (photo) => {
        const uri = await cachedPhotoUri(eventId, photo);
        return uri ? { ...photo, thumb_url: uri, url: uri } : photo;
      }),
    );
    return { ...payload, photos };
  } catch {
    return null;
  }
}

export async function queueLikeAction(action: PendingLike): Promise<void> {
  try {
    const raw = await AsyncStorage.getItem(`${CACHE_PREFIX}likes`);
    const actions: PendingLike[] = raw ? JSON.parse(raw) : [];
    const next = actions.filter((item) => !(item.eventId === action.eventId && item.photoId === action.photoId));
    next.push(action);
    await AsyncStorage.setItem(`${CACHE_PREFIX}likes`, JSON.stringify(next));
  } catch {
    // Keep the optimistic UI even if local action storage is unavailable.
  }
}

export async function pendingLikeActions(eventId: string): Promise<PendingLike[]> {
  try {
    const raw = await AsyncStorage.getItem(`${CACHE_PREFIX}likes`);
    const actions: PendingLike[] = raw ? JSON.parse(raw) : [];
    return actions.filter((item) => item.eventId === eventId);
  } catch {
    return [];
  }
}

export async function removeLikeActions(eventId: string, photoIds: string[]): Promise<void> {
  try {
    const raw = await AsyncStorage.getItem(`${CACHE_PREFIX}likes`);
    const actions: PendingLike[] = raw ? JSON.parse(raw) : [];
    const ids = new Set(photoIds);
    await AsyncStorage.setItem(
      `${CACHE_PREFIX}likes`,
      JSON.stringify(actions.filter((item) => item.eventId !== eventId || !ids.has(item.photoId))),
    );
  } catch {
    // Best effort cleanup.
  }
}

// --- Lightweight per-tab cache for the public share-link gallery ---
// Stores just the photo metadata for the last view so returning visitors see
// the grid instantly while fresh data is fetched in the background.
const PUBLIC_TAB_PREFIX = "pik-public-tab-v1:";
const publicTabKey = (eventId: string, tab: string) => `${PUBLIC_TAB_PREFIX}${eventId}:${tab}`;

export async function cachePublicTab(eventId: string, tab: string, photos: CachedPhoto[]): Promise<void> {
  try {
    await AsyncStorage.setItem(publicTabKey(eventId, tab), JSON.stringify(photos.slice(0, 120)));
  } catch {
    // Warm-up cache is best effort and must never block the gallery.
  }
}

export async function restorePublicTab(eventId: string, tab: string): Promise<CachedPhoto[]> {
  try {
    const raw = await AsyncStorage.getItem(publicTabKey(eventId, tab));
    return raw ? (JSON.parse(raw) as CachedPhoto[]) : [];
  } catch {
    return [];
  }
}
