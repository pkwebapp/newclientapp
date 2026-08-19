"""Google Drive read-only integration.

Reads images from a *publicly shared* Drive folder ("Anyone with the link →
Viewer") using a single server-side API key. Original files are never copied to
our servers — we only read metadata and stream web-sized previews on demand.

A single API key (from our own Google Cloud project) can read ANY publicly
shared folder, regardless of which Google account owns it, so one key works
across all of a studio's different client Drive accounts.
"""
import os
import re
import logging

import httpx

logger = logging.getLogger(__name__)

DRIVE_LIST = "https://www.googleapis.com/drive/v3/files"
FOLDER_MIME = "application/vnd.google-apps.folder"
FIELDS = (
    "nextPageToken,files(id,name,mimeType,parents,modifiedTime,"
    "md5Checksum,size,imageMediaMetadata(width,height,rotation),hasThumbnail)"
)


class DriveError(Exception):
    """Any failure talking to Google Drive (bad key, private folder, etc.)."""


def api_key() -> str | None:
    return os.environ.get("GOOGLE_DRIVE_API_KEY") or None


def is_configured() -> bool:
    return bool(api_key())


def extract_folder_id(link: str) -> str:
    """Parse a Drive folder ID from a share link, an ?id= URL, or a raw ID."""
    s = (link or "").strip()
    if not s:
        raise DriveError("Empty Google Drive link")
    m = re.search(r"/folders/([A-Za-z0-9_-]{10,})", s)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", s)
    if m:
        return m.group(1)
    m = re.search(r"/d/([A-Za-z0-9_-]{10,})", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", s):
        return s
    raise DriveError("Could not find a Google Drive folder ID in that link")


def _list_children(client: httpx.Client, folder_id: str, key: str) -> list[dict]:
    out: list[dict] = []
    token = None
    while True:
        params = {
            "key": key,
            "q": f"'{folder_id}' in parents and trashed=false",
            "pageSize": 1000,
            "fields": FIELDS,
            "orderBy": "folder,name_natural",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if token:
            params["pageToken"] = token
        r = client.get(DRIVE_LIST, params=params, timeout=30)
        if r.status_code == 403:
            raise DriveError(
                "Access denied. Make sure the folder is shared as "
                "'Anyone with the link → Viewer' and the API key is valid."
            )
        if r.status_code == 404:
            raise DriveError("Folder not found. Check the Drive link.")
        if r.status_code >= 400:
            raise DriveError(f"Google Drive API error {r.status_code}: {r.text[:180]}")
        data = r.json()
        out.extend(data.get("files", []))
        token = data.get("nextPageToken")
        if not token:
            break
    return out


def list_folder_images(folder_id: str, max_folders: int = 2000) -> list[dict]:
    """Recursively list image files under a folder (breadth-first), preserving
    the subfolder path. Returns metadata only — never file bytes."""
    key = api_key()
    if not key:
        raise DriveError("GOOGLE_DRIVE_API_KEY is not configured on the server")

    images: list[dict] = []
    visited = 0
    with httpx.Client(timeout=30) as client:
        queue: list[tuple[str, str]] = [(folder_id, "")]
        while queue and visited < max_folders:
            fid, path = queue.pop(0)
            visited += 1
            files = _list_children(client, fid, key)
            for f in files:
                mime = f.get("mimeType", "")
                if mime == FOLDER_MIME:
                    sub = f"{path}/{f.get('name', '')}".strip("/") if path else f.get("name", "")
                    queue.append((f["id"], sub))
                elif mime.startswith("image/"):
                    meta = f.get("imageMediaMetadata") or {}
                    w, h = meta.get("width"), meta.get("height")
                    # Account for EXIF rotation so masonry ratios are correct.
                    if meta.get("rotation") in (90, 270) and w and h:
                        w, h = h, w
                    images.append({
                        "drive_file_id": f["id"],
                        "name": f.get("name"),
                        "mime_type": mime,
                        "modified_time": f.get("modifiedTime"),
                        "md5_checksum": f.get("md5Checksum"),
                        "size": f.get("size"),
                        "width": w,
                        "height": h,
                        "folder_path": path,
                    })
    return images


def _preview_candidates(file_id: str, width: int) -> list[str]:
    return [
        f"https://lh3.googleusercontent.com/d/{file_id}=w{width}",
        f"https://drive.google.com/thumbnail?id={file_id}&sz=w{width}",
    ]


def preview_bytes(file_id: str, width: int = 1600) -> tuple[bytes, str]:
    """Fetch a web-sized preview (NOT the original) for a public Drive image.
    Used both for the thumbnail proxy and for face indexing."""
    last_err = None
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        for url in _preview_candidates(file_id, width):
            try:
                r = client.get(url)
                ct = r.headers.get("content-type", "")
                if r.status_code == 200 and r.content and ct.startswith("image/"):
                    return r.content, ct
                last_err = f"{r.status_code} {ct}"
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
    raise DriveError(f"Could not fetch preview for {file_id}: {last_err}")
