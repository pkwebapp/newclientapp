"""Album module routes — separate product from the photo Gallery.

Mounted as its own APIRouter(prefix="/api/albums") and included from server.py
with a single line. It reuses shared infrastructure (Mongo, Cloudinary storage,
admin auth) but has its own collection (`albums`), upload pipeline, and the
self-contained WebGL flipbook viewer.
"""
import io
import os
import uuid
import base64
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import qrcode
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from config import db, APP_NAME, PUBLIC_BASE_URL
from storage_service import get_storage
from auth_utils import require_admin
import album_service

logger = logging.getLogger(__name__)

album_router = APIRouter(prefix="/api/albums")

VIEWER_HTML_PATH = Path(__file__).parent / "album_viewer.html"
THREE_JS_PATH = Path(__file__).parent / "static" / "three.module.js"


@album_router.get("/assets/three.module.js")
async def three_module():
    try:
        data = THREE_JS_PATH.read_bytes()
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(content=data, media_type="application/javascript",
                    headers={"Cache-Control": "public, max-age=604800"})


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_prefix(album_id: str) -> str:
    return f"{APP_NAME}/albums/{album_id}"


def _asset_urls(node: Optional[dict]) -> Optional[dict]:
    """Turn stored asset paths into public CDN URLs for the viewer."""
    if not node:
        return None
    storage = get_storage()
    urls = {}
    for level, path in (node.get("assets") or {}).items():
        try:
            urls[level] = storage.public_url(path)
        except Exception:
            urls[level] = None
    return {
        "kind": node.get("kind"),
        "ratio": node.get("ratio"),
        "width_pt": node.get("width_pt"),
        "height_pt": node.get("height_pt"),
        "dims": node.get("master_dims"),
        "urls": urls,
    }


def _admin_album_public(a: dict) -> dict:
    """Admin-facing album summary (no raw storage paths)."""
    return {
        "album_id": a["album_id"],
        "title": a.get("title"),
        "client_name": a.get("client_name"),
        "event_name": a.get("event_name"),
        "status": a.get("status", "draft"),
        "total_spreads": a.get("total_spreads", 0),
        "page_count": a.get("page_count", 0),
        "has_pdf": bool(a.get("cover") or a.get("spreads")),
        "cover_url": (_asset_urls(a.get("cover")) or {}).get("urls", {}).get("thumb")
        if a.get("cover") else None,
        "warnings": a.get("warnings", []),
        "share_token": a.get("share_token"),
        "share_url": f"{PUBLIC_BASE_URL}/a/{a.get('share_token')}",
        "preview_url": f"{PUBLIC_BASE_URL}/a/{a.get('share_token')}?k={a.get('preview_token')}",
        "created_at": a.get("created_at"),
        "updated_at": a.get("updated_at"),
    }


def _viewer_manifest(a: dict) -> dict:
    """Public manifest the WebGL viewer consumes."""
    return {
        "album_id": a["album_id"],
        "title": a.get("title"),
        "client_name": a.get("client_name"),
        "event_name": a.get("event_name"),
        "total_spreads": a.get("total_spreads", 0),
        "settings": {
            "auto_open": a.get("auto_open", False),
            "page_turn_sound": a.get("page_turn_sound", False),
        },
        "cover": _asset_urls(a.get("cover")),
        "spreads": [_asset_urls(s) for s in a.get("spreads", [])],
        "back_cover": _asset_urls(a.get("back_cover")),
    }


# ---------------------------------------------------------------------------
# Admin CRUD
# ---------------------------------------------------------------------------
class AlbumCreate(BaseModel):
    title: str
    client_name: Optional[str] = None
    event_name: Optional[str] = None


class AlbumUpdate(BaseModel):
    title: Optional[str] = None
    client_name: Optional[str] = None
    event_name: Optional[str] = None
    auto_open: Optional[bool] = None
    page_turn_sound: Optional[bool] = None


