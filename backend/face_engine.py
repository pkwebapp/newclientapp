"""Pluggable face-recognition engine.

The app depends only on the `FaceEngine` interface. `MockFaceEngine` provides a
deterministic, no-cost implementation for development and demos. A
`RekognitionFaceEngine` can be dropped in (AWS Rekognition Collections) once AWS
credentials are configured, without touching any route code.

Selfie quality checks (brightness / blur / resolution) are performed with Pillow
+ numpy and are REAL — they run identically regardless of the active engine.
Side-profile (>45 deg) and face-out-of-frame checks require true face detection
and are therefore performed only by the Rekognition engine.
"""
import io
import hashlib
import random
import logging

import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Quality thresholds (tuned to be lenient enough to avoid false rejects while
# still catching genuinely unusable selfies).
MIN_RESOLUTION = 120        # px, shortest side
DARK_THRESHOLD = 35         # mean luminance 0-255
GLARE_THRESHOLD = 240       # mean luminance 0-255
BLUR_THRESHOLD = 6.0        # variance of Laplacian


class QualityResult:
    def __init__(self, ok: bool, reason: str | None = None):
        self.ok = ok
        self.reason = reason

    def to_dict(self):
        return {"ok": self.ok, "reason": self.reason}


def _variance_of_laplacian(gray: np.ndarray) -> float:
    lap = (
        -4.0 * gray
        + np.roll(gray, 1, axis=0)
        + np.roll(gray, -1, axis=0)
        + np.roll(gray, 1, axis=1)
        + np.roll(gray, -1, axis=1)
    )
    return float(lap[1:-1, 1:-1].var())


def check_selfie_quality(image_bytes: bytes) -> QualityResult:
    """Real, engine-agnostic quality gate. Sunglasses/makeup/beard are NOT
    checked here — those are acceptable and must not block search."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        return QualityResult(False, "We couldn't read that photo. Please retake.")

    w, h = img.size
    if min(w, h) < MIN_RESOLUTION:
        return QualityResult(False, "Photo is too small. Move closer and retake.")

    gray = np.asarray(img.convert("L"), dtype=np.float64)
    brightness = float(gray.mean())
    if brightness < DARK_THRESHOLD:
        return QualityResult(False, "It's too dark. Find better lighting and retake.")
    if brightness > GLARE_THRESHOLD:
        return QualityResult(False, "Too much glare. Reduce lighting and retake.")

    if _variance_of_laplacian(gray) < BLUR_THRESHOLD:
        return QualityResult(False, "The photo looks blurry. Hold steady and retake.")

    return QualityResult(True)


class FaceEngine:
    """Interface for face detection / indexing / search-by-image."""

    name = "base"

    def create_collection(self, event_id: str) -> str:
        raise NotImplementedError

    def index_photo(self, collection_id: str, photo_id: str, image_bytes: bytes) -> list[dict]:
        """Detect + index all faces in a photo. Returns list of
        {face_id, bounding_box}."""
        raise NotImplementedError

    def search(self, collection_id: str, image_bytes: bytes, threshold: float,
               faces: list[dict], client_seed: str) -> list[dict]:
        """Search the collection for the person in image_bytes. Returns list of
        {face_id, photo_id, similarity} above `threshold`."""
        raise NotImplementedError

    def delete_faces(self, collection_id: str, face_ids: list[str]) -> None:
        raise NotImplementedError

    def delete_collection(self, collection_id: str) -> None:
        raise NotImplementedError


class MockFaceEngine(FaceEngine):
    """Deterministic stand-in. Faces-per-photo and per-client matches are derived
    from stable hashes so results are consistent across re-runs, giving a
    believable end-to-end experience with zero external cost."""

    name = "mock"

    def create_collection(self, event_id: str) -> str:
        return f"mock-collection-{event_id}"

    def index_photo(self, collection_id: str, photo_id: str, image_bytes: bytes) -> list[dict]:
        seed = int(hashlib.sha256(photo_id.encode()).hexdigest(), 16)
        rng = random.Random(seed)
        n = rng.randint(1, 4)  # 1-4 faces per photo
        faces = []
        for i in range(n):
            faces.append({
                "face_id": f"{photo_id}:{i}",
                "bounding_box": {
                    "Left": round(rng.uniform(0.05, 0.6), 3),
                    "Top": round(rng.uniform(0.05, 0.6), 3),
                    "Width": round(rng.uniform(0.1, 0.3), 3),
                    "Height": round(rng.uniform(0.1, 0.3), 3),
                },
            })
        return faces

    def search(self, collection_id: str, image_bytes: bytes, threshold: float,
               faces: list[dict], client_seed: str) -> list[dict]:
        if not faces:
            return []
        seed = int(hashlib.sha256(client_seed.encode()).hexdigest(), 16)
        rng = random.Random(seed)
        # Each client "matches" a deterministic ~20-40% subset of faces.
        match_fraction = rng.uniform(0.2, 0.4)
        matches = []
        for f in faces:
            fseed = int(hashlib.sha256((client_seed + f["face_id"]).encode()).hexdigest(), 16)
            frng = random.Random(fseed)
            if frng.random() < match_fraction:
                similarity = round(frng.uniform(threshold, 99.7), 2)
                matches.append({
                    "face_id": f["face_id"],
                    "photo_id": f["photo_id"],
                    "similarity": similarity,
                })
        matches.sort(key=lambda m: m["similarity"], reverse=True)
        return matches

    def delete_faces(self, collection_id: str, face_ids: list[str]) -> None:
        return None

    def delete_collection(self, collection_id: str) -> None:
        return None


_engine: FaceEngine | None = None


def get_face_engine() -> FaceEngine:
    global _engine
    if _engine is None:
        from config import FACE_ENGINE

        if FACE_ENGINE == "mock":
            _engine = MockFaceEngine()
        elif FACE_ENGINE == "rekognition":
            raise RuntimeError(
                "RekognitionFaceEngine requires AWS credentials. Set AWS keys and "
                "implement the boto3 collection calls before enabling."
            )
        else:
            raise RuntimeError(f"Unsupported FACE_ENGINE: {FACE_ENGINE}")
    return _engine
