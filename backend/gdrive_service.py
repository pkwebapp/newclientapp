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
import html as _html
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
    # A bare folder ID (Drive IDs are long, ~25-44 chars, no spaces).
    if re.fullmatch(r"[A-Za-z0-9_-]{25,}", s):
        return s
    raise DriveError("That doesn't look like a Google Drive folder link. Paste the folder's share link.")


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
    the subfolder path. Returns metadata only — never file bytes.

    Uses the Drive API when GOOGLE_DRIVE_API_KEY is set (richer metadata:
    md5/modifiedTime/dimensions). Otherwise falls back to reading the *public*
    folder view, which needs no key for 'Anyone with the link → Viewer'
    folders."""
    if api_key():
        return _list_via_api(folder_id, max_folders)
    return _list_via_public(folder_id, max_folders)


def _list_via_api(folder_id: str, max_folders: int = 2000) -> list[dict]:
    key = api_key()

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


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif", ".tif", ".tiff")
PUBLIC_VIEW = "https://drive.google.com/embeddedfolderview?id={fid}#grid"
_ACCESS_WALL_MARKERS = ("accounts.google.com", "servicelogin", "you need access", "request access")


def _looks_like_image(name: str, mime: str) -> bool:
    if mime.startswith("image/"):
        return True
    return (name or "").lower().endswith(IMAGE_EXTS)


_ANCHOR_RE = re.compile(
    r'<a href="(https://drive\.google\.com/[^"]+)"[^>]*>.*?'
    r'<div class="flip-entry-title">(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)


def _parse_public_entries(html_text: str) -> list[dict]:
    """Parse an embeddedfolderview HTML page into entries {id,name,kind}.

    Primary: anchor href tells file (/file/d/ID) vs folder (/folders/ID).
    Fallback: older id="entry-ID" markers when anchors are absent."""
    entries: list[dict] = []
    seen: set[str] = set()

    for href, title in _ANCHOR_RE.findall(html_text):
        name = _html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        fm = re.search(r"/file/d/([A-Za-z0-9_-]{10,})", href)
        if fm:
            fid, kind = fm.group(1), "file"
        else:
            dm = re.search(r"/folders/([A-Za-z0-9_-]{10,})", href) or re.search(
                r"[?&]id=([A-Za-z0-9_-]{10,})", href
            )
            if not dm:
                continue
            fid, kind = dm.group(1), "folder"
        if fid in seen:
            continue
        seen.add(fid)
        entries.append({"id": fid, "name": name, "kind": kind})

    if entries:
        return entries

    # Fallback parser (older markup): id="entry-<ID>" + type icon.
    for part in html_text.split('id="entry-')[1:]:
        end = part.find('"')
        if end <= 0:
            continue
        fid = part[:end]
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,}", fid) or fid in seen:
            continue
        block = part[:4000]
        tm = re.search(r"flip-entry-title[^>]*>([^<]*)<", block)
        name = _html.unescape(tm.group(1)).strip() if tm else fid
        is_folder = f"/type/{FOLDER_MIME}" in block
        seen.add(fid)
        entries.append({"id": fid, "name": name, "kind": "folder" if is_folder else "file"})
    return entries


def _list_via_public(folder_id: str, max_folders: int = 2000) -> list[dict]:
    """Read a PUBLIC Drive folder with NO API key by parsing the embedded
    folder view. Recurses into subfolders and preserves paths. Metadata is
    limited (no md5/modifiedTime/dimensions)."""
    images: list[dict] = []
    visited: set[str] = set()
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        queue: list[tuple[str, str]] = [(folder_id, "")]
        folders_seen = 0
        while queue and folders_seen < max_folders:
            fid, path = queue.pop(0)
            if fid in visited:
                continue
            visited.add(fid)
            folders_seen += 1
            try:
                r = client.get(PUBLIC_VIEW.format(fid=fid))
            except Exception as e:  # noqa: BLE001
                raise DriveError(f"Could not reach Google Drive: {e}")
            text = r.text or ""
            entries = _parse_public_entries(text)
            if not entries and fid == folder_id:
                low = text.lower()
                if any(mk in low for mk in _ACCESS_WALL_MARKERS):
                    raise DriveError(
                        "This folder isn't public. Share it as 'Anyone with the "
                        "link → Viewer' and try again."
                    )
            for e in entries:
                if e["kind"] == "folder":
                    sub = f"{path}/{e['name']}".strip("/") if path else e["name"]
                    queue.append((e["id"], sub))
                elif _looks_like_image(e["name"], ""):
                    images.append({
                        "drive_file_id": e["id"],
                        "name": e["name"],
                        "mime_type": "image/jpeg",
                        "modified_time": None,
                        "md5_checksum": None,
                        "size": None,
                        "width": None,
                        "height": None,
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