async def _admin_album_or_404(album_id: str, admin: dict) -> dict:
    a = await db.albums.find_one({"album_id": album_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Album not found")
    if a.get("created_by") != admin["user_id"]:
        raise HTTPException(status_code=403, detail="Not your album")
    return a


@album_router.post("")
async def create_album(body: AlbumCreate, admin: dict = Depends(require_admin)):
    album_id = f"alb_{uuid.uuid4().hex[:12]}"
    doc = {
        "album_id": album_id,
        "title": body.title.strip() or "Untitled Album",
        "client_name": (body.client_name or "").strip() or None,
        "event_name": (body.event_name or "").strip() or None,
        "status": "draft",
        "share_token": uuid.uuid4().hex + uuid.uuid4().hex[:8],
        "preview_token": uuid.uuid4().hex[:16],
        "auto_open": False,
        "page_turn_sound": False,
        "page_count": 0,
        "total_spreads": 0,
        "cover": None,
        "spreads": [],
        "back_cover": None,
        "warnings": [],
        "created_by": admin["user_id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.albums.insert_one(doc)
    return _admin_album_public(doc)


@album_router.get("")
async def list_albums(admin: dict = Depends(require_admin)):
    items = await db.albums.find({"created_by": admin["user_id"]}, {"_id": 0}) \
        .sort("created_at", -1).to_list(500)
    return [_admin_album_public(a) for a in items]


@album_router.get("/{album_id}")
async def get_album(album_id: str, admin: dict = Depends(require_admin)):
    a = await _admin_album_or_404(album_id, admin)
    out = _admin_album_public(a)
    out["manifest"] = _viewer_manifest(a)
    return out


@album_router.patch("/{album_id}")
async def update_album(album_id: str, body: AlbumUpdate, admin: dict = Depends(require_admin)):
    await _admin_album_or_404(album_id, admin)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        updates["updated_at"] = now_iso()
        await db.albums.update_one({"album_id": album_id}, {"$set": updates})
    a = await db.albums.find_one({"album_id": album_id}, {"_id": 0})
    return _admin_album_public(a)


@album_router.post("/{album_id}/pdf")
async def upload_pdf(album_id: str, file: UploadFile = File(...),
                     admin: dict = Depends(require_admin)):
    a = await _admin_album_or_404(album_id, admin)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    fname = (file.filename or "").lower()
    if not (fname.endswith(".pdf") or (file.content_type or "").endswith("pdf")):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    storage = get_storage()
    # Remove any previously rendered assets (Replace PDF flow).
    try:
        await run_in_threadpool(storage.delete_prefix, _base_prefix(album_id))
    except Exception as e:
        logger.error(f"album {album_id}: delete old assets failed: {e}")

    try:
        result = await run_in_threadpool(
            album_service.render_album_assets, data, storage.put_object, _base_prefix(album_id)
        )
    except Exception as e:
        logger.error(f"album {album_id}: PDF processing failed: {e}")
        raise HTTPException(
            status_code=400,
            detail="Unable to process this album PDF. Please check the PDF format and try again.",
        )

    await db.albums.update_one({"album_id": album_id}, {"$set": {
        "page_count": result["page_count"],
        "total_spreads": result["total_spreads"],
        "cover": result["cover"],
        "spreads": result["spreads"],
        "back_cover": result["back_cover"],
        "warnings": result["warnings"],
        "updated_at": now_iso(),
    }})
    a = await db.albums.find_one({"album_id": album_id}, {"_id": 0})
    return _admin_album_public(a)


@album_router.post("/{album_id}/publish")
async def publish_album(album_id: str, admin: dict = Depends(require_admin)):
    a = await _admin_album_or_404(album_id, admin)
    if not (a.get("cover") or a.get("spreads")):
        raise HTTPException(status_code=400, detail="Upload a PDF before publishing")
    await db.albums.update_one({"album_id": album_id},
                               {"$set": {"status": "published", "updated_at": now_iso()}})
    a = await db.albums.find_one({"album_id": album_id}, {"_id": 0})
    return _admin_album_public(a)


@album_router.post("/{album_id}/unpublish")
async def unpublish_album(album_id: str, admin: dict = Depends(require_admin)):
    await _admin_album_or_404(album_id, admin)
    await db.albums.update_one({"album_id": album_id},
                               {"$set": {"status": "draft", "updated_at": now_iso()}})
    a = await db.albums.find_one({"album_id": album_id}, {"_id": 0})
    return _admin_album_public(a)


@album_router.delete("/{album_id}")
async def delete_album(album_id: str, admin: dict = Depends(require_admin)):
    await _admin_album_or_404(album_id, admin)
    removed = 0
    try:
        removed = await run_in_threadpool(get_storage().delete_prefix, _base_prefix(album_id))
    except Exception as e:
        logger.error(f"album {album_id}: delete assets failed: {e}")
    await db.albums.delete_one({"album_id": album_id})
    return {"status": "deleted", "album_id": album_id, "assets_deleted": removed}


def _qr_b64(data: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=16, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0D0D0D", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@album_router.get("/{album_id}/share")
async def album_share(album_id: str, admin: dict = Depends(require_admin)):
    a = await _admin_album_or_404(album_id, admin)
    share_url = f"{PUBLIC_BASE_URL}/a/{a['share_token']}"
    preview_url = f"{share_url}?k={a['preview_token']}"
    return {
        "share_url": share_url,
        "preview_url": preview_url,
        "status": a.get("status", "draft"),
        "qr_base64": _qr_b64(share_url),
    }


# ---------------------------------------------------------------------------
# Public — manifest + self-contained viewer (no auth; unguessable share token)
# ---------------------------------------------------------------------------
async def _load_public_album(token: str, preview_key: Optional[str]) -> dict:
    a = await db.albums.find_one({"share_token": token}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Album not found")
    is_preview = bool(preview_key) and preview_key == a.get("preview_token")
    if a.get("status") != "published" and not is_preview:
        raise HTTPException(status_code=403, detail="This album is not published")
    if not (a.get("cover") or a.get("spreads")):
        raise HTTPException(status_code=404, detail="Album has no pages yet")
    return a


@album_router.get("/public/{token}")
async def public_manifest(token: str, k: Optional[str] = None):
    a = await _load_public_album(token, k)
    return _viewer_manifest(a)


@album_router.get("/public/{token}/view", response_class=HTMLResponse)
async def public_view(token: str, k: Optional[str] = None):
    # Validate existence/visibility up-front so we don't serve a viewer shell
    # for a private/missing album.
    await _load_public_album(token, k)
    try:
        html = VIEWER_HTML_PATH.read_text(encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=500, detail="Viewer unavailable")
    manifest_url = f"{PUBLIC_BASE_URL}/api/albums/public/{token}"
    if k:
        manifest_url += f"?k={k}"
    html = html.replace("__MANIFEST_URL__", manifest_url)
    html = html.replace("__THREE_URL__", f"{PUBLIC_BASE_URL}/api/albums/assets/three.module.js")
    return HTMLResponse(content=html)
