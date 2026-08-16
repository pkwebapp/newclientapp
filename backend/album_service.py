"""Album module — PDF → optimized flipbook spread assets.

This module is fully independent of the photo Gallery. It reads a designed
physical photo-album PDF and turns each page into optimized, multi-resolution
JPEG textures the WebGL viewer consumes. The original PDF is the source of
truth and is never modified or exposed publicly.

Expected physical album structure (aspect ratio = height / width):
  - Front cover : 12 x 18 in  -> a single page, ratio ~= 0.667 (landscape page)
  - Interior    : 12 x 36 in  -> a lay-flat spread (2 pages), ratio ~= 0.333
  - ...
  - Back cover  : 12 x 18 in  -> a single page, ratio ~= 0.667
"""
import io
import logging

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)

# Aspect-ratio targets (height / width) with generous tolerance so PDFs whose
# metadata is slightly off are still recognised instead of rejected outright.
COVER_RATIO = 12 / 18      # 0.667  -> single page (cover / back cover)
SPREAD_RATIO = 12 / 36     # 0.333  -> continuous interior spread
RATIO_TOLERANCE = 0.10

# Rendered JPEG long-edge sizes (px). "high" balances face/skin/text detail
# against browser memory; the viewer lazy-loads and zoom uses "high".
RES_LEVELS = {"thumb": 700, "medium": 1500, "high": 3000}
JPEG_QUALITY = {"thumb": 72, "medium": 82, "high": 88}


def _classify(ratio: float) -> str:
    """Return 'cover' | 'spread' | 'unknown' for a page height/width ratio."""
    if abs(ratio - COVER_RATIO) <= RATIO_TOLERANCE:
        return "cover"
    if abs(ratio - SPREAD_RATIO) <= RATIO_TOLERANCE:
        return "spread"
    return "unknown"


def _render_page_png(page: "fitz.Page", target_long_edge: int) -> bytes:
    """Render a single PDF page to PNG bytes at approximately the requested
    long-edge resolution."""
    rect = page.rect
    long_edge_pt = max(rect.width, rect.height) or 1.0
    zoom = target_long_edge / long_edge_pt
    # Cap zoom so tiny-defined PDFs don't explode memory.
    zoom = max(0.2, min(zoom, 8.0))
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes("png")


def _to_jpeg(png_bytes: bytes, long_edge: int, quality: int) -> tuple[bytes, int, int]:
    """Resize (if needed) and encode as optimized JPEG."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    scale = long_edge / max(w, h)
    if scale < 1:
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue(), img.size[0], img.size[1]


def inspect_pdf(pdf_bytes: bytes) -> dict:
    """Read page count + per-page dimensions/classification without rendering.
    Used for fast validation feedback before committing to a full render."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i in range(doc.page_count):
        r = doc.load_page(i).rect
        w, h = float(r.width), float(r.height)
        ratio = (h / w) if w else 0
        pages.append({"index": i, "width_pt": w, "height_pt": h,
                      "ratio": round(ratio, 4), "kind": _classify(ratio)})
    doc.close()
    return {"page_count": len(pages), "pages": pages}


def analyze_structure(pages: list[dict]) -> tuple[str, str, list[str]]:
    """Given inspected pages, decide cover / spreads / back-cover roles and
    collect human-readable warnings. Never raises — the admin may proceed."""
    warnings: list[str] = []
    n = len(pages)
    if n < 2:
        warnings.append("The PDF has fewer than 2 pages; an album needs at least a cover and one spread.")

    covers = [p for p in pages if p["kind"] == "cover"]
    spreads = [p for p in pages if p["kind"] == "spread"]
    unknown = [p for p in pages if p["kind"] == "unknown"]

    if unknown:
        warnings.append(
            "This PDF does not appear to follow the standard 12x18 cover / 12x36 "
            f"spread album format ({len(unknown)} page(s) had an unexpected shape)."
        )
    if not covers:
        warnings.append("No 12x18 cover page detected; the first page will be used as the cover.")
    if not spreads:
        warnings.append("No 12x36 interior spreads detected.")
    return "ok", "ok", warnings


def assign_roles(pages: list[dict]) -> dict:
    """Map inspected pages to roles: first page -> front cover, last -> back
    cover, everything in between -> interior spreads (in order)."""
    n = len(pages)
    front = pages[0] if n else None
    back = pages[-1] if n >= 2 else None
    middle = pages[1:-1] if n >= 3 else (pages[1:] if n == 2 else [])
    return {"front": front, "back": back, "spreads": middle}


def render_album_assets(pdf_bytes: bytes, put_object, base_prefix: str) -> dict:
    """Full pipeline: inspect -> assign roles -> render each needed page to 3
    JPEG resolutions -> store via ``put_object(path, bytes, content_type)``.

    Returns a manifest-ready structure. ``put_object`` is the storage backend's
    method so this module stays storage-agnostic.
    """
    info = inspect_pdf(pdf_bytes)
    pages = info["pages"]
    _, _, warnings = analyze_structure(pages)
    roles = assign_roles(pages)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    def render_and_store(page_index: int, kind: str, key: str) -> dict:
        page = doc.load_page(page_index)
        # Render once at the highest needed resolution, then downscale for the
        # smaller levels (faster + consistent).
        master_png = _render_page_png(page, RES_LEVELS["high"])
        assets = {}
        dims = {}
        for level, long_edge in RES_LEVELS.items():
            jpeg, w, h = _to_jpeg(master_png, long_edge, JPEG_QUALITY[level])
            path = f"{base_prefix}/{key}_{level}.jpg"
            put_object(path, jpeg, "image/jpeg")
            assets[level] = path
            dims[level] = {"w": w, "h": h}
        r = page.rect
        return {
            "kind": kind,
            "page_index": page_index,
            "width_pt": float(r.width),
            "height_pt": float(r.height),
            "ratio": round((r.height / r.width) if r.width else 0, 4),
            "assets": assets,
            "master_dims": dims["high"],
        }

    manifest_cover = None
    manifest_back = None
    manifest_spreads = []

    if roles["front"] is not None:
        manifest_cover = render_and_store(roles["front"]["index"], "cover", "cover")
    for i, sp in enumerate(roles["spreads"]):
        manifest_spreads.append(render_and_store(sp["index"], "spread", f"spread_{i:03d}"))
    if roles["back"] is not None and roles["back"] is not roles["front"]:
        manifest_back = render_and_store(roles["back"]["index"], "back_cover", "back_cover")

    doc.close()

    return {
        "page_count": info["page_count"],
        "total_spreads": len(manifest_spreads),
        "cover": manifest_cover,
        "spreads": manifest_spreads,
        "back_cover": manifest_back,
        "warnings": warnings,
    }
